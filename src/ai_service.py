from __future__ import annotations

import base64
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Callable, Optional

from openai import OpenAI

from .models import Question, FragmentResult, Quote, SegmentAnalysisResult

# Max concurrent AI calls
MAX_CONCURRENT = 4

# Approximate token limit thresholds per model (conservative)
MODEL_TOKEN_LIMITS: dict[str, int] = {
    "gpt-5.4-mini": 120_000,
    "gpt-5.4-nano": 60_000,
    "gpt-5.4": 120_000,
}
# Rough chars-per-token ratio
CHARS_PER_TOKEN = 4
# Reserve tokens for system prompt + JSON output
RESERVED_TOKENS = 8_000

# Structured output JSON schema for quote extraction
QUOTE_EXTRACTION_SCHEMA = {
    "type": "json_schema",
    "name": "quote_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "fragments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "fragment_id": {"type": "integer"},
                        "fragment_title": {"type": "string"},
                        "fragment_summary": {"type": "string"},
                        "quotes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "page": {"type": "integer"},
                                },
                                "required": ["text", "page"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": [
                        "fragment_id",
                        "fragment_title",
                        "fragment_summary",
                        "quotes",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["fragments"],
        "additionalProperties": False,
    },
}


def _build_questions_block(questions: list[Question]) -> str:
    lines = []
    for q in questions:
        line = f"{q.id}. {q.title}"
        if q.description:
            line += f"\n   Opis: {q.description}"
        lines.append(line)
    return "\n".join(lines)


def _split_text_into_chunks(text: str, max_chars: int) -> list[str]:
    """Split text by page markers, grouping pages so each chunk stays under max_chars."""
    # Split on page separator pattern
    parts = re.split(r"(\n{0,3}=== \[PAGE \d+\] ===\n{0,3})", text)
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) > max_chars and current:
            chunks.append(current.strip())
            current = part
        else:
            current += part
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _merge_fragment_results(all_results: list[dict]) -> dict:
    """Merge multiple extraction results by fragment_id, combining quotes."""
    merged: dict[int, dict] = {}
    for result in all_results:
        for frag in result.get("fragments", []):
            fid = frag["fragment_id"]
            if fid not in merged:
                merged[fid] = {
                    "fragment_id": fid,
                    "fragment_title": frag["fragment_title"],
                    "fragment_summary": frag["fragment_summary"],
                    "quotes": list(frag["quotes"]),
                }
            else:
                # Merge summaries and quotes from multiple chunks
                existing = merged[fid]
                if frag["fragment_summary"] and not existing["fragment_summary"]:
                    existing["fragment_summary"] = frag["fragment_summary"]
                elif frag["fragment_summary"] and existing["fragment_summary"]:
                    existing["fragment_summary"] += " " + frag["fragment_summary"]
                existing["quotes"].extend(frag["quotes"])
    return {"fragments": list(merged.values())}


class AIService:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Optional[OpenAI] = None
        self._semaphore = threading.Semaphore(MAX_CONCURRENT)
        self._executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT, thread_name_prefix="ai_worker")

    def _get_client(self) -> OpenAI:
        if self._client is None or self._client.api_key != self._api_key:
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def update_api_key(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Graphic page description
    # ------------------------------------------------------------------

    def describe_graphic_page(
        self,
        image_path: Path,
        model: str,
        system_prompt: str,
        on_done: Optional[Callable[[str, Optional[Exception]], None]] = None,
    ) -> Future:
        def _run() -> str:
            with self._semaphore:
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()

                client = self._get_client()
                response = client.responses.create(
                    model=model,
                    instructions=system_prompt,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "Opisz dokładnie zawartość tej strony.",
                                },
                                {
                                    "type": "input_image",
                                    "image_url": f"data:image/png;base64,{b64}",
                                },
                            ],
                        }
                    ],
                )
                return response.output_text

        def _wrapped():
            try:
                result = _run()
                if on_done:
                    on_done(result, None)
                return result
            except Exception as exc:
                if on_done:
                    on_done("", exc)
                raise

        return self._executor.submit(_wrapped)

    # ------------------------------------------------------------------
    # Quote extraction
    # ------------------------------------------------------------------

    def extract_quotes(
        self,
        segment_text: str,
        questions: list[Question],
        model: str,
        system_prompt_template: str,
        on_done: Optional[Callable[[dict, Optional[Exception]], None]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Future:
        def _run() -> dict:
            with self._semaphore:
                max_chars = (
                    MODEL_TOKEN_LIMITS.get(model, 60_000) - RESERVED_TOKENS
                ) * CHARS_PER_TOKEN

                questions_block = _build_questions_block(questions)
                system_prompt = system_prompt_template.replace(
                    "{questions_block}", questions_block
                )

                chunks = _split_text_into_chunks(segment_text, max_chars)
                client = self._get_client()

                if len(chunks) == 1:
                    if on_progress:
                        on_progress("Wysyłanie do AI...")
                    result = _call_extraction(client, model, system_prompt, chunks[0])
                    return result
                else:
                    all_results = []
                    for i, chunk in enumerate(chunks, start=1):
                        if on_progress:
                            on_progress(f"Przetwarzanie fragmentu {i}/{len(chunks)}...")
                        res = _call_extraction(client, model, system_prompt, chunk)
                        all_results.append(res)
                    return _merge_fragment_results(all_results)

        def _wrapped():
            try:
                result = _run()
                if on_done:
                    on_done(result, None)
                return result
            except Exception as exc:
                if on_done:
                    on_done({}, exc)
                raise

        return self._executor.submit(_wrapped)


def _call_extraction(client: OpenAI, model: str, system_prompt: str, text: str) -> dict:
    response = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=text,
        text={"format": QUOTE_EXTRACTION_SCHEMA},
    )
    raw = response.output_text
    return json.loads(raw)

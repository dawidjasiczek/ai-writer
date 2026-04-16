import sys
import subprocess
from pathlib import Path
import shutil

def pdf_to_markdown(pdf_path, output_path):
    pdf_path = Path(pdf_path).resolve()
    output_path = Path(output_path).resolve()

    temp_dir = Path("temp_marker_input")
    temp_dir.mkdir(exist_ok=True)

    shutil.copy(pdf_path, temp_dir / pdf_path.name)

    output_dir = output_path.parent

    cmd = [
        "marker",
        str(temp_dir),
        "--output_dir",
        str(output_dir)
    ]

    subprocess.run(cmd, check=True)

    generated_md = output_dir / (pdf_path.stem + ".md")

    if generated_md.exists():
        generated_md.rename(output_path)

    shutil.rmtree(temp_dir)

    print(f"OK -> {output_path}")


if __name__ == "__main__":
    pdf_to_markdown(sys.argv[1], sys.argv[2])
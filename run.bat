@echo off
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo Make sure Python 3.10+ is installed and on your PATH.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate

echo Installing / updating requirements...
pip install -r requirements.txt --quiet

echo Starting Thesis Source Analyzer...
python main.py %*

pause

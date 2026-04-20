@echo off
cd /d "%~dp0"

python -c "import sys; raise SystemExit(0 if (sys.version_info >= (3,10) and sys.version_info < (3,14)) else 1)"
if errorlevel 1 (
    echo ERROR: Unsupported Python version detected.
    echo This project supports Python 3.10 - 3.13.
    echo Python 3.14 is not supported yet by several dependencies on Windows.
    echo.
    echo Install Python 3.12 (recommended), then recreate venv:
    echo   rmdir /s /q venv
    echo   run.bat
    pause
    exit /b 1
)

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

python -c "import sys; raise SystemExit(0 if (sys.version_info >= (3,10) and sys.version_info < (3,14)) else 1)"
if errorlevel 1 (
    echo ERROR: Existing venv uses unsupported Python version.
    echo Delete venv and recreate with Python 3.10 - 3.13 (3.12 recommended):
    echo   rmdir /s /q venv
    echo   run.bat
    pause
    exit /b 1
)

echo Installing / updating requirements...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Installing requirements failed.
    pause
    exit /b 1
)

echo Starting Thesis Source Analyzer...
python main.py %*

pause

@echo off
cd /d "%~dp0"

set "PY_CMD=python"
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -c "import sys; print(sys.version)" >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=py -3.12"
    )
)

%PY_CMD% -c "import sys; raise SystemExit(0 if (sys.version_info >= (3,10) and sys.version_info < (3,14)) else 1)"
if errorlevel 1 (
    echo ERROR: Unsupported Python version detected for %PY_CMD%.
    echo This project supports Python 3.10 - 3.13.
    echo Python 3.12 is recommended on Windows.
    echo.
    echo If you have Python 3.12 installed, run:
    echo   py -3.12 -m venv venv
    echo Then start again with run.bat.
    pause
    exit /b 1
)

if not exist venv (
    echo Creating virtual environment...
    %PY_CMD% -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo Make sure Python 3.10 - 3.13 is installed.
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

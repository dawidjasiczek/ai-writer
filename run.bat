@echo off
cd /d "%~dp0"

:: ---------------------------------------------------------------
:: 1. Pick Python 3.12 via launcher if available, else plain python
:: ---------------------------------------------------------------
set PYTHON=python

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3.12 --version >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON=py -3.12
    )
)

:: ---------------------------------------------------------------
:: 2. Validate version (3.10 - 3.13 only)
:: ---------------------------------------------------------------
%PYTHON% -c "import sys,os;sys.exit(0 if (3,10)<=sys.version_info<(3,14) else 1)" >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  BLAD: Nieobslugiwana wersja Pythona.
    echo  Wymagany Python 3.10 - 3.13  ^(zalecany 3.12^).
    echo.
    echo  Jesli masz Python 3.12 zainstalowany, recznie stworz venv:
    echo    py -3.12 -m venv venv
    echo  i uruchom run.bat ponownie.
    echo.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------
:: 3. Create venv if missing
:: ---------------------------------------------------------------
if not exist venv (
    echo Tworzenie srodowiska wirtualnego...
    %PYTHON% -m venv venv
    if %errorlevel% neq 0 (
        echo BLAD: Nie udalo sie stworzyc venv.
        pause
        exit /b 1
    )
)

:: ---------------------------------------------------------------
:: 4. Activate venv
:: ---------------------------------------------------------------
call venv\Scripts\activate.bat

:: ---------------------------------------------------------------
:: 5. Install / update requirements
:: ---------------------------------------------------------------
echo Instalacja/aktualizacja pakietow...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo BLAD: pip install nie powiodl sie.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------
:: 6. Run app
:: ---------------------------------------------------------------
echo Uruchamianie aplikacji...
python main.py %*

pause

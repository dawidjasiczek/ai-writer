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
:: 5. Select requirements profile
:: ---------------------------------------------------------------
set REQ_FILE=requirements-cuda-windows.txt
echo.
echo Wybierz profil zaleznosci:
echo   [C] CUDA/GPU  ^(domyslny^)
echo   [Z] Zwykly CPU
set /p REQ_CHOICE=Twoj wybor [C/Z, Enter=C]:
if /I "%REQ_CHOICE%"=="Z" (
    set REQ_FILE=requirements.txt
)

:: ---------------------------------------------------------------
:: 6. Install / update requirements
:: ---------------------------------------------------------------
echo Instalacja/aktualizacja pakietow z %REQ_FILE%...
pip install -r %REQ_FILE% --quiet
if %errorlevel% neq 0 (
    echo BLAD: pip install nie powiodl sie.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------
:: 7. CUDA sanity check + automatic fallback to CPU requirements
:: ---------------------------------------------------------------
if /I "%REQ_FILE%"=="requirements-cuda-windows.txt" (
    echo.
    echo CUDA sanity check...
    python -c "import sys,torch; assert torch.cuda.is_available(); x=torch.randn(1024,1024,device='cuda'); y=torch.randn(1024,1024,device='cuda'); _=x@y; print(torch.__version__)" >nul 2>nul
    if %errorlevel% neq 0 (
        echo UWAGA: CUDA sanity check nie powiodl sie. Przelaczam na profil CPU...
        echo Usuwanie pakietow torch/vision/audio z nieudanego profilu CUDA...
        pip uninstall -y torch torchvision torchaudio >nul 2>nul
        if %errorlevel% neq 0 (
            echo UWAGA: uninstall torch mogl byc niepelny, kontynuuje fallback...
        )
        echo Instalacja profilu CPU ^(requirements.txt^)...
        pip install -r requirements.txt --quiet
        if %errorlevel% neq 0 (
            echo BLAD: fallback do profilu CPU nie powiodl sie.
            pause
            exit /b 1
        )
        echo Fallback zakonczony - uruchamiam aplikacje na CPU.
    ) else (
        echo CUDA sanity check OK - uruchamiam aplikacje na GPU.
    )
)

:: ---------------------------------------------------------------
:: 8. Run app
:: ---------------------------------------------------------------
echo Uruchamianie aplikacji...
python main.py %*

pause

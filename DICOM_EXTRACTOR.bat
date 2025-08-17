@echo off
setlocal enabledelayedexpansion

:: Colors
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "NC=[0m"
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"

:: Get the directory where the script is located
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "REQUIREMENTS_FILE=%SCRIPT_DIR%\requirements.txt"
set "PYTHON_SCRIPT=%SCRIPT_DIR%\DICOM_EXTRACTOR.py"

:: Check if Python script exists
if not exist "%PYTHON_SCRIPT%" (
    echo %RED%Error: DICOM_EXTRACTOR.py not found in %SCRIPT_DIR%%NC%
    pause
    exit /b 1
)

:: Function to check Python installation
:CheckPython
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python -c "import sys; exit(0) if sys.version_info >= (3, 7) else exit(1)" >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        goto PythonOK
    )
)

:: Python not found or version too old
cls
echo %YELLOW%Python 3.7 or newer is required but not found or the version is too old.%NC%
echo.
echo Would you like to download and install Python 3.11.5 now? (Y/N)
set /p INSTALL_PYTHON=

if /i "%INSTALL_PYTHON%"=="Y" (
    echo Downloading Python installer...
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('%PYTHON_URL%', '%TEMP%\python_installer.exe')"
    if %ERRORLEVEL% NEQ 0 (
        echo %RED%Failed to download Python installer. Please check your internet connection.%NC%
        pause
        exit /b 1
    )
    
    echo Installing Python...
    echo %YELLOW%IMPORTANT: In the Python installer, make sure to check "Add Python to PATH"%NC%
    echo %YELLOW%at the bottom of the installer window before clicking "Install Now".%NC%
    echo.
    echo Press any key to start the Python installer...
    pause >nul
    
    start /wait "" "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1
    
    echo Installation complete. Please restart this application.
    echo Press any key to exit...
    pause >nul
    exit /b 0
) else (
    echo %RED%Python is required to run this application. Please install Python 3.7 or newer and try again.%NC%
    echo You can download Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:PythonOK

:: Install requirements if requirements.txt exists
if exist "%REQUIREMENTS_FILE%" (
    echo Installing required packages...
    python -m pip install --upgrade pip
    python -m pip install -r "%REQUIREMENTS_FILE%"
    if %ERRORLEVEL% NEQ 0 (
        echo %RED%Failed to install required packages. Please check your internet connection and try again.%NC%
        pause
        exit /b 1
    )
) else (
    echo %YELLOW%Warning: requirements.txt not found. Some features may not work.%NC%
)

:: Run the Python script
echo Starting DICOM Extractor...
python "%PYTHON_SCRIPT%"

:: Keep the window open if there's an error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo %RED%The program exited with an error. Press any key to close...%NC%
    pause >nul
)
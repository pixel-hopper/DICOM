@echo off
setlocal enabledelayedexpansion

:: Colors
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "NC=[0m"

:: Get the directory where the script is located
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "REQUIREMENTS_FILE=%SCRIPT_DIR%\requirements.txt"
set "PYTHON_SCRIPT=%SCRIPT_DIR%\DICOM_EXTRACTOR.py"

:: Check if Python script exists
if not exist "%PYTHON_SCRIPT%" (
    echo %RED%Error: extract_xray.py not found in %SCRIPT_DIR%%NC%
    exit /b 1
)

:: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %RED%Python is not installed or not in PATH. Please install Python 3 and try again.%NC%
    exit /b 1
)

:: Check if pip is installed
python -m pip --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%pip not found. Attempting to install pip...%NC%
    python -m ensurepip --upgrade
    if %ERRORLEVEL% NEQ 0 (
        echo %RED%Failed to install pip. Please install pip manually and try again.%NC%
        exit /b 1
    )
)

:: Check if requirements.txt exists
if exist "%REQUIREMENTS_FILE%" (
    echo %GREEN%Checking and installing required packages...%NC%
    
    :: Install required packages
    python -m pip install --upgrade pip
    if %ERRORLEVEL% NEQ 0 (
        echo %YELLOW%Warning: Failed to upgrade pip. Continuing anyway...%NC%
    )

    python -m pip install -r "%REQUIREMENTS_FILE%"
    if %ERRORLEVEL% NEQ 0 (
        echo %YELLOW%Warning: Failed to install some dependencies. The application might not work correctly.%NC%
        timeout /t 3 >nul
    )
)

echo %GREEN%Starting DICOM Extractor...%NC%
python "%PYTHON_SCRIPT%" %*

if %ERRORLEVEL% NEQ 0 (
    echo %RED%The DICOM Extractor encountered an error.%NC%
    pause
    exit /b 1
)

endlocal

@echo off
setlocal enabledelayedexpansion

:: Colors
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "NC=[0m"

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

:: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %RED%Python is not installed or not in PATH. Please install Python 3 and try again.%NC%
    pause
    exit /b 1
)

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
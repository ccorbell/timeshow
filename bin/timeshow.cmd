@echo off
setlocal enabledelayedexpansion
REM Get the directory of this script and resolve to parent (project root)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "PROJECT_ROOT=%cd%"
set "PYTHON_BIN=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "MAIN_SCRIPT=%PROJECT_ROOT%\timeshow\main.py"
set "REQUIREMENTS_FILE=%PROJECT_ROOT%\requirements.txt"
REM Lazy initialization: create venv and install dependencies if needed
if not exist "%PYTHON_BIN%" (
  set "VENV_DIR=%PROJECT_ROOT%\.venv"
  echo Setting up virtual environment at !VENV_DIR!... 1>&2
  python -m venv "!VENV_DIR!"
  if errorlevel 1 (
    echo Error: Failed to create virtual environment. 1>&2
    exit /b 1
  )
  if not exist "%REQUIREMENTS_FILE%" (
    echo Error: requirements.txt not found at %REQUIREMENTS_FILE% 1>&2
    exit /b 1
  )
  set "PIP_BIN=!VENV_DIR!\Scripts\pip.exe"
  echo Installing dependencies... 1>&2
  call "!PIP_BIN!" install -r "%REQUIREMENTS_FILE%"
  if errorlevel 1 (
    echo Error: Failed to install dependencies. 1>&2
    exit /b 1
  )
  echo Setup complete. 1>&2
)
if not exist "%MAIN_SCRIPT%" (
  echo Error: Could not find %MAIN_SCRIPT% 1>&2
  exit /b 1
)
REM Set PYTHONPATH and run the program
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"
"%PYTHON_BIN%" "%MAIN_SCRIPT%" %*
endlocal

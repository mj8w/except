@echo off
setlocal

set "PYTHON=%~dp0..\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Expected virtual environment interpreter at "%PYTHON%".
  echo Create it with "python -m venv .venv".
  exit /b 1
)

if "%~1"=="" (
  echo Usage: %~nx0 module [args...]
  exit /b 1
)

"%PYTHON%" -m %*
exit /b %ERRORLEVEL%

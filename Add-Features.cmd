@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Run Setup.cmd first to prepare BEYOND's Python environment.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -I "%~dp0installer\add_features.py" %*
set "feature_result=%errorlevel%"
if not "%feature_result%"=="0" echo See the message above for the step that needs attention.
if "%~1"=="" pause
exit /b %feature_result%

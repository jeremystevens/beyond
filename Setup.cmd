@echo off
setlocal
if /i "%~1"=="--check" goto check
if not "%~1"=="" goto usage
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
goto finish
:check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -CheckOnly
goto finish
:usage
echo Usage: Setup.cmd [--check]
exit /b 2
:finish
set "setup_result=%errorlevel%"
if not "%setup_result%"=="0" echo Setup needs attention. Read the message above.
if /i not "%~1"=="--check" pause
exit /b %setup_result%

@echo off
rem Update BEYOND to the latest release, keeping your chats, settings, models and files.
rem Put this file in your BEYOND folder (next to beyond.py) and double-click it.
rem It downloads the latest Update-Beyond.ps1 from GitHub, checks it against the release's checksums, and runs it.
rem From BEYOND 1.1.0 on you can also update from Settings, Updates.
setlocal
cd /d "%~dp0"
if not exist "beyond.py" (
  echo This file needs to be in your BEYOND folder, next to beyond.py.
  pause
  exit /b 1
)
echo Getting the BEYOND updater from GitHub...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { $v=(Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/jeremystevens/beyond/main/VERSION').Content.Trim(); $b='https://github.com/jeremystevens/beyond/releases/download/v'+$v; $d=Join-Path (Get-Location).Path ('data\updates\updater-'+$v); New-Item -ItemType Directory -Force -Path $d | Out-Null; $p=Join-Path $d 'Update-Beyond.ps1'; $s=Join-Path $d 'SHA256SUMS.txt'; Invoke-WebRequest -UseBasicParsing ($b+'/SHA256SUMS.txt') -OutFile $s; Invoke-WebRequest -UseBasicParsing ($b+'/Update-Beyond.ps1') -OutFile $p; $want=''; foreach ($l in Get-Content $s) { $x=$l.Trim() -split '\s+'; if ($x.Count -eq 2 -and $x[1].TrimStart('*') -eq 'Update-Beyond.ps1') { $want=$x[0].ToLower() } }; if (-not $want -or (Get-FileHash $p -Algorithm SHA256).Hash.ToLower() -ne $want) { throw 'The downloaded updater did not match the release checksum, so it was not run.' } } catch { Write-Host $_.Exception.Message -ForegroundColor Red; Read-Host 'Press Enter to close'; exit 1 }; & $p -InstallDir (Get-Location).Path -Version $v; exit $LASTEXITCODE"
exit /b %errorlevel%

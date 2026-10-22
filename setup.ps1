# BEYOND's Python bootstrap. Windows PowerShell 5.1+, no Python required.
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$Yes
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$ProjectRoot = $PSScriptRoot
$PythonVersion = '3.14.8'
$InstallerUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"

function Find-BeyondPython {
    $choices = @()
    $choices += ,@((Join-Path $ProjectRoot '.venv\Scripts\python.exe'))
    $choices += ,@('py', '-3.14')
    foreach ($hive in @('HKCU:', 'HKLM:')) {
        foreach ($tag in @('3.14', '3.14-64')) {
            foreach ($key in @("$hive\Software\Python\PythonCore\$tag\InstallPath",
                                "$hive\Software\WOW6432Node\Python\PythonCore\$tag\InstallPath")) {
                if (Test-Path -LiteralPath $key) {
                    $folder = (Get-Item -LiteralPath $key).GetValue('')
                    if ($folder) { $choices += ,@((Join-Path $folder 'python.exe')) }
                }
            }
        }
    }
    if ($env:LOCALAPPDATA) {
        $choices += ,@((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'))
    }
    $choices += ,@('python3.14')
    $choices += ,@('python')
    $probe = 'import sys,struct; print(sys.executable); sys.exit(0 if sys.version_info[:2]==(3,14) and struct.calcsize(chr(80))==8 else 1)'
    foreach ($choice in $choices) {
        $executable = $choice[0]
        if (-not (Get-Command $executable -ErrorAction SilentlyContinue)) { continue }
        # Windows Store aliases can open a window instead of running Python.
        if ($executable -eq 'python') {
            $resolved = (Get-Command $executable -ErrorAction SilentlyContinue).Source
            if ($resolved -like '*\Microsoft\WindowsApps\*') { continue }
        }
        $arguments = @()
        if ($choice.Count -gt 1) { $arguments += $choice[1..($choice.Count - 1)] }
        try {
            $answer = & $executable @arguments -I -c $probe 2>$null
            if ($LASTEXITCODE -eq 0 -and $answer) {
                return [string]($answer | Select-Object -Last 1)
            }
        } catch { }
    }
    return $null
}

function Test-BeyondInstaller {
    param([string]$Path)
    $expectedHash = '759BE887B96E736A3CA886DAF8D575F18FCAE1A09EFAB6902F42D59E8999F8EF'
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash -ne $expectedHash) {
        throw 'Python installer checksum does not match the verified 3.14.8 download. It will not be run.'
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or
        $signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Python Software Foundation(?:,|$)') {
        throw 'Python installer signature is not valid for the Python Software Foundation. It will not be run.'
    }
}

function Install-BeyondPython {
    if (-not $Yes) {
        $answer = Read-Host "Download and install Python $PythonVersion (64-bit) for your Windows account? [y/N]"
        if ($answer -notmatch '^(y|yes)$') { return $null }
    }
    $cache = Join-Path $ProjectRoot 'data\setup\downloads'
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    $installer = Join-Path $cache "python-$PythonVersion-amd64.exe"
    while ($true) {
        try {
            if (-not (Test-Path -LiteralPath $installer)) {
                Write-Host "Downloading Python from python.org..."
                $partial = "$installer.part.exe"
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -UseBasicParsing -Uri $InstallerUrl -OutFile $partial -TimeoutSec 120
                Test-BeyondInstaller -Path $partial
                Move-Item -LiteralPath $partial -Destination $installer -Force
            }
            Test-BeyondInstaller -Path $installer
            Write-Host 'Verified publisher: Python Software Foundation.'
            Write-Host 'Installing for this account; other Python versions and PATH are left alone.'
            $process = Start-Process -FilePath $installer -ArgumentList @(
                '/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=0',
                'Include_test=0', 'Include_doc=0', 'Include_pip=1') -Wait -PassThru
            if ($process.ExitCode -notin @(0, 3010)) {
                throw "Python installer exited with code $($process.ExitCode)."
            }
            $python = Find-BeyondPython
            if (-not $python) {
                throw 'Python installation finished but a usable 64-bit Python 3.14 was not found. Restart Setup after signing in again.'
            }
            return $python
        } catch {
            Write-Host "Python setup needs attention: $($_.Exception.Message)"
            Write-Host 'Completed, verified downloads are preserved. No existing Python was removed.'
            if ($Yes) { throw }
            $retry = Read-Host 'Retry this step? [y/N]'
            if ($retry -notmatch '^(y|yes)$') { throw }
            # Never reuse an invalid cached executable on retry.
            if (Test-Path -LiteralPath $installer) {
                try { Test-BeyondInstaller -Path $installer }
                catch { Remove-Item -LiteralPath $installer }
            }
        }
    }
}

try {
    $brand = 'BEYOND'
    try {
        $readme = [IO.File]::ReadAllText((Join-Path $ProjectRoot 'README.md'), [Text.Encoding]::UTF8)
        $match = [regex]::Match($readme, '(?s)\x60\x60\x60\s*(.*?)\x60\x60\x60')
        if ($match.Success) {
            $encoding = [Console]::OutputEncoding.Clone()
            $encoding.EncoderFallback = [Text.EncoderFallback]::ExceptionFallback
            [void]$encoding.GetByteCount($match.Groups[1].Value)
            $brand = $match.Groups[1].Value.TrimEnd()
        }
    } catch { }
    Write-Host $brand
    Write-Host 'Built Entirely on Your Own Network & Device'
    Write-Host 'Checking for Python 3.14 (64-bit)...'
    if ([Environment]::OSVersion.Version.Major -lt 10 -or
        -not [Environment]::Is64BitOperatingSystem -or
        $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or
        $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') {
        throw 'This setup currently supports Windows 10/11 on Intel/AMD 64-bit PCs.'
    }
    $python = Find-BeyondPython
    if (-not $python) {
        if ($CheckOnly) { throw 'Python 3.14 (64-bit) not found. Run Setup.cmd without --check to install it.' }
        $python = Install-BeyondPython
        if (-not $python) { Write-Host 'Setup cancelled.'; exit 0 }
    }
    $arguments = @('-I', (Join-Path $ProjectRoot 'setup.py'))
    if ($CheckOnly) { $arguments += '--check' }
    if ($Yes) { $arguments += '--yes' }
    & $python @arguments
    exit $LASTEXITCODE
} catch {
    Write-Host "Setup needs attention: $($_.Exception.Message)"
    exit 1
}

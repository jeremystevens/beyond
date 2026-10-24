<#
.SYNOPSIS
  Updates BEYOND to a newer published release, keeping your chats, settings, models and files (Phase 45).

.DESCRIPTION
  BEYOND starts this from Settings > Updates (Update now). People on 1.0.0, which can't check for updates, start it
  once with Update-Beyond.cmd. It:
    1. checks the BEYOND folder and the version to update to,
    2. waits for BEYOND to close (it never stops any other program),
    3. downloads the release ZIP and checks its SHA-256 against the release's SHA256SUMS.txt,
    4. unpacks it into a staging folder, refusing any path outside it,
    5. backs up the current program files,
    6. swaps in the new program files and removes ones the new version no longer has,
    7. updates the Python libraries in the existing .venv (only if the requirement files changed),
    8. starts BEYOND and checks the new version is running.
  If a step after the backup fails, the old files (and libraries) are put back and the old BEYOND is started.
  It never touches data\, models\, files\, .venv\ (except pip) or .git\. Copies set up with git are refused:
  run "git pull" there instead. A log of each run goes to data\updates\update-<version>.log.
#>
param(
    [string]$InstallDir = (Get-Location).Path,
    [string]$Version = '',
    [int]$WaitPid = 0,
    [int]$Port = 0,
    [string]$Repo = 'jeremystevens/beyond',
    [string]$DownloadBase = '',     # tests point these at a local server
    [string]$VersionUrl = '',
    [switch]$NoStart,               # tests: don't start BEYOND or open the browser afterwards
    [switch]$NoPause,
    [switch]$Yes                    # don't ask before waiting for BEYOND to close
)

# Started from PowerShell 7 (or by a program started from it), Windows PowerShell inherits PowerShell 7's module
# folders and can't load some of its own commands. Use Windows PowerShell's own folders.
if ($PSVersionTable.PSVersion.Major -lt 6) {
    $env:PSModulePath = (@([Environment]::GetFolderPath('MyDocuments') + '\WindowsPowerShell\Modules',
                           "$env:ProgramFiles\WindowsPowerShell\Modules",
                           "$env:SystemRoot\System32\WindowsPowerShell\v1.0\Modules") -join ';')
}
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression.FileSystem

if (-not $DownloadBase) { $DownloadBase = "https://github.com/$Repo/releases/download" }
if (-not $VersionUrl) { $VersionUrl = "https://raw.githubusercontent.com/$Repo/main/VERSION" }
$Protected = @('data/', 'models/', 'files/', '.venv/', '.git/')   # never replaced or removed
$Utf8 = New-Object System.Text.UTF8Encoding $false

function Say([string]$Text, [string]$Color = 'Gray') { Write-Host $Text -ForegroundColor $Color }
function Step([int]$Number, [string]$Text) { Write-Host ''; Write-Host "[$Number/8] $Text" -ForegroundColor Cyan }

function Finish([int]$Code) {
    try { Stop-Transcript | Out-Null } catch {}
    if (-not $NoPause) {
        if ($Code -eq 0) { Say 'This window closes in 15 seconds.'; Start-Sleep -Seconds 15 }
        else { Read-Host 'Press Enter to close this window' | Out-Null }
    }
    exit $Code
}

function Parse-Version([string]$Text) {
    if ($Text.Trim() -match '^v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})$') {
        return New-Object System.Version ([int]$Matches[1]), ([int]$Matches[2]), ([int]$Matches[3])
    }
    throw "'$Text' isn't a version number."
}

function Installed-Version([string]$Folder) {
    $line = Select-String -Path (Join-Path $Folder 'app\config.py') -Pattern "^VERSION = '([^']+)'" | Select-Object -First 1
    if (-not $line) { throw "Couldn't read the version in $Folder\app\config.py." }
    return $line.Matches[0].Groups[1].Value
}

function Fail-Test([string]$Stage) {
    # Lets the tests make one step fail on purpose, to check the rollback.
    if ($env:BEYOND_UPDATE_FAIL_AT -eq $Stage) { throw "Test failure at the $Stage step." }
}

function Download([string]$Url, [string]$Target) {
    Invoke-WebRequest -Uri $Url -OutFile $Target -UseBasicParsing -TimeoutSec 120
}

function Sha256([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    try { $bytes = [System.Security.Cryptography.SHA256]::Create().ComputeHash($stream) } finally { $stream.Dispose() }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

function Expected-Sum([string]$SumsFile, [string]$Name) {
    foreach ($line in Get-Content -Path $SumsFile) {
        $parts = $line.Trim() -split '\s+'
        if ($parts.Count -eq 2 -and $parts[1].TrimStart('*') -eq $Name) { return $parts[0].ToLowerInvariant() }
    }
    return ''
}

function Get-Release([string]$Ver, [string]$Folder) {
    # Download a release's ZIP and check it. Returns the ZIP's path.
    New-Item -ItemType Directory -Force -Path $Folder | Out-Null
    $zipName = "BEYOND-$Ver-source.zip"
    $sums = Join-Path $Folder 'SHA256SUMS.txt'
    $zip = Join-Path $Folder $zipName
    Download "$DownloadBase/v$Ver/SHA256SUMS.txt" $sums
    Download "$DownloadBase/v$Ver/$zipName" $zip
    $expected = Expected-Sum $sums $zipName
    if (-not $expected -or (Sha256 $zip) -ne $expected) {
        throw "The downloaded $zipName didn't match the release's checksum. It may have been damaged on the way; try again."
    }
    return $zip
}

function Zip-Entries([string]$ZipPath) {
    # The ZIP's file names relative to BEYOND's folder (the release ZIP keeps everything in one top folder).
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $names = @($archive.Entries | ForEach-Object { $_.FullName.Replace('\', '/') })
    } finally { $archive.Dispose() }
    $top = ($names[0] -split '/')[0] + '/'
    $shared = @($names | Where-Object { -not $_.StartsWith($top) }).Count -eq 0
    $files = foreach ($name in $names) {
        if ($name.EndsWith('/')) { continue }
        if ($shared) { $name.Substring($top.Length) } else { $name }
    }
    return @{ Prefix = $(if ($shared) { $top } else { '' }); Files = @($files) }
}

function Is-SafePath([string]$Relative) {
    if (-not $Relative -or $Relative.StartsWith('/') -or $Relative.Contains(':') -or $Relative.Contains('\')) { return $false }
    foreach ($part in $Relative.Split('/')) { if ($part -eq '..' -or $part -eq '') { return $false } }
    foreach ($prefix in $Protected) { if ($Relative.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { return $false } }
    return $true
}

function Expand-Safely([string]$ZipPath, [string]$Target) {
    if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    $root = [System.IO.Path]::GetFullPath($Target).TrimEnd('\') + '\'
    $listing = Zip-Entries $ZipPath
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        foreach ($entry in $archive.Entries) {
            $name = $entry.FullName.Replace('\', '/')
            if ($name.EndsWith('/')) { continue }
            $relative = $name.Substring($listing.Prefix.Length)
            if (-not (Is-SafePath $relative)) { throw "The update contains an unsafe file path ($name), so it was not used." }
            $destination = [System.IO.Path]::GetFullPath((Join-Path $Target $relative.Replace('/', '\')))
            if (-not $destination.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
                throw "The update contains an unsafe file path ($name), so it was not used."
            }
            New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination, $true)
        }
    } finally { $archive.Dispose() }
}

function Write-Lines([string]$Path, $Lines) {
    New-Item -ItemType Directory -Force -Path (Split-Path $Path) | Out-Null
    [System.IO.File]::WriteAllLines($Path, [string[]]@($Lines), $Utf8)
}

function Write-Result([bool]$Ok, [string]$Message) {
    $result = [ordered]@{ from = $Installed; to = $Version; ok = $Ok; message = $Message
                          at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
    [System.IO.File]::WriteAllText((Join-Path $UpdatesDir 'last-update.json'), ($result | ConvertTo-Json), $Utf8)
}

function Beyond-Answers {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        return $health
    } catch { return $null }
}

function Beyond-Processes {
    $venv = (Join-Path $InstallDir '.venv\Scripts\')
    return @(Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
             Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($venv, [StringComparison]::OrdinalIgnoreCase) -and
                            $_.CommandLine -like '*beyond.py*' })
}

function Wait-ForBeyondToClose {
    if ($WaitPid) {
        try { Wait-Process -Id $WaitPid -Timeout 120 -ErrorAction Stop } catch {}
    }
    for ($try = 0; $try -lt 60; $try++) {
        if (-not (Beyond-Answers) -and (Beyond-Processes).Count -eq 0) { return }
        if ($try -eq 5 -and -not $Yes) {
            Say 'BEYOND is still running. Close it: right-click the orange B by the clock, then Quit BEYOND.' 'Yellow'
            Read-Host 'Then press Enter to continue' | Out-Null
        }
        Start-Sleep -Seconds 2
    }
    throw 'BEYOND is still running, so its files could not be updated. Quit BEYOND from the tray icon and run the update again.'
}

function Start-Beyond([string]$ExpectVersion) {
    # Start BEYOND in the tray and wait until it answers with the expected version. Returns the process.
    $pythonw = Join-Path $InstallDir '.venv\Scripts\pythonw.exe'
    $process = Start-Process -FilePath $pythonw -ArgumentList 'beyond.py' -WorkingDirectory $InstallDir -PassThru
    for ($try = 0; $try -lt 120; $try++) {
        Start-Sleep -Seconds 2
        $health = Beyond-Answers
        if ($health -and $health.version -eq $ExpectVersion) { return $process }
        if ($process.HasExited) { break }
    }
    & taskkill.exe /T /F /PID $process.Id 2>$null | Out-Null
    throw "BEYOND $ExpectVersion didn't start properly. See data\beyond.log."
}

function Install-Libraries([string]$Folder) {
    $python = Join-Path $InstallDir '.venv\Scripts\python.exe'
    foreach ($file in $script:RequirementFiles) {
        Say "  Installing the libraries in $file"
        & $python -I -m pip install --only-binary=:all: --disable-pip-version-check --quiet --timeout 30 --retries 2 -r (Join-Path $Folder $file)
        if ($LASTEXITCODE -ne 0) { throw "Installing the libraries in $file failed." }
    }
}

# ---------------------------------------------------------------------------------------------------------------

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
$UpdatesDir = Join-Path $InstallDir 'data\updates'
New-Item -ItemType Directory -Force -Path $UpdatesDir | Out-Null
$Installed = ''
Say ''
Say '  BEYOND updater' 'White'
Say '  Your chats, memories, settings, models and files are kept.'

# 1. The folder and the versions -------------------------------------------------------------------------------
Step 1 'Checking this BEYOND folder'
try {
    foreach ($needed in @('beyond.py', 'app\config.py')) {
        if (-not (Test-Path (Join-Path $InstallDir $needed))) { throw "$InstallDir doesn't look like a BEYOND folder (no $needed)." }
    }
    if (Test-Path (Join-Path $InstallDir '.git')) {
        Say 'This copy of BEYOND was set up with git, so it updates the git way:' 'Yellow'
        Say '  run "git pull" in this folder, then restart BEYOND.' 'Yellow'
        Finish 2
    }
    if (-not (Test-Path (Join-Path $InstallDir '.venv\Scripts\python.exe'))) {
        throw "BEYOND's Python environment (.venv) is missing. Run Setup.cmd first."
    }
    $Installed = Installed-Version $InstallDir
    if (-not $Version) { $Version = (Invoke-WebRequest -Uri $VersionUrl -UseBasicParsing -TimeoutSec 30).Content.Trim() }
    $Version = $Version.Trim().TrimStart('v')
    if ((Parse-Version $Version) -le (Parse-Version $Installed)) {
        Say "BEYOND $Installed is already up to date (the latest is $Version)." 'Green'
        Finish 0
    }
    if (-not $Port) {
        $Port = 7770
        $settingsFile = Join-Path $InstallDir 'data\settings.json'
        if (Test-Path $settingsFile) {
            try { $saved = Get-Content -Raw $settingsFile | ConvertFrom-Json; if ($saved.web_port) { $Port = [int]$saved.web_port } } catch {}
        }
    }
    Start-Transcript -Path (Join-Path $UpdatesDir "update-$Version.log") -Append | Out-Null
    Say "Updating BEYOND $Installed to $Version in $InstallDir"
} catch {
    Say $_.Exception.Message 'Red'
    Finish 1
}

$BackupDir = Join-Path $UpdatesDir "backup-$Installed"
$Staging = Join-Path $UpdatesDir "staging-$Version"
$Downloads = Join-Path $UpdatesDir "download-$Version"
$Closed = $false
$Swapped = $false
$PipRan = $false
$Added = @()

try {
    # 2. Wait for BEYOND to close ------------------------------------------------------------------------------
    Step 2 'Waiting for BEYOND to close'
    Wait-ForBeyondToClose
    $Closed = $true
    Say 'BEYOND is closed.'

    # 3. Download and check ------------------------------------------------------------------------------------
    Step 3 "Downloading BEYOND $Version"
    $drive = New-Object System.IO.DriveInfo ([System.IO.Path]::GetPathRoot($InstallDir))
    if ($drive.AvailableFreeSpace -lt 500MB) { throw 'There is less than 500 MB free on this drive. Free some space and try again.' }
    $zip = Get-Release $Version $Downloads
    Say 'Downloaded and checked.'

    # 4. Unpack ------------------------------------------------------------------------------------------------
    Step 4 'Unpacking'
    Expand-Safely $zip $Staging
    if ((Installed-Version $Staging) -ne $Version) { throw "The downloaded release says it's version $(Installed-Version $Staging), not $Version." }
    $listFile = Join-Path $Staging 'app-files.txt'
    if (Test-Path $listFile) { $NewFiles = @(Get-Content $listFile | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }) }
    else { $NewFiles = @((Zip-Entries $zip).Files) }
    foreach ($file in $NewFiles) {
        if (-not (Is-SafePath $file) -or -not (Test-Path (Join-Path $Staging $file))) { throw "The update's file list is wrong ($file)." }
    }
    # The old version's program files: from the last update, or from the installed version's own release.
    $installedList = Join-Path $UpdatesDir 'installed-files.txt'
    $OldFiles = @()
    if (Test-Path $installedList) { $OldFiles = @(Get-Content $installedList | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }) }
    else {
        try { $OldFiles = @((Zip-Entries (Get-Release $Installed (Join-Path $Downloads "old-$Installed"))).Files) }
        catch { Say "  (Couldn't get the list of $Installed's files, so files it no longer needs are left in place.)" 'Yellow' }
    }
    $OldFiles = @($OldFiles | Where-Object { Is-SafePath $_ })
    $Removed = @($OldFiles | Where-Object { $NewFiles -notcontains $_ })
    Say "$($NewFiles.Count) program files; $($Removed.Count) no longer needed."

    # Which libraries to update: the text-chat set, plus each optional feature that's installed and passed its test.
    $script:RequirementFiles = @('requirements-text-lock.txt')
    $features = Join-Path $InstallDir 'data\setup\optional\features.json'
    if (Test-Path $features) {
        try {
            $state = Get-Content -Raw $features | ConvertFrom-Json
            foreach ($feature in $state.PSObject.Properties) {
                if ($feature.Value.status -eq 'passed' -and $feature.Name -notin @('vision', 'image') -and
                    (Test-Path (Join-Path $Staging "requirements-$($feature.Name).txt"))) {
                    $script:RequirementFiles += "requirements-$($feature.Name).txt"
                }
            }
        } catch { Say '  (The optional features list could not be read; only the text-chat libraries are checked.)' 'Yellow' }
    }
    $LibrariesChanged = $false
    foreach ($file in $script:RequirementFiles) {
        $old = Join-Path $InstallDir $file
        if (-not (Test-Path $old) -or (Sha256 $old) -ne (Sha256 (Join-Path $Staging $file))) { $LibrariesChanged = $true }
    }

    # 5. Back up -----------------------------------------------------------------------------------------------
    Step 5 'Backing up the current version'
    if (Test-Path $BackupDir) { Remove-Item -Recurse -Force $BackupDir }
    $Program = Join-Path $BackupDir 'program'
    New-Item -ItemType Directory -Force -Path $Program | Out-Null
    foreach ($file in @($OldFiles + $NewFiles | Select-Object -Unique)) {
        $source = Join-Path $InstallDir $file
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            $copy = Join-Path $Program $file
            New-Item -ItemType Directory -Force -Path (Split-Path $copy) | Out-Null
            Copy-Item -LiteralPath $source -Destination $copy -Force
        } else { $Added += $file }
    }
    Write-Lines (Join-Path $BackupDir 'added-files.txt') $Added
    Say "Backed up to $BackupDir"

    # 6. Swap the program files --------------------------------------------------------------------------------
    Step 6 'Updating the program files'
    $Swapped = $true
    foreach ($file in $NewFiles) {
        $target = Join-Path $InstallDir $file
        New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
        Copy-Item -LiteralPath (Join-Path $Staging $file) -Destination $target -Force
    }
    foreach ($file in $Removed) {
        $target = Join-Path $InstallDir $file
        if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target -Force }
    }
    Fail-Test 'swap'
    Say 'Program files updated.'

    # 7. Libraries ---------------------------------------------------------------------------------------------
    Step 7 'Updating the libraries'
    if ($LibrariesChanged) {
        $python = Join-Path $InstallDir '.venv\Scripts\python.exe'
        & $python -I -m pip freeze --disable-pip-version-check | Set-Content -Path (Join-Path $BackupDir 'pip-freeze.txt') -Encoding ascii
        $PipRan = $true
        Install-Libraries $InstallDir
    } else { Say 'No library changes.' }
    Fail-Test 'pip'

    # 8. Start the new version ---------------------------------------------------------------------------------
    Step 8 "Starting BEYOND $Version"
    Write-Lines $installedList $NewFiles
    Fail-Test 'start'
    if (-not $NoStart) {
        Start-Beyond $Version | Out-Null
        Start-Process "http://127.0.0.1:$Port/settings#group-updates"
    }
    Write-Result $true ''
    Remove-Item -Recurse -Force $Staging, $Downloads -ErrorAction SilentlyContinue
    Get-ChildItem $UpdatesDir -Directory -Filter 'backup-*' | Where-Object { $_.FullName -ne $BackupDir } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue   # keep only this update's backup
    Say ''
    Say "Done: BEYOND is now $Version." 'Green'
    Finish 0
} catch {
    $problem = $_.Exception.Message
    Say ''
    Say "The update stopped: $problem" 'Red'
    if ($Swapped) {
        Say "Putting BEYOND $Installed back..." 'Yellow'
        try {
            foreach ($file in $Added) {
                $target = Join-Path $InstallDir $file
                if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target -Force }
            }
            $Program = Join-Path $BackupDir 'program'
            foreach ($copy in Get-ChildItem -LiteralPath $Program -Recurse -File) {
                $target = Join-Path $InstallDir $copy.FullName.Substring($Program.Length + 1)
                New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
                Copy-Item -LiteralPath $copy.FullName -Destination $target -Force
            }
            if ($PipRan) {
                Say '  Putting the previous libraries back'
                $python = Join-Path $InstallDir '.venv\Scripts\python.exe'
                & $python -I -m pip install --disable-pip-version-check --quiet -r (Join-Path $BackupDir 'pip-freeze.txt')
            }
            if (Test-Path (Join-Path $UpdatesDir 'installed-files.txt')) {
                if ($OldFiles.Count) { Write-Lines (Join-Path $UpdatesDir 'installed-files.txt') $OldFiles }
                else { Remove-Item (Join-Path $UpdatesDir 'installed-files.txt') -Force }
            }
            Say "BEYOND $Installed is back." 'Yellow'
        } catch {
            Say "Putting the old version back also failed: $($_.Exception.Message)" 'Red'
            Say "The previous files are in $BackupDir. Copy its 'program' folder back over $InstallDir, or download BEYOND again." 'Red'
        }
    }
    try { Write-Result $false $problem } catch {}
    if ($Closed -and -not $NoStart) {
        try { Start-Beyond $Installed | Out-Null; Say "BEYOND $Installed is running again." }
        catch { Say 'Start BEYOND again from its shortcut.' 'Yellow' }
    }
    Finish 1
}

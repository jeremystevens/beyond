# Offline tests: load only function definitions, never the bootstrap's main body.
$ErrorActionPreference = 'Stop'
$source = Join-Path (Split-Path $PSScriptRoot -Parent) 'setup.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $false) |
    ForEach-Object { Invoke-Expression $_.Extent.Text }
$script:fileHash = '759BE887B96E736A3CA886DAF8D575F18FCAE1A09EFAB6902F42D59E8999F8EF'
function Get-FileHash {
    param($Algorithm, $LiteralPath)
    [pscustomobject]@{Hash=$script:fileHash}
}
$script:signatureStatus = 'Valid'
$script:publisher = 'CN=Python Software Foundation, O=Python Software Foundation, C=US'
function Get-AuthenticodeSignature {
    param($LiteralPath)
    [pscustomobject]@{Status=$script:signatureStatus; SignerCertificate=[pscustomobject]@{Subject=$script:publisher}}
}
Test-BeyondInstaller -Path 'not-run.exe'
foreach ($case in @(
    @('NotSigned','CN=Python Software Foundation, O=Python Software Foundation, C=US'),
    @('HashMismatch','CN=Python Software Foundation, O=Python Software Foundation, C=US'),
    @('Valid','CN=Other, O=Other, C=US'),
    @('Valid','CN=Python Software Foundation, O=Python Software Foundation Fake, C=US')
)) {
    $script:signatureStatus = $case[0]
    $script:publisher = $case[1]
    $rejected = $false
    try { Test-BeyondInstaller -Path 'not-run.exe' } catch { $rejected = $true }
    if (-not $rejected) { throw "Accepted untrusted signature: $case" }
}
$script:fileHash = 'BAD'
$rejected = $false
try { Test-BeyondInstaller -Path 'not-run.exe' } catch { $rejected = $true }
if (-not $rejected) { throw 'Accepted a checksum mismatch.' }
Write-Host 'PowerShell parse, five signature cases and checksum rejection passed.'

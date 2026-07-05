[CmdletBinding()]
param([switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

if (-not (Test-Path '.\config\sources.local.yaml')) {
    Copy-Item '.\config\sources.example.yaml' '.\config\sources.local.yaml'
    Write-Host 'Created config\sources.local.yaml. Review exclusions before a broad scan.'
}
if (-not (Test-Path '.\.venv')) { python -m venv .venv }
$Python = Join-Path $Root '.venv\Scripts\python.exe'
& $Python -m pip install --upgrade pip
& $Python -m pip install -e '.[dev]'

$DadBin = Join-Path $HOME '.dad\bin'
New-Item -ItemType Directory -Force -Path $DadBin | Out-Null
$PythonForPs1 = $Python.Replace("'", "''")
$ShimPs1 = Join-Path $DadBin 'asset-dir.ps1'
@"
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments=`$true)][string[]]`$CliArgs)
& '$PythonForPs1' -m digital_asset_directory.cli @CliArgs
exit `$LASTEXITCODE
"@ | Set-Content -Path $ShimPs1 -Encoding UTF8
$ShimCmd = Join-Path $DadBin 'asset-dir.cmd'
@"
@echo off
"$Python" -m digital_asset_directory.cli %*
"@ | Set-Content -Path $ShimCmd -Encoding ASCII

& $ShimPs1 doctor --hub $Root --scope deployment --write-hub-locator

& $Python -m digital_asset_directory.cli validate --hub $Root
& $Python -m digital_asset_directory.cli roadmap check --hub $Root --no-update
if (-not $SkipTests) { & $Python -m pytest }
Write-Host "Bootstrap complete. Stable shims written to $DadBin. Add that folder to PATH or run $ShimPs1 from any repo."
Write-Host 'Review config\sources.local.yaml, then run scripts\first_scan.ps1.'

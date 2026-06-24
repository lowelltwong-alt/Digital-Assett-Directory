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
& $Python -m digital_asset_directory.cli validate --hub $Root
& $Python -m digital_asset_directory.cli roadmap check --hub $Root
if (-not $SkipTests) { & $Python -m pytest }
Write-Host 'Bootstrap complete. Review config\sources.local.yaml, then run scripts\first_scan.ps1.'

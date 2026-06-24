[CmdletBinding()]
param(
    [switch]$LocalOnly,
    [switch]$GitHubOnly,
    [int]$MaxFiles = 0
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Run scripts\bootstrap.ps1 first.' }
$args = @('-m', 'digital_asset_directory.cli', 'scan', '--hub', $Root)
if ($LocalOnly) { $args += '--local-only' }
if ($GitHubOnly) { $args += '--github-only' }
if ($MaxFiles -gt 0) { $args += @('--max-files', $MaxFiles) }
& $Python @args

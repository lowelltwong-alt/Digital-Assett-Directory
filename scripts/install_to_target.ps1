[CmdletBinding()]
param(
    [string]$Target = 'C:\Users\lowel\OneDrive\Desktop\Git Projects\04_Digital_Assett_Directory',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$TargetPath = [System.IO.Path]::GetFullPath($Target)

if (Test-Path $TargetPath) {
    $items = Get-ChildItem -LiteralPath $TargetPath -Force -ErrorAction SilentlyContinue
    if ($items.Count -gt 0 -and -not $Force) {
        throw "Target is not empty: $TargetPath. Re-run with -Force only after reviewing existing content."
    }
} else {
    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
}

$excludeDirs = @('.git', '.venv', '__pycache__')
Get-ChildItem -LiteralPath $Source -Force | Where-Object { $excludeDirs -notcontains $_.Name } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $TargetPath -Recurse -Force:$Force
}

Write-Host "Seed copied to $TargetPath"
Write-Host "Next: cd '$TargetPath'; powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1"

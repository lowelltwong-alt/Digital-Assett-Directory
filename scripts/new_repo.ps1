[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [string]$Name,
    [string]$Hub = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$RepoPath = [System.IO.Path]::GetFullPath($Repo)

# 1. Scaffold starter files + hub governance via the CLI.
$nameArg = if ($Name) { @('--name', $Name) } else { @() }
& asset-dir agent new --repo $RepoPath --hub $Hub @nameArg

# 2. Initialize git and point it at the versioned hub hook so the postflight gate is live.
if (-not (Test-Path (Join-Path $RepoPath '.git'))) {
    git -C $RepoPath init | Out-Null
}
git -C $RepoPath config core.hooksPath .githooks

Write-Host "New repo wired to Digital Asset Directory hub at $Hub"
Write-Host "Next: cd '$RepoPath'; asset-dir agent preflight --repo . --hub '$Hub' --agent claude-code --task '<task>'"

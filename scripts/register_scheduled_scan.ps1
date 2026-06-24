[CmdletBinding()]
param(
    [string]$TaskName = 'Digital Asset Directory Scan',
    [string]$DailyAt = '02:30',
    [switch]$LocalOnly
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Run scripts\bootstrap.ps1 first.' }
$Args = "-m digital_asset_directory.cli scan --hub `"$Root`""
if ($LocalOnly) { $Args += ' --local-only' }
$Action = New-ScheduledTaskAction -Execute $Python -Argument $Args -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Read-only Digital Asset Directory change detection and catalog refresh.' -Force | Out-Null
Write-Host "Registered task '$TaskName' at $DailyAt."

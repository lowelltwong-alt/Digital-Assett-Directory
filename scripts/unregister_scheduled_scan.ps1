[CmdletBinding()]
param([string]$TaskName = 'Digital Asset Directory Scan')
$ErrorActionPreference = 'Stop'
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed task '$TaskName'."

$ErrorActionPreference = 'Stop'
$DadHub = if ($env:DAD_HUB) { $env:DAD_HUB } else { $env:DAD_HUB_PATH }
if (-not $DadHub) {
  $Locator = Join-Path $HOME '.dad/hub.json'
  if (Test-Path $Locator) {
    $Payload = Get-Content $Locator -Raw | ConvertFrom-Json
    $DadHub = if ($Payload.hub_path) { $Payload.hub_path } else { $Payload.path }
  }
}
if (-not $DadHub) {
  Write-Error 'DAD_HUB, DAD_HUB_PATH, or ~/.dad/hub.json is required before this DAD hook can enforce postflight.'
  exit 1
}
python "$DadHub/scripts/enforce_postflight.py" --hub "$DadHub" --repo (Get-Location).Path

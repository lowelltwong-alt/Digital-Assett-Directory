$ErrorActionPreference = 'Stop'
$DadHub = 'C:\Users\lowel\OneDrive\Desktop\Git Projects\04_Digital_Assett_Directory'
python "$DadHub/scripts/enforce_postflight.py" --hub "$DadHub" --repo (Get-Location).Path

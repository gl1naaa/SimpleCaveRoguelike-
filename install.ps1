$ErrorActionPreference = "Stop"

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "Python 3.10+ is required. Install Python and try again."
}

& $python.Source -m pip install --user --editable (Split-Path -Parent $MyInvocation.MyCommand.Path)
Write-Host "Installed. Restart PowerShell, then run: rogue"

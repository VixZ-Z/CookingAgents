param(
    [string]$Python = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python was not found at $Python. Create the project environment first."
}

& $Python -m PyInstaller --noconfirm `
    --distpath (Join-Path $projectRoot 'dist') `
    --workpath (Join-Path $projectRoot 'build') `
    (Join-Path $PSScriptRoot 'CookingAgents.spec')
if ($LASTEXITCODE -ne 0) {
    throw 'The executable build failed.'
}
Write-Host "Ready: $(Join-Path $projectRoot 'dist\CookingAgents.exe')"

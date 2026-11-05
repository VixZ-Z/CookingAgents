# Windows: set up the environment and run everything.
#   powershell -ExecutionPolicy Bypass -File run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv .venv }
$py = ".venv\Scripts\python.exe"
& $py -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($script in "main", "compare", "visualize", "animate") {
    Write-Host "`n=== $script.py ==="
    & $py "$script.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

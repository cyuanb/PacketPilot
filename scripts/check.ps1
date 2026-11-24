$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$python = '.\.venv\Scripts\python.exe'
& $python scripts/check_secrets.py
if ($LASTEXITCODE -ne 0) { throw 'Credential scan failed.' }
& $python -m ruff check backend
if ($LASTEXITCODE -ne 0) { throw 'Lint failed.' }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
Push-Location frontend
try { npm run build; if ($LASTEXITCODE -ne 0) { throw 'Build failed.' } } finally { Pop-Location }

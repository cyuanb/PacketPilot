$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Path 'data\tmp' -Force | Out-Null
$env:TEMP = Join-Path $projectRoot 'data\tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $projectRoot 'data\pip-cache'
$env:npm_config_cache = if ($env:PACKETPILOT_NPM_CACHE) { $env:PACKETPILOT_NPM_CACHE } elseif (Test-Path -LiteralPath 'E:\') { 'E:\npmtmps' } else { Join-Path $projectRoot 'data\npm-cache' }
New-Item -ItemType Directory -Path $env:npm_config_cache -Force | Out-Null
$nodeVersion = (Get-Content -LiteralPath '.nvmrc' -Raw).Trim()
if (-not (Get-Command nvm -ErrorAction SilentlyContinue)) { throw 'Install nvm for Windows first.' }
nvm install $nodeVersion
if ($LASTEXITCODE -ne 0) { throw 'Node installation failed.' }
nvm use $nodeVersion
if ($LASTEXITCODE -ne 0) { throw 'Node activation failed.' }
nvm alias PacketPilot $nodeVersion
if ($LASTEXITCODE -ne 0) { throw 'Node alias setup failed.' }
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    throw 'Created .env. Configure DATABASE_URL and model credentials, then run setup again.'
}
$configPath = Join-Path $projectRoot '.env'
$configText = [IO.File]::ReadAllText($configPath)
if ($configText -match '(?m)^OWNER_PASSWORD=\s*$') {
    $password = 'Pp!' + [Guid]::NewGuid().ToString('N')
    $configText = [regex]::Replace($configText, '(?m)^OWNER_PASSWORD=\s*$', ('OWNER_PASSWORD=' + $password))
    [IO.File]::WriteAllText($configPath, $configText, [Text.UTF8Encoding]::new($false))
    Write-Host 'Generated owner password in local .env (not printed).'
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
}
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
& $python -m pip install --disable-pip-version-check -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& $python scripts/init_db.py
if ($LASTEXITCODE -ne 0) { throw 'Database creation failed. Check local credentials.' }
& $python -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
& $python -m app.bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Owner initialization failed.' }
Push-Location frontend
try {
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Setup complete. Run scripts/start.ps1. Login credentials are in local .env.'

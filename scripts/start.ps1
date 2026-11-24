param([switch]$Dev)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/setup.ps1 first.' }
if (-not (Test-Path -LiteralPath '.env')) { throw 'Missing .env; run setup first.' }
$originLine = Get-Content -LiteralPath '.env' | Where-Object { $_ -match '^APP_ORIGIN=' } | Select-Object -First 1
$origin = if ($originLine) { $originLine.Substring(11).Trim() } else { 'http://localhost:8010' }
$port = ([uri]$origin).Port
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw "Port $port is occupied. Stop the existing PacketPilot instance or configure another port." }
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html') -and -not $Dev) { throw 'Frontend build missing. Run npm run build in frontend.' }
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
New-Item -ItemType Directory -Path 'data\runtime' -Force | Out-Null
$pidPath = Join-Path $projectRoot 'data\runtime\processes.json'
if (Test-Path -LiteralPath $pidPath) {
    $old = @(Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json)
    foreach ($entry in $old) {
        $proc = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
        if ($proc -and $proc.StartTime.ToUniversalTime() -eq ([datetime]$entry.started).ToUniversalTime()) {
            throw 'A recorded PacketPilot process is running. Run scripts/stop.ps1 first.'
        }
    }
}
$started = @()
try {
    $specs = @(
        [pscustomobject]@{Name='api';Args="-m uvicorn app.main:app --host 127.0.0.1 --port $port"},
        [pscustomobject]@{Name='worker';Args='-m app.worker'}
    )
    foreach ($spec in $specs) {
        $name = $spec.Name
        $process = Start-Process -FilePath $python -ArgumentList $spec.Args -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "data\runtime\$name.out.log" -RedirectStandardError "data\runtime\$name.err.log"
        $started += [pscustomobject]@{pid=$process.Id;started=$process.StartTime.ToUniversalTime().ToString('o');name=$name}
    }
    if ($Dev) {
        nvm use PacketPilot
        if ($LASTEXITCODE -ne 0) { throw 'Could not activate PacketPilot Node alias.' }
        $node = (Get-Command node).Source
        $vite = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
        $process = Start-Process -FilePath $node -ArgumentList @($vite,'--host','127.0.0.1') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput 'data\runtime\web.out.log' -RedirectStandardError 'data\runtime\web.err.log'
        $started += [pscustomobject]@{pid=$process.Id;started=$process.StartTime.ToUniversalTime().ToString('o');name='web'}
    }
    $started | ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding utf8
    $healthy = $false
    for ($i=0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $healthJson = & $python -c "import httpx; print(httpx.get('$origin/api/health',timeout=2,trust_env=False).text)" 2>$null
            if ($LASTEXITCODE -eq 0 -and ($healthJson | ConvertFrom-Json).status -eq 'ok') { $healthy=$true;break }
        } catch {}
    }
    if (-not $healthy) { throw 'Application did not become healthy. Inspect data/runtime logs.' }
    Write-Host "PacketPilot ready: $origin"
    Write-Host 'Owner credentials: local .env. Stop with scripts/stop.ps1.'
} catch {
    foreach ($entry in $started) {
        $proc = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
        if ($proc -and $proc.StartTime.ToUniversalTime() -eq ([datetime]$entry.started).ToUniversalTime()) { Stop-Process -Id $entry.pid }
    }
    throw
}

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $projectRoot 'data\runtime\processes.json'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Host 'No managed PacketPilot processes.'; exit 0 }
$entries = @(Get-Content -LiteralPath $pidPath -Raw | ConvertFrom-Json)
foreach ($entry in $entries) {
    $proc = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    if ($proc.StartTime.ToUniversalTime() -ne ([datetime]$entry.started).ToUniversalTime()) { Write-Warning 'PID was reused; skipped.'; continue }
    $info = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.pid)"
    if (-not $info.CommandLine.Contains($projectRoot)) { Write-Warning 'Process does not belong to this checkout; skipped.'; continue }
    Stop-Process -Id $entry.pid
    Write-Host ("Stopped " + $entry.name)
}
Remove-Item -LiteralPath $pidPath

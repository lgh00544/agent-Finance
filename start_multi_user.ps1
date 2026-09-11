[CmdletBinding()]
param([int]$Port = 8100)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw "Python not found: $Python" }
if (-not (Test-Path (Join-Path $Root '.env'))) { throw '.env not found' }
if (-not (Test-Path (Join-Path $Root 'backend\app\core\auth.py'))) { throw 'Multi-user backend not found' }
# Load the existing .env so database credentials and the migrated account are available.
foreach ($line in Get-Content (Join-Path $Root '.env')) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$' -and $line -notmatch '^\s*#') {
        $name = $matches[1]
        $value = $matches[2].Trim().Trim("'").Trim('"')
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}
$env:APP_ENV = 'dev'
$env:MULTI_USER_ENABLED = 'true'
$env:SERVER_PORT = "$Port"
$env:DB_BACKEND = 'mysql'
$env:CACHE_BACKEND = 'redis'
$env:REDIS_DB = '15'
$env:REDIS_NAMESPACE = 'stock-agent:multi-user'
$env:QDRANT_MODE = 'server'
$env:SYNC_ON_START = 'false'
$env:VITE_API_PROXY = "http://127.0.0.1:$Port"
$env:VITE_API_PROXY = 'http://localhost:8100'
if (-not (Test-NetConnection 127.0.0.1 -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue)) { throw 'Redis is not listening on 6379' }
if (-not (Test-NetConnection 127.0.0.1 -Port 6333 -InformationLevel Quiet -WarningAction SilentlyContinue)) { throw 'Qdrant is not listening on 6333' }
$old = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $old) { if ($processId -ne $PID) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue } }
Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.main:app','--app-dir',(Join-Path $Root 'backend'),'--host','127.0.0.1','--port',"$Port" -WorkingDirectory $Root -WindowStyle Hidden
$pnpm = (Get-Command pnpm.cmd -ErrorAction SilentlyContinue).Source
if (-not $pnpm) { $pnpm = (Get-Command pnpm -ErrorAction SilentlyContinue).Source }
if (-not $pnpm) { throw '未找到 pnpm，请先运行 setup_new_machine.bat' }
Start-Process -FilePath $pnpm -ArgumentList 'dev','--host','0.0.0.0' -WorkingDirectory (Join-Path $Root 'web')
Write-Host "Multi-user backend: http://127.0.0.1:$Port; frontend: http://127.0.0.1:5173" -ForegroundColor Green

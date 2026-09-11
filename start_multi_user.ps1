[CmdletBinding()]
param([int]$Port = 8100)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw "未找到虚拟环境：$Python，请先运行 setup_new_machine.bat" }
if (-not (Test-Path (Join-Path $Root '.env'))) { throw '未找到 .env，请先运行 setup_new_machine.bat' }

$env:APP_ENV = 'dev'
$env:MULTI_USER_ENABLED = 'true'
$env:SERVER_PORT = "$Port"
$env:DB_BACKEND = 'mysql'
$env:CACHE_BACKEND = 'redis'
$env:REDIS_DB = '15'
$env:REDIS_NAMESPACE = 'stock-agent:multi-user'
$env:QDRANT_MODE = 'server'
$env:SYNC_ON_START = 'false'

$redis = Get-Service -Name Redis -ErrorAction SilentlyContinue
if ($redis -and $redis.Status -ne 'Running') { Start-Service Redis }
if (-not (Test-NetConnection 127.0.0.1 -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue)) { throw 'Redis 未监听 6379' }
if (-not (Test-NetConnection 127.0.0.1 -Port 6333 -InformationLevel Quiet -WarningAction SilentlyContinue)) { throw 'Qdrant 未监听 6333' }

$old = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $old) { if ($pid -ne $PID) { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue } }

Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.main:app','--app-dir',(Join-Path $Root 'backend'),'--host','127.0.0.1','--port',"$Port" -WorkingDirectory $Root -WindowStyle Hidden
Start-Process -FilePath 'pnpm' -ArgumentList 'dev','--host','0.0.0.0' -WorkingDirectory (Join-Path $Root 'web')
Write-Host "多人后端：http://127.0.0.1:$Port；前端：http://127.0.0.1:5173" -ForegroundColor Green

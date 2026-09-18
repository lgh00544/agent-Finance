[CmdletBinding()]
param([int]$Port = 8100)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw "Python not found: $Python" }
if (-not (Test-Path (Join-Path $Root '.env'))) { throw '.env not found' }
if (-not (Test-Path (Join-Path $Root 'backend\app\core\auth.py'))) { throw 'Multi-user backend not found' }
# Settings loads .env with python-dotenv, preserving JSON and quoted values.
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
function Test-Port([int]$CheckPort) {
    return [bool](Test-NetConnection 127.0.0.1 -Port $CheckPort -InformationLevel Quiet -WarningAction SilentlyContinue)
}
function Wait-Port([int]$CheckPort, [int]$Seconds = 90) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Test-Port $CheckPort) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}
if (-not (Test-NetConnection 127.0.0.1 -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue)) { throw 'Redis is not listening on 6379' }
if (-not (Test-NetConnection 127.0.0.1 -Port 6333 -InformationLevel Quiet -WarningAction SilentlyContinue)) { throw 'Qdrant is not listening on 6333' }
$old = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $old) { if ($processId -ne $PID) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue } }
$frontendPort = 5173
$frontendRoot = (Resolve-Path (Join-Path $Root 'web')).Path
$oldFrontend = Get-NetTCPConnection -State Listen -LocalPort $frontendPort -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $oldFrontend) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -and $process.CommandLine.Contains($frontendRoot)) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}
if (Test-Port $frontendPort) { throw '5173 已被其他程序占用，请先关闭该程序后重试' }
$LogRoot = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force $LogRoot | Out-Null
$Started = Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.main:app','--app-dir',(Join-Path $Root 'backend'),'--host','127.0.0.1','--port',"$Port" -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogRoot 'multi-user.stdout.log') -RedirectStandardError (Join-Path $LogRoot 'multi-user.stderr.log')
Write-Host "Backend process: $($Started.Id); logs: $LogRoot"
if (-not (Wait-Port $Port)) {
    Get-Content (Join-Path $LogRoot 'multi-user.stderr.log') -Tail 40 -ErrorAction SilentlyContinue
    throw "后端未能在 $Port 启动，请查看 $LogRoot"
}
$frontendLauncher = Join-Path $Root 'web\start_frontend_hidden.bat'
if (-not (Test-Path $frontendLauncher)) { throw "前端启动脚本不存在: $frontendLauncher" }
Start-Process -FilePath "cmd.exe" -ArgumentList @("/d", "/c", "`"$frontendLauncher`" http://127.0.0.1:$Port") -WorkingDirectory (Join-Path $Root "web") -WindowStyle Hidden
if (-not (Wait-Port $frontendPort)) { throw "前端未能在 $frontendPort 启动，请检查 web 启动脚本和 pnpm" }
Write-Host "Multi-user backend: http://127.0.0.1:$Port; frontend: http://127.0.0.1:$frontendPort" -ForegroundColor Green

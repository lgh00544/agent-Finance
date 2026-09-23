[CmdletBinding()]
param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $PSScriptRoot).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw "Python not found: $Python" }
if (-not (Test-Path (Join-Path $Root '.env'))) { throw '.env not found' }
$env:APP_ENV = 'dev'
$env:MULTI_USER_ENABLED = 'false'
$env:SERVER_PORT = "$Port"
$env:DB_BACKEND = 'sqlite'
$env:CACHE_BACKEND = 'memory'
$env:QDRANT_MODE = 'local'
$env:SYNC_ON_START = 'false'
$env:VITE_API_PROXY = "http://127.0.0.1:$Port"
function Test-Port([int]$CheckPort) { return [bool](Test-NetConnection 127.0.0.1 -Port $CheckPort -InformationLevel Quiet -WarningAction SilentlyContinue) }
function Wait-Port([int]$CheckPort, [int]$Seconds = 90) {
    for ($i = 0; $i -lt $Seconds; $i++) { if (Test-Port $CheckPort) { return $true }; Start-Sleep -Seconds 1 }
    return $false
}
$old = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $old) { if ($processId -ne $PID) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue } }
$frontendPort = 5173
$frontendRoot = (Resolve-Path (Join-Path $Root 'web')).Path
$oldFrontend = Get-NetTCPConnection -State Listen -LocalPort $frontendPort -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $oldFrontend) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -and $process.CommandLine.Contains($frontendRoot)) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }
}
if (Test-Port $frontendPort) { throw '5173 已被其他程序占用，请先关闭该程序后重试' }
$LogRoot = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force $LogRoot | Out-Null
Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.main:app','--app-dir',(Join-Path $Root 'backend'),'--host','127.0.0.1','--port',"$Port" -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogRoot 'single-user.stdout.log') -RedirectStandardError (Join-Path $LogRoot 'single-user.stderr.log')
if (-not (Wait-Port $Port)) { throw "后端未能在 $Port 启动，请检查 $LogRoot" }
$frontendLauncher = Join-Path $Root 'web\start_frontend_hidden.bat'
if (-not (Test-Path $frontendLauncher)) { throw "前端启动脚本不存在: $frontendLauncher" }
Start-Process -FilePath 'cmd.exe' -ArgumentList '/d','/c',"`"$frontendLauncher`" `"http://127.0.0.1:$Port`"" -WorkingDirectory (Join-Path $Root 'web') -WindowStyle Hidden
if (-not (Wait-Port $frontendPort)) { throw "前端未能在 $frontendPort 启动，请检查 web 启动脚本和 pnpm" }
Write-Host "Single-user backend: http://127.0.0.1:$Port; frontend: http://127.0.0.1:$frontendPort" -ForegroundColor Green

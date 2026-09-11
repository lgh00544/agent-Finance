param(
    [int]$Port = 8100
)

$env:APP_ENV = "dev"
$env:MULTI_USER_ENABLED = "true"
$env:SYNC_ON_START = "false"
$env:SERVER_PORT = "$Port"
$env:DB_BACKEND = "mysql"
$env:CACHE_BACKEND = "redis"
$env:REDIS_DB = "15"
$env:REDIS_NAMESPACE = "stock-agent:multi-user"
$env:QDRANT_MODE = "server"

if (-not $env:AUTH_DEFAULT_PASSWORD) {
    throw "AUTH_DEFAULT_PASSWORD must be set; refusing to start multi-user mode"
}
if ($env:DB_BACKEND -ne "mysql" -or $env:CACHE_BACKEND -ne "redis" -or $env:QDRANT_MODE -ne "server") {
    throw "Multi-user mode requires shared MySQL, Redis, and Qdrant server"
}

New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot "data") | Out-Null
& "D:\self\.venv\Scripts\python.exe" -m uvicorn app.main:app `
    --app-dir (Join-Path $PSScriptRoot "backend") --host 127.0.0.1 --port $Port

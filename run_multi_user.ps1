param(
    [int]$Port = 8100
)

$env:APP_ENV = "dev"
$env:MULTI_USER_ENABLED = "false"
$env:SYNC_ON_START = "false"
$env:SERVER_PORT = "$Port"
$env:DB_BACKEND = "sqlite"
$env:SQLITE_PATH = (Join-Path $PSScriptRoot "data\multi-user.db")
$env:CACHE_BACKEND = "redis"
$env:REDIS_DB = "15"
$env:REDIS_NAMESPACE = "stock-agent:multi-user"
$env:QDRANT_MODE = "local"
$env:QDRANT_LOCAL_PATH = (Join-Path $PSScriptRoot "data\qdrant_multi_user")

New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot "data") | Out-Null
& "D:\self\.venv\Scripts\python.exe" -m uvicorn app.main:app `
    --app-dir (Join-Path $PSScriptRoot "backend") --host 127.0.0.1 --port $Port

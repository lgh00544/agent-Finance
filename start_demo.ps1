$env:APP_ENV = 'dev'
$env:MULTI_USER_ENABLED = 'true'
$env:SERVER_PORT = '8100'
$env:DB_BACKEND = 'sqlite'
$env:SQLITE_PATH = 'D:\self-multi-user\data\multi-auth-demo.db'
$env:CACHE_BACKEND = 'memory'
$env:QDRANT_MODE = 'local'
$env:QDRANT_LOCAL_PATH = 'D:\self-multi-user\data\qdrant_multi_auth_demo'
$env:SYNC_ON_START = 'false'
$env:AUTH_DEFAULT_USERNAME = 'legacy'
$env:AUTH_DEFAULT_PASSWORD = 'DemoLegacy-2026!'
$env:PYTEST_CURRENT_TEST = 'local-multi-user-demo'
New-Item -ItemType Directory -Force 'D:\self-multi-user\data' | Out-Null
$old = Get-NetTCPConnection -State Listen -LocalPort 8100 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique
foreach ($p in $old) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
$proc = Start-Process -FilePath 'D:\self\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--app-dir','D:\self-multi-user\backend','--host','127.0.0.1','--port','8100' -WorkingDirectory 'D:\self-multi-user' -WindowStyle Hidden -PassThru
Write-Output "pid=$($proc.Id)"

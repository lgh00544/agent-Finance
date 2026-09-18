[CmdletBinding()]
param(
    [ValidateSet('MultiUser', 'SingleUser')]
    [string]$Mode = 'MultiUser',
    [switch]$Start,
    [switch]$SkipPackageInstall,
    [switch]$SkipQdrant,
    [string]$Username = 'lugenghua',
    [string]$MysqlHost,
    [int]$MysqlPort = 4000,
    [string]$MysqlUser,
    [string]$MysqlDatabase = 'stock_agent',
    [string]$MysqlPassword,
    [string]$DeepseekApiKey
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '.')).Path
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$RuntimeRoot = Join-Path $ProjectRoot 'data\runtime'
$QdrantRoot = Join-Path $RuntimeRoot 'qdrant'
$QdrantData = Join-Path $ProjectRoot 'data\qdrant_server'
$QdrantZip = Join-Path $RuntimeRoot 'qdrant.zip'
$QdrantVersion = 'v1.19.1'
$QdrantSha256 = '9b6f69bd85f6abed4bc13f943099f55c6ffd55f5dd90388635320d8fbb569eb0'
$QdrantUrl = "https://github.com/qdrant/qdrant/releases/download/$QdrantVersion/qdrant-x86_64-pc-windows-msvc.zip"
$PreferredPythonVersion = '3.13'

function Write-Step([string]$Message) { Write-Host "`n== $Message ==" -ForegroundColor Cyan }
function Fail([string]$Message) { throw $Message }
function Invoke-Native([string]$File, [string[]]$Args) {
    & $File @Args
    if ($LASTEXITCODE -ne 0) { Fail "命令失败（$LASTEXITCODE）：$File $($Args -join ' ')" }
}
function Test-Command([string]$Name) { return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue) }
function Refresh-Path() {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}
function Test-Port([int]$Port) {
    try { return [bool](Test-NetConnection 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue) }
    catch { return $false }
}
function Set-EnvValue([string]$Path, [string]$Name, [string]$Value) {
    $lines = if (Test-Path $Path) { [System.Collections.Generic.List[string]](Get-Content $Path) } else { [System.Collections.Generic.List[string]]::new() }
    $quoted = $Value.Replace('\', '\\').Replace("'", "\'")
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*#?\s*$([regex]::Escape($Name))=") {
            $lines[$i] = "$Name='$quoted'"
            $found = $true
            break
        }
    }
    if (-not $found) { $lines.Add("$Name='$quoted'") }
    Set-Content -LiteralPath $Path -Value $lines -Encoding utf8
}
function Read-Secret([string]$Prompt, [string]$Existing = '') {
    if ($Existing) { return $Existing }
    $secure = Read-Host $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
function Ensure-WingetPackage([string]$Id, [string]$Name) {
    if ($SkipPackageInstall) { return }
    Write-Host "检查 $Name ..."
    winget list --id $Id --exact --accept-source-agreements 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "安装 $Name ..."
        Invoke-Native 'winget' @('install', '--id', $Id, '--exact', '--silent', '--accept-source-agreements', '--accept-package-agreements')
    } else { Write-Host "$Name 已存在" -ForegroundColor DarkGray }
}

Set-Location $ProjectRoot
Write-Host "A 股决策 Agent 新机器初始化：$Mode" -ForegroundColor Green
if ($Mode -eq 'MultiUser' -and -not (Test-Path (Join-Path $ProjectRoot 'backend\app\core\auth.py'))) {
    Fail '当前项目不包含多人认证后端。请先切换到已合入多人化代码的分支，再运行本脚本。'
}

Write-Step '安装基础软件'
if (-not (Test-Command 'winget') -and -not $SkipPackageInstall) {
    Fail '未找到 winget。请先安装 Windows App Installer，或使用 -SkipPackageInstall 并手动准备 Python、Node.js、Git。'
}
if (-not $SkipPackageInstall) {
    Ensure-WingetPackage 'Python.Python.3.13' 'Python 3.13'
    Ensure-WingetPackage 'OpenJS.NodeJS.LTS' 'Node.js LTS'
    Ensure-WingetPackage 'Git.Git' 'Git'
    if ($Mode -eq 'MultiUser') { Ensure-WingetPackage 'Redis.Redis' 'Redis' }
    Refresh-Path
}
Refresh-Path

$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    $pythonCommand = $python.Source
    $pythonArgs = @("-$PreferredPythonVersion")
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { Fail '未找到 Python。请重新打开终端后重试。' }
    $pythonCommand = $python.Source
    $pythonArgs = @()
}
function Read-EnvValue([string]$Path, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path)) { return '' }
    $prefix = "^\s*#?\s*$([regex]::Escape($Name))=(.*)$"
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match $prefix) { return $matches[1].Trim().Trim("'").Trim('"') }
    }
    return ''
}
$version = (& $pythonCommand @pythonArgs --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $version -notmatch "Python $PreferredPythonVersion(\.|$)") {
    Fail "需要 Python $PreferredPythonVersion；当前无法找到对应版本。请重新打开终端后重试。"
}
Write-Host "使用 $version"

Write-Step '创建 Python 虚拟环境并安装依赖'
if (-not (Test-Path $VenvPython)) { Invoke-Native $pythonCommand ($pythonArgs + @('-m', 'venv', (Join-Path $ProjectRoot '.venv'))) }
& $VenvPython -m pip --version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Invoke-Native $VenvPython @('-m', 'ensurepip', '--upgrade', '--default-pip') }
Invoke-Native $VenvPython @('-m', 'pip', 'install', '--upgrade', '--no-cache-dir', 'pip')
Invoke-Native $VenvPython @('-m', 'pip', 'install', '--no-cache-dir', '-r', (Join-Path $ProjectRoot 'backend\requirements.txt'))

Write-Step '安装前端依赖'
if (-not (Test-Command 'pnpm')) {
    if (-not (Test-Command 'npm')) { Fail '未找到 npm。请重新打开终端后重试。' }
    Invoke-Native 'npm' @('install', '--global', 'pnpm')
    Refresh-Path
}
Push-Location (Join-Path $ProjectRoot 'web')
try {
    if (Test-Path 'pnpm-lock.yaml') { Invoke-Native 'pnpm' @('install', '--frozen-lockfile') }
    else { Invoke-Native 'pnpm' @('install') }
} finally { Pop-Location }

Write-Step '初始化配置文件'
$envPath = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $envPath)) { Copy-Item (Join-Path $ProjectRoot '.env.example') $envPath }
if ($Mode -eq 'MultiUser') {
    if (-not $MysqlHost) { $MysqlHost = Read-EnvValue $envPath 'MYSQL_HOST' }
    if (-not $MysqlHost) { $MysqlHost = Read-Host 'TiDB/MySQL 主机地址' }
    if (-not $MysqlUser) { $MysqlUser = Read-EnvValue $envPath 'MYSQL_USER' }
    if (-not $MysqlUser) { $MysqlUser = Read-Host 'TiDB/MySQL 用户名' }
    if (-not $MysqlPassword) { $MysqlPassword = Read-EnvValue $envPath 'MYSQL_ROOT_PASSWORD' }
    $MysqlPassword = Read-Secret 'TiDB/MySQL 密码' $MysqlPassword
    $authPassword = Read-Secret 'lugenghua 登录密码（至少 8 位）' (Read-EnvValue $envPath 'AUTH_DEFAULT_PASSWORD')
    if ($authPassword.Length -lt 8) { Fail '登录密码至少需要 8 位。' }
    Set-EnvValue $envPath 'APP_ENV' 'dev'
    Set-EnvValue $envPath 'MULTI_USER_ENABLED' 'true'
    Set-EnvValue $envPath 'SERVER_PORT' '8100'
    Set-EnvValue $envPath 'DB_BACKEND' 'mysql'
    Set-EnvValue $envPath 'CACHE_BACKEND' 'redis'
    Set-EnvValue $envPath 'REDIS_DB' '15'
    Set-EnvValue $envPath 'REDIS_NAMESPACE' 'stock-agent:multi-user'
    Set-EnvValue $envPath 'QDRANT_MODE' 'server'
    Set-EnvValue $envPath 'QDRANT_HOST' '127.0.0.1'
    Set-EnvValue $envPath 'QDRANT_PORT' '6333'
    Set-EnvValue $envPath 'MYSQL_HOST' $MysqlHost
    Set-EnvValue $envPath 'MYSQL_PORT' $MysqlPort
    Set-EnvValue $envPath 'MYSQL_USER' $MysqlUser
    Set-EnvValue $envPath 'MYSQL_ROOT_PASSWORD' $MysqlPassword
    Set-EnvValue $envPath 'MYSQL_DATABASE' $MysqlDatabase
    Set-EnvValue $envPath 'AUTH_DEFAULT_USERNAME' $Username
    Set-EnvValue $envPath 'AUTH_DEFAULT_PASSWORD' $authPassword
    if (-not $DeepseekApiKey) { $DeepseekApiKey = Read-Secret 'DeepSeek API Key（可留空）' (Read-EnvValue $envPath 'DEEPSEEK_API_KEY') }
    if ($DeepseekApiKey) { Set-EnvValue $envPath 'DEEPSEEK_API_KEY' $DeepseekApiKey }
} else {
    Set-EnvValue $envPath 'MULTI_USER_ENABLED' 'false'
    Set-EnvValue $envPath 'DB_BACKEND' 'sqlite'
    Set-EnvValue $envPath 'CACHE_BACKEND' 'memory'
    Set-EnvValue $envPath 'QDRANT_MODE' 'local'
    if (-not $DeepseekApiKey) { $DeepseekApiKey = Read-Secret 'DeepSeek API Key（可留空）' (Read-EnvValue $envPath 'DEEPSEEK_API_KEY') }
    if ($DeepseekApiKey) { Set-EnvValue $envPath 'DEEPSEEK_API_KEY' $DeepseekApiKey }
}
Write-Host "配置已写入 .env（密码和密钥不显示）"

if ($Mode -eq 'MultiUser') {
    Write-Step '启动 Redis'
    $redisService = Get-Service -Name Redis -ErrorAction SilentlyContinue
    if ($redisService -and $redisService.Status -ne 'Running') { Start-Service Redis }
    if (-not (Test-Port 6379)) { Fail 'Redis 未监听 6379。请检查 Redis 服务。' }

    if (-not $SkipQdrant) {
        Write-Step '安装并启动 Qdrant'
        New-Item -ItemType Directory -Force $RuntimeRoot, $QdrantData | Out-Null
        $qdrantExe = Get-ChildItem $QdrantRoot -Filter 'qdrant.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $qdrantExe) {
            if (-not (Test-Path $QdrantZip)) {
                Invoke-WebRequest -Uri $QdrantUrl -OutFile $QdrantZip -UseBasicParsing
            }
            $actualHash = (Get-FileHash $QdrantZip -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualHash -ne $QdrantSha256) { Fail 'Qdrant 下载包 SHA256 校验失败，已停止。' }
            if (Test-Path $QdrantRoot) { Remove-Item $QdrantRoot -Recurse -Force }
            Expand-Archive -LiteralPath $QdrantZip -DestinationPath $QdrantRoot -Force
            $qdrantExe = Get-ChildItem $QdrantRoot -Filter 'qdrant.exe' -Recurse | Select-Object -First 1
        }
        if (-not $qdrantExe) { Fail '解压后没有找到 qdrant.exe。' }
        if (-not (Test-Port 6333)) {
            $qdrantConfig = Join-Path $RuntimeRoot 'qdrant.yaml'
            @"
storage:
  storage_path: '$($QdrantData.Replace('\','/'))/storage'
  snapshots_path: '$($QdrantData.Replace('\','/'))/snapshots'
service:
  host: 127.0.0.1
  http_port: 6333
"@ | Set-Content $qdrantConfig -Encoding utf8
            New-Item -ItemType Directory -Force (Join-Path $QdrantData 'storage'), (Join-Path $QdrantData 'snapshots') | Out-Null
            Start-Process -FilePath $qdrantExe.FullName -ArgumentList '--config-path', $qdrantConfig -WorkingDirectory $qdrantExe.DirectoryName -WindowStyle Hidden
            for ($i = 0; $i -lt 30 -and -not (Test-Port 6333); $i++) { Start-Sleep -Seconds 1 }
        }
        if (-not (Test-Port 6333)) { Fail 'Qdrant 未监听 6333。' }
    }
}

Write-Step '项目初始化检查'
$envLines = Get-Content $envPath
foreach ($line in $envLines) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        $name = $matches[1]; $value = $matches[2].Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}
$env:PYTEST_CURRENT_TEST = 'setup-smoke'
Push-Location (Join-Path $ProjectRoot 'backend')
try { & $VenvPython -c "from app.db.session import init_db; print(init_db().get('status'))"; if ($LASTEXITCODE -ne 0) { Fail '数据库初始化检查失败。' } }
finally { Pop-Location }

if ($Start) {
    Write-Step '启动项目'
    if ($Mode -eq 'MultiUser') { & (Join-Path $ProjectRoot 'start_multi_user.ps1') }
    else { & (Join-Path $ProjectRoot 'start_single_user.ps1') }
} else {
    Write-Host "`n初始化完成。启动多人版：powershell -ExecutionPolicy Bypass -File .\start_multi_user.ps1" -ForegroundColor Green
    Write-Host '浏览器地址：http://127.0.0.1:5173'
}

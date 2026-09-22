# 注册后端守护计划任务（批A A1）
# 必须在「普通用户交互会话」运行（DSH/WorkBuddy 沙箱内会被拒绝访问）。
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File D:\self\scripts\register_backend_watchdog_task.ps1
$ErrorActionPreference = 'Stop'
$taskName = 'DSH_BackendWatchdog'
$script   = 'D:\self\scripts\backend_watchdog.ps1'
if (-not (Test-Path $script)) { throw "watchdog not found: $script" }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '"') -WorkingDirectory 'D:\self'
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId ($env:USERDOMAIN + '\' + $env:USERNAME) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'DSH 后端进程守护（探活 + net 门禁 + 单日3次上限 + 拉起前归档）' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
$t = Get-ScheduledTask -TaskName $taskName
Write-Host ('REGISTERED State=' + $t.State + ' RunLevel=' + $t.Principal.RunLevel + ' LogonType=' + $t.Principal.LogonType)

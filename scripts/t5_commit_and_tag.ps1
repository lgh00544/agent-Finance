# T5 批C 基线锁：提交 + 打 tag（**须显式 -Confirm 才执行**）
# 用法（默认 dry-run，只打印计划）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File D:\self\scripts\t5_commit_and_tag.ps1
# 真正执行（需 sir 授权后）：
#   ... -Confirm [-IncludeDocs]
param([switch]$Confirm, [switch]$IncludeDocs)
$ErrorActionPreference='Stop'
$env:PATH='C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd;C:\Windows\system32;C:\Windows'
Set-Location 'D:\self'
$code = @(
  'backend/app/agents/monitor.py','backend/app/agents/portfolio_sentinel.py','backend/app/api/routes.py',
  'backend/app/core/config.py','backend/app/db/models.py','backend/app/db/repo.py','backend/app/db/session.py',
  'backend/app/scheduler/jobs.py','backend/app/services/chat_handlers.py','backend/app/services/feishu.py',
  'backend/app/services/holding_view.py','backend/app/services/paper_monitor.py',
  'backend/app/services/kline_store.py','backend/app/services/kline_backfill.py',
  'backend/app/services/signal_scan.py',
  'backend/app/services/pre_market_screen.py','backend/app/services/ths_pnl.py',
  'backend/tests/test_batch2_reduce_ratio.py','backend/tests/test_batch4_pre_market.py',
  'backend/tests/test_feishu_b4.py','backend/tests/test_model_optimizations.py',
  'backend/tests/test_portfolio_sentinel.py','backend/tests/test_ths_pnl.py',
  'backend/tests/test_kline_store.py','backend/tests/test_signal_registry.py',
  'web/src/api/account.ts','web/src/pages/OverviewPage.tsx','web/src/types/index.ts',
  'scripts/backend_watchdog.ps1','scripts/register_backend_watchdog_task.ps1','mem_probe.py'
)
$docs = @(
  '实盘GoNoGo清单_核对_20260930.md','实盘就绪补齐_批A-D_提交清单_20260921.md',
  '实盘就绪补齐_待确认事项_审核包_20260921.md'
)
$files = if ($IncludeDocs) { $code + $docs } else { $code }
Write-Host '=== T5 提交计划 ==='
$files | ForEach-Object { Write-Host ('  ' + $_) }
Write-Host ('文件数: ' + $files.Count + '  IncludeDocs=' + [bool]$IncludeDocs)
if (-not $Confirm) { Write-Host '[DRY-RUN] 未加 -Confirm，未做任何提交/打标签。'; exit 0 }
# 注意：jobs.py / routes.py / config.py / models.py / repo.py 跨批重叠；
# 若必须严格按批拆分，请改用 git add -p 手动暂存后分别提交。
git add -- $files
git commit -m "feat(实盘就绪): 批A 稳定性底座 + 批D 同花顺下线/盈亏推算 + 8a B5修复 + 本地仓库 local-only"
git tag -a 'pre-live-2026-10-08' -m 'pre-live baseline 2026-10-08（批A/批D/8a/批1.5 local-only）'
Write-Host '=== 结果 ==='
git --no-pager show --stat --oneline HEAD
git tag --list 'pre-live*'
git status --porcelain | Measure-Object -Line

@echo off
setlocal
set BASE=http://localhost:8000/api

echo [1/5] GET /api/market/diagnostics
curl -sS "%BASE%/market/diagnostics"
echo.
echo.

echo [2/5] POST /api/market/sector-forward/run
curl -sS -X POST "%BASE%/market/sector-forward/run" -H "Content-Type: application/json" -d "{}"
echo.
echo.

echo [3/5] POST /api/market/sector-rotation/run
curl -sS -X POST "%BASE%/market/sector-rotation/run"
echo.
echo.

echo [4/5] GET /api/market/regime-view
curl -sS "%BASE%/market/regime-view"
echo.
echo.

echo [5/5] GET /api/market_intel
curl -sS "%BASE%/market_intel"
echo.
echo.

endlocal

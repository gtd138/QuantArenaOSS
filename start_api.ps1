# API Server Startup Script

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Starting API Server" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "API URL: http://localhost:8000" -ForegroundColor White
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

python -m uvicorn api.arena_api:app --reload --host 0.0.0.0 --port 8000


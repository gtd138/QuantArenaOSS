# Frontend Server Startup Script

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Starting Frontend Server" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 使用自定义服务器（带异常处理，避免 ConnectionAbortedError 干扰）
python scripts\serve_frontend.py

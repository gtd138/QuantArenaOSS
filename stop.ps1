# ============================================================
# AI量化竞技场 - 一键停止脚本
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 🛑 停止AI量化竞技场" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 停止FastAPI进程（端口8000）
Write-Host "🔍 查找API进程（端口8000）..." -ForegroundColor Yellow
$apiPids = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique | 
    Where-Object { $_ -gt 0 }  # 过滤掉PID=0（系统进程）

if ($apiPids) {
    $stopped = $false
    foreach ($processId in $apiPids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "⏹️  停止API进程: $($proc.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }
    if ($stopped) {
        Write-Host "✓ API已停止" -ForegroundColor Green
    }
} else {
    Write-Host "ℹ️  未找到运行API" -ForegroundColor Gray
}

# 停止前端HTTP服务器进程（端口8080）
Write-Host ""
Write-Host "🔍 查找前端进程（端口8080）..." -ForegroundColor Yellow
$frontendPids = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique | 
    Where-Object { $_ -gt 0 }  # 过滤掉PID=0（系统进程）

if ($frontendPids) {
    $stopped = $false
    foreach ($processId in $frontendPids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "⏹️  停止前端进程: $($proc.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }
    if ($stopped) {
        Write-Host "✓ 前端已停止" -ForegroundColor Green
    }
} else {
    Write-Host "ℹ️  未找到运行前端" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ✅ 所有服务已停止！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

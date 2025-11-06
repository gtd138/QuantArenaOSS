# ============================================================
# AI量化竞技场 - 一键启动脚本
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 🏆 AI量化竞技场 - 一键启动" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python环境
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 未找到Python，请先安装Python 3.8+！" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python环境: $pythonVersion" -ForegroundColor Green

# 检查依赖
Write-Host "✓ 检查依赖..." -ForegroundColor Green

# 启动后端API（弹窗）
Write-Host ""
Write-Host "🚀 正在启动后端API..." -ForegroundColor Yellow
$apiProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python api/arena_api.py" -PassThru

# 等待API启动
Write-Host "⏳ 等待API启动（3秒）..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# 测试API是否启动成功
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/arena/config" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✓ API启动成功！" -ForegroundColor Green
} catch {
    Write-Host "⚠️ API可能还在启动中..." -ForegroundColor Yellow
}

# 启动前端服务器（弹窗）
Write-Host ""
Write-Host "🚀 正在启动前端服务器..." -ForegroundColor Yellow
$frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python scripts\serve_frontend.py" -PassThru

# 等待前端启动
Write-Host "⏳ 等待前端启动（2秒）..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

# 显示访问信息
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ✅ 启动完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📡 后端API: http://localhost:8000" -ForegroundColor White
Write-Host "🌐 前端界面: http://localhost:8080" -ForegroundColor White
Write-Host ""
Write-Host "💡 提示:" -ForegroundColor Yellow
Write-Host "  - 访问前端界面开始使用" -ForegroundColor Gray
Write-Host "  - 关闭任一窗口都会停止服务" -ForegroundColor Gray
Write-Host "  - 按 Ctrl+C 可以停止服务器" -ForegroundColor Gray
Write-Host ""

# 自动打开浏览器
Write-Host "🌐 正在打开浏览器..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Start-Process "http://localhost:8080"

Write-Host ""
Write-Host "✨ 竞技场已就绪！" -ForegroundColor Green
Write-Host ""
Write-Host "💡 提示：关闭任一服务窗口会停止该服务" -ForegroundColor Gray
Write-Host "💡 按任意键退出此窗口（服务将继续运行）..." -ForegroundColor Gray
Write-Host ""
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

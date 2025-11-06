# ============================================================
# AI量化竞技场 - 优雅停止脚本
# 先通知系统停止，等待数据保存，再关闭进程
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 🛑 优雅停止AI量化竞技场" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查API是否运行
Write-Host "🔍 检查API服务器状态..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    Write-Host "✓ API服务器正在运行" -ForegroundColor Green
} catch {
    Write-Host "❌ API服务器未运行" -ForegroundColor Red
    Write-Host ""
    Write-Host "将直接停止所有进程..." -ForegroundColor Yellow
    
    # 直接停止进程
    & "$PSScriptRoot\stop.ps1"
    exit
}

# 发送优雅停止信号
Write-Host ""
Write-Host "📡 发送停止信号..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/shutdown" -Method Post -TimeoutSec 5
    Write-Host "✓ 停止信号已发送" -ForegroundColor Green
    Write-Host "   状态: $($response.status)" -ForegroundColor Gray
    Write-Host "   消息: $($response.message)" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  无法发送停止信号: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "将强制停止进程..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    & "$PSScriptRoot\stop.ps1"
    exit
}

# 等待竞技场保存数据（监控日志文件）
Write-Host ""
Write-Host "⏳ 等待竞技场保存数据..." -ForegroundColor Yellow
Write-Host "   提示: 等待当前交易日完成" -ForegroundColor Gray

$maxWaitSeconds = 60  # 最多等待1分钟（优化：减少等待时间）
$waited = 0
$logFile = "$PSScriptRoot\logs\arena_background.log"

# 记录当前日志大小
$lastSize = 0
if (Test-Path $logFile) {
    $lastSize = (Get-Item $logFile).Length
}

while ($waited -lt $maxWaitSeconds) {
    Start-Sleep -Seconds 3
    $waited += 3
    
    # 检查日志是否还在更新
    if (Test-Path $logFile) {
        $currentSize = (Get-Item $logFile).Length
        if ($currentSize -ne $lastSize) {
            # 日志还在更新，说明还在运行
            Write-Host "   等待中... ($waited秒) [日志活跃]" -ForegroundColor Gray
            $lastSize = $currentSize
        } else {
            # 日志停止更新，可能已经完成
            Write-Host "   日志停止更新，检查最后内容..." -ForegroundColor Gray
            
            # 读取最后几行日志
            $lastLines = Get-Content $logFile -Tail 5 -ErrorAction SilentlyContinue
            $lastContent = $lastLines -join " "
            
            if ($lastContent -match "数据已保存|保存数据后退出|停止信号") {
                Write-Host "✓ 检测到数据保存完成" -ForegroundColor Green
                break
            } else {
                Write-Host "   等待确认... ($waited秒)" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "   等待中... ($waited秒)" -ForegroundColor Gray
    }
    
    # 每15秒提示一次
    if ($waited % 15 -eq 0 -and $waited -gt 0) {
        Write-Host "   💡 已等待 $waited 秒，最多等待 $maxWaitSeconds 秒" -ForegroundColor Cyan
    }
}

if ($waited -ge $maxWaitSeconds) {
    Write-Host ""
    Write-Host "⚠️  等待超时 (${maxWaitSeconds}秒)" -ForegroundColor Yellow
    Write-Host "   AI调用较慢或当前交易日未完成" -ForegroundColor Yellow
    Write-Host "   将强制停止进程..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "💡 提示：如需更快停止，可直接运行 .\force_stop.ps1" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "✅ 数据保存完成，准备停止进程" -ForegroundColor Green
}

# 额外等待2秒确保数据写入
Start-Sleep -Seconds 2

# 停止所有Python进程
Write-Host ""
Write-Host "🛑 停止所有服务进程..." -ForegroundColor Yellow

# 停止API进程
$apiPids = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique | 
    Where-Object { $_ -gt 0 }  # 过滤掉PID=0（系统进程）

if ($apiPids) {
    foreach ($processId in $apiPids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "⏹️  停止API: $($proc.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "✓ API已停止" -ForegroundColor Green
}

# 停止前端进程
$frontendPids = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique | 
    Where-Object { $_ -gt 0 }  # 过滤掉PID=0（系统进程）

if ($frontendPids) {
    foreach ($processId in $frontendPids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "⏹️  停止前端: $($proc.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "✓ 前端已停止" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ✅ 优雅停止完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 提示:" -ForegroundColor Cyan
Write-Host "  - 数据已保存到数据库" -ForegroundColor Gray
Write-Host "  - 下次启动会自动续跑" -ForegroundColor Gray
Write-Host "  - 查看日志: logs\arena_background.log" -ForegroundColor Gray
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

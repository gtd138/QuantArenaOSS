# 强制停止（跳过等待）
Write-Host "🛑 强制停止所有进程..." -ForegroundColor Red

# 停止API
$apiPids = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique | 
    Where-Object { $_ -gt 0 }

if ($apiPids) {
    foreach ($processId in $apiPids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "⏹️  强制停止: $($proc.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

# 停止前端
$frontendPids = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | 
    Select-Object -ExpandProperty OwningProcess -Unique | 
    Where-Object { $_ -gt 0 }

if ($frontendPids) {
    foreach ($processId in $frontendPids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "⏹️  强制停止: $($proc.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host ""
Write-Host "✅ 已强制停止所有进程" -ForegroundColor Green
Write-Host ""

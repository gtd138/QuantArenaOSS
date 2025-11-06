"""
恢复上一个session为running状态，以便继续运行
"""
import sqlite3
import sys

# 要恢复的session ID
TARGET_SESSION = '20251028_144733'

conn = sqlite3.connect('data/arena_sessions.db')
cursor = conn.cursor()

# 1. 检查session当前状态
cursor.execute('''
    SELECT session_id, start_date, current_date, end_date, status
    FROM arena_sessions
    WHERE session_id = ?
''', (TARGET_SESSION,))

row = cursor.fetchone()
if not row:
    print(f"❌ 找不到session: {TARGET_SESSION}")
    conn.close()
    sys.exit(1)

print(f"\n当前状态:")
print(f"  Session ID: {row[0]}")
print(f"  日期范围: {row[1]} -> {row[3]}")
print(f"  当前日期: {row[2]}")
print(f"  状态: {row[3]}")

# 2. 查看数据统计
cursor.execute('SELECT COUNT(*) FROM arena_daily_assets WHERE session_id = ?', (TARGET_SESSION,))
daily_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM arena_trades WHERE session_id = ?', (TARGET_SESSION,))
trade_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM arena_holdings WHERE session_id = ?', (TARGET_SESSION,))
holding_count = cursor.fetchone()[0]

print(f"\n数据统计:")
print(f"  每日资产: {daily_count} 条")
print(f"  交易记录: {trade_count} 笔")
print(f"  持仓记录: {holding_count} 条")

# 3. 获取实际最新日期
cursor.execute('''
    SELECT MAX(trade_date) FROM arena_daily_assets WHERE session_id = ?
''', (TARGET_SESSION,))
latest_date = cursor.fetchone()[0]
print(f"  实际最新日期: {latest_date}")

# 4. 更新session状态
print(f"\n正在更新session状态...")

cursor.execute('''
    UPDATE arena_sessions
    SET status = 'running',
        current_date = ?
    WHERE session_id = ?
''', (latest_date, TARGET_SESSION))

conn.commit()

print(f"✅ Session已更新:")
print(f"   状态: completed -> running")
print(f"   当前日期: {latest_date}")
print(f"\n💡 现在可以重启服务，将从 {latest_date} 继续运行")

# 5. 同时停止新创建的session
cursor.execute('''
    UPDATE arena_sessions
    SET status = 'aborted'
    WHERE session_id != ? AND status = 'running'
''', (TARGET_SESSION,))

if cursor.rowcount > 0:
    print(f"\n✅ 已停止 {cursor.rowcount} 个其他运行中的session")

conn.commit()
conn.close()

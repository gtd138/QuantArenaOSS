import requests
import sqlite3

# 1. 检查API当前session
resp = requests.get('http://localhost:8000/api/arena/current_session')
current_session = resp.json()
print(f"当前Session: {current_session}")

# 2. 检查数据库中的session列表
conn = sqlite3.connect('data/arena_sessions.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT session_id, start_date, current_date, status, created_at
    FROM arena_sessions
    ORDER BY created_at DESC
    LIMIT 5
''')

print("\n最近的5个session:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} -> {row[2]} ({row[3]}) - {row[4]}")

# 3. 检查是否有未完成的session
cursor.execute('''
    SELECT session_id, start_date, current_date
    FROM arena_sessions
    WHERE status = 'running'
    ORDER BY created_at DESC
    LIMIT 1
''')

row = cursor.fetchone()
if row:
    print(f"\n未完成的session: {row[0]}")
    print(f"  开始日期: {row[1]}")
    print(f"  当前日期: {row[2]}")
else:
    print("\n❌ 没有未完成的session")

conn.close()

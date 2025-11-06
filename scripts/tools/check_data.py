import sqlite3

conn = sqlite3.connect('data/arena_sessions.db')
cursor = conn.cursor()

# 先查看表结构
print("arena_daily_assets 表结构:")
cursor.execute("PRAGMA table_info(arena_daily_assets)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

print("\n" + "="*50)

# 检查每个AI的天数
cursor.execute('SELECT model_name, COUNT(*) FROM arena_daily_assets WHERE session_id="20251028_144733" GROUP BY model_name')
print("\n各AI的数据天数:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}天")

# 获取正确的日期字段名（可能是trade_date）
print("\n检查日期连续性:")
cursor.execute('SELECT DISTINCT trade_date FROM arena_daily_assets WHERE session_id="20251028_144733" ORDER BY trade_date')
dates = [r[0] for r in cursor.fetchall()]
print(f"总共{len(dates)}个交易日")
if dates:
    print(f"首日: {dates[0]}")
    print(f"末日: {dates[-1]}")

    # 检查是否有日期缺失
    print("\n检查每个AI在每天是否都有数据:")
    cursor.execute('SELECT trade_date, GROUP_CONCAT(model_name) as models FROM arena_daily_assets WHERE session_id="20251028_144733" GROUP BY trade_date ORDER BY trade_date')
    rows = cursor.fetchall()
    incomplete_days = []
    for i, (date, models) in enumerate(rows):
        model_count = len(models.split(','))
        if model_count != 5:
            print(f"  ⚠️  {date}: 只有{model_count}个AI ({models})")
            incomplete_days.append(date)
        elif i < 3 or i >= len(rows) - 3:
            print(f"  ✅ {date}: {model_count}个AI")
    
    if incomplete_days:
        print(f"\n⚠️  发现{len(incomplete_days)}天数据不完整")
    else:
        print("\n✅ 所有日期数据完整")

# 检查是否有重复的日期数据
print("\n检查重复数据:")
cursor.execute('''
    SELECT trade_date, model_name, COUNT(*) as cnt 
    FROM arena_daily_assets 
    WHERE session_id="20251028_144733" 
    GROUP BY trade_date, model_name 
    HAVING cnt > 1
''')
duplicates = cursor.fetchall()
if duplicates:
    print("发现重复数据:")
    for row in duplicates:
        print(f"  {row[0]} - {row[1]}: {row[2]}条")
else:
    print("  无重复数据")

conn.close()

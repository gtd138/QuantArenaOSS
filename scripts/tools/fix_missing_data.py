"""
修复缺失的daily_assets数据
对于执行失败的日期，使用前一天的数据填补
"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/arena_sessions.db')
cursor = conn.cursor()

session_id = '20251028_144733'

# 获取所有日期和每天的AI数据
cursor.execute('''
    SELECT trade_date, GROUP_CONCAT(model_name) as models, GROUP_CONCAT(assets) as assets_list
    FROM arena_daily_assets 
    WHERE session_id=? 
    GROUP BY trade_date 
    ORDER BY trade_date
''', (session_id,))

all_dates_data = cursor.fetchall()
all_models = ['DeepSeek-V3.2', 'Qwen3-Max', 'glm-4.6', 'Kimi-K2', 'Doubao-1.6']

# 记录每个AI的最后已知资产
last_known_assets = {}

print("开始修复缺失数据...\n")
fixed_count = 0

for trade_date, models_str, assets_str in all_dates_data:
    if not models_str:
        continue
        
    existing_models = models_str.split(',')
    existing_assets = [float(a) for a in assets_str.split(',')]
    
    # 更新last_known_assets
    for model, asset in zip(existing_models, existing_assets):
        last_known_assets[model] = asset
    
    # 检查缺失的AI
    missing_models = [m for m in all_models if m not in existing_models]
    
    if missing_models:
        print(f"📅 {trade_date}: 缺少 {', '.join(missing_models)}")
        
        for model in missing_models:
            if model in last_known_assets:
                # 使用前一天的资产值填补
                asset_value = last_known_assets[model]
                
                # 插入数据
                cursor.execute('''
                    INSERT INTO arena_daily_assets (session_id, model_name, trade_date, assets, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, model, trade_date, asset_value, datetime.now().isoformat()))
                
                print(f"  ✅ {model}: 填补数据 ¥{asset_value:.2f} (使用前一天数据)")
                fixed_count += 1
            else:
                print(f"  ⚠️  {model}: 无前一天数据，无法填补")

conn.commit()
print(f"\n{'='*50}")
print(f"✅ 修复完成！共填补 {fixed_count} 条数据")

# 验证修复结果
print("\n验证修复结果:")
cursor.execute('''
    SELECT trade_date, COUNT(DISTINCT model_name) as model_count
    FROM arena_daily_assets 
    WHERE session_id=? 
    GROUP BY trade_date 
    HAVING model_count < 5
    ORDER BY trade_date
''', (session_id,))

incomplete = cursor.fetchall()
if incomplete:
    print("⚠️  仍有不完整的日期:")
    for date, count in incomplete:
        print(f"  {date}: {count}/5 个AI")
else:
    print("✅ 所有日期数据完整！")

conn.close()
print("\n🎉 数据修复完成，请刷新前端查看效果！")

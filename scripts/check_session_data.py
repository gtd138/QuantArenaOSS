"""
检查会话数据的脚本
用于验证数据是否正确保存到数据库
"""

import sys
import os
import sqlite3
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persistence.arena_persistence import get_arena_persistence


def check_session_data():
    """检查最新会话的数据完整性"""
    persistence = get_arena_persistence()
    
    # 1. 获取所有会话
    sessions = persistence.list_sessions(limit=5)
    
    if not sessions:
        print("❌ 数据库中没有会话记录")
        return
    
    print(f"\n📊 找到 {len(sessions)} 个会话\n")
    print("=" * 80)
    
    for i, session in enumerate(sessions, 1):
        print(f"\n{i}. 会话ID: {session['session_id']}")
        print(f"   状态: {session['status']}")
        print(f"   日期范围: {session['start_date']} → {session['end_date']}")
        print(f"   当前日期: {session['current_date']}")
        print(f"   创建时间: {session['created_at']}")
        
        # 获取该会话的详细数据
        session_id = session['session_id']
        
        # 连接数据库查询统计
        db_path = persistence.db_path
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 模型数量
            cursor.execute('''
                SELECT COUNT(DISTINCT model_name) FROM arena_model_state
                WHERE session_id = ?
            ''', (session_id,))
            model_count = cursor.fetchone()[0]
            
            # AI日志数量
            cursor.execute('''
                SELECT COUNT(*) FROM arena_ai_logs
                WHERE session_id = ?
            ''', (session_id,))
            log_count = cursor.fetchone()[0]
            
            # 交易记录数量
            cursor.execute('''
                SELECT COUNT(*) FROM arena_trades
                WHERE session_id = ?
            ''', (session_id,))
            trade_count = cursor.fetchone()[0]
            
            # 每日资产数量
            cursor.execute('''
                SELECT COUNT(*) FROM arena_daily_assets
                WHERE session_id = ?
            ''', (session_id,))
            daily_count = cursor.fetchone()[0]
            
            # 持仓数量
            cursor.execute('''
                SELECT COUNT(*) FROM arena_holdings
                WHERE session_id = ?
            ''', (session_id,))
            holding_count = cursor.fetchone()[0]
            
            # 各模型的交易数量
            cursor.execute('''
                SELECT model_name, COUNT(*) as cnt FROM arena_trades
                WHERE session_id = ?
                GROUP BY model_name
                ORDER BY cnt DESC
            ''', (session_id,))
            model_trades = cursor.fetchall()
            
            print(f"\n   📈 数据统计:")
            print(f"      - 模型数量: {model_count}")
            print(f"      - AI日志: {log_count} 条")
            print(f"      - 交易记录: {trade_count} 笔")
            print(f"      - 每日资产: {daily_count} 条")
            print(f"      - 持仓记录: {holding_count} 条")
            
            if model_trades:
                print(f"\n   🤖 各模型交易数量:")
                for model_name, cnt in model_trades:
                    print(f"      - {model_name}: {cnt} 笔")
        
        print("\n" + "-" * 80)


def check_latest_session():
    """详细检查最新会话"""
    persistence = get_arena_persistence()
    
    # 获取最新会话
    sessions = persistence.list_sessions(limit=1)
    if not sessions:
        print("❌ 没有会话")
        return
    
    session_id = sessions[0]['session_id']
    print(f"\n🔍 详细检查会话: {session_id}\n")
    
    # 加载完整数据
    try:
        data = persistence.load_session_data(session_id)
        
        print("✅ 数据加载成功\n")
        
        # 会话信息
        session = data['session']
        print(f"📋 会话信息:")
        print(f"   - ID: {session['session_id']}")
        print(f"   - 状态: {session['status']}")
        print(f"   - 日期: {session['start_date']} → {session['end_date']}")
        print(f"   - 当前: {session['current_date']}")
        
        # 模型状态
        print(f"\n💰 模型状态:")
        for model_name, state in data['model_states'].items():
            print(f"   - {model_name}:")
            print(f"     现金: ¥{state['cash']:.2f}")
            print(f"     总资产: ¥{state['total_assets']:.2f}")
            print(f"     收益率: {state['profit_pct']:.2f}%")
        
        # 图表数据
        print(f"\n📈 每日资产:")
        for model_name, daily_list in data['daily_assets'].items():
            print(f"   - {model_name}: {len(daily_list)} 天")
            if daily_list:
                first = daily_list[0]
                last = daily_list[-1]
                print(f"     起始: {first['date']} ¥{first['assets']:.2f}")
                print(f"     最新: {last['date']} ¥{last['assets']:.2f}")
        
        # 交易记录
        print(f"\n📝 交易记录: {len(data['trades'])} 笔")
        trade_by_model = {}
        for trade in data['trades']:
            model = trade['model_name']
            trade_by_model[model] = trade_by_model.get(model, 0) + 1
        
        for model_name, count in trade_by_model.items():
            print(f"   - {model_name}: {count} 笔")
        
        # 持仓
        print(f"\n💼 持仓:")
        for model_name, holdings in data['holdings'].items():
            print(f"   - {model_name}: {len(holdings)} 只股票")
            for h in holdings[:3]:  # 只显示前3个
                print(f"     {h['stock_code']} {h['amount']}股")
        
        # AI日志
        print(f"\n🤖 AI日志: {len(data['ai_logs'])} 条")
        log_by_model = {}
        for log in data['ai_logs']:
            model = log['model_name']
            log_by_model[model] = log_by_model.get(model, 0) + 1
        
        for model_name, count in log_by_model.items():
            print(f"   - {model_name}: {count} 条")
        
        # 显示最新5条日志
        print(f"\n   最新5条日志:")
        for log in data['ai_logs'][-5:]:
            timestamp = log['timestamp'][:19]  # 只显示到秒
            model = log['model_name']
            message = log['message'][:50]  # 只显示前50字
            print(f"   [{timestamp}] {model}: {message}...")
        
        print("\n" + "=" * 80)
        print("✅ 数据检查完成")
        
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Arena 数据库检查工具")
    print("=" * 80)
    
    # 检查所有会话
    check_session_data()
    
    # 详细检查最新会话
    print("\n")
    check_latest_session()

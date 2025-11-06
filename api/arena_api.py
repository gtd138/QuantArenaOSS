"""
AI Arena FastAPI后端
提供RESTful API接口，支持前后端分离
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import base64
import os
import shutil
import datetime as dt
from pathlib import Path

# 导入memory_store
import sys
import yaml
import json
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from persistence.memory_store import MemoryStore

# 全局变量：竞技场实例引用
_arena_instance = None
_config = None
_arena_thread = None
_should_stop = False  # 优雅停止标志

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（替代已弃用的 on_event）"""
    # 启动逻辑
    global _config, _arena_instance, _arena_thread
    
    # ✅ 添加日志文件输出
    import sys
    import os
    os.makedirs('logs', exist_ok=True)  # 确保logs目录存在
    log_file = open('logs/startup.log', 'w', encoding='utf-8')
    
    def log(msg):
        """同时输出到控制台和日志文件"""
        print(msg)
        log_file.write(msg + '\n')
        log_file.flush()
    
    log("=" * 60)
    log("🚀 启动事件开始")
    log("=" * 60)
    
    # 加载配置（优先yaml，fallback到json）
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    yaml_path = os.path.join(base_dir, 'config.yaml')
    json_path = os.path.join(base_dir, 'config.json')
    
    try:
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r', encoding='utf-8') as f:
                _config = yaml.safe_load(f)
            log("✅ 配置加载成功 (config.yaml)")
        elif os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                _config = json.load(f)
            log("✅ 配置加载成功 (config.json)")
        else:
            log("❌ 配置文件不存在")
            return
    except Exception as e:
        log(f"❌ 配置加载失败: {e}")
        import traceback
        log(traceback.format_exc())
        return
    
    # ✅ 检查是否有未完成的会话
    log("\n" + "=" * 60)
    log("🔍 检查数据库中的会话...")
    log("=" * 60)
    
    from persistence.arena_persistence import get_arena_persistence
    try:
        persistence = get_arena_persistence()
        unfinished_session = persistence.get_latest_unfinished_session()
        
        if unfinished_session:
            log(f"\n⚠️  发现未完成的会话!")
            log(f"   会话ID: {unfinished_session['session_id']}")
            log(f"   开始日期: {unfinished_session['start_date']}")
            log(f"   当前日期: {unfinished_session['current_date']}")
            log(f"   结束日期: {unfinished_session['end_date']}")
            log(f"   创建时间: {unfinished_session['created_at']}")
            log(f"\n✅ 将自动继续运行（断点续跑）")
        else:
            log("✅ 没有未完成的会话")
            log("✅ 将创建新会话并开始运行")
        
        # 显示所有会话统计
        sessions = persistence.list_sessions(limit=10)
        if sessions:
            log(f"\n📊 数据库中共有 {len(sessions)} 个会话（最近10个）:")
            for i, sess in enumerate(sessions[:5], 1):
                status_icon = "✅" if sess['status'] == 'completed' else "⏸️"
                log(f"   {status_icon} {i}. {sess['session_id']} - {sess['status']}")
        else:
            log("\n📊 数据库中暂无会话记录")
    
    except Exception as e:
        log(f"⚠️  检查会话时出错: {e}")
        import traceback
        log(traceback.format_exc())
    
    log("=" * 60 + "\n")
    
    # 启动前自动备份数据库
    db_path = os.path.join(base_dir, 'data', 'trading.db')
    # 切换到Baostock在线行情后，停止自动备份trading.db（避免冗余备份）
    # if os.path.exists(db_path):
    #     log("💾 备份数据库...")
    #     backup_database(db_path, max_backups=10)
    #     log("✅ 数据库备份完成")
    
    # 自动启动竞技场（异步线程）
    def run_arena():
        import sys
        
        # ✅ 创建后台线程的日志文件
        import os
        os.makedirs('logs', exist_ok=True)  # 确保logs目录存在
        arena_log = open('logs/arena_background.log', 'w', encoding='utf-8')
        
        # ✅ 创建自动刷新的文件包装器（确保所有输出立即写入）
        class FlushingFile:
            def __init__(self, file):
                self.file = file
            
            def write(self, text):
                self.file.write(text)
                self.file.flush()  # 每次写入后立即刷新
            
            def flush(self):
                self.file.flush()
            
            def __getattr__(self, name):
                return getattr(self.file, name)
        
        # ✅ 重定向标准输出到日志文件（捕获所有print输出）
        original_stdout = sys.stdout
        sys.stdout = FlushingFile(arena_log)
        
        def arena_log_msg(msg):
            print(msg, flush=True)  # 使用flush=True确保立即写入
            arena_log.flush()  # 额外刷新一次确保写入
        
        try:
            arena_log_msg("=" * 60)
            arena_log_msg("🚀 后台竞技场线程启动")
            arena_log_msg("=" * 60)
            from agent_v2.arena_manager import ArenaManager
            
            # ✅ 第一步：创建ArenaManager（只创建数据提供者，不创建Agent - 延迟初始化）
            arena_log_msg("\n📊 正在创建竞技场管理器...")
            arena = ArenaManager(_config)
            global _arena_instance
            _arena_instance = arena
            arena_log_msg("✅ 竞技场管理器创建完成（Agent延迟初始化）")
            
            # ✅ 第二步：先检查是否有未完成的会话并决定是续跑还是新建
            from persistence.arena_persistence import get_arena_persistence
            persistence = get_arena_persistence()
            unfinished_session = persistence.get_latest_unfinished_session()
            
            # 获取交易日期范围（可能会被会话覆盖）
            trading_config = (_config or {}).get('trading', {})
            raw_start_date = trading_config.get('start_date', '20250101')
            raw_end_date = trading_config.get('end_date', '20251231')

            def _parse_trade_date(raw: str) -> dt.datetime:
                raw = (raw or '').strip()
                for fmt in ('%Y%m%d', '%Y-%m-%d'):
                    if not raw:
                        continue
                    try:
                        return dt.datetime.strptime(raw, fmt)
                    except ValueError:
                        continue
                raise ValueError(f"Unsupported trade date format: {raw}")

            start_date = _parse_trade_date(raw_start_date).strftime('%Y%m%d')
            end_date = _parse_trade_date(raw_end_date).strftime('%Y%m%d')
            initial_capital = trading_config.get('initial_capital', 10000)
            
            session_id = None
            resume_from_date = None
            
            if unfinished_session:
                arena_log_msg(f"\n🔄 发现未完成会话，准备断点续跑...")
                arena_log_msg(f"   会话ID: {unfinished_session['session_id']}")
                arena_log_msg(f"   已完成: {unfinished_session['start_date']} → {unfinished_session['current_date']}")
                arena_log_msg(f"   待运行: {unfinished_session['current_date']} → {unfinished_session['end_date']}")
                
                # 使用现有会话ID
                session_id = unfinished_session['session_id']
                
                # ✅ 加载历史会话数据到内存
                arena_log_msg(f"📂 加载历史会话数据...")
                try:
                    MemoryStore.load_session(session_id)
                    arena_log_msg(f"✅ 历史数据已加载")
                    
                    # ✅ 验证加载的数据
                    chart_data = MemoryStore.get_chart_data()
                    trades = MemoryStore.get_trades()
                    holdings = MemoryStore.get_holdings()
                    arena_log_msg(f"   - 图表数据: {sum(len(v) for v in chart_data.values())} 条")
                    arena_log_msg(f"   - 交易记录: {len(trades)} 笔")
                    arena_log_msg(f"   - 持仓记录: {sum(len(v) for v in holdings.values())} 条")
                except Exception as e:
                    arena_log_msg(f"⚠️  加载历史数据失败: {e}")
                    import traceback
                    arena_log_msg(traceback.format_exc())
                    arena_log_msg(f"⚠️  将以空状态继续运行")
                    MemoryStore._session_id = session_id
                
                # ✅ 从数据库实际的最新日期继续（而不是依赖可能错误的current_date）
                # 查询数据库中的实际最新日期
                actual_latest_date = persistence.get_latest_trade_date(session_id)
                
                if actual_latest_date:
                    # 从最新日期的下一天继续
                    current_date = _parse_trade_date(actual_latest_date)
                    next_date = current_date + dt.timedelta(days=1)
                    resume_from_date = next_date.strftime('%Y%m%d')
                    arena_log_msg(f"📊 数据库最新日期: {actual_latest_date}")
                    arena_log_msg(f"   会话记录的current_date: {unfinished_session['current_date']} (可能过时)")
                else:
                    # 没有数据，从会话记录的日期继续
                    current_date = _parse_trade_date(unfinished_session['current_date'])
                    next_date = current_date + dt.timedelta(days=1)
                    resume_from_date = next_date.strftime('%Y%m%d')
                    arena_log_msg(f"⚠️  数据库无数据，从会话记录继续")
                
                # 使用原会话的配置
                start_date = resume_from_date
                end_date = unfinished_session['end_date']
                
                arena_log_msg(f"✅ 将从 {resume_from_date} 继续运行到 {end_date}")
                
                # ✅ 此时数据已加载到MemoryStore，前端可以立即显示
                arena_log_msg(f"✅ 历史数据已就绪，前端可立即查看")
            else:
                arena_log_msg(f"\n🆕 创建新会话...")
                # 创建新会话（持久化）
                session_id = MemoryStore.start_new_session(
                    start_date, end_date, initial_capital, _config or {}
                )
                arena_log_msg(f"📝 新会话ID: {session_id}")
            
            # ✅ 第三步：预加载指数数据（在确定日期范围后，恢复现场时可以只加载剩余日期）
            arena_log_msg("\n📊 预加载指数数据到内存...")
            try:
                arena.data_provider.preload_index_data(start_date, end_date)
                arena_log_msg("✅ 指数数据预加载完成")
            except Exception as e:
                arena_log_msg(f"⚠️  指数数据预加载失败: {e}")
                arena_log_msg(f"   将在运行时动态获取")
            
            # ✅ 第四步：触发初始化Agent（延迟初始化）
            arena_log_msg("\n🚀 开始初始化Agent（触发式延迟初始化）...")
            arena.initialize_agents()
            arena_log_msg("✅ Agent初始化完成")
            
            # ✅ 跟踪每个模型已保存的数据（避免重复保存）
            saved_trade_counts = {}  # {model_name: count}
            saved_daily_counts = {}  # {model_name: count}
            
            # ✅ 第五步：如果是断点续跑，恢复Agent状态
            if unfinished_session:
                # 从MemoryStore获取已有的数据量
                all_trades = MemoryStore.get_trades()
                all_chart_data = MemoryStore.get_chart_data()
                
                # 统计每个模型的已有数据量
                for trade in all_trades:
                    model = trade.get('model_name')
                    if model:
                        saved_trade_counts[model] = saved_trade_counts.get(model, 0) + 1
                
                for model_name, daily_list in all_chart_data.items():
                    saved_daily_counts[model_name] = len(daily_list)
                
                arena_log_msg(f"\n📊 已加载历史数据统计:")
                for model_name in saved_trade_counts:
                    trades = saved_trade_counts.get(model_name, 0)
                    days = saved_daily_counts.get(model_name, 0)
                    arena_log_msg(f"   - {model_name}: {trades}笔交易, {days}天资产数据")
                
                # ✅ 恢复Agent的历史数据（从MemoryStore，不查数据库）
                arena_log_msg(f"\n🔄 恢复Agent历史数据...")
                initial_capital = arena.config.get('trading', {}).get('initial_capital', 10000)
                
                for agent_info in arena.agents:
                    model_name = agent_info['name']
                    agent = agent_info['agent']
                    
                    # 恢复daily_assets（重要！很多逻辑依赖这个）
                    chart_data = MemoryStore.get_chart_data().get(model_name, [])
                    if chart_data:
                        agent.daily_assets = [{'date': d['date'], 'total_assets': d['assets']} for d in chart_data]
                        
                        # ✅ 从最后一天的资产数据推算cash和total_assets
                        last_day_assets = chart_data[-1]['assets']
                        agent.total_assets = last_day_assets
                        
                        # 从holdings推算持仓市值，并恢复holdings字典
                        model_holdings = MemoryStore.get_holdings().get(model_name, [])
                        holdings_value = 0
                        agent.holdings = {}  # ✅ 重新构建holdings字典
                        
                        if model_holdings:
                            for h in model_holdings:
                                code = h.get('code') or h.get('stock_code')
                                amount = h.get('amount', 0)
                                cost = h.get('cost') or h.get('avg_price', 0)
                                price = h.get('current_price', cost)
                                
                                if code:
                                    # ✅ 恢复holdings字典（Agent需要的格式）
                                    agent.holdings[code] = {
                                        'amount': amount,
                                        'cost': cost,
                                        'current_price': price,
                                        'hold_days': h.get('hold_days', 0),
                                        'date': h.get('date', ''),
                                    }
                                    holdings_value += amount * price
                        
                        # 计算现金 = 总资产 - 持仓市值
                        agent.cash = agent.total_assets - holdings_value
                        arena_log_msg(f"   💰 {model_name}: 现金={agent.cash:.2f}, 持仓={holdings_value:.2f}, 总资产={agent.total_assets:.2f}")
                    
                    # 恢复trade_history
                    model_trades = [t for t in MemoryStore.get_trades() if t.get('model_name') == model_name]
                    if model_trades:
                        agent.trade_history = model_trades
                        arena_log_msg(f"   📝 {model_name}: 恢复 {len(model_trades)} 笔交易")
                    
                    # ⭐ 恢复现场后立即检测数据完整性和连续性
                    if agent.daily_assets or agent.trade_history:
                        arena_log_msg(f"   🔍 [{model_name}] 检测数据完整性与连续性...")
                        
                        # ⭐ 首先检测日期连续性：找到最初连续数据的末端
                        last_continuous_date, first_gap_date = agent.find_first_continuous_data_end()
                        
                        if first_gap_date:
                            # 发现日期断点（跳过了交易日），自动回滚到连续数据末端
                            arena_log_msg(f"   ⚠️ [{model_name}] 检测到日期断点，将从 {first_gap_date} 之前的所有数据回滚")
                            arena_log_msg(f"   🔄 [{model_name}] 自动回滚到最后一个连续日期 {last_continuous_date} 之后...")
                            
                            if last_continuous_date and agent.rollback_to_date(first_gap_date):
                                arena_log_msg(f"   ✅ [{model_name}] 回滚成功，将从 {last_continuous_date} 之后重新开始")
                                arena_log_msg(f"   📊 [{model_name}] 回滚后剩余 {len(agent.daily_assets)} 天历史")
                                arena_log_msg(f"   📝 [{model_name}] 回滚后剩余 {len(agent.trade_history)} 笔交易")
                                arena_log_msg(f"   💰 [{model_name}] 回滚后资产: ¥{agent.total_assets:.2f} (现金: ¥{agent.cash:.2f})")
                                
                                # ✅ 回滚后更新MemoryStore，确保数据同步
                                if agent.daily_assets:
                                    # 更新图表数据（直接修改类变量）
                                    chart_data_after_rollback = [
                                        {'date': d['date'], 'assets': d.get('total_assets') or d.get('assets', 0)}
                                        for d in agent.daily_assets
                                    ]
                                    MemoryStore._chart_data[model_name] = chart_data_after_rollback
                                    
                                    # 更新模型状态
                                    MemoryStore._model_assets[model_name] = {
                                        'cash': agent.cash,
                                        'total_assets': agent.total_assets,
                                        'holdings': agent.holdings
                                    }
                                    
                                    # 更新交易记录
                                    MemoryStore._trades = [
                                        t for t in MemoryStore.get_trades()
                                        if t.get('model_name') != model_name
                                    ] + agent.trade_history
                            else:
                                arena_log_msg(f"   ❌ [{model_name}] 回滚失败，将从头开始")
                                # 回滚失败，重置到初始状态
                                agent.cash = initial_capital
                                agent.holdings = {}
                                agent.total_assets = initial_capital
                                agent.trade_history = []
                                agent.daily_assets = []
                        
                        # ⭐ 然后检测数据损坏（其他类型的问题）
                        is_corrupted, corrupted_date = agent.detect_data_corruption()
                        
                        if is_corrupted:
                            arena_log_msg(f"   ⚠️ [{model_name}] 检测到数据损坏！损坏日期: {corrupted_date}")
                            
                            if corrupted_date:
                                # 找到损坏日期之前的最后一个有效日期
                                from datetime import datetime
                                try:
                                    # 统一日期格式
                                    if corrupted_date and '-' not in corrupted_date and len(corrupted_date) == 8:
                                        corrupted_date = f"{corrupted_date[:4]}-{corrupted_date[4:6]}-{corrupted_date[6:8]}"
                                    
                                    corrupted_dt = datetime.strptime(corrupted_date, '%Y-%m-%d')
                                    
                                    # 找到最后一个有效日期（在损坏日期之前）
                                    last_valid_date = None
                                    for entry in reversed(agent.daily_assets):
                                        entry_date = entry.get('date')
                                        if entry_date:
                                            try:
                                                # 统一日期格式
                                                if '-' not in entry_date and len(entry_date) == 8:
                                                    entry_date = f"{entry_date[:4]}-{entry_date[4:6]}-{entry_date[6:8]}"
                                                entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
                                                if entry_dt < corrupted_dt:
                                                    last_valid_date = entry_date
                                                    break
                                            except:
                                                continue
                                    
                                    if last_valid_date:
                                        arena_log_msg(f"   🔄 [{model_name}] 自动回滚到最后一个有效日期 {last_valid_date} 之后...")
                                        
                                        # 回滚到损坏日期之前（删除损坏日期及之后的所有数据）
                                        if agent.rollback_to_date(corrupted_date):
                                            arena_log_msg(f"   ✅ [{model_name}] 回滚成功，将从 {last_valid_date} 之后重新开始")
                                            arena_log_msg(f"   📊 [{model_name}] 回滚后剩余 {len(agent.daily_assets)} 天历史")
                                            arena_log_msg(f"   📝 [{model_name}] 回滚后剩余 {len(agent.trade_history)} 笔交易")
                                            arena_log_msg(f"   💰 [{model_name}] 回滚后资产: ¥{agent.total_assets:.2f} (现金: ¥{agent.cash:.2f})")
                                            
                                            # ✅ 回滚后更新MemoryStore，确保数据同步
                                            if agent.daily_assets:
                                                # 更新图表数据（直接修改类变量）
                                                chart_data_after_rollback = [
                                                    {'date': d['date'], 'assets': d.get('total_assets') or d.get('assets', 0)}
                                                    for d in agent.daily_assets
                                                ]
                                                # 直接访问MemoryStore的内部变量（更新回滚后的数据）
                                                MemoryStore._chart_data[model_name] = chart_data_after_rollback
                                                
                                                # 更新模型资产状态
                                                if model_name in MemoryStore._model_assets:
                                                    MemoryStore._model_assets[model_name]['total_assets'] = agent.total_assets
                                                    MemoryStore._model_assets[model_name]['cash'] = agent.cash
                                            
                                            # 更新交易记录（只保留回滚后的）
                                            filtered_trades = [
                                                t for t in MemoryStore._trades 
                                                if t.get('model_name') != model_name or t in agent.trade_history
                                            ]
                                            MemoryStore._trades = filtered_trades
                                            
                                            # 更新持仓数据（从agent.holdings字典转换为列表格式）
                                            holdings_list = []
                                            for code, holding_info in agent.holdings.items():
                                                holdings_list.append({
                                                    'code': code,
                                                    'stock_code': code,
                                                    'amount': holding_info.get('amount', 0),
                                                    'volume': holding_info.get('amount', 0),  # 兼容字段名
                                                    'cost': holding_info.get('cost', 0),
                                                    'cost_price': holding_info.get('cost', 0),  # 兼容字段名
                                                    'avg_price': holding_info.get('cost', 0),  # 兼容字段名
                                                    'current_price': holding_info.get('current_price', holding_info.get('cost', 0)),
                                                    'hold_days': holding_info.get('hold_days', 0),
                                                    'date': holding_info.get('date', '')
                                                })
                                            MemoryStore.update_holdings(model_name, holdings_list)
                                        else:
                                            arena_log_msg(f"   ❌ [{model_name}] 回滚失败，将从头开始")
                                            # 回滚失败，重置到初始状态
                                            agent.cash = initial_capital
                                            agent.holdings = {}
                                            agent.total_assets = initial_capital
                                            agent.trade_history = []
                                            agent.daily_assets = []
                                    else:
                                        arena_log_msg(f"   ❌ [{model_name}] 无法找到有效日期，将从头开始")
                                        # 找不到有效日期，重置到初始状态
                                        agent.cash = initial_capital
                                        agent.holdings = {}
                                        agent.total_assets = initial_capital
                                        agent.trade_history = []
                                        agent.daily_assets = []
                                except Exception as e:
                                    arena_log_msg(f"   ❌ [{model_name}] 回滚过程出错: {e}，将从头开始")
                                    import traceback
                                    traceback.print_exc()
                                    # 出错，重置到初始状态
                                    agent.cash = initial_capital
                                    agent.holdings = {}
                                    agent.total_assets = initial_capital
                                    agent.trade_history = []
                                    agent.daily_assets = []
                            else:
                                arena_log_msg(f"   ❌ [{model_name}] 无法确定损坏日期，将从头开始")
                                # 无法确定损坏日期，重置到初始状态
                                agent.cash = initial_capital
                                agent.holdings = {}
                                agent.total_assets = initial_capital
                                agent.trade_history = []
                                agent.daily_assets = []
                        else:
                            arena_log_msg(f"   ✅ [{model_name}] 数据完整性检测通过")
                
                arena_log_msg(f"✅ Agent状态完整恢复完成\n")
            
            # 定义回调函数，实时更新MemoryStore
            def progress_callback(agent_name, current, total, message):
                """进度回调"""
                MemoryStore.update_progress(current, total, message)
            
            def _dedupe_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                """按交易唯一键去重（保持原顺序）。"""
                seen = set()
                deduped = []
                for trade in trades:
                    if not isinstance(trade, dict):
                        continue
                    key = (
                        trade.get('date'),
                        trade.get('time'),
                        trade.get('code'),
                        trade.get('action'),
                        trade.get('price'),
                        trade.get('amount'),
                        trade.get('total'),
                    )
                    if key in seen:
                        current_time = dt.datetime.now().strftime('%H:%M:%S')
                        print(f"⚠️  [{current_time}] 去重重复交易: {trade}")
                        continue
                    seen.add(key)
                    deduped.append(trade)
                return deduped

            def update_callback(agent_name, update_data):
                """更新回调（增强版，实时保存）"""
                # 🔍 调试：打印回调信息
                print(f"🔔 [{agent_name}] update_callback 被调用，数据键: {list(update_data.keys())}", flush=True)
                
                # ✅ 先对交易记录去重，避免前端重复展示
                if 'trade_history' in update_data and isinstance(update_data['trade_history'], list):
                    original_len = len(update_data['trade_history'])
                    update_data['trade_history'] = _dedupe_trades(update_data['trade_history'])
                    if len(update_data['trade_history']) != original_len:
                        print(f"🧹 [{agent_name}] 去除 {original_len - len(update_data['trade_history'])} 条重复交易记录", flush=True)
                
                # ✅ 立即保存交易记录（不依赖其他条件）
                if 'trade_history' in update_data:
                    trade_history = update_data.get('trade_history', [])
                    saved_count = saved_trade_counts.get(agent_name, 0)
                    new_trades = trade_history[saved_count:]  # 只取新增的交易
                    
                    # 🔍 调试：打印交易保存信息
                    print(f"🔍 [{agent_name}] 交易保存检查: trade_history长度={len(trade_history)}, saved_count={saved_count}, new_trades={len(new_trades)}", flush=True)
                    
                    for trade in new_trades:
                        if not isinstance(trade, dict):
                            print(f"⚠️  [{agent_name}] trade 不是字典: {type(trade)}")
                            continue
                        
                        # ✅ 验证必需字段
                        if not trade.get('date') or not trade.get('code') or not trade.get('action'):
                            print(f"⚠️  [{agent_name}] trade 缺少必需字段: {trade}")
                            continue
                        
                        try:
                            # ✅ 字段映射：code -> stock_code, amount -> volume, total -> amount
                            trade_data = {
                                'model_name': agent_name,
                                'date': trade.get('date'),
                                'stock_code': trade.get('code'),  # code -> stock_code
                                'name': trade.get('name', ''),
                                'action': trade.get('action'),
                                'price': trade.get('price', 0),
                                'volume': trade.get('amount', 0),  # amount(数量) -> volume
                                'amount': trade.get('total', trade.get('value', 0)),  # total(总金额) -> amount
                                'commission': trade.get('commission', 0),
                                'profit': trade.get('profit'),
                                'profit_pct': trade.get('profit_pct'),
                                'time': trade.get('time', ''),
                                'reason': trade.get('reason', ''),
                            }
                            # ✅ 同时保存到数据库和内存
                            persistence.save_trade(session_id, trade_data)
                            MemoryStore.add_trade(trade_data)  # 添加到内存，前端才能看到
                            saved_trade_counts[agent_name] = saved_trade_counts.get(agent_name, 0) + 1
                            print(f"💾 [{agent_name}] 已保存交易: {trade_data['date']} {trade_data['action']} {trade_data['stock_code']} (总计已保存{saved_trade_counts[agent_name]}笔)", flush=True)
                        except Exception as e:
                            print(f"⚠️  [{agent_name}] 保存交易失败: {e} - {trade}")
                            continue

                # ✅ 只要有daily_assets或total_assets，就更新arena_data（不再要求holdings）
                if 'daily_assets' in update_data or 'total_assets' in update_data:
                    # 获取现有的arena_data（如果有）
                    existing_data = MemoryStore.get_arena_data(agent_name) or {}
                    # 合并新数据
                    merged_data = {**existing_data, **update_data}
                    # 保存完整的agent数据
                    MemoryStore.save_arena_data(agent_name, merged_data)
                    print(f"💾 [{agent_name}] 数据已保存到MemoryStore，total_assets={merged_data.get('total_assets', 'N/A')}, daily_assets长度={len(merged_data.get('daily_assets', []))}", flush=True)
                    
                    # 同时更新model_assets供排名使用
                    total_assets = update_data.get('total_assets', existing_data.get('total_assets', 10000))
                    initial_capital = _config.get('trading', {}).get('initial_capital', 10000)
                    profit_pct = ((total_assets - initial_capital) / initial_capital) * 100
                    
                    # 获取模型颜色
                    model_color = update_data.get('model_color') or existing_data.get('model_color')
                    if not model_color:
                        arena_config = _config.get('arena', {})
                        for m in arena_config.get('models', []):
                            if m['name'] == agent_name:
                                model_color = m.get('color', '#1976D2')
                                break
                    
                    MemoryStore.save_model_asset(
                        model_name=agent_name,
                        total_assets=total_assets,
                        profit_pct=profit_pct,
                        color=model_color
                    )
                    
                    # ✅ 实时保存每日资产数据
                    if 'daily_assets' in update_data:
                        daily_list = update_data.get('daily_assets', [])
                        saved_count = saved_daily_counts.get(agent_name, 0)
                        new_daily = daily_list[saved_count:]  # 只取新增的
                        
                        for day_data in new_daily:
                            try:
                                trade_date = day_data.get('date')
                                total_assets = day_data.get('total_assets') or day_data.get('assets', 0)
                                if trade_date:
                                    # 保存到数据库
                                    persistence.save_daily_assets(session_id, agent_name, trade_date, total_assets)
                                    persistence.update_session_progress(session_id, trade_date)
                                    # ✅ 同时保存到MemoryStore（供前端实时获取）
                                    MemoryStore.add_chart_data(agent_name, trade_date, total_assets)
                            except Exception as e:
                                print(f"⚠️  [{agent_name}] 保存每日资产失败: {e} - {day_data}")
                                continue
                        
                        # 更新已保存计数
                        saved_daily_counts[agent_name] = len(daily_list)
                    
                    # ✅ 实时保存持仓数据到MemoryStore
                    if 'holdings' in update_data:
                        holdings_list = update_data.get('holdings', [])
                        # 如果是字典格式，转换为列表，并添加code字段
                        if isinstance(holdings_list, dict):
                            holdings_list = [
                                {**holding, 'code': code} 
                                for code, holding in holdings_list.items()
                            ]
                        # ✅ 确保每个持仓都有code字段
                        for holding in holdings_list:
                            if isinstance(holding, dict) and 'code' not in holding:
                                # 如果没有code字段，尝试从其他字段获取
                                holding['code'] = holding.get('stock_code', '')
                        MemoryStore.update_holdings(agent_name, holdings_list)
                        
                        # 同时保存到数据库
                        if persistence:
                            try:
                                persistence.save_holdings(session_id, agent_name, holdings_list)
                            except Exception as e:
                                print(f"⚠️  [{agent_name}] 保存持仓到数据库失败: {e}")
                    
                    # ✅ 实时保存模型状态
                    cash = update_data.get('cash', 0)
                    persistence.save_model_state(
                        session_id, agent_name,
                        cash, total_assets, profit_pct
                    )
                
                # 处理AI日志（使用持久化版本）
                if 'ai_logs' in update_data:
                    for log in update_data.get('ai_logs', []):
                        # log可能是字符串或字典
                        if isinstance(log, str):
                            MemoryStore.add_ai_log_with_persistence(
                                model_name=agent_name,
                                message=log,
                                color=None
                            )
                        elif isinstance(log, dict):
                            MemoryStore.add_ai_log_with_persistence(
                                model_name=agent_name,
                                message=log.get('message', ''),
                                color=log.get('color')
                            )
            
            # 开始运行（使用并行模式）
            arena_log_msg(f"\n📅 交易日期: {start_date} - {end_date}")
            arena_log_msg(f"🚀 开始运行竞技场...")
            arena_log_msg(f"🔍 调用 arena.run_arena_parallel() ...")
            arena_log_msg(f"   参数: start_date={start_date}, end_date={end_date}")
            
            try:
                # 创建停止检查函数
                def should_stop():
                    global _should_stop
                    if _should_stop:
                        arena_log_msg("⚠️  收到停止信号，保存数据后退出...")
                        MemoryStore.save_to_database()
                        arena_log_msg("✅ 数据已保存")
                    return _should_stop
                
                results = arena.run_arena_parallel(
                    start_date=start_date,
                    end_date=end_date,
                    progress_callback=progress_callback,
                    update_callback=update_callback,
                    should_stop=should_stop,
                    session_id=session_id  # Phase 4: 传入session_id用于Agent经验管理
                )
                arena_log_msg("✅ run_arena_parallel() 返回成功")
                arena_log_msg(f"   返回结果: {type(results)}")
            except Exception as run_error:
                arena_log_msg(f"❌ run_arena_parallel() 抛出异常:")
                arena_log_msg(f"   {type(run_error).__name__}: {run_error}")
                import traceback
                arena_log_msg(traceback.format_exc())
                raise
            
            arena_log_msg("✅ 竞技场运行完成")
            arena_log_msg(f"📊 最终结果: {len(results)} 个模型完成交易")
            
            # ✅ 标记会话完成（数据已实时保存，无需再次批量保存）
            arena_log_msg("💾 标记会话完成...")
            MemoryStore.complete_current_session()
            arena_log_msg("✅ 会话已完成")
            arena_log_msg(f"📂 数据库文件: data/arena_sessions.db")
            arena_log_msg(f"📝 会话ID: {session_id}")
            arena_log_msg("=" * 60)
            
        except Exception as e:
            arena_log_msg(f"❌ 竞技场启动失败: {e}")
            import traceback
            arena_log_msg(traceback.format_exc())
            
            # ✅ 异常时数据也已实时保存，只需标记即可
            arena_log_msg("⚠️  虽然发生异常，但数据已实时保存")
            arena_log_msg("=" * 60)
            
        finally:
            # ✅ 恢复标准输出
            sys.stdout = original_stdout
            arena_log.close()
    
    log("\n🚀 启动后台竞技场线程...")
    _arena_thread = threading.Thread(target=run_arena, daemon=True)
    _arena_thread.start()
    log("✅ 竞技场已在后台启动")
    log("=" * 60)
    log("🎉 启动事件完成\n")
    log_file.close()
    
    # 应用运行时的 yield
    yield
    
    # 关闭逻辑（如果需要）
    # 这里可以添加清理代码，比如停止线程、关闭连接等

app = FastAPI(
    title="AI Arena API",
    description="AI量化竞技场后端API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def set_arena_instance(arena, config):
    """设置竞技场实例（从main.py调用）"""
    global _arena_instance, _config
    _arena_instance = arena
    _config = config

# ============================================================
# 数据库备份工具
# ============================================================

def backup_database(db_path: str, max_backups: int = 10) -> bool:
    """
    自动备份数据库
    Args:
        db_path: 数据库文件路径
        max_backups: 保留的最大备份数量
    Returns:
        bool: 备份是否成功
    """
    try:
        if not os.path.exists(db_path):
            return False
        
        # 创建备份目录
        backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        
        # 生成备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"trading_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        
        # 复制数据库文件
        shutil.copy2(db_path, backup_path)
        print(f"✅ 数据库已备份: {backup_name}")
        
        # 清理旧备份（保留最新的N个）
        backups = sorted(Path(backup_dir).glob("trading_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_backup in backups[max_backups:]:
            old_backup.unlink()
            print(f"🗑️ 删除旧备份: {old_backup.name}")
        
        return True
    except Exception as e:
        print(f"❌ 数据库备份失败: {e}")
        return False

# ============================================================
# 请求/响应模型
# ============================================================

class StartArenaRequest(BaseModel):
    """启动竞技场请求"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ApiResponse(BaseModel):
    """统一响应格式"""
    success: bool
    message: Optional[str] = None
    error: Optional[Dict[str, str]] = None

# ============================================================
# 1. 基础接口
# ============================================================

@app.get("/api/arena/config")
async def get_config():
    """获取竞技场配置"""
    if not _config:
        # 后端尚未加载配置时提供安全默认值，避免前端崩溃
        return {
            'initial_capital': 10000,
            'start_date': '20250101',
            'end_date': '20251231',
            'models': []
        }
    
    def get_logo_base64(logo_path: str) -> str:
        """从配置的logo路径读取图片并转换为base64"""
        if not logo_path:
            return None
        
        # 如果路径是相对路径，转换为绝对路径
        if not os.path.isabs(logo_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(base_dir, logo_path)
        
        if not os.path.exists(logo_path):
            return None
        
        try:
            with open(logo_path, 'rb') as f:
                image_data = f.read()
                base64_data = base64.b64encode(image_data).decode('utf-8')
                # 根据文件扩展名判断MIME类型
                ext = os.path.splitext(logo_path)[1].lower()
                mime_type = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
                return f'data:{mime_type};base64,{base64_data}'
        except Exception:
            return None
    
    # 获取竞技场配置
    arena_config = _config.get('arena', {})
    models = []
    for index, model in enumerate(arena_config.get('models', [])):
        if model.get('enabled', True):
            # 直接从配置中读取logo路径，并转换为base64
            logo_path = model.get('logo')
            models.append({
                'id': model.get('id', model['name']),  # 使用ID，如果没有则回退到name
                'index': index,  # 添加序号，基于配置数组中的原始位置
                'name': model['name'],
                'color': model.get('color', '#1976D2'),
                'logo': get_logo_base64(logo_path) if logo_path else None
            })
    
    trading_config = _config.get('trading', {})
    
    return {
        'initial_capital': trading_config.get('initial_capital', 10000),
        'start_date': trading_config.get('start_date', '20250101'),
        'end_date': trading_config.get('end_date', '20251231'),
        'models': models
    }

# ============================================================
# 2. 数据接口
# ============================================================

@app.get("/api/arena/data")
async def get_arena_data():
    """获取所有模型的完整数据（包含图表、持仓、交易记录）
    
    ✅ 前端可以超前拿数据：从数据库加载所有数据（包括未来的），但前端显示时会做同步过滤
    """
    try:
        arena_data = MemoryStore.get_arena_data()
        
        # ✅ 创建model_name到model_id的映射
        model_id_map = {}  # {model_name: model_id}
        if _config:
            arena_config = _config.get('arena', {})
            for model in arena_config.get('models', []):
                model_name = model['name']
                model_id = model.get('id', model_name)  # 如果没有id则使用name
                model_id_map[model_name] = model_id
        
        # ✅ 获取MemoryStore中的数据
        chart_data = MemoryStore.get_chart_data()  # {model_name: [{date, assets}, ...]}
        holdings_data = MemoryStore.get_holdings()  # {model_name: [holdings]}
        all_trades = MemoryStore.get_trades()  # 所有交易记录
        
        # ✅ 从数据库补充完整数据（包括未来的），让前端可以超前拿数据
        # 但前端显示时会做同步过滤，只显示到所有模型都有的最新日期
        session_id = MemoryStore.get_current_session_id()
        if session_id:
            try:
                from persistence.arena_persistence import get_arena_persistence
                persistence = get_arena_persistence()
                # 从数据库加载所有数据（include_future=True），包括未来数据
                db_data = persistence.load_session_data(session_id, include_future=True)
                
                # 合并数据库中的完整数据到MemoryStore数据中
                if db_data and 'daily_assets' in db_data:
                    db_chart_data = db_data.get('daily_assets', {})
                    for model_name, db_daily_assets in db_chart_data.items():
                        if model_name not in chart_data:
                            chart_data[model_name] = []
                        
                        # 合并数据，使用数据库中的完整数据（包括未来的）
                        # 创建日期到资产的映射，MemoryStore数据优先（可能更新），数据库数据作为补充
                        date_asset_map = {}
                        
                        # 先添加数据库数据（包括未来的）
                        for item in db_daily_assets:
                            date_asset_map[item['date']] = item['assets']
                        
                        # 再用MemoryStore数据覆盖（可能更新）
                        for item in chart_data[model_name]:
                            date_asset_map[item['date']] = item['assets']
                        
                        # 转换回列表格式并排序
                        chart_data[model_name] = [
                            {'date': date, 'assets': assets}
                            for date, assets in sorted(date_asset_map.items())
                        ]
                
                # 合并交易记录
                if db_data and 'trades' in db_data:
                    db_trades = db_data.get('trades', [])
                    # 创建交易ID到交易的映射，避免重复
                    trade_id_map = {t.get('id'): t for t in all_trades if t.get('id')}
                    for db_trade in db_trades:
                        trade_id = db_trade.get('id')
                        if trade_id and trade_id not in trade_id_map:
                            trade_id_map[trade_id] = db_trade
                    all_trades = list(trade_id_map.values())
                
                # 合并持仓数据
                if db_data and 'holdings' in db_data:
                    db_holdings = db_data.get('holdings', {})
                    for model_name, db_model_holdings in db_holdings.items():
                        # 使用数据库中的完整持仓数据
                        holdings_data[model_name] = db_model_holdings
            except Exception as e:
                # 如果从数据库加载失败，继续使用MemoryStore的数据
                pass
        
        # ✅ 如果arena_data为空，但有历史数据，则从配置初始化
        if not arena_data:
            arena_data = {}
            if not _config:
                # 配置未加载，返回空数据
                return {}
            initial_capital = _config.get('trading', {}).get('initial_capital', 10000)
            # ✅ 从arena配置读取模型（而不是config.models）
            arena_config = _config.get('arena', {})
            for model in arena_config.get('models', []):
                if not model.get('enabled', True):
                    continue
                model_name = model['name']
                model_id = model.get('id', model_name)
                arena_data[model_name] = {
                    'model_id': model_id,  # 添加model_id字段
                    'total_assets': initial_capital,
                    'cash': initial_capital,
                    'holdings': [],
                    'profit_pct': 0.0,
                    'model_color': model.get('color', '#1976D2')
                }
        
        # 按模型分组交易记录（同时转换字段名以匹配前端期望）
        trades_by_model = {}
        for trade in all_trades:
            model_name = trade.get('model_name')
            if model_name:
                if model_name not in trades_by_model:
                    trades_by_model[model_name] = []
                
                # ✅ 转换字段名以匹配前端期望
                trade_copy = dict(trade)
                
                # trade_date -> date (如果有trade_date字段)
                if 'trade_date' in trade_copy and 'date' not in trade_copy:
                    trade_copy['date'] = trade_copy['trade_date']
                
                # stock_code -> code (总是添加code字段)
                if 'stock_code' in trade_copy:
                    trade_copy['code'] = trade_copy['stock_code']
                
                # 数据库/内存中：amount=总金额, volume=数量
                # 前端需要：total=总金额, amount=数量, code=股票代码
                # ⚠️ 注意：必须先保存原值，再覆盖
                db_amount = trade_copy.get('amount', 0)  # 原amount是总金额
                db_volume = trade_copy.get('volume', 0)  # 原volume是数量
                
                trade_copy['total'] = db_amount    # 前端的total = 总金额
                trade_copy['amount'] = db_volume   # 前端的amount = 数量（覆盖）
                
                # ✅ 补充name字段（如果没有）
                if 'name' not in trade_copy or not trade_copy['name']:
                    stock_code = trade_copy.get('code') or trade_copy.get('stock_code')
                    if stock_code and _arena_instance:
                        try:
                            stock_info = _arena_instance.data_provider.get_stock_basic_info(stock_code)
                            trade_copy['name'] = stock_info.get('name', stock_code)
                        except:
                            trade_copy['name'] = stock_code
                    else:
                        trade_copy['name'] = stock_code or '未知'
                
                trades_by_model[model_name].append(trade_copy)
        
        # ✅ 确保所有在历史数据中的模型都在arena_data中
        all_model_names = set(arena_data.keys())
        all_model_names.update(chart_data.keys())
        all_model_names.update(holdings_data.keys())
        all_model_names.update(trades_by_model.keys())
        
        initial_capital = _config.get('trading', {}).get('initial_capital', 10000) if _config else 10000
        
        # 为历史数据中存在但arena_data中不存在的模型创建基础结构
        for model_name in all_model_names:
            if model_name not in arena_data:
                arena_data[model_name] = {
                    'total_assets': initial_capital,
                    'cash': initial_capital,
                    'holdings': [],
                    'profit_pct': 0.0
                }
        
        # 为每个模型合并所有数据
        # 获取开始日期，用于初始化空数据模型
        start_date = _config.get('trading', {}).get('start_date', '20250101') if _config else '20250101'
        
        for model_name, model_data in arena_data.items():
            # ✅ 添加图表数据（daily_assets）- 转换字段名为前端期望的格式
            daily_assets_raw = chart_data.get(model_name, [])
            model_data['daily_assets'] = [
                {
                    'date': item['date'],
                    'total_assets': item.get('assets', 0)  # 转换 assets -> total_assets
                }
                for item in daily_assets_raw
            ]
            
            # ✅ 如果daily_assets为空，但有模型数据（说明模型已初始化），添加初始资产记录
            # 这样前端才能显示图表，即使arena还没有开始运行或模型还没有交易记录
            if len(model_data['daily_assets']) == 0:
                initial_assets = model_data.get('total_assets', initial_capital)
                model_data['daily_assets'] = [{
                    'date': start_date,
                    'total_assets': initial_assets
                }]
            
            # ⚠️ 注意：不在这里更新total_assets，让前端自己从daily_assets获取
            # 因为arena_data中的total_assets是agent的实时状态，可能与daily_assets不同步
            
            # ✅ 添加持仓数据（转换字段名以匹配前端期望）
            raw_holdings = holdings_data.get(model_name, [])
            model_data['holdings'] = [
                {
                    # 必需字段（前端期望）
                    'code': h.get('stock_code', h.get('code')),  # stock_code -> code
                    'name': h.get('stock_name', h.get('name')),  # stock_name -> name
                    'amount': h.get('amount', 0),
                    'cost': h.get('avg_price', h.get('cost', 0)),  # avg_price -> cost
                    'current_price': h.get('current_price', 0),
                    'profit_pct': h.get('profit_pct', 0),
                    # 额外字段
                    'hold_days': h.get('hold_days', 0),
                    'date': h.get('updated_at', ''),
                    'buy_date': h.get('updated_at', '')
                }
                for h in raw_holdings
            ]
            
            # ✅ 添加交易记录
            model_data['trade_history'] = trades_by_model.get(model_name, [])
            
            # 调试：验证返回数据
            if model_data['trade_history'] and len(model_data['trade_history']) > 0:
                first_trade = model_data['trade_history'][0]
                if 'code' not in first_trade or 'total' not in first_trade:
                    print(f"[ERROR] {model_name} 第一条交易缺少字段: code={first_trade.get('code', 'N/A')}, total={first_trade.get('total', 'N/A')}")
            
            # 添加model_color如果没有
            if 'model_color' not in model_data:
                if _config and 'models' in _config:
                    for m in _config['models']:
                        if m['name'] == model_name:
                            model_data['model_color'] = m['color']
                            break
        
            # ✅ 确保每个模型数据都包含model_id字段
            if 'model_id' not in model_data:
                model_id = model_id_map.get(model_name, model_name)
                model_data['model_id'] = model_id
        
        # ✅ 只使用model_id作为key，避免重复显示
        result = {}
        for model_name, model_data in arena_data.items():
            model_id = model_data.get('model_id', model_id_map.get(model_name, model_name))
            # 只用model_id作为key
            result[model_id] = model_data
        
        return result
        
    except Exception as e:
        print(f"❌ get_arena_data 错误: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

@app.get("/api/arena/rankings")
async def get_rankings():
    """获取模型排名"""
    model_assets = MemoryStore.get_all_model_assets()
    
    # 按收益率排序
    rankings = []
    for model_name, asset_data in model_assets.items():
        rankings.append({
            'model_name': model_name,
            'total_assets': asset_data['total_assets'],
            'profit_pct': asset_data['profit_pct'],
            'color': asset_data.get('color', '#1976D2')
        })
    
    rankings.sort(key=lambda x: x['profit_pct'], reverse=True)
    
    # 添加排名
    for i, item in enumerate(rankings):
        item['rank'] = i + 1
    
    return {'rankings': rankings}

@app.get("/api/arena/progress")
async def get_progress():
    """获取执行进度"""
    progress_data = MemoryStore.get_progress()
    
    current = progress_data.get('current', 0)
    total = progress_data.get('total', 0)
    
    return {
        'current': current,
        'total': total,
        'message': progress_data.get('message', ''),
        'percent': round((current / total * 100) if total > 0 else 0, 2),
        'is_running': _arena_instance is not None
    }

# ============================================================
# 3. 控制接口
# ============================================================

@app.post("/api/arena/start")
async def start_arena(request: StartArenaRequest):
    """启动竞技场"""
    if _arena_instance is None:
        raise HTTPException(status_code=500, detail="竞技场实例未初始化")
    
    # TODO: 实现启动逻辑（需要在main.py中集成）
    return {
        'success': True,
        'message': '竞技场已启动'
    }

@app.post("/api/arena/stop")
async def stop_arena():
    """停止竞技场"""
    if _arena_instance is None:
        raise HTTPException(status_code=400, detail="竞技场未运行")
    
    # TODO: 实现停止逻辑
    return {
        'success': True,
        'message': '竞技场已停止'
    }

@app.post("/api/arena/reset")
async def reset_arena():
    """重置竞技场"""
    MemoryStore.reset()
    
    return {
        'success': True,
        'message': '竞技场已重置'
    }

# ============================================================
# 4. 详细数据接口
# ============================================================

@app.get("/api/arena/models/{model_name}")
async def get_model_data(model_name: str):
    """获取单个模型的详细数据"""
    arena_data = MemoryStore.get_arena_data()
    
    if model_name not in arena_data:
        raise HTTPException(status_code=404, detail=f"模型 {model_name} 不存在")
    
    return arena_data[model_name]

@app.get("/api/arena/logs/{model_name}")
async def get_model_logs(model_name: str, limit: int = 50):
    """获取AI日志"""
    all_logs = MemoryStore.get_ai_logs()  # 已经是倒序（最新在前）
    
    # 过滤指定模型的日志
    model_logs = [log for log in all_logs if log.get('model_name') == model_name]
    
    # ✅ 限制返回数量（取前N条，因为已经是倒序）
    model_logs = model_logs[:limit]
    
    return {'logs': model_logs}

# ============================================================
# 5. 备份管理接口
# ============================================================

@app.get("/api/arena/backups")
async def list_backups():
    """列出所有可用的数据库备份"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(base_dir, 'data', 'backups')
    
    if not os.path.exists(backup_dir):
        return {'backups': []}
    
    backups = []
    for backup_file in sorted(Path(backup_dir).glob("trading_*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        backups.append({
            'filename': backup_file.name,
            'size': backup_file.stat().st_size,
            'created_at': datetime.fromtimestamp(backup_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return {'backups': backups}

@app.post("/api/arena/restore")
async def restore_backup(backup_filename: str):
    """恢复指定的备份"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(base_dir, 'data', 'backups')
    backup_path = os.path.join(backup_dir, backup_filename)
    db_path = os.path.join(base_dir, 'data', 'trading.db')
    
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")
    
    try:
        # 在恢复前先备份当前数据库
        if os.path.exists(db_path):
            backup_database(db_path, max_backups=10)
        
        # 恢复备份
        shutil.copy2(backup_path, db_path)
        return {'status': 'success', 'message': f'已恢复备份: {backup_filename}'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")

# ============================================================
# 6. 会话管理接口
# ============================================================

@app.get("/api/arena/sessions")
async def list_sessions(limit: int = 10):
    """列出历史会话"""
    from persistence.arena_persistence import get_arena_persistence
    persistence = get_arena_persistence()
    sessions = persistence.list_sessions(limit)
    return {'sessions': sessions}

@app.get("/api/arena/sessions/latest")
async def get_latest_unfinished_session():
    """获取最新的未完成会话"""
    from persistence.arena_persistence import get_arena_persistence
    persistence = get_arena_persistence()
    session = persistence.get_latest_unfinished_session()
    return {'session': session}

@app.get("/api/arena/sessions/{session_id}")
async def get_session_data(session_id: str):
    """获取指定会话的数据"""
    from persistence.arena_persistence import get_arena_persistence
    persistence = get_arena_persistence()
    try:
        data = persistence.load_session_data(session_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"会话不存在: {str(e)}")

@app.post("/api/arena/sessions/{session_id}/load")
async def load_session(session_id: str):
    """加载指定会话的数据到内存"""
    try:
        MemoryStore.load_session(session_id)
        return {'status': 'success', 'message': f'已加载会话: {session_id}'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载失败: {str(e)}")

@app.get("/api/arena/current_session")
async def get_current_session():
    """获取当前会话ID"""
    session_id = MemoryStore.get_current_session_id()
    return {'session_id': session_id}

# ============================================================
# 7. 健康检查
# ============================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'arena_running': _arena_instance is not None
    }

@app.get("/")
async def root():
    """根路径"""
    return {
        'name': 'AI Arena API',
        'version': '1.0.0',
        'docs': '/docs',
        'health': '/health'
    }

@app.post("/shutdown")
async def shutdown():
    """优雅停止竞技场"""
    global _should_stop
    _should_stop = True
    
    # 保存当前数据
    try:
        MemoryStore.save_to_database()
        return {
            "status": "stopping",
            "message": "停止信号已发送，等待当前交易日完成后保存数据..."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"保存数据失败: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    
    # 开发模式：独立运行API服务器
    print("🚀 启动API服务器...")
    print("📖 API文档: http://localhost:8000/docs")
    print("🏥 健康检查: http://localhost:8000/health")
    print("")
    print("按 Ctrl+C 停止服务器")
    print("")
    
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000,
        log_level="warning",
        access_log=False
    )

"""
AI竞技场管理器
管理多个AI模型同时进行交易回测，比较性能
"""
from typing import Dict, List, Any
import concurrent.futures
import time

from .langgraph_trading_agent import LangGraphTradingAgent
from services.baostock_provider_v2 import BaostockProviderV2  # ⚡ V2版本：线程安全


class ArenaManager:
    """AI竞技场管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化竞技场（延迟初始化模式）
        
        Args:
            config: 配置信息
        """
        self.config = config
        self.arena_config = config.get('arena', {})
        
        # 创建Baostock数据提供者（所有Agent共享）
        # ⚡ 使用V2版本：支持多线程，加速4.94x
        print("📊 正在创建数据提供者...", flush=True)
        self.data_provider = BaostockProviderV2()
        print("✅ 数据提供者创建完成", flush=True)
        
        # ✅ 延迟初始化：只保存配置，不立即创建Agent
        self.agents = []
        self._agents_initialized = False
        
        # 保存模型配置供后续使用
        self.model_configs = [
            model_config for model_config in self.arena_config.get('models', [])
            if model_config.get('enabled', True)
        ]
        
        if len(self.model_configs) == 0:
            raise RuntimeError("❌ 没有可用的Agent配置，竞技场创建失败！")
        
        print(f"\n🏆 竞技场管理器已创建，共 {len(self.model_configs)} 个AI配置", flush=True)
        for model_config in self.model_configs:
            print(f"  - {model_config['name']} ({model_config['provider']})", flush=True)
        print(f"  ⚡ Agent将在需要时触发初始化（延迟加载）", flush=True)
    
    def initialize_agents(self):
        """
        触发初始化所有Agent（延迟初始化）
        只有在实际需要运行竞技场时才调用此方法
        """
        if self._agents_initialized:
            print("✅ Agent已经初始化，跳过重复初始化", flush=True)
            return
        
        print("\n" + "="*60, flush=True)
        print("🚀 开始触发式初始化Agent...", flush=True)
        print("="*60 + "\n", flush=True)
        
        # 创建所有Agent
        for model_config in self.model_configs:
            try:
                print(f"📝 正在创建 {model_config['name']} Agent...", flush=True)
                agent = LangGraphTradingAgent(
                    data_provider=self.data_provider,
                    config=self.config,
                    model_provider=model_config['provider']
                )
                self.agents.append({
                    'name': model_config['name'],
                    'provider': model_config['provider'],
                    'color': model_config['color'],
                    'agent': agent
                })
                print(f"  ✅ {model_config['name']} Agent创建成功", flush=True)
            except Exception as e:
                print(f"  ❌ {model_config['name']} Agent创建失败: {e}", flush=True)
                import traceback
                traceback.print_exc()
        
        if len(self.agents) == 0:
            raise RuntimeError("❌ 没有可用的Agent，Agent初始化失败！")
        
        self._agents_initialized = True
        
        print(f"\n✅ Agent初始化完成，共 {len(self.agents)} 个AI准备就绪", flush=True)
        for agent_info in self.agents:
            print(f"  - {agent_info['name']} ({agent_info['provider']})", flush=True)
    
    def run_arena(self, start_date: str, end_date: str, 
                  progress_callback=None, update_callback=None,
                  should_stop=None) -> Dict[str, Any]:
        """
        运行竞技场（串行模式）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            progress_callback: 进度回调
            update_callback: 更新回调
            should_stop: 停止检查函数
            
        Returns:
            所有Agent的结果
        """
        # ✅ 确保Agent已初始化（延迟初始化检查）
        if not self._agents_initialized:
            self.initialize_agents()
        
        print(f"\n{'='*60}")
        print(f"🏆 AI Trading Arena 开始")
        print(f"参赛AI: {', '.join([a['name'] for a in self.agents])}")
        print(f"时间范围: {start_date} - {end_date}")
        print(f"初始资金: 每个Agent {self.config.get('trading', {}).get('initial_capital', 10000):.2f}元（独立账户）")
        print(f"{'='*60}\n")
        
        results = {}
        
        # 串行运行每个Agent
        for idx, agent_info in enumerate(self.agents):
            name = agent_info['name']
            agent = agent_info['agent']
            
            # ✅ 修复：检查是否有历史数据（断点续跑）
            initial_capital = self.config.get('trading', {}).get('initial_capital', 10000)
            has_history = (
                len(agent.daily_assets) > 0 or 
                len(agent.trade_history) > 0 or 
                len(agent.holdings) > 0
            )
            
            print(f"\n{'='*60}")
            print(f"🤖 {name} 开始回测 [{idx+1}/{len(self.agents)}]")
            
            if not has_history:
                # 🆕 新运行：初始化Agent状态
                agent.cash = initial_capital
                agent.holdings = {}
                agent.total_assets = initial_capital
                agent.trade_history = []
                agent.daily_assets = []
                print(f"💰 独立账户: {initial_capital:.2f}元（新运行）")
            else:
                # 🔄 断点续跑：保持现有状态
                print(f"🔄 断点续跑模式")
                print(f"   📊 已有 {len(agent.daily_assets)} 天历史")
                print(f"   💰 当前资产: ¥{agent.total_assets:.2f}")
            
            print(f"{'='*60}\n")
            
            # 包装进度回调，加上模型名称
            def wrapped_progress(current, total, message):
                if progress_callback:
                    progress_callback(name, current, total, message)
            
            # 包装更新回调
            def wrapped_update(data):
                if update_callback:
                    data['model_name'] = name
                    data['model_color'] = agent_info['color']
                    update_callback(name, data)
            
            try:
                result = agent.run_backtest(
                    start_date=start_date,
                    end_date=end_date,
                    progress_callback=wrapped_progress,
                    update_callback=wrapped_update,
                    should_stop=should_stop
                )
                
                results[name] = {
                    'result': result,
                    'color': agent_info['color'],
                    'provider': agent_info['provider']
                }
                
                # 显示结果
                profit_pct = ((result['total_assets'] - result['initial_capital']) 
                            / result['initial_capital'] * 100)
                print(f"\n{'='*60}")
                print(f"✅ {name} 回测完成")
                print(f"最终资产: {result['total_assets']:.2f}元")
                print(f"收益率: {profit_pct:+.2f}%")
                print(f"{'='*60}\n")
                
            except Exception as e:
                print(f"❌ {name} 回测失败: {e}")
                results[name] = {
                    'error': str(e),
                    'color': agent_info['color'],
                    'provider': agent_info['provider']
                }
        
        # 显示最终排名
        self._show_rankings(results)
        
        return results
    
    def run_arena_parallel(self, start_date: str, end_date: str,
                          progress_callback=None, update_callback=None,
                          should_stop=None, session_id: str = None) -> Dict[str, Any]:
        """
        运行竞技场（同步竞技模式 - 公平对决！）
        
        按交易日同步执行：
        - 每个交易日，所有AI并行决策
        - 等待全部完成后，进入下一个交易日
        - 确保公平对比同一天的表现
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            progress_callback: 进度回调
            update_callback: 更新回调
            should_stop: 停止检查函数
            session_id: 会话ID（Phase 4: 用于经验管理）
            
        Returns:
            所有Agent的结果
        """
        # ✅ 确保Agent已初始化（延迟初始化检查）
        if not self._agents_initialized:
            self.initialize_agents()
        
        import sys
        print(f"\n{'='*60}", flush=True)
        sys.stdout.flush()  # 强制刷新
        print(f"🏆 AI Trading Arena 开始（同步竞技模式）", flush=True)
        sys.stdout.flush()
        print(f"参赛AI: {', '.join([a['name'] for a in self.agents])}", flush=True)
        sys.stdout.flush()
        print(f"时间范围: {start_date} - {end_date}", flush=True)
        sys.stdout.flush()
        print(f"初始资金: 每个Agent {self.config.get('trading', {}).get('initial_capital', 10000):.2f}元（独立账户）", flush=True)
        sys.stdout.flush()
        print(f"🏁 按交易日同步推进，每天所有AI并行决策！", flush=True)
        sys.stdout.flush()
        print(f"{'='*60}\n", flush=True)
        sys.stdout.flush()
        
        # 初始化所有Agent的状态
        print(f"\n🔧 开始初始化Agent状态...", flush=True)
        sys.stdout.flush()
        
        initial_capital = self.config.get('trading', {}).get('initial_capital', 10000)
        agent_states = {}
        
        # ⭐ 数据损坏检测和回滚
        print(f"\n🔍 开始检测Agent数据完整性...", flush=True)
        sys.stdout.flush()
        
        for agent_info in self.agents:
            name = agent_info['name']
            agent = agent_info['agent']
            
            # ✅ 修复：检查是否有历史数据（断点续跑）
            has_history = (
                len(agent.daily_assets) > 0 or 
                len(agent.trade_history) > 0 or 
                len(agent.holdings) > 0
            )
            
            if not has_history:
                # 🆕 新运行：初始化Agent状态
                print(f"🆕 {name}: 新运行，初始化状态")
                agent.cash = initial_capital
                agent.holdings = {}
                agent.total_assets = initial_capital
                agent.trade_history = []
                agent.daily_assets = []
                print(f"   💰 初始资金: ¥{initial_capital:.2f}")
            else:
                # 🔄 断点续跑：检测数据损坏
                print(f"🔄 {name}: 检测到历史数据，开始数据完整性检测...")
                print(f"   📊 已有 {len(agent.daily_assets)} 天历史")
                print(f"   📝 已有 {len(agent.trade_history)} 笔交易")
                print(f"   💼 当前持仓: {len(agent.holdings)} 只股票")
                print(f"   💰 当前资产: ¥{agent.total_assets:.2f} (现金: ¥{agent.cash:.2f})")
                
                # ⭐ 首先检测日期连续性：找到最初连续数据的末端
                last_continuous_date, first_gap_date = agent.find_first_continuous_data_end()
                
                if first_gap_date:
                    # 发现日期断点（跳过了交易日），自动回滚到连续数据末端
                    print(f"   ⚠️ 检测到日期断点，将从 {first_gap_date} 之前的所有数据回滚", flush=True)
                    print(f"   🔄 自动回滚到最后一个连续日期 {last_continuous_date} 之后...", flush=True)
                    
                    if last_continuous_date and agent.rollback_to_date(first_gap_date):
                        print(f"   ✅ 回滚成功，将从 {last_continuous_date} 之后重新开始", flush=True)
                        print(f"   📊 回滚后剩余 {len(agent.daily_assets)} 天历史", flush=True)
                        print(f"   📝 回滚后剩余 {len(agent.trade_history)} 笔交易", flush=True)
                        print(f"   💰 回滚后资产: ¥{agent.total_assets:.2f} (现金: ¥{agent.cash:.2f})", flush=True)
                    else:
                        print(f"   ❌ 回滚失败，将从头开始", flush=True)
                        # 回滚失败，重置到初始状态
                        agent.cash = initial_capital
                        agent.holdings = {}
                        agent.total_assets = initial_capital
                        agent.trade_history = []
                        agent.daily_assets = []
                
                # ⭐ 然后检测数据损坏（其他类型的问题）
                is_corrupted, corrupted_date = agent.detect_data_corruption()
                
                if is_corrupted:
                    print(f"   ⚠️ 检测到数据损坏！第一个损坏日期: {corrupted_date}", flush=True)
                    
                    if corrupted_date:
                        # 找到损坏日期之前的最后一个有效日期（在daily_assets中）
                        from datetime import datetime
                        try:
                            if '-' not in corrupted_date:
                                corrupted_date = f"{corrupted_date[:4]}-{corrupted_date[4:6]}-{corrupted_date[6:8]}"
                            corrupted_dt = datetime.strptime(corrupted_date, '%Y-%m-%d')
                            
                            # 找到最后一个有效日期（在损坏日期之前）
                            last_valid_date = None
                            for entry in reversed(agent.daily_assets):
                                entry_date = entry.get('date')
                                if entry_date:
                                    try:
                                        if '-' not in entry_date:
                                            entry_date = f"{entry_date[:4]}-{entry_date[4:6]}-{entry_date[6:8]}"
                                        entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
                                        if entry_dt < corrupted_dt:
                                            last_valid_date = entry_date
                                            break
                                    except:
                                        continue
                            
                            if last_valid_date:
                                print(f"   🔄 自动回滚到最后一个有效日期 {last_valid_date} 之后...", flush=True)
                                
                                # 回滚到last_valid_date之后（即删除last_valid_date之后的所有数据）
                                # rollback_to_date会删除target_date及之后的数据，所以要传入损坏日期
                                if agent.rollback_to_date(corrupted_date):
                                    print(f"   ✅ 回滚成功，将从 {last_valid_date} 之后重新开始", flush=True)
                                    
                                    # 更新状态信息
                                    print(f"   📊 回滚后剩余 {len(agent.daily_assets)} 天历史")
                                    print(f"   📝 回滚后剩余 {len(agent.trade_history)} 笔交易")
                                    print(f"   💰 回滚后资产: ¥{agent.total_assets:.2f} (现金: ¥{agent.cash:.2f})")
                                else:
                                    print(f"   ❌ 回滚失败，将从头开始", flush=True)
                                    # 回滚失败，重置到初始状态
                                    agent.cash = initial_capital
                                    agent.holdings = {}
                                    agent.total_assets = initial_capital
                                    agent.trade_history = []
                                    agent.daily_assets = []
                            else:
                                print(f"   ❌ 无法找到有效日期，将从头开始", flush=True)
                                # 找不到有效日期，重置到初始状态
                                agent.cash = initial_capital
                                agent.holdings = {}
                                agent.total_assets = initial_capital
                                agent.trade_history = []
                                agent.daily_assets = []
                        except Exception as e:
                            print(f"   ❌ 回滚过程出错: {e}，将从头开始", flush=True)
                            import traceback
                            traceback.print_exc()
                            # 出错，重置到初始状态
                            agent.cash = initial_capital
                            agent.holdings = {}
                            agent.total_assets = initial_capital
                            agent.trade_history = []
                            agent.daily_assets = []
                    else:
                        print(f"   ❌ 无法确定损坏日期，将从头开始", flush=True)
                        # 无法确定损坏日期，重置到初始状态
                        agent.cash = initial_capital
                        agent.holdings = {}
                        agent.total_assets = initial_capital
                        agent.trade_history = []
                        agent.daily_assets = []
                else:
                    print(f"   ✅ 数据完整性检测通过，断点续跑")
            
            # 初始化状态记录
            agent_states[name] = {
                'agent': agent,
                'info': agent_info,
                'completed': False,
                'error': None
            }
            
            print(f"🏁 {name} 准备就绪！")
        
        # 获取交易日列表（使用任意一个Agent的方法）
        print(f"\n📅 正在获取交易日列表...", flush=True)
        import sys
        sys.stdout.flush()
        
        first_agent = self.agents[0]['agent']
        trade_dates = first_agent._get_trade_dates(start_date, end_date)
        total_days = len(trade_dates)
        
        print(f"✅ 交易日列表获取成功！共 {total_days} 个交易日", flush=True)
        sys.stdout.flush()
        print(f"📊 预计总进度: {total_days} 天 × {len(self.agents)} 个AI\n", flush=True)
        sys.stdout.flush()
        
        # 按交易日同步执行
        print(f"\n🚀 开始进入每日交易循环...", flush=True)
        sys.stdout.flush()
        
        for day_idx, trade_date in enumerate(trade_dates):
            print(f"\n⏰ 处理第 {day_idx+1}/{total_days} 个交易日: {trade_date}", flush=True)
            sys.stdout.flush()
            
            # 检查停止
            if should_stop and should_stop():
                print(f"\n⚠️ 竞技场在 {trade_date} 被用户停止", flush=True)
                sys.stdout.flush()
                break
            
            # 格式化日期为YYYY-MM-DD
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            
            print(f"\n{'─'*60}", flush=True)
            sys.stdout.flush()
            print(f"📅 Day {day_idx+1}/{total_days}: {formatted_date}", flush=True)
            sys.stdout.flush()
            print(f"{'─'*60}", flush=True)
            sys.stdout.flush()

            # 预热行情数据
            try:
                preload_start = time.time()
                self.data_provider.preload_daily_data(trade_date)
                preload_elapsed = time.time() - preload_start
                print(f"⚡ 预热完成 ({trade_date}) - 耗时 {preload_elapsed:.2f}s", flush=True)
            except Exception as preload_err:
                print(f"❌ 预热失败 {trade_date}: {preload_err}", flush=True)
                print("⚠️ 将使用退化候选逻辑，可能导致性能下降", flush=True)
                hot_codes_fallback = []
                hot_sectors_fallback = []
            else:
                pool_info = self.data_provider.get_candidate_pool(trade_date)
                hot_codes_fallback = pool_info.get('hot_codes', [])
                hot_sectors_fallback = pool_info.get('hot_sectors', [])
            
            # 更新进度（使用第一个Agent的名字显示整体进度）
            if progress_callback:
                progress_callback(self.agents[0]['name'], day_idx+1, total_days, f"📅 Day {day_idx+1}/{total_days}: {formatted_date}")
            
            # 定义单个Agent单日执行函数
            def run_agent_one_day(agent_info, agent_state):
                import threading
                name = agent_info['name']
                agent = agent_state['agent']
                thread_id = threading.current_thread().name
                
                print(f"🏃 [{thread_id}] {name} 开始执行 {trade_date} @ {time.strftime('%H:%M:%S')}")
                
                # ⭐ 为该Agent生成专属的排名上下文
                agent_ranking_context = self.get_ranking_context_for_agent(
                    agent_name=name,
                    current_day=day_idx + 1,
                    total_days=total_days
                )
                
                # 用于收集该Agent的数据（不含日志）
                collected_data = {}
                
                def mixed_callback(data):
                    """混合回调：日志立即传递，数据也立即传递"""
                    # 🔍 调试：打印回调数据
                    print(f"📥 [{name}] mixed_callback 收到数据，键: {list(data.keys())}", flush=True)
                    
                    # AI日志和交易记录立即回调UI（实时显示）
                    ai_logs = data.get('ai_logs', [])
                    trade_history = data.get('trade_history', [])
                    
                    # 第1次回调：AI日志和交易记录（避免重复，只在这里传一次）
                    if (ai_logs or trade_history) and update_callback:
                        immediate_data = {
                            'model_name': name,
                            'model_color': agent_info['color']
                        }
                        if ai_logs:
                            immediate_data['ai_logs'] = ai_logs
                        if trade_history:
                            immediate_data['trade_history'] = trade_history
                        update_callback(name, immediate_data)
                    
                    # 第2次回调：其他数据（排除ai_logs和trade_history，避免重复保存）
                    other_data = {k: v for k, v in data.items() if k not in ['ai_logs', 'trade_history']}
                    if other_data:
                        print(f"📤 [{name}] 准备发送数据到update_callback，键: {list(other_data.keys())}", flush=True)
                        if update_callback:
                            callback_data = other_data.copy()
                            callback_data['model_name'] = name
                            callback_data['model_color'] = agent_info['color']
                            update_callback(name, callback_data)
                    else:
                        print(f"⚠️ [{name}] other_data 为空，跳过数据回调", flush=True)
                    
                    # 仍然收集数据（用于最终汇总）
                    collected_data.update(other_data)
                
                # ⭐ 保存执行前的资产状态（用于失败时的数据恢复）
                pre_exec_assets = agent.total_assets
                pre_exec_daily_assets = list(agent.daily_assets)  # 复制列表
                
                try:
                    # 调用Agent执行单日交易（⭐ 传入排名上下文）
                    exec_start = time.time()
                    agent.run_single_day(
                        trade_date=trade_date,
                        update_callback=mixed_callback,  # 混合回调
                        should_stop=should_stop,
                        ranking_context=agent_ranking_context,
                        hot_codes=hot_codes_fallback,
                        hot_sectors=hot_sectors_fallback,
                        session_id=session_id  # Phase 4: 传入session_id用于经验管理
                    )
                    exec_duration = time.time() - exec_start
                    print(f"✅ [{thread_id}] {name} 完成 {trade_date} @ {time.strftime('%H:%M:%S')} (耗时{exec_duration:.1f}秒)")
                    return name, None, collected_data  # 返回收集的数据（不含日志）
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"❌ [{thread_id}] {name} 在 {trade_date} 失败: {e}")
                    print(f"   错误详情: {error_detail}", flush=True)
                    
                    # ⭐ 关键修复：即使失败，也要保存当天的资产数据，确保图表连续
                    # 使用失败前的资产值（保持数据连续性）
                    # ✅ 修复：使用与正常执行相同的日期格式（8位数字，无横杠）
                    
                    # 恢复daily_assets（移除可能的损坏数据）
                    agent.daily_assets = pre_exec_daily_assets
                    
                    # 添加当天的资产数据（即使失败也要记录）
                    daily_asset_entry = {
                        'date': trade_date,  # ✅ 修复：使用原始格式 "20250102" 而不是 "2025-01-02"
                        'assets': pre_exec_assets,
                        'total_assets': pre_exec_assets,
                        'cash': agent.cash,
                        'stock_value': pre_exec_assets - agent.cash
                    }
                    
                    # 检查是否已经有当天的数据（避免重复）
                    existing_date = None
                    for idx, entry in enumerate(agent.daily_assets):
                        if entry.get('date') == trade_date:  # ✅ 修复：使用统一格式
                            existing_date = idx
                            break
                    
                    if existing_date is not None:
                        # 更新现有数据
                        agent.daily_assets[existing_date] = daily_asset_entry
                    else:
                        # 添加新数据
                        agent.daily_assets.append(daily_asset_entry)
                    
                    # ⭐ 构建失败时的数据，确保UI能看到数据点
                    failure_data = {
                        'daily_assets': agent.daily_assets,
                        'total_assets': pre_exec_assets,
                        'cash': agent.cash,
                        'holdings': [{'code': k, **v} for k, v in agent.holdings.items()],
                        'trade_history': agent.trade_history
                    }
                    
                    # 回调更新UI（即使失败也要显示数据点）
                    if update_callback:
                        callback_data = failure_data.copy()
                        callback_data['model_name'] = name
                        callback_data['model_color'] = agent_info['color']
                        callback_data['error'] = str(e)  # 标记为错误
                        update_callback(name, callback_data)
                    
                    # 返回失败数据（包含当天的资产记录）
                    return name, str(e), failure_data
            
            # 并行执行所有Agent的当日决策
            print(f"\n🚀 开始并行执行{len([a for a in self.agents if not agent_states[a['name']]['completed']])}个Agent...", flush=True)
            sys.stdout.flush()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
                print(f"📋 创建线程池（最大工作线程: {len(self.agents)}）...", flush=True)
                sys.stdout.flush()
                
                # ⭐ 关键修复：所有Agent都必须执行同一天，确保同步
                # 即使有Agent失败，也要等待所有Agent完成才能进入下一天
                active_agents = [
                    info for info in self.agents
                    if not agent_states[info['name']]['completed']
                ]
                
                if not active_agents:
                    print(f"⚠️ 所有Agent都已完成，停止执行", flush=True)
                    sys.stdout.flush()
                    break
                
                futures = {
                    executor.submit(run_agent_one_day, info, agent_states[info['name']]): info['name']
                    for info in active_agents
                }
                
                print(f"✅ 所有Agent已提交到线程池（{len(futures)}个任务），等待完成...", flush=True)
                sys.stdout.flush()
                
                start_time = time.time()
                
                # 收集所有Agent的数据
                agent_day_data = {}  # {name: collected_data}
                agent_errors = {}  # {name: error_msg} 记录失败的Agent
                
                # ⭐ 强制同步：必须等待所有Agent完成才能进入下一天
                total_count = len(futures)
                print(f"⏳ 等待 {total_count} 个Agent完成（严格同步模式：所有Agent必须完成）...", flush=True)
                sys.stdout.flush()
                
                # ⭐ 关键修复：等待所有任务完成，总超时时间：10分钟
                all_futures = list(futures.keys())
                deadline = start_time + 600  # 10分钟总超时
                
                # 使用 wait() 等待所有任务完成（或超时）
                done, not_done = concurrent.futures.wait(
                    all_futures,
                    timeout=600,
                    return_when=concurrent.futures.ALL_COMPLETED
                )
                
                # 处理已完成的future
                completed_count = 0
                for future in done:
                    name = futures[future]
                    completed_count += 1
                    try:
                        _, error, collected_data = future.result(timeout=0)  # 立即获取结果
                        if error:
                            print(f"❌ [{completed_count}/{total_count}] {name} 当日执行出错: {error}", flush=True)
                            agent_errors[name] = error
                            agent_states[name]['error'] = error
                        else:
                            # 保存收集的数据
                            agent_day_data[name] = collected_data
                            print(f"✅ [{completed_count}/{total_count}] {name} 已完成", flush=True)
                    except Exception as e:
                        import traceback
                        error_detail = traceback.format_exc()
                        print(f"❌ [{completed_count}/{total_count}] {name} 当日处理失败: {e}", flush=True)
                        print(f"   错误详情: {error_detail}", flush=True)
                        agent_errors[name] = str(e)
                        agent_states[name]['error'] = str(e)
                
                # ⭐ 关键检查：处理超时未完成的Agent
                if not_done:
                    remaining_names = [futures[f] for f in not_done]
                    print(f"⚠️ 严重警告：有 {len(not_done)} 个Agent超时未完成: {remaining_names}", flush=True)
                    print(f"   ⚠️ 这将导致数据不同步！", flush=True)
                    print(f"   ⚠️ 强制等待这些Agent完成（即使需要更长时间）", flush=True)
                    
                    # ⭐ 关键：强制等待所有未完成的Agent，不允许跳过
                    # 等待剩余任务完成（额外等待最多5分钟）
                    additional_timeout = 300  # 额外5分钟
                    remaining_done, remaining_not_done = concurrent.futures.wait(
                        not_done,
                        timeout=additional_timeout,
                        return_when=concurrent.futures.ALL_COMPLETED
                    )
                    
                    # 处理最终完成的
                    for future in remaining_done:
                        name = futures[future]
                        completed_count += 1
                        try:
                            _, error, collected_data = future.result(timeout=0)
                            if error:
                                agent_errors[name] = error
                                agent_states[name]['error'] = error
                            else:
                                agent_day_data[name] = collected_data
                            print(f"✅ [{completed_count}/{total_count}] {name} 最终完成", flush=True)
                        except Exception as e:
                            agent_errors[name] = str(e)
                            agent_states[name]['error'] = str(e)
                    
                    # 如果仍有未完成的，强制标记为失败，但允许下一天继续执行以保持同步
                    if remaining_not_done:
                        print(f"❌ 严重警告：仍有 {len(remaining_not_done)} 个Agent严重超时未完成: {[futures[f] for f in remaining_not_done]}", flush=True)
                        print(f"   ⚠️ 标记为失败，但下一天仍会执行以保持同步", flush=True)
                        for future in remaining_not_done:
                            name = futures[future]
                            agent_errors[name] = "严重超时（超过15分钟）"
                            agent_states[name]['error'] = "严重超时"
                            # ⚠️ 不标记为completed，允许下一天继续执行（保持同步）
                
                if agent_errors:
                    print(f"⚠️ 当日有 {len(agent_errors)} 个Agent执行失败: {list(agent_errors.keys())}", flush=True)
                    print(f"   这些Agent的数据可能不完整", flush=True)
                
                # ⭐ 确保所有Agent都已处理（成功或失败）
                actual_completed = len(done)
                print(f"✅ 所有Agent已处理完成 ({actual_completed}/{total_count})", flush=True)
                if actual_completed < total_count:
                    print(f"⚠️ 注意：仍有 {total_count - actual_completed} 个Agent未完成，可能导致数据不同步！", flush=True)
                sys.stdout.flush()
            
            # ✅ 所有AI完成当天交易后的统一回调已移除
            # 原因：每个Agent已经在mixed_callback中实时更新了数据
            # 统一回调会导致trade_history重复保存
            
            # 显示当日排名
            print(f"\n📊 当日资产排名:")
            day_rankings = []
            for info in self.agents:
                name = info['name']
                agent = agent_states[name]['agent']
                profit_pct = ((agent.total_assets - initial_capital) / initial_capital) * 100
                day_rankings.append((name, agent.total_assets, profit_pct))
            
            day_rankings.sort(key=lambda x: x[2], reverse=True)
            for idx, (name, assets, profit_pct) in enumerate(day_rankings):
                medal = ['🥇', '🥈', '🥉'][idx] if idx < 3 else f'{idx+1}.'
                print(f"  {medal} {name}: ¥{assets:.2f} ({profit_pct:+.2f}%)")
        
        # 构建最终结果
        results = {}
        for info in self.agents:
            name = info['name']
            agent = agent_states[name]['agent']
            
            if agent_states[name]['error']:
                results[name] = {
                    'error': agent_states[name]['error'],
                    'color': info['color'],
                    'provider': info['provider']
                }
            else:
                # 计算最终结果
                total_return = ((agent.total_assets - initial_capital) / initial_capital) * 100
                results[name] = {
                    'result': {
                        'total_assets': agent.total_assets,
                        'initial_capital': initial_capital,
                        'total_return': total_return,
                        'trade_count': len(agent.trade_history),
                        'daily_assets': agent.daily_assets
                    },
                    'color': info['color'],
                    'provider': info['provider']
                }
                print(f"\n✅ {name} 完成！收益率: {total_return:+.2f}%")
        
        # 显示排名
        self._show_rankings(results)
        
        return results
    
    def _show_rankings(self, results: Dict[str, Any]):
        """显示排名"""
        print(f"\n{'='*60}")
        print(f"🏆 最终排名")
        print(f"{'='*60}")
        
        # 计算收益率并排序
        rankings = []
        for name, data in results.items():
            if 'result' in data:
                result = data['result']
                profit_pct = ((result['total_assets'] - result['initial_capital']) 
                            / result['initial_capital'] * 100)
                rankings.append({
                    'name': name,
                    'profit_pct': profit_pct,
                    'total_assets': result['total_assets'],
                    'initial_capital': result['initial_capital']
                })
        
        # 按收益率排序
        rankings.sort(key=lambda x: x['profit_pct'], reverse=True)
        
        # 显示
        for idx, rank in enumerate(rankings):
            medal = ['🥇', '🥈', '🥉'][idx] if idx < 3 else f"{idx+1}."
            print(f"{medal} {rank['name']}: {rank['profit_pct']:+.2f}% "
                  f"(¥{rank['total_assets']:.2f})")
        
        print(f"{'='*60}\n")
    
    def get_current_rankings(self) -> List[Dict[str, Any]]:
        """
        获取当前实时排名
        
        Returns:
            排名列表，包含每个AI的信息
        """
        rankings = []
        initial_capital = self.config.get('trading', {}).get('initial_capital', 10000)
        
        for agent_info in self.agents:
            name = agent_info['name']
            agent = agent_info['agent']
            
            # 计算收益率
            profit_pct = ((agent.total_assets - initial_capital) / initial_capital) * 100
            
            # 计算最大回撤
            max_assets = initial_capital
            max_drawdown = 0
            if agent.daily_assets:
                max_assets = max(d['total_assets'] for d in agent.daily_assets)
                current_drawdown = (max_assets - agent.total_assets) / max_assets * 100
                max_drawdown = max(max_drawdown, current_drawdown)
            
            # 计算胜率
            sell_trades = [t for t in agent.trade_history if t.get('action') == 'sell']
            successful_trades = [t for t in sell_trades if t.get('profit', 0) > 0]
            win_rate = len(successful_trades) / len(sell_trades) * 100 if sell_trades else 0
            
            rankings.append({
                'name': name,
                'profit_pct': profit_pct,
                'total_assets': agent.total_assets,
                'cash': agent.cash,
                'holdings_count': len(agent.holdings),
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'trade_count': len(agent.trade_history),
                'color': agent_info['color']
            })
        
        # 按收益率排序
        rankings.sort(key=lambda x: x['profit_pct'], reverse=True)
        
        # 添加排名
        for idx, rank in enumerate(rankings):
            rank['rank'] = idx + 1
            rank['medal'] = ['🥇', '🥈', '🥉', ''][idx] if idx < 4 else ''
        
        return rankings
    
    def get_ranking_context_for_agent(self, agent_name: str, current_day: int, total_days: int) -> Dict[str, Any]:
        """
        获取排名上下文（用于AI Prompt）
        
        Args:
            agent_name: AI名称
            current_day: 当前第几天
            total_days: 总天数
            
        Returns:
            排名上下文字典
        """
        rankings = self.get_current_rankings()
        
        # 找到自己的排名
        your_rank = next((r for r in rankings if r['name'] == agent_name), None)
        if not your_rank:
            print(f"⚠️ 警告：找不到 {agent_name} 的排名！")
            print(f"   可用的AI名称: {[r['name'] for r in rankings]}")
            return {}
        
        # 领先者
        leader = rankings[0]
        
        # 计算进度和阶段
        progress = current_day / total_days
        if progress < 0.3:
            stage = "🌅 前期（建仓期）"
            strategy = "积极寻找优质标的，建立仓位"
        elif progress < 0.7:
            stage = "🏃 中期（持仓期）"
            strategy = "保持仓位，动态调整，抓住波段机会"
        else:
            stage = "🔥 冲刺期（决胜期）"
            strategy = "⚠️ 最后冲刺！该冒险时就要冒险！"
        
        # 生成排名评论
        rank_num = your_rank['rank']
        profit = your_rank['profit_pct']
        
        if rank_num == 1:
            if profit > 5:
                comment = "表现优异，继续保持优势"
            elif profit > 0:
                comment = "暂时领先，可进一步扩大差距"
            else:
                comment = "排名第一但收益为负，建议调整策略改善收益率"
        elif rank_num == 2:
            comment = "排名第二，有机会超越第一名"
        elif rank_num == 3:
            comment = "中游水平，可寻找机会提升排名"
        else:
            comment = "排名较低，建议分析策略并寻找改进机会"
        
        # 生成今日目标
        if rank_num == 1:
            goal = f"保持第一，争取今日收益+0.5%扩大优势"
        elif rank_num == 2:
            gap = leader['profit_pct'] - profit
            goal = f"追赶第一名，争取今日缩小差距至少{gap/3:.2f}%"
        elif rank_num == 3:
            goal = f"冲击前二，建议今日进行盈利交易，目标+1%"
        else:
            goal = f"提升排名，建议分析机会并进行合理交易"
        
        return {
            'rankings': rankings,
            'your_rank': your_rank,
            'leader': leader,
            'gap_to_leader': leader['profit_pct'] - profit,
            'current_day': current_day,
            'total_days': total_days,
            'progress': progress,
            'stage': stage,
            'strategy': strategy,
            'comment': comment,
            'goal': goal
        }

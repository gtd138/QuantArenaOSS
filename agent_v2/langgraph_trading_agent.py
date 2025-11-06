"""
LangGraph版交易Agent
使用状态图管理复杂的交易决策流程
"""
from typing import TypedDict, List, Dict, Any, Annotated, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from datetime import datetime
import json
import time

# 导入新闻服务和提示词
from services.akshare_news_service import get_news_service
from prompts.simple_trading_prompt import (
    get_simple_sell_prompt,
    get_simple_buy_prompt
)
from prompts.trading_prompts import (
    get_reflection_prompt,  # 反思提示词暂时保留原版
    STOP_SIGNAL
)
from agent_v2.motivation_engine import MotivationEngine
# Phase 5: 导入数据增强模块
from services.enhanced_data_provider import EnhancedDataProvider
# Phase 4: 导入持久化模块以支持经验管理
from persistence.arena_persistence import get_arena_persistence


class TradingState(TypedDict):
    """交易状态"""
    # 基础信息
    trade_date: str
    session_id: str
    
    # 账户状态
    cash: float
    initial_capital: float
    holdings: Dict[str, Dict[str, Any]]
    total_assets: float
    
    # 决策数据
    candidates: List[Dict[str, Any]]
    sell_analysis: Dict[str, Any]
    buy_analysis: Dict[str, Any]
    index_data: Dict[str, Dict[str, float]]  # 指数数据
    
    # 执行结果
    sell_trades: List[Dict[str, Any]]
    buy_trades: List[Dict[str, Any]]
    
    # 历史记录
    trade_history: List[Dict[str, Any]]
    daily_assets: List[Dict[str, Any]]
    
    # AI日志
    ai_logs: List[str]
    
    # 反思数据
    reflection: Dict[str, Any]
    
    # 竞技场排名上下文
    ranking_context: Dict[str, Any]
    hot_codes: List[str]
    hot_sectors: List[Dict[str, Any]]


class LangGraphTradingAgent:
    """基于LangGraph的交易Agent"""
    
    def __init__(self, data_provider, config: Dict[str, Any], model_provider: str = 'deepseek'):
        """
        初始化LangGraph Agent
        
        Args:
            data_provider: 数据提供者 (Baostock)
            config: 配置信息
            model_provider: 模型提供商 ('deepseek' 或 'qwen')
        """
        self.data_provider = data_provider
        self.config = config.get('trading', {})
        self.model_provider = model_provider
        
        # 🔍 调试：打印配置值
        print(f"🔍 [{model_provider}] 配置检查:", flush=True)
        print(f"   max_price = {self.config.get('max_price', 50)}", flush=True)
        print(f"   analyze_stock_count = {self.config.get('analyze_stock_count', 20)}", flush=True)
        
        # 停止标志
        self.should_stop_callback = None
        
        # 模型显示名称（从配置文件读取）
        arena_config = config.get('arena', {})
        model_display_name = model_provider  # 默认使用 provider 名称
        for model_config in arena_config.get('models', []):
            if model_config.get('provider') == model_provider:
                model_display_name = model_config.get('name', model_provider)
                break
        self.model_display_name = model_display_name
        
        # 初始化账户状态（用于UI兼容）
        self.initial_capital = self.config.get('initial_capital', 10000)
        self.cash = self.initial_capital
        self.holdings = {}
        self.total_assets = self.initial_capital
        self.trade_history = []
        self.daily_assets = []
        
        # Phase 4: 初始化持久化管理器（用于经验管理）
        self.persistence = get_arena_persistence()
        self.session_id = None  # 将在run_single_day时设置
        
        # 🔧 开始初始化，添加进度输出
        print(f"🔧 [{self.model_display_name}] 开始初始化...", flush=True)
        
        # 初始化LLM（根据provider选择）
        print(f"🤖 [{self.model_display_name}] 正在初始化LLM模型...", flush=True)
        self.llm = self._create_llm(config, model_provider)
        print(f"✅ [{self.model_display_name}] LLM模型就绪", flush=True)
        
        # 初始化新闻服务
        print(f"📰 [{self.model_display_name}] 正在初始化新闻服务...", flush=True)
        self.news_service = get_news_service()
        print(f"✅ [{self.model_display_name}] 新闻服务就绪", flush=True)
        
        # 初始化动机引擎
        print(f"🎯 [{self.model_display_name}] 正在初始化动机引擎...", flush=True)
        self.motivation_engine = MotivationEngine()
        print(f"✅ [{self.model_display_name}] 动机引擎就绪", flush=True)
        
        # Phase 5: 初始化数据增强提供者
        print(f"📊 [{self.model_display_name}] 正在初始化数据增强模块...", flush=True)
        self.enhanced_data = EnhancedDataProvider()
        print(f"✅ [{self.model_display_name}] 数据增强模块就绪", flush=True)
        
        # 构建状态图
        print(f"🔧 [{self.model_display_name}] 正在构建交易状态图...", flush=True)
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
        print(f"✅ [{self.model_display_name}] 状态图构建完成", flush=True)
        
        # 🎉 初始化完成
        print(f"🎉 [{self.model_display_name}] Agent初始化完成", flush=True)
    
    def _log(self, state, message):
        """统一日志输出，添加模型名称标识（仅控制台，不发送UI）"""
        prefixed_msg = f"[{self.model_display_name}] {message}"
        print(prefixed_msg, flush=True)
        # ❌ 不再发送到UI - 操作日志已有表格展示
        # state['ai_logs'].append(prefixed_msg)
    
    def _log_thinking(self, state, thinking_content):
        """AI思考日志（发送到UI展示）- 类似AlphaArena"""
        current_time = datetime.now().strftime('%H:%M:%S')
        prefixed_msg = f"[{self.model_display_name}] [{current_time}] 💭 {thinking_content}"
        print(prefixed_msg, flush=True)
        state['ai_logs'].append(prefixed_msg)
    
    def _load_agent_principles(self, state: TradingState) -> List[str]:
        """
        Phase 4: 加载Agent的交易原则
        
        Returns:
            交易原则列表
        """
        if not self.session_id:
            return []
        
        try:
            principles = self.persistence.get_agent_principles(
                session_id=self.session_id,
                model_name=self.model_provider
            )
            return principles
        except Exception as e:
            self._log(state, f"⚠️ 加载交易原则失败: {e}")
            return []
    
    def _is_insufficient_balance_error(self, e: Exception) -> bool:
        """
        检查异常是否为API余额不足错误（错误码 1113）
        
        Args:
            e: 异常对象
            
        Returns:
            如果是余额不足错误，返回True
        """
        # 方法1: 尝试从response对象获取错误信息
        if hasattr(e, 'response') and hasattr(e.response, 'json'):
            try:
                error_data = e.response.json()
                if isinstance(error_data, dict):
                    error_info = error_data.get('error', {})
                    error_code = error_info.get('code', '')
                    # 错误码 1113 表示余额不足
                    if error_code == '1113' or '余额不足' in str(error_info.get('message', '')):
                        return True
            except:
                pass
        
        # 方法2: 从错误消息字符串中检测
        error_str = str(e).lower()
        if '1113' in error_str or '余额不足' in error_str or '无可用资源包' in error_str:
            return True
        
        return False
    
    def _extract_json_array(self, content: str):
        """
        从文本中提取JSON数组
        
        处理AI可能返回的各种格式：
        - 纯JSON
        - JSON + 额外文本
        - Markdown代码块中的JSON
        """
        import re
        import json
        
        # 方法1: 尝试直接解析整个内容
        try:
            return json.loads(content.strip())
        except:
            pass
        
        # 方法2: 提取```json ... ```代码块
        code_block_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except:
                pass
        
        # 方法3: 查找第一个完整的JSON数组（使用栈匹配）
        start_idx = content.find('[')
        if start_idx == -1:
            return None
        
        bracket_count = 0
        in_string = False
        escape_next = False
        
        for i in range(start_idx, len(content)):
            char = content[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        # 找到完整的JSON数组
                        json_str = content[start_idx:i+1]
                        try:
                            return json.loads(json_str)
                        except:
                            return None
        
        return None
    
    def _create_llm(self, config: Dict[str, Any], provider: str):
        """
        创建LLM实例
        
        Args:
            config: 配置信息
            provider: 模型提供商
            
        Returns:
            LLM实例
        """
        if provider == 'deepseek':
            model_config = config.get('deepseek', {})
            return ChatOpenAI(
                base_url=model_config.get('api_base', 'https://api.deepseek.com'),
                api_key=model_config.get('api_key'),
                model=model_config.get('model', 'deepseek-chat'),
                temperature=0.3,
                timeout=600,  # ⚡ AI Agent需要足够时间思考（10分钟）
                max_retries=3,  # 重试3次（平衡等待时间和成功率）
                request_timeout=600,  # 请求超时600秒
                max_tokens=4096  # 限制最大token数
            )
        elif provider == 'qwen':
            model_config = config.get('qwen', {})
            return ChatOpenAI(
                base_url=model_config.get('api_base', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
                api_key=model_config.get('api_key'),
                model=model_config.get('model', 'qwen-max'),
                temperature=0.3,
                timeout=600,  # ⚡ AI Agent需要足够时间思考（10分钟）
                max_retries=5,  # 重试5次（Qwen可能需要更多重试）
                request_timeout=600,  # 请求超时600秒
                max_tokens=4096  # 限制最大token数
            )
        elif provider == 'glm':
            model_config = config.get('glm', {})
            # 构建基础参数
            llm_kwargs = {
                'base_url': model_config.get('api_base', 'https://open.bigmodel.cn/api/paas/v4'),
                'api_key': model_config.get('api_key'),
                'model': model_config.get('model', 'glm-4.6'),
                'temperature': 0.3,
                'timeout': 600,
                'max_retries': 5,
                'request_timeout': 600,
                'max_tokens': 4096
            }
            # 🔧 只有显式启用思考模式时才传递参数（GLM API不支持该参数，默认不传）
            if model_config.get('enable_thinking', False):
                llm_kwargs['model_kwargs'] = {'enable_thinking': True}
            return ChatOpenAI(**llm_kwargs)
        elif provider == 'kimi':
            model_config = config.get('kimi', {})
            # ⚠️ 注意：Kimi-K2使用Moonshot API
            # 从config.json读取配置，如果没有则使用默认值
            api_base = model_config.get('api_base', 'https://api.moonshot.cn/v1')
            api_key = model_config.get('api_key')
            model_name = model_config.get('model', 'kimi-k2-turbo-preview')
            
            print(f"🔧 [Kimi配置] api_base={api_base}, model={model_name}", flush=True)
            
            return ChatOpenAI(
                base_url=api_base,
                api_key=api_key,
                model=model_name,
                temperature=0.3,
                timeout=600,  # ⚡ 增加到600秒（10分钟）- AI Agent需要足够时间思考
                max_retries=3,  # 重试3次（平衡等待时间和成功率）
                request_timeout=600,  # 请求超时600秒
                max_tokens=4096
            )
        elif provider == 'doubao':
            model_config = config.get('doubao', {})
            # 构建基础参数
            llm_kwargs = {
                'base_url': model_config.get('api_base', 'https://ark.cn-beijing.volces.com/api/v3'),
                'api_key': model_config.get('api_key'),
                'model': model_config.get('model', 'doubao-seed-1-6-251015'),
                'temperature': 0.3,
                'timeout': 600,
                'max_retries': 5,
                'request_timeout': 600,
                'max_tokens': 4096
            }
            # 🔧 只有显式启用思考模式时才传递参数（Doubao API不支持该参数，默认不传）
            if model_config.get('enable_thinking', False):
                llm_kwargs['model_kwargs'] = {'enable_thinking': True}
            return ChatOpenAI(**llm_kwargs)
        else:
            raise ValueError(f"Unsupported model provider: {provider}")
        
    def _build_workflow(self) -> StateGraph:
        """构建LangGraph工作流"""
        workflow = StateGraph(TradingState)
        
        # 添加节点
        workflow.add_node("update_prices", self._update_holdings_prices)
        workflow.add_node("evaluate_holdings", self._evaluate_holdings)
        workflow.add_node("execute_sells", self._execute_sells)
        workflow.add_node("find_candidates", self._find_candidates)
        workflow.add_node("analyze_candidates", self._analyze_candidates)
        workflow.add_node("execute_buys", self._execute_buys)
        workflow.add_node("record_daily", self._record_daily_assets)
        workflow.add_node("reflect", self._daily_reflection)
        
        # 定义流程
        workflow.set_entry_point("update_prices")
        workflow.add_edge("update_prices", "evaluate_holdings")
        workflow.add_edge("evaluate_holdings", "execute_sells")
        workflow.add_edge("execute_sells", "find_candidates")
        workflow.add_edge("find_candidates", "analyze_candidates")
        workflow.add_edge("analyze_candidates", "execute_buys")
        workflow.add_edge("execute_buys", "record_daily")
        workflow.add_edge("record_daily", "reflect")
        workflow.add_edge("reflect", END)
        
        return workflow
    
    def _normalize_trade_date(self, trade_date: str) -> str:
        """
        标准化交易日期格式为 YYYYMMDD（去掉横线）
        
        Args:
            trade_date: 可能是 "2025-01-15" 或 "20250115"
            
        Returns:
            "20250115"
        """
        return trade_date.replace('-', '')
    
    def _get_holdings_news(self, state: TradingState) -> str:
        """
        获取持仓股票的最新新闻（优化性能）
        
        Returns:
            格式化的新闻摘要
        """
        if not state['holdings']:
            return "暂无持仓"
        
        # 标准化日期格式，确保与新闻服务匹配（防前瞻）
        normalized_date = self._normalize_trade_date(state['trade_date'])
        
        # ⚡ 优化：减少新闻查询，每只股票只查1条
        news_texts = []
        for code in list(state['holdings'].keys())[:2]:  # 最多查询2只持仓股票（降低到2只）
            try:
                import time
                start = time.time()
                
                news_list = self.news_service.get_stock_news(
                    stock_code=code,
                    trade_date=normalized_date,  # 使用标准化日期
                    max_news=1  # ⚡ 每只股票只查1条（降低到1条）
                )
                
                elapsed = time.time() - start
                print(f"  [新闻服务] {code} 耗时{elapsed:.2f}秒，获取{len(news_list)}条", flush=True)
                
                if news_list:
                    stock_info = self.data_provider.get_stock_basic_info(code)
                    stock_name = stock_info.get('name', code)
                    news_texts.append(f"\n📰 {stock_name}: {news_list[0]['title'][:40]}...")
            except Exception as e:
                print(f"  [新闻服务] {code} 失败: {e}", flush=True)
                continue
        
        return "\n".join(news_texts) if news_texts else "暂无重要新闻"
    
    def _get_market_news(self, state: TradingState) -> str:
        """
        获取市场热点新闻（优化性能）
        
        Returns:
            格式化的新闻摘要
        """
        try:
            import time
            start = time.time()
            
            # 标准化日期格式，确保与新闻服务匹配（防前瞻）
            normalized_date = self._normalize_trade_date(state['trade_date'])
            
            news_list = self.news_service.get_market_hot_news(
                trade_date=normalized_date,  # 使用标准化日期
                max_news=2  # ⚡ 降低到2条（原来3条）
            )
            
            elapsed = time.time() - start
            print(f"  [新闻服务] 市场热点耗时{elapsed:.2f}秒，获取{len(news_list)}条", flush=True)
            
            if news_list:
                # ⚡ 简化输出，只显示标题
                titles = [news['title'][:40] for news in news_list[:2]]
                return f"📰 市场: {' / '.join(titles)}"
        except Exception as e:
            print(f"  [新闻服务] 市场热点失败: {e}", flush=True)
            pass
        
        return ""
    
    def _update_holdings_prices(self, state: TradingState) -> TradingState:
        """更新持仓价格"""
        trade_date = state['trade_date']
        holdings = state['holdings']
        
        current_time = datetime.now().strftime('%H:%M:%S')
        self._log(state, f"[{current_time}] 📊 更新持仓价格 ({trade_date})")
        
        price_update_failed = []
        
        for code in list(holdings.keys()):
            stock_data = self.data_provider.get_daily_price(code, trade_date)
            if stock_data:
                current_price = stock_data.get('close', 0)
                if current_price > 0:  # 确保价格有效
                    holdings[code]['current_price'] = current_price
                    cost = holdings[code]['cost']
                    # ✅ 修复：防止除零错误（数据恢复时可能cost为0）
                    if cost > 0:
                        holdings[code]['profit_pct'] = ((current_price - cost) / cost) * 100
                    else:
                        holdings[code]['profit_pct'] = 0
                        # 如果成本为0，说明数据异常，用当前价格作为成本
                        holdings[code]['cost'] = current_price
                    holdings[code]['hold_days'] = holdings[code].get('hold_days', 0) + 1
                else:
                    # 价格为0，保持前一天价格不变
                    holdings[code]['hold_days'] = holdings[code].get('hold_days', 0) + 1
                    price_update_failed.append(f"{code}(价格为0)")
                
                # ✅ 确保name字段存在（如果没有则从股票基本信息获取）
                if 'name' not in holdings[code] or not holdings[code].get('name'):
                    stock_info = self.data_provider.get_stock_basic_info(code)
                    holdings[code]['name'] = stock_info.get('name', code)
            else:
                # 无法获取数据（停牌/退市等），保持前一天价格不变
                holdings[code]['hold_days'] = holdings[code].get('hold_days', 0) + 1
                price_update_failed.append(f"{code}(无数据)")
        
        # 记录价格更新失败的股票
        if price_update_failed:
            self._log(state, f"  ⚠️ {len(price_update_failed)}只股票价格未更新: {', '.join(price_update_failed[:3])}")
        
        # 更新总资产
        holdings_value = sum(
            h['amount'] * h.get('current_price', h.get('cost', 0))  # 使用current_price，如果没有则用cost
            for h in holdings.values()
        )
        state['total_assets'] = state['cash'] + holdings_value
        
        return state
    
    def _evaluate_holdings(self, state: TradingState) -> TradingState:
        """评估持仓"""
        # 检查是否停止
        if self.should_stop_callback and self.should_stop_callback():
            state['sell_analysis'] = {'decisions': []}
            return state
        
        if not state['holdings']:
            state['sell_analysis'] = {'decisions': []}
            return state
        
        current_time = datetime.now().strftime('%H:%M:%S')
        self._log(state, f"[{current_time}] 🤖 评估持仓...")
        
        # ✅ 防御性检查：确保所有持仓都有name字段（在评估前修复）
        for code in state['holdings'].keys():
            if 'name' not in state['holdings'][code] or not state['holdings'][code].get('name'):
                stock_info = self.data_provider.get_stock_basic_info(code)
                state['holdings'][code]['name'] = stock_info.get('name', code)
        
        # 🔴 硬性止盈止损检查（系统强制执行，不依赖AI）
        stop_loss_pct = self.config.get('stop_loss_pct', 0.05) * 100  # 转换为百分比
        stop_profit_pct = self.config.get('stop_profit_pct', 0.15) * 100
        
        forced_sells = []  # 强制卖出列表
        
        for code, holding in state['holdings'].items():
            profit_pct = holding.get('profit_pct', 0)
            stock_info = self.data_provider.get_stock_basic_info(code)
            name = stock_info.get('name', '未知')
            
            # 强制止损
            if profit_pct <= -stop_loss_pct:
                forced_sells.append({
                    'action': 'sell',  # ✅ 添加action字段
                    'code': code,      # ✅ 使用code而不是stock_code
                    'amount': holding['amount'],
                    'reason': f'🔴 系统强制止损（亏损{abs(profit_pct):.1f}%≥{stop_loss_pct}%）'
                })
                self._log(state, f"  🔴 [{current_time}] 强制止损: {name}({code}) 亏损{abs(profit_pct):.1f}%")
            
            # 强制止盈
            elif profit_pct >= stop_profit_pct:
                forced_sells.append({
                    'action': 'sell',  # ✅ 添加action字段
                    'code': code,      # ✅ 使用code而不是stock_code
                    'amount': holding['amount'],
                    'reason': f'🟢 系统强制止盈（盈利{profit_pct:.1f}%≥{stop_profit_pct}%）'
                })
                self._log(state, f"  🟢 [{current_time}] 强制止盈: {name}({code}) 盈利{profit_pct:.1f}%")
        
        # 如果有强制卖出，直接返回，不再让AI分析
        if forced_sells:
            self._log(state, f"  ⚠️ 系统强制执行止盈止损，共{len(forced_sells)}只股票")
            state['sell_analysis'] = {'decisions': forced_sells}
            return state
        
        # 准备持仓数据（供AI分析）
        holdings_data = []
        for code, holding in state['holdings'].items():
            stock_info = self.data_provider.get_stock_basic_info(code)
            holdings_data.append({
                'code': code,
                'name': stock_info.get('name', '未知'),
                'amount': holding['amount'],
                'cost': holding['cost'],
                'current_price': holding.get('current_price', 0),
                'profit_pct': holding.get('profit_pct', 0),
                'hold_days': holding.get('hold_days', 0)
            })
        
        # 获取策略配置
        strategy = self.config.get('strategy', 'short_term')
        target_hold_days = self.config.get('target_hold_days', 5)
        
        # 策略描述
        strategy_map = {
            'short_term': f'短线交易（参考{target_hold_days}天，快进快出）',
            'mid_term': f'中线交易（参考{target_hold_days}天，趋势跟踪）',
            'long_term': f'长线投资（参考{target_hold_days}天，价值投资）'
        }
        strategy_desc = strategy_map.get(strategy, strategy_map['short_term'])
        
        # 计算盈亏
        current_profit = state['total_assets'] - state['initial_capital']
        profit_pct = (current_profit / state['initial_capital']) * 100
        
        # ⭐ 构建竞技场排名信息（如果有）
        ranking_header = ""
        ranking_context = state.get('ranking_context', {})
        if ranking_context and ranking_context.get('rankings'):
            your_rank = ranking_context.get('your_rank', {})
            rankings = ranking_context.get('rankings', [])
            leader = ranking_context.get('leader', {})
            current_day = ranking_context.get('current_day', 1)
            total_days = ranking_context.get('total_days', 195)
            stage = ranking_context.get('stage', '')
            comment = ranking_context.get('comment', '')
            goal = ranking_context.get('goal', '')
            gap = ranking_context.get('gap_to_leader', 0)
            
            # 格式化排名列表（明确标注第一名）
            rank_lines = []
            for r in rankings[:4]:  # 显示前4名
                medal = r.get('medal', '')
                rank_num = r.get('rank', 0)
                name = r.get('name', '')
                profit = r.get('profit_pct', 0)
                is_you = (name == your_rank.get('name', ''))
                
                # ✅ 更明确的标注
                if rank_num == 1:
                    indicator = "👑 当前第一名（领先所有人）" if not is_you else "👑 你是第一名！"
                elif is_you:
                    indicator = f"👈 你排第{rank_num}名"
                else:
                    indicator = ""
                    
                rank_lines.append(f"{medal} 第{rank_num}名: {name:<15} 收益率{profit:+.2f}%  {indicator}")
            
            # 生成激励话术
            motivation_message = self.motivation_engine.get_motivation_message(
                ranking_context, 
                state['total_assets'], 
                state['initial_capital']
            )
            
            # 生成纪律提醒
            discipline_reminder = self.motivation_engine.get_discipline_reminder(
                state['cash'],
                state['total_assets']
            )
            
            ranking_header = f"""
🏆 LHArena Season 1 竞技场 - Day {current_day}/{total_days}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 实时排名（LIVE）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(rank_lines)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{motivation_message}

{discipline_reminder}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        # 获取上次反思内容
        reflection_text = ""
        if state.get('reflection') and state['reflection'].get('reflection_text'):
            reflection_text = f"""
📝 **上次反思总结**（建议参考）：
{state['reflection']['reflection_text'][:300]}

建议参考上述反思内容，避免重复之前的错误。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # 📰 获取持仓股票的最新新闻
        news_summary = self._get_holdings_news(state)
        
        # Phase 4: 加载Agent的交易原则
        agent_principles = self._load_agent_principles(state)
        
        # 构建prompt（使用简化提示词模板）
        prompt = get_simple_sell_prompt(
            trade_date=state['trade_date'],
            cash=state['cash'],
            total_assets=state['total_assets'],
            holdings=state['holdings'],
            model_name=self.model_display_name,
            index_data=state.get('index_data', {}),
            recent_news=news_summary,
            initial_capital=self.initial_capital
        )
        
        # 添加竞技场排名信息（简化提示词暂不支持）
        # if ranking_header:
        #     prompt = ranking_header + "\n" + prompt
        
        # 添加反思内容（简化提示词暂不支持反思内容嵌入）
        # if reflection_text:
        #     prompt = prompt.replace("【最新资讯】", reflection_text + "\n【最新资讯】")
        
        # 重试机制（指数退避）
        max_retries = 3  # ⚡ 优化：最多重试3次（原来5次）
        base_retry_delay = 2  # ⚡ 优化：基础延迟2秒（原来3秒）
        
        for attempt in range(max_retries):
            try:
                import time as time_module
                start_time = time_module.time()
                self._log(state, f"  [尝试 {attempt+1}/{max_retries}] 正在调用AI API评估持仓...")
                response = self.llm.invoke(prompt)
                elapsed = time_module.time() - start_time
                self._log(state, f"  ✅ AI API调用成功，耗时 {elapsed:.1f}秒")
                content = response.content
                
                # 解析JSON（使用智能JSON提取）
                decisions = self._extract_json_array(content)
                if decisions:
                    # ✨ 容错处理：修复缺失的stock_code字段
                    fixed_decisions = []
                    for dec in decisions:
                        if not isinstance(dec, dict):
                            continue
                        
                        # ✨ 容错1：尝试多个字段名获取股票代码
                        code = (
                            dec.get('stock_code') or 
                            dec.get('code') or 
                            dec.get('stock')
                        )
                        
                        # ✨ 容错2：如果仍然没有，尝试从名称反查
                        if not code and dec.get('name'):
                            stock_name = dec.get('name')
                            for holding_code, info in state['holdings'].items():
                                if info.get('name') == stock_name:
                                    code = holding_code
                                    self._log(state, f"  🔧 从名称'{stock_name}'反查到代码: {code}")
                                    break
                        
                        # ✨ 容错3：如果只有一只持仓，默认就是它
                        if not code and len(state['holdings']) == 1:
                            code = list(state['holdings'].keys())[0]
                            self._log(state, f"  🔧 单只持仓自动推断代码: {code}")
                        
                        # 最终检查
                        if not code:
                            self._log(state, f"  ⚠️ 卖出决策缺少股票代码，已忽略: {dec.get('reason', '未知原因')[:30]}")
                            continue
                        
                        # 验证code是否在持仓中
                        if code not in state['holdings']:
                            self._log(state, f"  ⚠️ 股票代码不在持仓中，已忽略: {code}")
                            continue
                        
                        # 修复decision对象，统一使用'code'字段
                        dec['code'] = code
                        fixed_decisions.append(dec)
                        
                        # 记录日志
                        if dec.get('action') == 'sell':
                            emoji = "📤"
                            current_time = datetime.now().strftime('%H:%M:%S')
                            confidence = dec.get('confidence', 0.0)
                            reason = dec.get('reason', '无原因')
                            self._log(state, f"  [{current_time}] {emoji} {code}: sell (置信度: {confidence:.2f}) - {reason[:50]}")
                    
                    state['sell_analysis'] = {'decisions': fixed_decisions}
                    break  # 成功，退出重试循环
                else:
                    state['sell_analysis'] = {'decisions': []}
                    break
                    
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                self._log(state, f"❌ 评估持仓失败 (尝试 {attempt+1}/{max_retries}): {e}")
                print(f"完整错误: {error_detail}", flush=True)
                
                # 检查是否为余额不足错误（错误码 1113）
                if self._is_insufficient_balance_error(e):
                    self._log(state, f"💳 ❌ API余额不足，无法继续分析。请充值后重试。")
                    state['sell_analysis'] = {'decisions': []}
                    break  # 立即退出重试循环
                
                if attempt < max_retries - 1:
                    # 指数退避：3秒、6秒、12秒、24秒、48秒
                    retry_delay = base_retry_delay * (2 ** attempt)
                    self._log(state, f"⏳ {retry_delay}秒后重试...（指数退避策略）")
                    time.sleep(retry_delay)
                else:
                    self._log(state, f"❌ 已达最大重试次数，跳过本次卖出分析")
                    state['sell_analysis'] = {'decisions': []}
        
        return state
    
    def _execute_sells(self, state: TradingState) -> TradingState:
        """执行卖出"""
        decisions = state['sell_analysis'].get('decisions', [])
        sell_trades = []
        processed_codes: set[str] = set()
        
        for decision in decisions:
            # 确保decision是字典类型
            if not isinstance(decision, dict):
                continue
            if decision.get('action') != 'sell':
                continue
                
            code = decision.get('code')
            if not code:
                continue
            if code in processed_codes:
                current_time = datetime.now().strftime('%H:%M:%S')
                self._log(state, f"  [{current_time}] ⚠️ 跳过重复卖出指令: {code}")
                continue
            processed_codes.add(code)
            if code not in state['holdings']:
                continue
        
            holding = state['holdings'][code]
            
            # T+1检查
            if holding.get('hold_days', 0) == 0:
                current_time = datetime.now().strftime('%H:%M:%S')
                self._log(state, f"  [{current_time}] ⚠️ {code} T+1限制，明天才能卖")
                continue
            
            # 执行卖出
            amount = holding['amount']
            current_price = holding['current_price']
            
            # 计算收入
            sell_amount = amount * current_price
            commission = max(sell_amount * 0.0003, 5)
            stamp_tax = sell_amount * 0.001
            net_income = sell_amount - commission - stamp_tax
            
            # 计算利润
            cost_total = amount * holding['cost']
            profit = net_income - cost_total
            profit_pct = (profit / cost_total) * 100
            
            # 更新账户
            state['cash'] += net_income
            del state['holdings'][code]
            
            # 获取股票名称
            stock_info = self.data_provider.get_stock_basic_info(code)
            
            # 记录交易
            trade_record = {
                'date': state['trade_date'],
                'time': datetime.now().strftime('%H:%M:%S'),
                'action': 'sell',
                'code': code,
                'name': stock_info.get('name', '未知'),
                'amount': amount,
                'price': current_price,
                'total': sell_amount,
                'commission': commission + stamp_tax,
                'profit': profit,
                'profit_pct': profit_pct,
                'reason': decision.get('reason', 'AI决策卖出')
            }
            
            sell_trades.append(trade_record)
            state['trade_history'].append(trade_record)
            
            # 日志（控制台）
            emoji = "🟢" if profit > 0 else "🔴"
            current_time = datetime.now().strftime('%H:%M:%S')
            self._log(state, f"  [{current_time}] {emoji} 卖出: {code}, {amount}股 @ {current_price:.2f}元, 利润: {profit:+.2f}元 ({profit_pct:+.2f}%)")
            
            # ✅ 思考说明（发送到UI）- AI内心独白
            name = stock_info.get('name', '未知')
            reason = decision.get('reason', '策略卖出')
            confidence = decision.get('confidence', 0)
            
            thinking = f"💭 {reason}"
            self._log_thinking(state, thinking)
        
        state['sell_trades'] = sell_trades
        return state
    
    def _find_candidates(self, state: TradingState) -> TradingState:
        """查找候选股票"""
        # 检查是否停止
        if self.should_stop_callback and self.should_stop_callback():
            state['candidates'] = []
            return state
        
        current_time = datetime.now().strftime('%H:%M:%S')
        
        # 检查是否有足够资金买入
        min_cash_to_buy = self.config.get('min_cash_to_buy', 500)
        if state['cash'] < min_cash_to_buy:
            self._log(state, f"[{current_time}] ⚠️ 现金不足{min_cash_to_buy}元，跳过选股（当前: {state['cash']:.2f}元）")
            state['candidates'] = []
            return state
        
        self._log(state, f"[{current_time}] 🔍 查找候选股票...")
        
        # 获取指数数据
        index_data = self.data_provider.get_index_data(state['trade_date'])
        state['index_data'] = index_data
        
        # 输出指数信息
        if index_data:
            index_info = []
            if 'sh_index' in index_data:
                sh_pct = index_data['sh_index'].get('pct_chg', 0)
                index_info.append(f"上证 {sh_pct:+.2f}%")
            if 'hs300' in index_data:
                hs_pct = index_data['hs300'].get('pct_chg', 0)
                index_info.append(f"沪深300 {hs_pct:+.2f}%")
            if index_info:
                self._log(state, f"[{current_time}] 📊 大盘走势: {', '.join(index_info)}")
        
        pool_info = self.data_provider.get_candidate_pool(state['trade_date'])
        existing_hot_codes = set(state.get('hot_codes', []))
        pool_hot_codes = pool_info.get('hot_codes', [])
        hot_codes = list(dict.fromkeys(list(existing_hot_codes) + pool_hot_codes))
        hot_sectors = pool_info.get('hot_sectors', []) or state.get('hot_sectors', [])
        start_fetch = time.time()
        candidates = self.data_provider.get_candidates(
            trade_date=state['trade_date'],
            max_price=self.config.get('max_price', 50),
            limit=self.config.get('analyze_stock_count', 20) * 5
        )
        elapsed_fetch = time.time() - start_fetch
        if candidates:
            cache_tag = "缓存命中" if pool_info.get('candidates') else "退化遍历"
        else:
            cache_tag = "候选为空"
        self._log(state, f"[{current_time}] 📦 候选获取({cache_tag}) - 耗时 {elapsed_fetch:.2f}s, 热点 {len(hot_codes)} 只")
        state['hot_sectors'] = hot_sectors
        state['hot_codes'] = hot_codes

        if candidates and hot_codes:
            hot_set = set(hot_codes)
            hot_candidates = [c for c in candidates if c.get('code') in hot_set]
            other_candidates = [c for c in candidates if c.get('code') not in hot_set]
            candidates = hot_candidates + other_candidates

        # 选取候选数量
        analyze_count = self.config.get('analyze_stock_count', 20)
        
        # 🔄 轮换批次策略：根据日期和模型名称轮换，确保不同AI看到不同批次
        # 将日期转为数字，例如 20240102 -> 2
        trade_date_int = int(state['trade_date'])
        
        # 根据模型提供商计算不同的偏移量
        model_offset = {
            'deepseek': 0,
            'qwen': 1,
            'glm': 2,
            'kimi': 3
        }.get(self.model_provider, 0)
        
        # 组合日期和模型偏移，确保：
        # - 同一天，不同AI看到不同批次
        # - 不同天，同一AI也会轮换
        batch_number = (trade_date_int + model_offset) % 5  # 5个批次轮换（增加多样性）
        start_idx = batch_number * analyze_count
        end_idx = start_idx + analyze_count
        
        # 确保不超出范围
        if start_idx < len(candidates):
            state['candidates'] = candidates[start_idx:end_idx]
            batch_info = f"批次{batch_number + 1}（第{start_idx + 1}-{min(end_idx, len(candidates))}名）"
        else:
            # 如果超出范围，回到第一批
            state['candidates'] = candidates[:analyze_count]
            batch_info = "批次1（第1-20名）"
        
        current_time = datetime.now().strftime('%H:%M:%S')
        self._log(state, f"  [{current_time}] 找到 {len(state['candidates'])} 只候选股票 - {batch_info}")
        
        return state
    
    def _analyze_candidates(self, state: TradingState) -> TradingState:
        """分析候选股票"""
        # 检查是否停止
        if self.should_stop_callback and self.should_stop_callback():
            state['buy_analysis'] = {'decisions': []}
            return state
        
        if not state['candidates']:
            state['buy_analysis'] = {'decisions': []}
            return state
        
        current_time = datetime.now().strftime('%H:%M:%S')
        self._log(state, f"[{current_time}] 🤖 分析候选股票...")
        self._log(state, f"[{current_time}] 🤖 AI分析候选股票...")
        
        # 计算当前表现
        daily_profit = state['total_assets'] - state['initial_capital']
        profit_pct = (daily_profit / state['initial_capital']) * 100
        
        # 根据盈亏调整策略（平衡风控和收益）
        if profit_pct < -5:
            strategy_tone = "⚠️ 当前亏损较大，适度控制节奏，但不能完全停止交易。"
            target = "寻找中等确定性机会（置信度≥0.70），保持适度仓位"
        elif profit_pct < 0:
            strategy_tone = "📊 当前轻微亏损，正常波动，按量化规则正常交易。"
            target = "积极寻找优质标的，通过交易扭亏"
        elif profit_pct < 10:
            strategy_tone = "📈 表现正常，继续执行量化策略，稳中有进。"
            target = "积极寻找优质标的，扩大收益"
        else:
            strategy_tone = "✅ 表现优秀，保持策略纪律，继续寻找机会。"
            target = "保持优势，适度控制回撤"
        
        # 获取策略配置
        strategy = self.config.get('strategy', 'short_term')
        target_hold_days = self.config.get('target_hold_days', 5)
        
        # 策略描述
        strategy_map = {
            'short_term': f'短线交易（参考{target_hold_days}天，快进快出）',
            'mid_term': f'中线交易（参考{target_hold_days}天，趋势跟踪）',
            'long_term': f'长线投资（参考{target_hold_days}天，价值投资）'
        }
        strategy_desc = strategy_map.get(strategy, strategy_map['short_term'])
        
        # ⭐ 构建竞技场排名信息（如果有）
        ranking_header = ""
        ranking_context = state.get('ranking_context', {})
        if ranking_context and ranking_context.get('rankings'):
            your_rank = ranking_context.get('your_rank', {})
            rankings = ranking_context.get('rankings', [])
            leader = ranking_context.get('leader', {})
            current_day = ranking_context.get('current_day', 1)
            total_days = ranking_context.get('total_days', 195)
            stage = ranking_context.get('stage', '')
            comment = ranking_context.get('comment', '')
            goal = ranking_context.get('goal', '')
            gap = ranking_context.get('gap_to_leader', 0)
            
            # 格式化排名列表（明确标注第一名）
            rank_lines = []
            for r in rankings[:4]:  # 显示前4名
                medal = r.get('medal', '')
                rank_num = r.get('rank', 0)
                name = r.get('name', '')
                profit = r.get('profit_pct', 0)
                is_you = (name == your_rank.get('name', ''))
                
                # ✅ 更明确的标注
                if rank_num == 1:
                    indicator = "👑 当前第一名（领先所有人）" if not is_you else "👑 你是第一名！"
                elif is_you:
                    indicator = f"👈 你排第{rank_num}名"
                else:
                    indicator = ""
                    
                rank_lines.append(f"{medal} 第{rank_num}名: {name:<15} 收益率{profit:+.2f}%  {indicator}")
            
            # 生成激励话术
            motivation_message = self.motivation_engine.get_motivation_message(
                ranking_context, 
                state['total_assets'], 
                state['initial_capital']
            )
            
            # 生成纪律提醒
            discipline_reminder = self.motivation_engine.get_discipline_reminder(
                state['cash'],
                state['total_assets']
            )
            
            # 期望值和盈亏比教育
            expected_value_edu = self.motivation_engine.get_expected_value_education()
            profit_loss_ratio_edu = self.motivation_engine.get_profit_loss_ratio_education()
            
            ranking_header = f"""
🏆 LHArena Season 1 竞技场 - Day {current_day}/{total_days}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 实时排名（LIVE）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(rank_lines)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{motivation_message}

{discipline_reminder}

{expected_value_edu}

{profit_loss_ratio_edu}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 策略建议：
- 建议积极配置资产，把握市场机会
- 合理的仓位管理是获取收益的基础
- 分散投资可降低风险，提高收益稳定性

🎯 今日目标
{goal}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        # 构建候选股票列表
        candidates_list = [{
            'code': s['code'],
            'name': s.get('name', ''),
            'price': s.get('close', 0),
            'pct_chg': s.get('pct_chg', 0),
            'pe': s.get('pe_ttm', 0),
            'turnover': s.get('turnover_rate', 0)
        } for s in state['candidates']]
        
        # 获取上次反思内容
        reflection_text = ""
        if state.get('reflection') and state['reflection'].get('reflection_text'):
            reflection_text = f"""
📝 **上次反思总结**（建议参考）：
{state['reflection']['reflection_text'][:500]}

建议参考上述反思的改进建议，避免重复之前的错误。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # 构建指数信息
        index_info_text = ""
        if state.get('index_data'):
            index_lines = []
            if 'sh_index' in state['index_data']:
                sh = state['index_data']['sh_index']
                index_lines.append(f"上证指数: {sh.get('close', 0):.2f} ({sh.get('pct_chg', 0):+.2f}%)")
            if 'hs300' in state['index_data']:
                hs = state['index_data']['hs300']
                index_lines.append(f"沪深300: {hs.get('close', 0):.2f} ({hs.get('pct_chg', 0):+.2f}%)")
            if 'cyb_index' in state['index_data']:
                cyb = state['index_data']['cyb_index']
                index_lines.append(f"创业板指: {cyb.get('close', 0):.2f} ({cyb.get('pct_chg', 0):+.2f}%)")
            if index_lines:
                index_info_text = f"""
📊 **大盘走势**：
{chr(10).join(index_lines)}
"""
        
        # 📰 获取市场新闻
        market_news = self._get_market_news(state)
        
        # 构建排名上下文文本
        ranking_context_text = ""
        if ranking_header:
            ranking_context_text = ranking_header
        
        # 获取置信度阈值（用于提示词）
        confidence_threshold = self.config.get('ai_confidence_threshold', 0.20)
        
        # Phase 4: 加载Agent的交易原则
        agent_principles = self._load_agent_principles(state)
        
        # Phase 5: 为前N只候选股票添加详细分析
        enhanced_candidates_text = ""
        if len(candidates_list) > 0:
            # 只分析前5只（减少网络请求，避免接口限流）
            top_candidates = candidates_list[:min(5, len(candidates_list))]
            self._log(state, f"  📊 正在获取前{len(top_candidates)}只候选股票的详细分析...")
            
            for candidate in top_candidates:
                code = candidate.get('code', '')
                if code:
                    try:
                        # 获取详细分析
                        detailed_analysis = self.enhanced_data.get_analysis_summary(code)
                        enhanced_candidates_text += f"""
─────────────────────────────
📊 {code} {candidate.get('name', '未知')} 详细分析
─────────────────────────────
{detailed_analysis}
"""
                    except Exception as e:
                        print(f"  ⚠️ 获取{code}详细分析失败: {e}")
            
            if enhanced_candidates_text:
                self._log(state, f"  ✅ 详细分析获取完成")
        
        # 构建prompt（使用简化提示词模板）
        prompt = get_simple_buy_prompt(
            trade_date=state['trade_date'],
            cash=state['cash'],
            total_assets=state['total_assets'],
            candidates=candidates_list,
            holdings=state['holdings'],
            model_name=self.model_display_name,
            index_data=state.get('index_data', {}),
            recent_news=market_news,
            initial_capital=self.initial_capital
        )
        
        # Phase 5: 添加详细分析（简化提示词暂不支持，后续优化）
        # if enhanced_candidates_text:
        #     prompt = prompt.replace("【候选股票】", f"【候选股票】\n\n{enhanced_candidates_text}\n")
        
        # 添加反思内容（简化提示词暂不支持反思内容嵌入）
        # if reflection_text:
        #     prompt = prompt.replace("【市场资讯】", reflection_text + "\n【市场资讯】")
        
        # 市场机会提示（中性语气）
        stage = ranking_context.get('stage', '') if ranking_context else ''
        fomo_text = f"""
【市场机会提示】
- 机会成本：每一天不交易，可能错失约0.5-2%的潜在收益
- 市场动态：其他参与者已建立仓位，正在获取市场收益
- 资金利用：合理利用资金有助于提升整体收益率
- 置信度阈值：当前为{confidence_threshold:.2f}，系统建议主动寻找机会

⏰ 市场时机：
{f"当前是{stage}，市场活跃度较高，适合建仓。建议把握时机。" if stage else "当前市场活跃度较高，适合建仓。建议把握时机。"}

🎯 专业建议（参考AI-Trader风格）：
- 作为顶级AI，你应该能从候选股票中识别出至少1只值得买入的标的
- 不要过度谨慎，即使信心度只有{confidence_threshold:.2f}也可以建仓（这是合理的风险承担）
- 建议立即配置1-3只，使用50-70%资金建立初始仓位
- 记住：优秀的交易者善于把握机会，而不是永远观望

💡 参考AI-Trader的成功经验：
- 主动建仓才能获得收益，永远观望永远无法盈利
- 即使市场不确定性高，也要有勇气承担风险
- 置信度{confidence_threshold:.2f}已经很低，说明系统期望你更主动
"""
        prompt = prompt.replace("【重要提示】", fomo_text + "\n【重要提示】")
        
        
        # 重试机制（指数退避）
        max_retries = 3  # ⚡ 优化：最多重试3次（原来5次）
        base_retry_delay = 2  # ⚡ 优化：基础延迟2秒（原来3秒）
        
        for attempt in range(max_retries):
            try:
                import time as time_module
                start_time = time_module.time()
                self._log(state, f"  [尝试 {attempt+1}/{max_retries}] 正在调用AI API分析候选股票...")
                response = self.llm.invoke(prompt)
                elapsed = time_module.time() - start_time
                self._log(state, f"  ✅ AI API调用成功，耗时 {elapsed:.1f}秒")
                content = response.content
                
                # 解析JSON（使用智能JSON提取）
                decisions = self._extract_json_array(content)
                if decisions:
                    # 只保留置信度≥配置阈值的（确保d是字典类型）
                    confidence_threshold = self.config.get('ai_confidence_threshold', 0.30)
                    buy_decisions = []
                    
                    for d in decisions:
                        if not isinstance(d, dict):
                            continue
                        
                        # 支持 stock_code 或 code 字段
                        code = d.get('stock_code') or d.get('code')
                        if not code:
                            continue
                        
                        # 检查置信度
                        confidence = d.get('confidence', 0.0)
                        if confidence < confidence_threshold:
                            continue
                        
                        # 统一字段名：将 stock_code 转为 code，添加 action
                        normalized_decision = {
                            'code': code,
                            'action': 'buy',  # 添加action字段以兼容后续逻辑
                            'suggested_amount': d.get('suggested_amount', 0),
                            'confidence': confidence,
                            'reason': d.get('reason', ''),
                            'expected_days': d.get('expected_days', 5)
                        }
                        buy_decisions.append(normalized_decision)
                    
                    # 记录日志
                    if buy_decisions:
                        for dec in buy_decisions:
                            current_time = datetime.now().strftime('%H:%M:%S')
                            code = dec.get('code', 'UNKNOWN')
                            suggested_amount = dec.get('suggested_amount', 0)
                            confidence = dec.get('confidence', 0.0)
                            reason = dec.get('reason', '无原因')
                            self._log(state, f"  [{current_time}] 📥 {code}: 买入{suggested_amount}股 (置信度: {confidence:.2f}) - {reason[:50]}")
                    else:
                        current_time = datetime.now().strftime('%H:%M:%S')
                        self._log(state, f"  [{current_time}] ⚠️ 未找到符合置信度阈值({confidence_threshold:.2f})的买入建议")
                    
                    state['buy_analysis'] = {'decisions': buy_decisions}
                    break  # 成功，退出重试循环
                else:
                    state['buy_analysis'] = {'decisions': []}
                    break
                    
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                self._log(state, f"❌ 分析候选股票失败 (尝试 {attempt+1}/{max_retries}): {e}")
                print(f"完整错误: {error_detail}", flush=True)
                
                # 检查是否为余额不足错误（错误码 1113）
                if self._is_insufficient_balance_error(e):
                    self._log(state, f"💳 ❌ API余额不足，无法继续分析。请充值后重试。")
                    state['buy_analysis'] = {'decisions': []}
                    break  # 立即退出重试循环
                
                if attempt < max_retries - 1:
                    # 指数退避：3秒、6秒、12秒、24秒
                    retry_delay = base_retry_delay * (2 ** attempt)
                    self._log(state, f"⏳ {retry_delay}秒后重试...（使用指数退避策略）")
                    time.sleep(retry_delay)
                else:
                    self._log(state, f"❌ 已达最大重试次数，跳过本次买入分析")
                    state['buy_analysis'] = {'decisions': []}
        
        return state
    
    def _execute_buys(self, state: TradingState) -> TradingState:
        """执行买入（含硬性风控）"""
        decisions = state['buy_analysis'].get('decisions', [])
        buy_trades = []
        processed_codes: set[str] = set()
        
        # ========== 硬性风控检查 ==========
        
        # 检查1：持仓数量限制（从配置读取）
        max_holdings = self.config.get('max_holdings', 5)
        if len(state['holdings']) >= max_holdings:
            current_time = datetime.now().strftime('%H:%M:%S')
            self._log(state, f"[{current_time}] ⚠️ 风控拒绝：持仓已达{max_holdings}只上限，禁止买入")
            state['buy_trades'] = []
            return state
        
        # 检查2：现金储备（放宽至5%）
        min_cash_reserve = state['initial_capital'] * 0.05
        if state['cash'] < min_cash_reserve:
            current_time = datetime.now().strftime('%H:%M:%S')
            self._log(state, f"[{current_time}] ⚠️ 风控拒绝：现金低于5%安全线，禁止买入")
            state['buy_trades'] = []
            return state
        
        # 检查3：可用于买入的最大资金（放宽至95%）
        max_buy_cash = state['cash'] * 0.95
        
        for decision in decisions:
            # 确保decision是字典类型
            if not isinstance(decision, dict):
                continue
            if decision.get('action') != 'buy':
                continue
            
            code = decision.get('code')
            if not code:
                continue
            if code in processed_codes:
                current_time = datetime.now().strftime('%H:%M:%S')
                self._log(state, f"  [{current_time}] ⚠️ 跳过重复买入指令: {code}")
                continue
            processed_codes.add(code)
            suggested_amount = decision.get('suggested_amount', 100)
            
            # 获取价格
            stock_data = self.data_provider.get_daily_price(code, state['trade_date'])
            if not stock_data:
                continue
            price = stock_data.get('close', 0)
            if price <= 0:
                continue
            
            # 调整买入数量
            max_amount = int(state['cash'] / price / 100) * 100
            amount = min(suggested_amount, max_amount)
            amount = (amount // 100) * 100
            
            if amount < 100:
                current_time = datetime.now().strftime('%H:%M:%S')
                self._log(state, f"  [{current_time}] ⚠️ 资金不足买入{code}")
                continue
            
            # 计算成本
            stock_cost = amount * price
            commission = max(stock_cost * 0.0003, 5)
            total_cost = stock_cost + commission
            
            # 检查是否超过现金
            if total_cost > state['cash']:
                continue
            
            # 检查4：单只股票仓位限制（放宽至40%总资产）
            max_single_position = state['total_assets'] * 0.40
            if stock_cost > max_single_position:
                current_time = datetime.now().strftime('%H:%M:%S')
                self._log(state, f"  [{current_time}] ⚠️ 风控拒绝：{code}仓位{stock_cost:.0f}元超过40%上限({max_single_position:.0f}元)")
                continue
            
            # 获取股票名称
            stock_info = self.data_provider.get_stock_basic_info(code)
            
            # 更新账户（Phase 1: 在holdings中保存exit_plan）
            state['cash'] -= total_cost
            exit_plan = decision.get('exit_plan', {})
            state['holdings'][code] = {
                'amount': amount,
                'cost': price,
                'date': state['trade_date'],
                'current_price': price,
                'profit_pct': 0,
                'hold_days': 0,
                'buy_date': state['trade_date'],
                'name': stock_info.get('name', '未知'),
                # Phase 1: 保存退出计划
                'profit_target': exit_plan.get('profit_target', '未设置'),
                'stop_loss': exit_plan.get('stop_loss', '未设置'),
                'invalidation': exit_plan.get('invalidation', '未设置'),
                'expected_days': decision.get('expected_days', 5)
            }
            
            # 记录交易（Phase 1 & 2: 保存退出计划和买入前状态）
            exit_plan = decision.get('exit_plan', {})
            trade_record = {
                'date': state['trade_date'],
                'time': datetime.now().strftime('%H:%M:%S'),
                'action': 'buy',
                'code': code,
                'name': stock_info.get('name', '未知'),
                'amount': amount,
                'price': price,
                'total': stock_cost,
                'commission': commission,
                'reason': decision.get('reason', 'AI决策买入'),
                # Phase 1: 退出计划字段
                'profit_target': exit_plan.get('profit_target', '未设置'),
                'stop_loss': exit_plan.get('stop_loss', '未设置'),
                'invalidation': exit_plan.get('invalidation', '未设置'),
                'expected_days': decision.get('expected_days', 5),
                # Phase 2: 买入前状态（用于历史分析）
                'cash_before': state['cash'] + total_cost,  # 买入前的现金（还原）
                'assets_before': state['total_assets']
            }
            
            buy_trades.append(trade_record)
            state['trade_history'].append(trade_record)
            
            # 日志（控制台）
            current_time = datetime.now().strftime('%H:%M:%S')
            self._log(state, f"  [{current_time}] ✅ 买入: {code}, {amount}股 @ {price:.2f}元, 成本: {total_cost:.2f}元")
            # stock_info已在上面获取（get_stock_basic_info返回字典）
            name = stock_info.get('name', '未知')
            reason = decision.get('reason', '策略买入')
            confidence = decision.get('confidence', 0)
            
            # ✅ 记录AI内心独白（自然语言，不要标签）
            thinking = f"💭 {reason}"
            self._log_thinking(state, thinking)
        
        # 如果没有买入任何股票，说明观望
        if not buy_trades and len(decisions) > 0:
            # 有推荐但没买成（可能因为资金不足或风控）
            self._log_thinking(state, "💭 今日观望 - 虽然有些机会，但资金和仓位限制让我选择暂时不入场。")
        elif not buy_trades and not decisions:
            # 完全没有推荐
            self._log_thinking(state, "💭 今日观望 - 市场没有符合我标准的机会，保持耐心等待更好的入场点。")
        
        state['buy_trades'] = buy_trades
        return state
    
    def _record_daily_assets(self, state: TradingState) -> TradingState:
        """记录每日资产"""
        # 计算持仓市值
        holdings_value = sum(
            h['amount'] * h['current_price'] 
            for h in state['holdings'].values()
        )
        state['total_assets'] = state['cash'] + holdings_value
        
        # 记录
        daily_record = {
            'date': state['trade_date'],
            'total_assets': state['total_assets'],
            'cash': state['cash'],
            'holdings_value': holdings_value,
            'holdings_count': len(state['holdings'])
        }
        
        state['daily_assets'].append(daily_record)
        
        return state
    
    def _daily_reflection(self, state: TradingState) -> TradingState:
        """每日反思"""
        enable_reflection = self.config.get('enable_reflection', False)
        
        if not enable_reflection:
            return state
        
        # 计算当前收益
        daily_profit = state['total_assets'] - state['initial_capital']
        profit_pct = (daily_profit / state['initial_capital']) * 100
        
        # 触发反思的条件
        should_reflect = False
        reflection_reason = ""
        
        # 1. 定期反思（每N天）
        reflection_interval = self.config.get('reflection_interval', 5)
        if len(state['daily_assets']) % reflection_interval == 0:
            should_reflect = True
            reflection_reason = "定期反思"
        
        # 2. 亏损时立即反思（亏损>3%）
        if profit_pct < -3:
            should_reflect = True
            reflection_reason = f"⚠️ 亏损{profit_pct:.1f}%，紧急反思"
        
        # 3. 大幅回撤时反思（当前资产比最高点跌>5%）
        if state['daily_assets']:
            max_assets = max(d['total_assets'] for d in state['daily_assets'])
            drawdown_pct = (max_assets - state['total_assets']) / max_assets * 100
            if drawdown_pct > 5:
                should_reflect = True
                reflection_reason = f"⚠️ 回撤{drawdown_pct:.1f}%，紧急反思"
        
        if not should_reflect:
            return state
        
        current_time = datetime.now().strftime('%H:%M:%S')
        self._log(state, f"[{current_time}] 💭 {reflection_reason}...")
        
        # Phase 4: 加载Agent之前的交易原则
        agent_principles = self._load_agent_principles(state)
        
        # 构建当前策略参数
        current_strategy = {
            'stop_loss_pct': self.config.get('stop_loss_pct', 0.08),
            'stop_profit_pct': self.config.get('stop_profit_pct', 0.12),
            'target_hold_days': self.config.get('target_hold_days', 5),
            'ai_confidence_threshold': self.config.get('ai_confidence_threshold', 0.30)
        }
        
        # 使用新的反思prompt（Phase 3 & 4）
        prompt = get_reflection_prompt(
            trade_history=state['trade_history'],
            daily_assets=state['daily_assets'],
            current_strategy=current_strategy,
            agent_principles=agent_principles  # Phase 4
        )
        
        try:
            response = self.llm.invoke(prompt)
            reflection_text = response.content
            
            # ⚠️ 检查返回内容是否为空
            if not reflection_text or not reflection_text.strip():
                self._log(state, f"⚠️ 反思返回内容为空（API调用成功但无响应内容）")
                return state
            
            # Phase 4: 解析反思结果（JSON格式）
            try:
                # 尝试从markdown代码块中提取JSON
                if '```json' in reflection_text:
                    json_start = reflection_text.find('```json') + 7
                    json_end = reflection_text.find('```', json_start)
                    reflection_json = reflection_text[json_start:json_end].strip()
                elif '```' in reflection_text:
                    json_start = reflection_text.find('```') + 3
                    json_end = reflection_text.find('```', json_start)
                    reflection_json = reflection_text[json_start:json_end].strip()
                else:
                    reflection_json = reflection_text.strip()
                
                reflection_data = json.loads(reflection_json)
                
                # Phase 4: 保存经验到数据库
                if self.session_id:
                    try:
                        self.persistence.save_agent_reflection(
                            session_id=self.session_id,
                            model_name=self.model_provider,
                            reflection_date=state['trade_date'],
                            reflection_data=reflection_data
                        )
                        
                        # 输出交易原则到日志
                        principles = reflection_data.get('trading_principles', [])
                        if principles:
                            self._log(state, f"✅ 更新了 {len(principles)} 条交易原则")
                            for i, p in enumerate(principles[:3], 1):  # 只显示前3条
                                self._log(state, f"   {i}. {p[:50]}...")
                    except Exception as e:
                        self._log(state, f"⚠️ 保存经验失败: {e}")
                
                # 格式化反思内容用于UI展示
                summary_lines = []
                summary_lines.append("【反思总结】")
                summary_lines.append(f"现金管理: {reflection_data.get('cash_reflection', 'N/A')[:80]}...")
                summary_lines.append(f"持仓时间: {reflection_data.get('timing_reflection', 'N/A')[:80]}...")
                summary_lines.append(f"决策习惯: {reflection_data.get('decision_reflection', 'N/A')[:80]}...")
                
                strengths = reflection_data.get('my_strengths', [])
                weaknesses = reflection_data.get('my_weaknesses', [])
                if strengths:
                    summary_lines.append(f"\n优势: {strengths[0][:60]}...")
                if weaknesses:
                    summary_lines.append(f"问题: {weaknesses[0][:60]}...")
                
                summary_text = "\n".join(summary_lines)
                
                # 保存到state
                reflection = {
                    'date': state['trade_date'],
                    'reflection_text': summary_text,
                    'full_data': reflection_data
                }
                state['reflection'] = reflection
                
                # 输出到UI
                self._log_thinking(state, summary_text)
                
            except json.JSONDecodeError as e:
                # 如果JSON解析失败，仍然保存原始文本
                self._log(state, f"⚠️ 反思结果解析失败，使用原始文本")
                reflection = {
                    'date': state['trade_date'],
                    'reflection_text': reflection_text
                }
                state['reflection'] = reflection
                self._log_thinking(state, reflection_text[:300])
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self._log(state, f"❌ 反思失败: {e}")
            print(f"完整错误: {error_detail}")
            
            # 检查是否为余额不足错误（错误码 1113）
            if self._is_insufficient_balance_error(e):
                self._log(state, f"💳 ❌ API余额不足，无法进行反思。请充值后重试。")
        
        return state
    
    def run_single_day(self, trade_date: str, 
                      update_callback=None,
                      should_stop=None,
                      ranking_context=None,
                      hot_codes: Optional[List[str]] = None,
                      hot_sectors: Optional[List[Dict[str, Any]]] = None,
                      session_id: str = None):
        """
        执行单个交易日的操作（用于竞技场同步模式）
        
        Args:
            trade_date: 交易日期
            update_callback: 更新回调
            should_stop: 停止检查函数
            ranking_context: 竞技场排名上下文（包含排名、对手信息等）
            session_id: 会话ID（Phase 4: 用于经验管理）
        """
        # Phase 4: 设置session_id（用于经验管理）
        if session_id:
            self.session_id = session_id
        
        # 检查停止
        if should_stop and should_stop():
            return
        
        # 构建状态（复用当前Agent的状态）
        state: TradingState = {
            'trade_date': trade_date,
            'session_id': self.session_id or '',  # Phase 4: 使用实例的session_id
            'cash': self.cash,
            'initial_capital': self.initial_capital,
            'holdings': self.holdings,
            'total_assets': self.total_assets,
            'candidates': [],
            'sell_analysis': {},
            'buy_analysis': {},
            'index_data': {},  # 指数数据
            'sell_trades': [],
            'buy_trades': [],
            'trade_history': self.trade_history,
            'daily_assets': self.daily_assets,
            'ai_logs': [],
            'reflection': {},
            'ranking_context': ranking_context or {},
            'hot_codes': hot_codes or [],
            'hot_sectors': hot_sectors or []
        }
        
        # 保存停止回调
        self.should_stop_callback = should_stop
        
        # ⭐ 保存执行前的状态（用于异常恢复）
        pre_state = {
            'cash': self.cash,
            'holdings': dict(self.holdings),  # 深拷贝
            'total_assets': self.total_assets,
            'trade_history': list(self.trade_history),  # 深拷贝
            'daily_assets': list(self.daily_assets)  # 深拷贝
        }
        
        try:
            # 运行状态图
            result_state = self.app.invoke(state)
            
            # 更新实例属性
            self.cash = result_state['cash']
            self.holdings = result_state['holdings']
            self.total_assets = result_state['total_assets']
            self.trade_history = result_state['trade_history']
            self.daily_assets = result_state['daily_assets']
            
            # 回调UI更新
            if update_callback:
                update_callback({
                    'daily_assets': self.daily_assets,
                    'trade_history': self.trade_history,
                    'holdings': self.holdings,
                    'total_assets': self.total_assets,
                    'cash': self.cash,  # ✅ 添加现金字段
                    'ai_logs': result_state['ai_logs']
                })
                
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[{self.model_display_name}] ❌ {trade_date} 执行失败: {e}", flush=True)
            print(f"完整错误: {error_detail}", flush=True)
            
            # ⭐ 关键修复：恢复Agent状态，确保下一天可以继续执行
            # 恢复到执行前的状态，避免状态损坏导致无法继续
            self.cash = pre_state['cash']
            self.holdings = pre_state['holdings']
            self.total_assets = pre_state['total_assets']
            self.trade_history = pre_state['trade_history']
            self.daily_assets = pre_state['daily_assets']
            
            print(f"[{self.model_display_name}] 🔄 已恢复Agent状态，可以继续执行下一天", flush=True)
            raise
    
    def run_backtest(self, start_date: str, end_date: str, 
                    progress_callback=None, update_callback=None, 
                    should_stop=None) -> Dict[str, Any]:
        """
        运行回测
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            progress_callback: 进度回调
            update_callback: 更新回调
            should_stop: 停止检查函数，返回True时停止回测
            
        Returns:
            回测结果
        """
        print(f"\n{'='*60}", flush=True)
        print(f"🚀 LangGraph Agent 回测", flush=True)
        print(f"开始日期: {start_date}", flush=True)
        print(f"结束日期: {end_date}", flush=True)
        print(f"交易日数量: {len(self._get_trade_dates(start_date, end_date))}", flush=True)
        print(f"初始资金: {self.config.get('initial_capital', 10000):.2f}元\n", flush=True)
        
        # Arena模式不需要创建session（由persistence管理）
        session_id = ''
        
        # 获取交易日列表
        trade_dates = self._get_trade_dates(start_date, end_date)
        total_days = len(trade_dates)
        initial_capital = self.config.get('initial_capital', 10000)
        
        print(f"交易日数量: {total_days}", flush=True)
        print(f"初始资金: {initial_capital:.2f}元\n", flush=True)
        
        # 初始化状态
        initial_state: TradingState = {
            'trade_date': '',
            'session_id': session_id,
            'cash': initial_capital,
            'initial_capital': initial_capital,
            'holdings': {},
            'total_assets': initial_capital,
            'candidates': [],
            'sell_analysis': {},
            'buy_analysis': {},
            'index_data': {},  # 指数数据
            'sell_trades': [],
            'buy_trades': [],
            'trade_history': [],
            'daily_assets': [],
            'ai_logs': [],
            'reflection': {},
            'ranking_context': {},  # 单Agent模式无竞技场排名
            'hot_codes': [],
            'hot_sectors': []
        }
        
        # 保存停止回调
        self.should_stop_callback = should_stop
        
        # 遍历每个交易日
        for idx, trade_date in enumerate(trade_dates):
            # 检查是否应该停止
            if should_stop and should_stop():
                self._log(initial_state, f"\n⚠️ 回测被用户停止")
                break
            
            if progress_callback:
                progress_callback(idx + 1, total_days, f"LangGraph决策: {trade_date}")
            
            # 每10天打印进度
            if (idx + 1) % 10 == 0:
                print(f"\n[{idx+1}/{total_days}] {trade_date} | "
                      f"💰{initial_state['cash']:.0f}元 | "
                      f"📊{len(initial_state['holdings'])}只 | "
                      f"💼{initial_state['total_assets']:.0f}元", flush=True)
            
            # 更新日期
            initial_state['trade_date'] = trade_date
            initial_state['ai_logs'] = []  # 重置日志
            
            # 运行状态图
            try:
                result_state = self.app.invoke(initial_state)
                initial_state = result_state  # 更新状态
                
                # 实时更新UI
                if update_callback:
                    update_callback({
                        'daily_assets': initial_state['daily_assets'],
                        'trade_history': initial_state['trade_history'],
                        'holdings': initial_state['holdings'],
                        'total_assets': initial_state['total_assets'],
                        'cash': initial_state['cash'],  # ✅ 添加现金字段
                        'ai_logs': initial_state['ai_logs']
                    })
                    
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"[{self.model_display_name}] ❌ 执行失败: {e}", flush=True)
                print(f"完整错误: {error_detail}", flush=True)
                continue
        
        # 更新实例属性（用于UI显示）
        self.cash = initial_state['cash']
        self.holdings = initial_state['holdings']
        self.total_assets = initial_state['total_assets']
        self.trade_history = initial_state['trade_history']
        self.daily_assets = initial_state['daily_assets']
        
        # 计算最终结果
        result = self._calculate_result(initial_state)
        
        print(f"\n{'='*60}", flush=True)
        print(f"🎉 LangGraph回测完成", flush=True)
        print(f"最终资产: {initial_state['total_assets']:.2f}元", flush=True)
        print(f"总收益率: {result['total_return']:.2f}%", flush=True)
        print(f"{'='*60}\n", flush=True)
        
        return result
    
    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        return self.data_provider.get_trade_dates(start_date, end_date)
    
    def _calculate_result(self, state: TradingState) -> Dict[str, Any]:
        """计算回测结果"""
        initial_capital = state['initial_capital']
        final_assets = state['total_assets']
        
        # 计算收益率
        total_return = ((final_assets - initial_capital) / initial_capital) * 100
        
        # 计算最大回撤
        max_drawdown = 0
        peak = initial_capital
        for record in state['daily_assets']:
            assets = record['total_assets']
            if assets > peak:
                peak = assets
            drawdown = (peak - assets) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 计算胜率
        win_trades = [t for t in state['trade_history'] 
                     if t.get('action') == 'sell' and t.get('profit', 0) > 0]
        total_sell_trades = [t for t in state['trade_history'] 
                            if t.get('action') == 'sell']
        win_rate = (len(win_trades) / len(total_sell_trades) * 100) if total_sell_trades else 0
        
        return {
            'initial_capital': initial_capital,
            'final_assets': final_assets,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trade_count': len(total_sell_trades),
            'daily_assets': state['daily_assets'],
            'trade_history': state['trade_history'],
            'holdings': state['holdings']
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            'cash': self.cash,
            'holdings': self.holdings,
            'total_assets': self.total_assets,
            'trade_history': self.trade_history,
            'daily_assets': self.daily_assets
        }
    
    def detect_data_corruption(self) -> tuple[bool, str | None]:
        """
        检测数据损坏
        
        Returns:
            (is_corrupted, first_corrupted_date):
            - is_corrupted: 是否发现损坏
            - first_corrupted_date: 第一个损坏的日期 (YYYY-MM-DD格式)，如果没有损坏则为None
        """
        if not self.daily_assets:
            return False, None  # 没有数据，不算损坏
        
        from datetime import datetime, timedelta
        
        try:
            # 初始化前一天的资产值
            self._prev_assets = None
            
            # 1. 检查daily_assets的数据完整性和连续性
            prev_date = None
            for idx, entry in enumerate(self.daily_assets):
                # 检查必需字段
                if not isinstance(entry, dict):
                    print(f"⚠️ [{self.model_display_name}] daily_assets[{idx}] 不是字典类型", flush=True)
                    return True, self._get_first_date() if prev_date is None else prev_date
                
                date_str = entry.get('date')
                if not date_str or not isinstance(date_str, str):
                    print(f"⚠️ [{self.model_display_name}] daily_assets[{idx}] 缺少date字段或格式错误", flush=True)
                    return True, self._get_first_date() if prev_date is None else prev_date
                
                # 统一日期格式：支持YYYYMMDD和YYYY-MM-DD两种格式
                original_date_str = date_str
                if '-' not in date_str:
                    if len(date_str) == 8:
                        # YYYYMMDD格式，转换为YYYY-MM-DD
                        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    else:
                        print(f"⚠️ [{self.model_display_name}] daily_assets[{idx}] 日期格式错误: {original_date_str}", flush=True)
                        return True, self._get_first_date() if prev_date is None else prev_date
                
                # 检查日期格式 (YYYY-MM-DD)
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    # 更新entry中的日期为标准格式
                    if entry.get('date') != date_str:
                        entry['date'] = date_str
                except ValueError:
                    print(f"⚠️ [{self.model_display_name}] daily_assets[{idx}] 日期格式错误: {original_date_str}", flush=True)
                    return True, self._get_first_date() if prev_date is None else prev_date
                
                # 检查日期连续性（应该是递增的，允许跳过非交易日）
                if prev_date is not None:
                    # prev_date是datetime对象，直接比较
                    if date_obj < prev_date:
                        print(f"⚠️ [{self.model_display_name}] daily_assets 日期倒序: {prev_date.strftime('%Y-%m-%d')} -> {date_str}", flush=True)
                        return True, date_str  # 返回倒序的那个日期
                
                # 检查数值合理性
                total_assets = entry.get('total_assets') or entry.get('assets')  # 兼容两种字段名
                if total_assets is None:
                    print(f"⚠️ [{self.model_display_name}] daily_assets[{idx}] 缺少资产字段", flush=True)
                    return True, date_str
                
                if not isinstance(total_assets, (int, float)) or total_assets < 0:
                    print(f"⚠️ [{self.model_display_name}] daily_assets[{idx}] 资产值无效: {total_assets}", flush=True)
                    return True, date_str
                
                # ⭐ 新增：检查资产大幅异常变化（可能是数据损坏）
                if prev_date is not None and hasattr(self, '_prev_assets') and self._prev_assets is not None:
                    prev_assets_val = self._prev_assets
                    if prev_assets_val > 0:
                        asset_change_pct = ((total_assets - prev_assets_val) / prev_assets_val) * 100
                        # 计算日期间隔（天数）
                        days_diff = (date_obj - prev_date).days
                        
                        # 如果日期间隔超过3天，说明中间有交易日缺失，可能是数据不完整
                        if days_diff > 3:
                            print(f"⚠️ [{self.model_display_name}] 日期间隔过大: {prev_date.strftime('%Y-%m-%d')} -> {date_str} (间隔 {days_diff} 天)，可能有数据缺失", flush=True)
                            return True, date_str  # 返回有间隔的日期
                        
                        # 单日资产下降超过12%或上升超过30%视为异常（正常情况下不可能，除非止损）
                        # 但如果是多天间隔，允许更大的变化
                        if days_diff == 1:
                            # 相邻日期，变化应该更小
                            if asset_change_pct < -12 or asset_change_pct > 30:
                                print(f"⚠️ [{self.model_display_name}] 单日资产异常变化: {date_str} 从 {prev_assets_val:.2f} -> {total_assets:.2f} (变化 {asset_change_pct:+.2f}%)", flush=True)
                                return True, date_str
                        elif days_diff > 1:
                            # 多天间隔，允许更大的变化，但变化幅度不应超过间隔天数×10%
                            max_allowed_change = days_diff * 10
                            if abs(asset_change_pct) > max_allowed_change:
                                print(f"⚠️ [{self.model_display_name}] {days_diff}天间隔资产异常变化: {date_str} 从 {prev_assets_val:.2f} -> {total_assets:.2f} (变化 {asset_change_pct:+.2f}%)", flush=True)
                                return True, date_str
                
                cash = entry.get('cash', 0)
                if not isinstance(cash, (int, float)) or cash < 0:
                    print(f"⚠️ [{self.model_display_name}] daily_assets[{idx}] 现金值无效: {cash}", flush=True)
                    return True, date_str
                
                prev_date = date_obj  # 存储datetime对象用于下一次比较
                self._prev_assets = total_assets  # 存储前一天的资产用于下次比较
            
            # 2. 检查最后一天的资产状态一致性
            if self.daily_assets:
                last_entry = self.daily_assets[-1]
                last_total = last_entry.get('total_assets') or last_entry.get('assets', 0)
                
                # 计算实际持仓市值
                holdings_value = sum(
                    h.get('amount', 0) * h.get('current_price', h.get('price', 0))
                    for h in self.holdings.values()
                )
                
                expected_total = self.cash + holdings_value
                
                # 允许5%的误差（浮点数精度问题）
                if abs(last_total - expected_total) > expected_total * 0.05 and expected_total > 100:
                    print(f"⚠️ [{self.model_display_name}] 资产不一致: daily_assets={last_total:.2f}, 实际={expected_total:.2f}", flush=True)
                    # 返回最后一天作为损坏点
                    return True, last_entry.get('date')
            
            # 3. 检查trade_history的日期是否在daily_assets范围内
            if self.trade_history:
                # 构建daily_assets的日期集合（统一格式）
                daily_dates = set()
                for entry in self.daily_assets:
                    entry_date = entry.get('date')
                    if entry_date:
                        # 统一格式
                        if '-' not in entry_date and len(entry_date) == 8:
                            entry_date = f"{entry_date[:4]}-{entry_date[4:6]}-{entry_date[6:8]}"
                        daily_dates.add(entry_date)
                
                for trade in self.trade_history:
                    trade_date = trade.get('date') or trade.get('trade_date')
                    if trade_date:
                        # 统一日期格式
                        original_trade_date = trade_date
                        if '-' not in trade_date:
                            if len(trade_date) == 8:
                                trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                            else:
                                print(f"⚠️ [{self.model_display_name}] 交易记录日期格式错误: {original_trade_date}", flush=True)
                                return True, original_trade_date
                        
                        # 更新trade中的日期为标准格式
                        if 'date' in trade and trade['date'] != trade_date:
                            trade['date'] = trade_date
                        if 'trade_date' in trade and trade['trade_date'] != trade_date:
                            trade['trade_date'] = trade_date
                        
                        # 检查该日期是否在daily_assets中
                        if trade_date not in daily_dates and self.daily_assets:
                            # 交易日期不在daily_assets中，可能有问题
                            print(f"⚠️ [{self.model_display_name}] 交易记录日期 {trade_date} 不在daily_assets中", flush=True)
                            return True, trade_date
            
            return False, None  # 没有发现损坏
            
        except Exception as e:
            import traceback
            print(f"⚠️ [{self.model_display_name}] 数据损坏检测异常: {e}", flush=True)
            traceback.print_exc()
            # 检测过程本身出错，视为数据损坏
            return True, self._get_first_date()
    
    def _get_first_date(self) -> str | None:
        """获取daily_assets中的第一个日期（统一为YYYY-MM-DD格式）"""
        if not self.daily_assets:
            return None
        first_entry = self.daily_assets[0]
        date_str = first_entry.get('date')
        if date_str:
            # 统一日期格式
            if '-' not in date_str and len(date_str) == 8:
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str
    
    def find_first_continuous_data_end(self) -> tuple[str | None, str | None]:
        """
        找到最初连续数据的末端
        
        从第一个日期开始检查，如果发现日期间隔 > 3天（可能跳过了交易日），
        就找到第一个断点，返回断点之前的最后一个连续日期。
        
        Returns:
            (last_continuous_date, first_gap_date):
            - last_continuous_date: 最后一个连续日期（如果没有断点，返回最后一个日期）
            - first_gap_date: 第一个断点的日期（如果没有断点，返回None）
        """
        if not self.daily_assets:
            return None, None
        
        from datetime import datetime, timedelta
        
        prev_date_obj = None
        
        for idx, entry in enumerate(self.daily_assets):
            if not isinstance(entry, dict):
                continue
            
            date_str = entry.get('date')
            if not date_str:
                continue
            
            # 统一日期格式
            if '-' not in date_str and len(date_str) == 8:
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                entry['date'] = date_str  # 更新为标准格式
            
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                # 日期格式错误，这是断点
                if prev_date_obj:
                    return prev_date_obj.strftime('%Y-%m-%d'), date_str
                else:
                    return None, date_str
            
            # 检查日期连续性
            if prev_date_obj is not None:
                days_diff = (date_obj - prev_date_obj).days
                
                # 如果日期间隔 > 3天，说明可能跳过了交易日，这是断点
                if days_diff > 3:
                    # 找到断点，返回前一个日期
                    gap_date = date_str
                    last_continuous_date = prev_date_obj.strftime('%Y-%m-%d')
                    print(f"⚠️ [{self.model_display_name}] 检测到日期断点: {last_continuous_date} -> {gap_date} (间隔 {days_diff} 天)", flush=True)
                    return last_continuous_date, gap_date
                
                # 如果日期倒序，这也是断点
                if date_obj < prev_date_obj:
                    gap_date = date_str
                    last_continuous_date = prev_date_obj.strftime('%Y-%m-%d')
                    print(f"⚠️ [{self.model_display_name}] 检测到日期倒序: {last_continuous_date} -> {gap_date}", flush=True)
                    return last_continuous_date, gap_date
            
            prev_date_obj = date_obj
        
        # 没有发现断点，返回最后一个日期
        if prev_date_obj:
            return prev_date_obj.strftime('%Y-%m-%d'), None
        else:
            return None, None
    
    def rollback_to_date(self, target_date: str) -> bool:
        """
        回滚到指定日期，删除该日期之后的所有数据
        
        Args:
            target_date: 目标日期 (YYYY-MM-DD格式)，回滚到这个日期之前（不包含该日期）
            
        Returns:
            是否成功回滚
        """
        try:
            from datetime import datetime
            
            # 确保日期格式正确
            if '-' not in target_date and len(target_date) == 8:
                target_date = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}"
            
            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
            
            print(f"🔄 [{self.model_display_name}] 开始回滚到 {target_date} 之前...", flush=True)
            
            # 1. 回滚daily_assets：保留target_date之前的所有数据
            original_count = len(self.daily_assets)
            filtered_assets = []
            for entry in self.daily_assets:
                entry_date = entry.get('date')
                if entry_date:
                    # 统一日期格式
                    if '-' not in entry_date and len(entry_date) == 8:
                        entry_date = f"{entry_date[:4]}-{entry_date[4:6]}-{entry_date[6:8]}"
                        entry['date'] = entry_date  # 更新为标准格式
                    
                    try:
                        entry_dt = datetime.strptime(entry_date, '%Y-%m-%d')
                        if entry_dt < target_dt:
                            filtered_assets.append(entry)
                    except ValueError:
                        # 日期格式错误，跳过
                        continue
            
            self.daily_assets = filtered_assets
            removed_count = original_count - len(self.daily_assets)
            
            if removed_count > 0:
                print(f"  ✅ 已删除 {removed_count} 条daily_assets记录", flush=True)
            
            # 2. 回滚trade_history：删除target_date及之后的交易记录
            original_trades = len(self.trade_history)
            self.trade_history = [
                trade for trade in self.trade_history
                if self._is_trade_before_date(trade, target_dt)
            ]
            removed_trades = original_trades - len(self.trade_history)
            
            if removed_trades > 0:
                print(f"  ✅ 已删除 {removed_trades} 条交易记录", flush=True)
            
            # 3. 恢复Agent状态到最后一个有效日期的状态
            if self.daily_assets:
                last_entry = self.daily_assets[-1]
                last_date = last_entry.get('date')
                
                # 恢复资产（从daily_assets的最后一条记录）
                self.total_assets = last_entry.get('total_assets') or last_entry.get('assets', self.initial_capital)
                self.cash = last_entry.get('cash', self.total_assets)
                
                # 重建holdings（按时间顺序从trade_history中恢复）
                self.holdings = {}
                
                # 按日期排序交易记录（确保正确重建持仓）
                sorted_trades = sorted(
                    self.trade_history,
                    key=lambda t: self._get_trade_date_for_sort(t)
                )
                
                for trade in sorted_trades:
                    code = trade.get('code') or trade.get('stock_code')
                    if not code:
                        continue
                    
                    action = trade.get('action')
                    amount = trade.get('amount', 0)
                    price = trade.get('price', 0)
                    
                    if action == 'buy':
                        if code in self.holdings:
                            old_amount = self.holdings[code]['amount']
                            old_cost = self.holdings[code]['cost']
                            new_amount = old_amount + amount
                            new_cost = old_cost + (amount * price)
                            self.holdings[code]['amount'] = new_amount
                            self.holdings[code]['cost'] = new_cost
                            # 更新平均成本
                            self.holdings[code]['price'] = new_cost / new_amount if new_amount > 0 else price
                        else:
                            self.holdings[code] = {
                                'amount': amount,
                                'cost': amount * price,
                                'price': price,
                                'current_price': price
                            }
                    elif action == 'sell':
                        if code in self.holdings:
                            self.holdings[code]['amount'] -= amount
                            if self.holdings[code]['amount'] <= 0:
                                del self.holdings[code]
                            else:
                                # 更新成本（FIFO简化：按比例减少成本）
                                sell_ratio = amount / (self.holdings[code]['amount'] + amount)
                                self.holdings[code]['cost'] *= (1 - sell_ratio)
                
                # 如果有现金记录，优先使用记录的现金值
                if 'cash' in last_entry:
                    self.cash = last_entry['cash']
                
                # ⭐ 更新持仓价格为回滚日期的真实市场价（避免使用成本价导致资产计算错误）
                try:
                    self._update_holdings_current_prices(last_date)
                except Exception as e:
                    print(f"  ⚠️ 更新持仓价格失败: {e}，使用成本价", flush=True)
                
                # 计算持仓市值并调整现金（确保total_assets一致）
                holdings_value = sum(
                    h.get('amount', 0) * h.get('current_price', h.get('price', 0))
                    for h in self.holdings.values()
                )
                
                # 如果记录中的总资产与计算的不一致，调整现金
                expected_cash = self.total_assets - holdings_value
                if expected_cash >= 0:
                    self.cash = expected_cash
                
                print(f"  ✅ 已恢复到 {last_date} 的状态: 资产={self.total_assets:.2f}, 现金={self.cash:.2f}, 持仓={len(self.holdings)}只", flush=True)
            else:
                # 没有有效数据，恢复到初始状态
                self.cash = self.initial_capital
                self.total_assets = self.initial_capital
                self.holdings = {}
                print(f"  ✅ 已恢复到初始状态: 资产={self.total_assets:.2f}", flush=True)
            
            print(f"✅ [{self.model_display_name}] 回滚完成", flush=True)
            return True
            
        except Exception as e:
            import traceback
            print(f"❌ [{self.model_display_name}] 回滚失败: {e}", flush=True)
            traceback.print_exc()
            return False
    
    def _is_trade_before_date(self, trade: Dict[str, Any], target_dt) -> bool:
        """检查交易记录是否在目标日期之前"""
        from datetime import datetime
        
        trade_date = trade.get('date') or trade.get('trade_date')
        if not trade_date:
            return True  # 没有日期信息，保留（可能是旧格式）
        
        try:
            # 统一日期格式
            if '-' not in trade_date:
                if len(trade_date) == 8:
                    trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                else:
                    return True  # 格式无法解析，保留
            
            trade_dt = datetime.strptime(trade_date, '%Y-%m-%d')
            return trade_dt < target_dt
        except:
            return True  # 解析失败，保留
    
    def _get_trade_date_for_sort(self, trade: Dict[str, Any]) -> str:
        """获取交易日期用于排序（返回标准格式YYYY-MM-DD）"""
        trade_date = trade.get('date') or trade.get('trade_date')
        if not trade_date:
            return '0000-00-00'  # 没有日期，排在最前
        
        try:
            # 统一日期格式
            if '-' not in trade_date:
                if len(trade_date) == 8:
                    trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            return trade_date
        except:
            return '0000-00-00'

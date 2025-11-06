"""
内存数据存储
用于支持浏览器刷新后从后端恢复数据
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from .arena_persistence import get_arena_persistence


class MemoryStore:
    """
    全局内存数据存储
    后端保持运行，前端刷新时可以恢复数据
    """
    
    # 类级别的数据存储（全局单例）
    _session_id = None  # 当前会话ID
    _session_data = {
        'is_running': False,
        'current_mode': 'arena',
        'initial_capital': 10000,
        'start_time': None,
        'config': {}
    }
    
    _model_assets = {}  # {model_name: {total_assets, profit_pct, color}}
    _chart_data = {}     # {model_name: [{date, assets}, ...]}
    _ai_logs = []        # [{model_name, timestamp, message, color}, ...]
    _trades = []         # [{model_name, date, stock_code, action, ...}, ...]
    _holdings = {}       # {model_name: [{stock_code, volume, ...}, ...]}
    _arena_data = {}     # 完整的竞技场数据
    _progress_data = {'current': 0, 'total': 0, 'message': ''}  # 进度信息
    
    # 全局消息队列（用于跨UI实例通信）
    _ai_message_queue = []  # AI消息队列
    _ui_update_queue = []    # UI更新队列
    
    # 持久化开关
    _persistence_enabled = True  # 是否启用持久化
    
    @classmethod
    def reset(cls):
        """重置所有数据（程序重启时调用）"""
        cls._session_data = {
            'is_running': False,
            'current_mode': 'arena',
            'initial_capital': 10000,
            'start_time': None,
            'config': {}
        }
        cls._model_assets = {}
        cls._chart_data = {}
        cls._ai_logs = []
        cls._trades = []
        cls._holdings = {}
        cls._arena_data = {}
        cls._progress_data = {'current': 0, 'total': 0, 'message': ''}
        cls._ai_message_queue = []
        cls._ui_update_queue = []
    
    # ==================== 会话状态 ====================
    
    @classmethod
    def set_session_state(cls, key: str, value: Any):
        """设置会话状态"""
        cls._session_data[key] = value
    
    @classmethod
    def get_session_state(cls, key: str, default=None) -> Any:
        """获取会话状态"""
        return cls._session_data.get(key, default)
    
    @classmethod
    def get_all_session_state(cls) -> Dict[str, Any]:
        """获取所有会话状态"""
        return cls._session_data.copy()
    
    # ==================== 模型资产 ====================
    
    @classmethod
    def save_model_asset(cls, model_name: str, total_assets: float, 
                        profit_pct: float, color: str = None):
        """保存模型资产"""
        cls._model_assets[model_name] = {
            'total_assets': total_assets,
            'profit_pct': profit_pct,
            'color': color,
            'updated_at': datetime.now().isoformat()
        }
    
    @classmethod
    def get_all_model_assets(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有模型资产"""
        return cls._model_assets.copy()
    
    @classmethod
    def get_model_asset(cls, model_name: str) -> Optional[Dict[str, Any]]:
        """获取指定模型资产"""
        return cls._model_assets.get(model_name)
    
    # ==================== 图表数据 ====================
    
    @classmethod
    def add_chart_data(cls, model_name: str, trade_date: str, total_assets: float):
        """添加图表数据点（去重）"""
        if model_name not in cls._chart_data:
            cls._chart_data[model_name] = []
        
        # 检查是否已存在相同日期的数据（去重）
        existing_dates = {point['date'] for point in cls._chart_data[model_name]}
        if trade_date not in existing_dates:
            cls._chart_data[model_name].append({
                'date': trade_date,
                'assets': total_assets
            })
    
    @classmethod
    def get_chart_data(cls, model_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取图表数据
        
        Args:
            model_name: 如果指定，只返回该模型的数据
            
        Returns:
            {model_name: [{date, assets}, ...]}
        """
        if model_name:
            return {model_name: cls._chart_data.get(model_name, [])}
        return cls._chart_data.copy()
    
    @classmethod
    def get_all_dates(cls) -> List[str]:
        """获取所有交易日期（去重排序）"""
        dates = set()
        for data_list in cls._chart_data.values():
            for item in data_list:
                dates.add(item['date'])
        return sorted(list(dates))
    
    # ==================== AI日志 ====================
    
    @classmethod
    def add_ai_log(cls, model_name: str, message: str, color: str = None):
        """添加AI日志（限制最多保留1000条）"""
        cls._ai_logs.append({
            'model_name': model_name,
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'color': color
        })
        
        # ✅ 限制日志数量，防止内存无限增长（保留最新的1000条）
        if len(cls._ai_logs) > 1000:
            cls._ai_logs = cls._ai_logs[-1000:]
    
    @classmethod
    def get_ai_logs(cls, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取AI日志
        
        Args:
            limit: 返回数量限制（从最新开始）
            
        Returns:
            日志列表（最新的在前）
        """
        logs = cls._ai_logs[::-1]  # 倒序，最新的在前
        if limit:
            logs = logs[:limit]
        return logs
    
    @classmethod
    def get_ai_logs_count(cls) -> int:
        """获取日志总数"""
        return len(cls._ai_logs)
    
    # ==================== 交易记录 ====================
    
    @classmethod
    def add_trade(cls, trade_data: Dict[str, Any]):
        """添加交易记录"""
        trade = {
            'model_name': trade_data.get('model_name'),
            'date': trade_data.get('date'),
            'stock_code': trade_data.get('stock_code'),
            'action': trade_data.get('action'),
            'price': trade_data.get('price'),
            'volume': trade_data.get('volume'),
            'amount': trade_data.get('amount'),
            'reason': trade_data.get('reason', ''),
            'created_at': datetime.now().isoformat(),
            # ✅ 新增字段：盈亏、手续费、时间等
            'profit': trade_data.get('profit'),  # 卖出时的盈亏金额
            'profit_pct': trade_data.get('profit_pct'),  # 卖出时的盈亏百分比
            'commission': trade_data.get('commission'),  # 手续费
            'time': trade_data.get('time'),  # 交易时间
            'name': trade_data.get('name'),  # 股票名称
        }
        cls._trades.append(trade)
    
    @classmethod
    def get_trades(cls, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取交易记录
        
        Args:
            limit: 返回数量限制（从最新开始）
            
        Returns:
            交易记录列表（最新的在前）
        """
        trades = cls._trades[::-1]  # 倒序
        if limit:
            trades = trades[:limit]
        return trades
    
    # ==================== 持仓数据 ====================
    
    @classmethod
    def update_holdings(cls, model_name: str, holdings_list: List[Dict[str, Any]]):
        """更新持仓数据"""
        # ✅ 数据验证：过滤非字典元素
        if isinstance(holdings_list, list):
            valid_holdings = [h for h in holdings_list if isinstance(h, dict)]
            if len(valid_holdings) != len(holdings_list):
                print(f"⚠️  [{model_name}] 持仓数据包含 {len(holdings_list) - len(valid_holdings)} 个非字典元素，已过滤")
            cls._holdings[model_name] = valid_holdings
        else:
            print(f"⚠️  [{model_name}] 持仓数据不是列表: {type(holdings_list)}")
            cls._holdings[model_name] = []
    
    @classmethod
    def get_holdings(cls, model_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取持仓数据
        
        Args:
            model_name: 如果指定，只返回该模型的持仓
            
        Returns:
            {model_name: [holdings...]}
        """
        if model_name:
            return {model_name: cls._holdings.get(model_name, [])}
        return cls._holdings.copy()
    
    # ==================== 竞技场数据 ====================
    
    @classmethod
    def save_arena_data(cls, model_name: str, data: Dict[str, Any]):
        """保存竞技场数据"""
        cls._arena_data[model_name] = data
    
    @classmethod
    def get_arena_data(cls, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取竞技场数据
        
        Args:
            model_name: 如果指定，只返回该模型的数据
            
        Returns:
            竞技场数据
        """
        if model_name:
            return cls._arena_data.get(model_name, {})
        return cls._arena_data.copy()
    
    # ==================== 统计信息 ====================
    
    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'is_running': cls._session_data.get('is_running', False),
            'model_count': len(cls._model_assets),
            'chart_data_points': sum(len(v) for v in cls._chart_data.values()),
            'ai_logs_count': len(cls._ai_logs),
            'trades_count': len(cls._trades),
            'start_time': cls._session_data.get('start_time'),
            'models': list(cls._model_assets.keys())
        }
    
    # ==================== 数据检查 ====================
    
    @classmethod
    def has_data(cls) -> bool:
        """检查是否有数据"""
        return (
            len(cls._model_assets) > 0 or
            len(cls._chart_data) > 0 or
            len(cls._ai_logs) > 0 or
            len(cls._trades) > 0
        )
    
    @classmethod
    def is_running(cls) -> bool:
        """检查是否正在运行"""
        return cls._session_data.get('is_running', False)
    
    # ==================== 全局消息队列 ====================
    
    @classmethod
    def add_ai_message_to_queue(cls, model_name: str, message: str):
        """添加AI消息到全局队列"""
        cls._ai_message_queue.append({
            'model_name': model_name,
            'message': message
        })
    
    @classmethod
    def add_ui_update_to_queue(cls, update_data: Dict[str, Any]):
        """添加UI更新到全局队列"""
        cls._ui_update_queue.append(update_data)
    
    @classmethod
    def get_ai_message_queue(cls) -> List[Dict[str, Any]]:
        """获取AI消息队列（不清空）"""
        return cls._ai_message_queue.copy()
    
    @classmethod
    def get_ui_update_queue(cls) -> List[Dict[str, Any]]:
        """获取UI更新队列（不清空）"""
        return cls._ui_update_queue.copy()
    
    @classmethod
    def pop_ai_message(cls) -> Optional[Dict[str, Any]]:
        """弹出一条AI消息"""
        if cls._ai_message_queue:
            return cls._ai_message_queue.pop(0)
        return None
    
    @classmethod
    def pop_ui_update(cls) -> Optional[Dict[str, Any]]:
        """弹出一条UI更新"""
        if cls._ui_update_queue:
            return cls._ui_update_queue.pop(0)
        return None
    
    # ==================== 进度信息 ====================
    
    @classmethod
    def update_progress(cls, current: int, total: int, message: str = ''):
        """更新进度信息"""
        cls._progress_data = {
            'current': current,
            'total': total,
            'message': message
        }
    
    @classmethod
    def get_progress(cls) -> Dict[str, Any]:
        """获取进度信息"""
        return cls._progress_data.copy()
    
    # ==================== 持久化相关 ====================
    
    @classmethod
    def set_persistence_enabled(cls, enabled: bool):
        """设置是否启用持久化"""
        cls._persistence_enabled = enabled
    
    @classmethod
    def start_new_session(cls, start_date: str, end_date: str, 
                         initial_capital: float, config: Dict[str, Any]) -> str:
        """
        开始新会话并创建数据库记录
        
        Returns:
            session_id: 会话ID
        """
        if cls._persistence_enabled:
            persistence = get_arena_persistence()
            cls._session_id = persistence.create_session(
                start_date, end_date, initial_capital, config
            )
        return cls._session_id
    
    @classmethod
    def load_session(cls, session_id: str):
        """从数据库加载会话数据"""
        if not cls._persistence_enabled:
            return
        
        persistence = get_arena_persistence()
        # ✅ 后端恢复现场时，只加载到current_date，避免加载未来数据造成混乱
        data = persistence.load_session_data(session_id, include_future=False)
        
        # 恢复会话ID
        cls._session_id = session_id
        
        # 恢复会话信息
        session = data['session']
        cls._session_data = {
            'is_running': session['status'] == 'running',
            'current_mode': 'arena',
            'initial_capital': session['initial_capital'],
            'start_time': session['created_at'],
            'config': json.loads(session.get('config', '{}'))
        }
        
        # 恢复模型资产
        cls._model_assets = data['model_states']
        
        # 恢复图表数据
        cls._chart_data = data['daily_assets']
        
        # 恢复交易记录
        cls._trades = data['trades']
        
        # 恢复持仓
        cls._holdings = data['holdings']
        
        # 恢复AI日志
        cls._ai_logs = data['ai_logs']
        
        print(f"✅ 已加载会话 {session_id}")
        print(f"   - 开始日期: {session['start_date']}")
        print(f"   - 当前日期: {session['current_date']}")
        print(f"   - 结束日期: {session['end_date']}")
    
    @classmethod
    def save_to_database(cls):
        """将当前数据保存到数据库"""
        if not cls._persistence_enabled or not cls._session_id:
            return
        
        persistence = get_arena_persistence()
        
        # 保存模型状态
        for model_name, state in cls._model_assets.items():
            arena_data = cls._arena_data.get(model_name, {})
            cash = arena_data.get('cash', 0)
            persistence.save_model_state(
                cls._session_id, model_name,
                cash, state['total_assets'], state['profit_pct']
            )
        
        # 保存每日资产
        for model_name, daily_list in cls._chart_data.items():
            for item in daily_list:
                persistence.save_daily_assets(
                    cls._session_id, model_name,
                    item['date'], item['assets']
                )
        
        # 保存持仓
        for model_name, holdings_list in cls._holdings.items():
            persistence.save_holdings(cls._session_id, model_name, holdings_list)
    
    @classmethod
    def complete_current_session(cls):
        """标记当前会话完成"""
        if cls._persistence_enabled and cls._session_id:
            persistence = get_arena_persistence()
            persistence.complete_session(cls._session_id)
    
    @classmethod
    def get_current_session_id(cls) -> Optional[str]:
        """获取当前会话ID"""
        return cls._session_id
    
    @classmethod
    def add_trade_with_persistence(cls, trade_data: Dict[str, Any]):
        """添加交易记录并保存到数据库"""
        cls.add_trade(trade_data)
        
        if cls._persistence_enabled and cls._session_id:
            persistence = get_arena_persistence()
            persistence.save_trade(cls._session_id, trade_data)
    
    @classmethod
    def add_ai_log_with_persistence(cls, model_name: str, message: str, color: str = None):
        """添加AI日志并保存到数据库"""
        cls.add_ai_log(model_name, message, color)
        
        if cls._persistence_enabled and cls._session_id:
            persistence = get_arena_persistence()
            timestamp = datetime.now().isoformat()
            persistence.save_ai_log(cls._session_id, model_name, timestamp, message)


# 创建全局实例（单例模式）
memory_store = MemoryStore()

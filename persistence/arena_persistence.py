"""
Arena数据持久化模块
负责将竞技场运行数据保存到数据库，支持断点续跑
"""

import sqlite3
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import os


class ArenaPersistence:
    """Arena数据持久化管理器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径，默认为 data/arena_sessions.db
        """
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'arena_sessions.db')
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 会话表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arena_sessions (
                    session_id TEXT PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    current_date TEXT,
                    initial_capital REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    config TEXT
                )
            ''')
            
            # 2. 模型状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arena_model_state (
                    session_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    cash REAL NOT NULL,
                    total_assets REAL NOT NULL,
                    profit_pct REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, model_name),
                    FOREIGN KEY (session_id) REFERENCES arena_sessions(session_id)
                )
            ''')
            
            # 3. 每日资产表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arena_daily_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    assets REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, model_name, trade_date),
                    FOREIGN KEY (session_id) REFERENCES arena_sessions(session_id)
                )
            ''')
            
            # 4. 交易记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arena_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    action TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    profit REAL,
                    profit_pct REAL,
                    commission REAL,
                    time TEXT,
                    name TEXT,
                    FOREIGN KEY (session_id) REFERENCES arena_sessions(session_id)
                )
            ''')
            
            # ✅ 为旧表添加新字段（如果不存在）
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN profit REAL")
            except sqlite3.OperationalError:
                pass  # 字段已存在
            
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN profit_pct REAL")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN commission REAL")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN time TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN name TEXT")
            except sqlite3.OperationalError:
                pass
            
            # Phase 1: 添加退出计划字段
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN profit_target TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN stop_loss TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN invalidation TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN expected_days INTEGER")
            except sqlite3.OperationalError:
                pass
            
            # Phase 2: 添加买入前状态字段
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN cash_before REAL")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_trades ADD COLUMN assets_before REAL")
            except sqlite3.OperationalError:
                pass
            
            # 5. 持仓表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arena_holdings (
                    session_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    amount INTEGER NOT NULL,
                    avg_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    market_value REAL NOT NULL,
                    profit_loss REAL NOT NULL,
                    profit_pct REAL NOT NULL,
                    hold_days INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, model_name, stock_code),
                    FOREIGN KEY (session_id) REFERENCES arena_sessions(session_id)
                )
            ''')
            
            # Phase 1: 为持仓表添加退出计划字段
            try:
                cursor.execute("ALTER TABLE arena_holdings ADD COLUMN profit_target TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_holdings ADD COLUMN stop_loss TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_holdings ADD COLUMN invalidation TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE arena_holdings ADD COLUMN expected_days INTEGER")
            except sqlite3.OperationalError:
                pass
            
            # 6. AI思考日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arena_ai_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    message TEXT NOT NULL,
                    log_type TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES arena_sessions(session_id)
                )
            ''')
            
            # Phase 4: Agent经验总结表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_reflections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    reflection_date TEXT NOT NULL,
                    cash_reflection TEXT,
                    timing_reflection TEXT,
                    decision_reflection TEXT,
                    self_awareness TEXT,
                    strengths TEXT,
                    weaknesses TEXT,
                    adjustment_plan TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES arena_sessions(session_id)
                )
            ''')
            
            # Phase 4: Agent交易原则表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_principles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    principle TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (session_id) REFERENCES arena_sessions(session_id)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_status ON arena_sessions(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_assets_session ON arena_daily_assets(session_id, model_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_session ON arena_trades(session_id, model_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_logs_session ON arena_ai_logs(session_id, model_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_reflections_session ON agent_reflections(session_id, model_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_principles_session ON agent_principles(session_id, model_name, is_active)')
            
            conn.commit()
    
    def create_session(self, start_date: str, end_date: str, 
                      initial_capital: float, config: Dict[str, Any]) -> str:
        """
        创建新会话
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            config: 配置信息
            
        Returns:
            session_id: 会话ID
        """
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO arena_sessions 
                (session_id, start_date, end_date, current_date, initial_capital, 
                 status, created_at, updated_at, config)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session_id, start_date, end_date, start_date, initial_capital,
                  'running', now, now, json.dumps(config)))
            conn.commit()
        
        return session_id
    
    def save_model_state(self, session_id: str, model_name: str, 
                        cash: float, total_assets: float, profit_pct: float):
        """保存模型状态"""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO arena_model_state
                (session_id, model_name, cash, total_assets, profit_pct, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, model_name, cash, total_assets, profit_pct, now))
            conn.commit()
    
    def save_daily_assets(self, session_id: str, model_name: str, 
                         trade_date: str, assets: float):
        """保存每日资产"""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO arena_daily_assets
                (session_id, model_name, trade_date, assets, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, model_name, trade_date, assets, now))
            conn.commit()
    
    def save_trade(self, session_id: str, trade_data: Dict[str, Any]):
        """保存交易记录"""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO arena_trades
                (session_id, model_name, trade_date, stock_code, action, 
                 price, volume, amount, reason, created_at, 
                 profit, profit_pct, commission, time, name,
                 profit_target, stop_loss, invalidation, expected_days,
                 cash_before, assets_before)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                trade_data.get('model_name'),
                trade_data.get('date'),
                trade_data.get('stock_code'),
                trade_data.get('action'),
                trade_data.get('price'),
                trade_data.get('volume'),
                trade_data.get('amount'),
                trade_data.get('reason', ''),
                now,
                trade_data.get('profit'),  # 盈亏金额
                trade_data.get('profit_pct'),  # 盈亏百分比
                trade_data.get('commission'),  # 手续费
                trade_data.get('time'),  # 交易时间
                trade_data.get('name'),  # 股票名称
                # Phase 1: 退出计划字段
                trade_data.get('profit_target'),  # 止盈目标
                trade_data.get('stop_loss'),  # 止损条件
                trade_data.get('invalidation'),  # 失效条件
                trade_data.get('expected_days'),  # 预期持有天数
                # Phase 2: 买入前状态字段
                trade_data.get('cash_before'),  # 买入前现金
                trade_data.get('assets_before')  # 买入前总资产
            ))
            conn.commit()
    
    def save_holdings(self, session_id: str, model_name: str, holdings: List[Dict[str, Any]]):
        """保存持仓信息"""
        now = datetime.now().isoformat()
        
        # ✅ 数据验证和过滤
        if not isinstance(holdings, list):
            print(f"⚠️  holdings 不是列表类型: {type(holdings)}")
            return
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 先删除该模型的旧持仓
            cursor.execute('''
                DELETE FROM arena_holdings 
                WHERE session_id = ? AND model_name = ?
            ''', (session_id, model_name))
            
            # 插入新持仓
            for holding in holdings:
                # ✅ 跳过非字典元素
                if not isinstance(holding, dict):
                    print(f"⚠️  跳过非字典持仓数据: {type(holding)} - {holding}")
                    continue
                
                # ✅ 确保必需字段存在
                if 'code' not in holding:
                    print(f"⚠️  持仓数据缺少 'code' 字段: {holding}")
                    continue
                
                try:
                    cursor.execute('''
                        INSERT INTO arena_holdings
                        (session_id, model_name, stock_code, stock_name, amount, 
                         avg_price, current_price, market_value, profit_loss, 
                         profit_pct, hold_days, updated_at,
                         profit_target, stop_loss, invalidation, expected_days)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id, model_name,
                        holding.get('code'),
                        holding.get('name', ''),
                        holding.get('amount', 0),
                        holding.get('cost') or holding.get('avg_price', 0.0),  # ← 修复：优先使用cost字段
                        holding.get('current_price', 0.0),
                        holding.get('market_value', 0.0),
                        holding.get('profit_loss', 0.0),
                        holding.get('profit_pct', 0.0),
                        holding.get('hold_days', 0),
                        now,
                        # Phase 1: 退出计划字段
                        holding.get('profit_target'),
                        holding.get('stop_loss'),
                        holding.get('invalidation'),
                        holding.get('expected_days')
                    ))
                except Exception as e:
                    print(f"⚠️  保存持仓失败: {e} - {holding}")
                    continue
            
            conn.commit()
    
    def save_ai_log(self, session_id: str, model_name: str, 
                   timestamp: str, message: str, log_type: str = 'info'):
        """保存AI思考日志"""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO arena_ai_logs
                (session_id, model_name, timestamp, message, log_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, model_name, timestamp, message, log_type, now))
            conn.commit()
    
    def update_session_progress(self, session_id: str, current_date: str):
        """更新会话进度"""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE arena_sessions 
                SET current_date = ?, updated_at = ?
                WHERE session_id = ?
            ''', (current_date, now, session_id))
            conn.commit()
    
    def complete_session(self, session_id: str):
        """标记会话完成"""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE arena_sessions 
                SET status = 'completed', updated_at = ?
                WHERE session_id = ?
            ''', (now, session_id))
            conn.commit()

    def purge_session_data(self, session_id: str) -> None:
        """彻底清除指定会话的所有数据（用于恢复异常情况）。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for table in (
                'arena_daily_assets',
                'arena_trades',
                'arena_holdings',
                'arena_ai_logs',
                'arena_model_state',
                'arena_sessions'
            ):
                cursor.execute(f'DELETE FROM {table} WHERE session_id = ?', (session_id,))
            conn.commit()
    
    def get_latest_unfinished_session(self) -> Optional[Dict[str, Any]]:
        """
        获取最新的未完成会话
        
        智能判断：
        1. 优先返回 status='running' 的session
        2. 如果没有running，检查最近的completed session是否真的完成了
        3. 如果completed但current_date < end_date，说明是强制停止的，可以继续
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. 先找running状态的
            cursor.execute('''
                SELECT * FROM arena_sessions 
                WHERE status = 'running'
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                return dict(row)
            
            # 2. 没有running，找最近的completed，检查是否真的完成了
            cursor.execute('''
                SELECT * FROM arena_sessions 
                WHERE status = 'completed'
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                session = dict(row)
                # 获取实际最新日期
                cursor.execute('''
                    SELECT MAX(trade_date) as latest_date
                    FROM arena_daily_assets
                    WHERE session_id = ?
                ''', (session['session_id'],))
                latest = cursor.fetchone()
                
                if latest and latest['latest_date']:
                    latest_date = latest['latest_date']
                    end_date = session['end_date']
                    
                    # 如果实际最新日期 < 结束日期，说明未完成
                    if latest_date < end_date:
                        # 自动改为running状态
                        cursor.execute('''
                            UPDATE arena_sessions
                            SET status = 'running', current_date = ?
                            WHERE session_id = ?
                        ''', (latest_date, session['session_id']))
                        conn.commit()
                        
                        # 返回更新后的session
                        session['status'] = 'running'
                        session['current_date'] = latest_date
                        return session
            
            return None
    
    def load_session_data(self, session_id: str, include_future: bool = True) -> Dict[str, Any]:
        """
        加载会话的所有数据
        
        Args:
            session_id: 会话ID
            include_future: 是否包含未来数据（超过current_date的数据）
                          - True: 加载所有数据，用于前端显示（前端会做同步过滤）
                          - False: 只加载到current_date，用于后端恢复现场
        
        Returns:
            包含所有数据的字典，格式与MemoryStore兼容
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. 加载会话信息
            cursor.execute('SELECT * FROM arena_sessions WHERE session_id = ?', (session_id,))
            session = dict(cursor.fetchone())
            
            # ✅ 获取会话的日期范围（用于过滤数据）
            session_start_date = session.get('start_date', '')
            session_end_date = session.get('end_date', '')
            current_date = session.get('current_date', session_end_date)  # ✅ 当前进度日期
            
            # 2. 加载模型状态
            cursor.execute('''
                SELECT * FROM arena_model_state WHERE session_id = ?
            ''', (session_id,))
            model_states = {row['model_name']: dict(row) for row in cursor.fetchall()}
            
            # 3. 加载每日资产
            # ✅ 前端显示时可以加载所有数据（include_future=True），但显示时会做同步过滤
            # ✅ 后端恢复现场时只加载到current_date（include_future=False），避免数据混乱
            if include_future:
                # 前端模式：加载所有数据（包括未来的），让前端做同步过滤
                max_date = session_end_date  # 加载到end_date，允许包含未来数据
            else:
                # 后端恢复模式：只加载到current_date，避免加载超出进度的数据
                max_date = current_date if current_date else session_end_date
            if session_start_date and max_date:
                cursor.execute('''
                    SELECT * FROM arena_daily_assets 
                    WHERE session_id = ? 
                    AND trade_date >= ? 
                    AND trade_date <= ?
                    ORDER BY trade_date
                ''', (session_id, session_start_date, max_date))
            else:
                cursor.execute('''
                    SELECT * FROM arena_daily_assets 
                    WHERE session_id = ?
                    ORDER BY trade_date
                ''', (session_id,))
            
            daily_assets = {}
            for row in cursor.fetchall():
                model_name = row['model_name']
                trade_date = row['trade_date']
                
                # ✅ 双重验证：确保日期在有效范围内（不超过current_date）
                if session_start_date and max_date:
                    if trade_date < session_start_date or trade_date > max_date:
                        continue  # 跳过超出范围的数据
                
                if model_name not in daily_assets:
                    daily_assets[model_name] = []
                daily_assets[model_name].append({
                    'date': trade_date,
                    'assets': row['assets']
                })
            
            # 4. 加载交易记录（根据include_future参数决定是否加载未来数据）
            if session_start_date and max_date:
                cursor.execute('''
                    SELECT * FROM arena_trades 
                    WHERE session_id = ?
                    AND trade_date >= ?
                    AND trade_date <= ?
                    ORDER BY id
                ''', (session_id, session_start_date, max_date))
            else:
                cursor.execute('''
                    SELECT * FROM arena_trades 
                    WHERE session_id = ?
                    ORDER BY id
                ''', (session_id,))
            
            trades = []
            for row in cursor.fetchall():
                trade_date = row['trade_date']  # sqlite3.Row支持字典式访问
                
                # ✅ 双重验证：确保日期在有效范围内（不超过current_date）
                if session_start_date and max_date:
                    if not trade_date or trade_date < session_start_date or trade_date > max_date:
                        continue  # 跳过超出范围的数据
                
                trades.append(dict(row))
            
            # 5. 加载持仓
            cursor.execute('''
                SELECT * FROM arena_holdings WHERE session_id = ?
            ''', (session_id,))
            holdings = {}
            for row in cursor.fetchall():
                model_name = row['model_name']
                if model_name not in holdings:
                    holdings[model_name] = []
                holdings[model_name].append(dict(row))
            
            # 6. 加载AI日志
            cursor.execute('''
                SELECT * FROM arena_ai_logs 
                WHERE session_id = ?
                ORDER BY id
            ''', (session_id,))
            ai_logs = [dict(row) for row in cursor.fetchall()]
            
            return {
                'session': session,
                'model_states': model_states,
                'daily_assets': daily_assets,
                'trades': trades,
                'holdings': holdings,
                'ai_logs': ai_logs
            }
    
    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """列出最近的会话"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM arena_sessions 
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_trade_date(self, session_id: str) -> Optional[str]:
        """
        获取数据库中的实际最新交易日期
        
        Args:
            session_id: 会话ID
            
        Returns:
            最新的交易日期（YYYYMMDD格式），如果没有数据则返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MAX(trade_date) as latest_date
                FROM arena_daily_assets
                WHERE session_id = ?
            ''', (session_id,))
            
            row = cursor.fetchone()
            return row[0] if row and row[0] else None
    
    def get_latest_model_state(self, session_id: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        获取模型的最新状态
        
        Args:
            session_id: 会话ID
            model_name: 模型名称
            
        Returns:
            最新状态字典（包含cash、total_assets、profit_pct），如果没有则返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT cash, total_assets, profit_pct, updated_at
                FROM arena_model_state
                WHERE session_id = ? AND model_name = ?
                ORDER BY updated_at DESC
                LIMIT 1
            ''', (session_id, model_name))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== Phase 4: Agent经验管理 ====================
    
    def save_agent_reflection(self, session_id: str, model_name: str, 
                             reflection_date: str, reflection_data: Dict[str, Any]):
        """
        保存Agent的反思总结
        
        Args:
            session_id: 会话ID
            model_name: 模型名称
            reflection_date: 反思日期
            reflection_data: 反思数据（JSON格式）
        """
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 保存反思总结
            cursor.execute('''
                INSERT INTO agent_reflections 
                (session_id, model_name, reflection_date, 
                 cash_reflection, timing_reflection, decision_reflection, self_awareness,
                 strengths, weaknesses, adjustment_plan, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, model_name, reflection_date,
                reflection_data.get('cash_reflection'),
                reflection_data.get('timing_reflection'),
                reflection_data.get('decision_reflection'),
                reflection_data.get('self_awareness'),
                json.dumps(reflection_data.get('my_strengths', []), ensure_ascii=False),
                json.dumps(reflection_data.get('my_weaknesses', []), ensure_ascii=False),
                json.dumps(reflection_data.get('adjustment_plan', {}), ensure_ascii=False),
                now
            ))
            
            # 保存交易原则（先清除旧的）
            cursor.execute('''
                UPDATE agent_principles 
                SET is_active = 0
                WHERE session_id = ? AND model_name = ?
            ''', (session_id, model_name))
            
            # 插入新的交易原则
            trading_principles = reflection_data.get('trading_principles', [])
            for principle in trading_principles:
                cursor.execute('''
                    INSERT INTO agent_principles 
                    (session_id, model_name, principle, created_at, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (session_id, model_name, principle, now))
            
            conn.commit()
    
    def get_agent_principles(self, session_id: str, model_name: str) -> List[str]:
        """
        获取Agent的当前交易原则
        
        Args:
            session_id: 会话ID
            model_name: 模型名称
            
        Returns:
            交易原则列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT principle FROM agent_principles
                WHERE session_id = ? AND model_name = ? AND is_active = 1
                ORDER BY id DESC
            ''', (session_id, model_name))
            
            return [row[0] for row in cursor.fetchall()]
    
    def get_latest_reflection(self, session_id: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        获取Agent最近的反思总结
        
        Args:
            session_id: 会话ID
            model_name: 模型名称
            
        Returns:
            反思数据字典
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM agent_reflections
                WHERE session_id = ? AND model_name = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (session_id, model_name))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            reflection = dict(row)
            # 解析JSON字段
            if reflection.get('strengths'):
                reflection['strengths'] = json.loads(reflection['strengths'])
            if reflection.get('weaknesses'):
                reflection['weaknesses'] = json.loads(reflection['weaknesses'])
            if reflection.get('adjustment_plan'):
                reflection['adjustment_plan'] = json.loads(reflection['adjustment_plan'])
            
            return reflection


# 全局单例
_arena_persistence = None

def get_arena_persistence() -> ArenaPersistence:
    """获取全局持久化管理器实例"""
    global _arena_persistence
    if _arena_persistence is None:
        _arena_persistence = ArenaPersistence()
    return _arena_persistence

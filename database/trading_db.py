"""交易数据库管理 - 专门存储交易记录、持仓、回测结果"""
import sqlite3
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
import json
from datetime import datetime


class TradingDatabase:
    """交易数据库 - 与股票数据分离"""
    
    def __init__(self, db_path: str = 'data/trading.db'):
        """
        初始化交易数据库
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 回测会话表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_sessions (
                    session_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    initial_capital REAL NOT NULL,
                    final_assets REAL,
                    total_return REAL,
                    max_drawdown REAL,
                    trade_count INTEGER,
                    win_rate REAL,
                    config TEXT,
                    create_time TEXT NOT NULL,
                    status TEXT DEFAULT 'running'
                )
            ''')
            
            # 2. 交易记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    action TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    amount INTEGER NOT NULL,
                    price REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    commission REAL NOT NULL,
                    profit REAL,
                    profit_pct REAL,
                    reason TEXT,
                    create_time TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(session_id)
                )
            ''')
            
            # 3. 持仓记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    record_date TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    amount INTEGER NOT NULL,
                    cost_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    market_value REAL NOT NULL,
                    profit REAL NOT NULL,
                    profit_pct REAL NOT NULL,
                    hold_days INTEGER,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(session_id)
                )
            ''')
            
            # 4. 每日资产表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    cash REAL NOT NULL,
                    market_value REAL NOT NULL,
                    total_assets REAL NOT NULL,
                    holdings_count INTEGER NOT NULL,
                    daily_return REAL,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(session_id)
                )
            ''')
            
            # 5. AI决策历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    decision_date TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    stock_code TEXT,
                    action TEXT NOT NULL,
                    confidence REAL,
                    reason TEXT,
                    input_data TEXT,
                    output_data TEXT,
                    create_time TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(session_id)
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_session 
                ON trades(session_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trades_date 
                ON trades(trade_date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_holdings_session 
                ON holdings(session_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_daily_assets_session 
                ON daily_assets(session_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ai_decisions_session 
                ON ai_decisions(session_id)
            ''')
    
    def create_backtest_session(self, mode: str, start_date: str, end_date: str,
                                initial_capital: float, config: Dict[str, Any], 
                                model_name: str = None) -> str:
        """
        创建回测会话
        
        Args:
            model_name: 模型名称（竞技场模式下必须提供，确保session_id唯一）
        
        Returns:
            str: session_id
        """
        import uuid
        # 生成唯一ID：如果有model_name就用，否则用UUID确保唯一性
        unique_suffix = model_name.replace('-', '_') if model_name else str(uuid.uuid4())[:8]
        session_id = f"{mode}_{start_date}_{end_date}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{unique_suffix}"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO backtest_sessions 
                (session_id, mode, start_date, end_date, initial_capital, config, create_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                mode,
                start_date,
                end_date,
                initial_capital,
                json.dumps(config, ensure_ascii=False),
                datetime.now().isoformat(),
                'running'
            ))
        
        return session_id
    
    def update_backtest_session(self, session_id: str, result: Dict[str, Any]):
        """更新回测会话结果"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE backtest_sessions
                SET final_assets = ?,
                    total_return = ?,
                    max_drawdown = ?,
                    trade_count = ?,
                    win_rate = ?,
                    status = 'completed'
                WHERE session_id = ?
            ''', (
                result.get('final_assets', 0),
                result.get('total_return', 0),
                result.get('max_drawdown', 0),
                result.get('trade_count', 0),
                result.get('win_rate', 0),
                session_id
            ))
    
    def save_trade(self, session_id: str, trade: Dict[str, Any]):
        """保存交易记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades
                (session_id, trade_date, action, stock_code, stock_name, amount, price,
                 total_amount, commission, profit, profit_pct, reason, create_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                trade.get('date', ''),
                trade.get('action', ''),
                trade.get('code', ''),
                trade.get('name', ''),
                trade.get('amount', 0),
                trade.get('price', 0),
                trade.get('total', 0),
                trade.get('commission', 0),
                trade.get('profit', 0),
                trade.get('profit_pct', 0),
                trade.get('reason', ''),
                datetime.now().isoformat()
            ))
    
    def save_holdings(self, session_id: str, trade_date: str, holdings: Dict[str, Dict[str, Any]]):
        """保存持仓快照"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for code, holding in holdings.items():
                cursor.execute('''
                    INSERT INTO holdings
                    (session_id, record_date, stock_code, stock_name, amount, cost_price,
                     current_price, market_value, profit, profit_pct, hold_days)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    trade_date,
                    code,
                    holding.get('name', ''),
                    holding.get('amount', 0),
                    holding.get('cost', 0),
                    holding.get('current_price', 0),
                    holding.get('amount', 0) * holding.get('current_price', 0),
                    holding.get('amount', 0) * (holding.get('current_price', 0) - holding.get('cost', 0)),
                    holding.get('profit_pct', 0),
                    holding.get('hold_days', 0)
                ))
    
    def save_daily_assets(self, session_id: str, daily_record: Dict[str, Any]):
        """保存每日资产记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO daily_assets
                (session_id, trade_date, cash, market_value, total_assets, holdings_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                daily_record.get('date', ''),
                daily_record.get('cash', 0),
                daily_record.get('market_value', 0),
                daily_record.get('total_assets', 0),
                daily_record.get('holdings_count', 0)
            ))
    
    def save_ai_decision(self, session_id: str, decision: Dict[str, Any]):
        """保存AI决策历史"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ai_decisions
                (session_id, decision_date, decision_type, stock_code, action,
                 confidence, reason, input_data, output_data, create_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                decision.get('date', ''),
                decision.get('type', ''),
                decision.get('code', ''),
                decision.get('action', ''),
                decision.get('confidence', 0),
                decision.get('reason', ''),
                json.dumps(decision.get('input', {}), ensure_ascii=False),
                json.dumps(decision.get('output', {}), ensure_ascii=False),
                datetime.now().isoformat()
            ))
    
    def get_backtest_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取回测会话列表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM backtest_sessions
                ORDER BY create_time DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_session_trades(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的交易记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM trades
                WHERE session_id = ?
                ORDER BY trade_date, create_time
            ''', (session_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_session_daily_assets(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的每日资产"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM daily_assets
                WHERE session_id = ?
                ORDER BY trade_date
            ''', (session_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_session_ai_decisions(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的AI决策历史"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM ai_decisions
                WHERE session_id = ?
                ORDER BY decision_date, create_time
            ''', (session_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def compare_sessions(self, session_ids: List[str]) -> Dict[str, Any]:
        """对比多个回测会话"""
        sessions = []
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(session_ids))
            cursor.execute(f'''
                SELECT * FROM backtest_sessions
                WHERE session_id IN ({placeholders})
                ORDER BY total_return DESC
            ''', session_ids)
            
            rows = cursor.fetchall()
            sessions = [dict(row) for row in rows]
        
        return {
            'sessions': sessions,
            'best': sessions[0] if sessions else None,
            'worst': sessions[-1] if sessions else None
        }

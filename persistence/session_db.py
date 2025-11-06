"""
会话持久化数据库
用于支持浏览器刷新后恢复数据，程序重启时清空
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import os
import atexit


class SessionDB:
    """会话数据库管理类（支持刷新恢复）"""
    
    def __init__(self, db_path: str = "data/current_session.db"):
        """
        初始化会话数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 程序启动时清空旧数据
        if os.path.exists(db_path):
            os.remove(db_path)
        
        # 初始化数据库表
        self._init_database()
        
        # 注册程序退出时的清理函数
        atexit.register(self._cleanup)
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 当前运行状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_session (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # AI模型资产表（竞技场模式）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_assets (
                model_name TEXT PRIMARY KEY,
                total_assets REAL NOT NULL,
                profit_pct REAL NOT NULL,
                color TEXT,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # 图表数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chart_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT,
                trade_date TEXT NOT NULL,
                total_assets REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # AI日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                message TEXT NOT NULL,
                color TEXT
            )
        ''')
        
        # 交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT,
                trade_date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                action TEXT NOT NULL,
                price REAL NOT NULL,
                volume INTEGER NOT NULL,
                amount REAL NOT NULL
            )
        ''')
        
        # 持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                volume INTEGER NOT NULL,
                cost_price REAL NOT NULL,
                current_price REAL,
                market_value REAL,
                profit_loss REAL,
                profit_loss_pct REAL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _cleanup(self):
        """程序退出时清理"""
        # 不删除数据库文件，因为可能需要恢复
        pass
    
    def save_session_state(self, key: str, value: Any):
        """
        保存会话状态
        
        Args:
            key: 状态键
            value: 状态值
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO current_session (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', (key, json.dumps(value, ensure_ascii=False), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_session_state(self, key: str) -> Optional[Any]:
        """
        获取会话状态
        
        Args:
            key: 状态键
            
        Returns:
            状态值
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM current_session WHERE key = ?', (key,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def save_model_asset(self, model_name: str, total_assets: float, 
                        profit_pct: float, color: str = None):
        """
        保存模型资产数据
        
        Args:
            model_name: 模型名称
            total_assets: 总资产
            profit_pct: 收益率
            color: 颜色
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO model_assets 
            (model_name, total_assets, profit_pct, color, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (model_name, total_assets, profit_pct, color, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_all_model_assets(self) -> List[Dict[str, Any]]:
        """获取所有模型资产"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM model_assets ORDER BY total_assets DESC')
        rows = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return rows
    
    def add_chart_data(self, model_name: Optional[str], trade_date: str, total_assets: float):
        """
        添加图表数据点
        
        Args:
            model_name: 模型名称（竞技场模式）
            trade_date: 交易日期
            total_assets: 总资产
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chart_data (model_name, trade_date, total_assets, created_at)
            VALUES (?, ?, ?, ?)
        ''', (model_name, trade_date, total_assets, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_chart_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取图表数据
        
        Returns:
            {model_name: [{date, assets}, ...]}
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM chart_data ORDER BY id')
        rows = cursor.fetchall()
        
        conn.close()
        
        # 按模型分组
        result = {}
        for row in rows:
            model = row['model_name'] or 'default'
            if model not in result:
                result[model] = []
            result[model].append({
                'date': row['trade_date'],
                'assets': row['total_assets']
            })
        
        return result
    
    def add_ai_log(self, model_name: str, message: str, color: str = None):
        """
        添加AI日志
        
        Args:
            model_name: 模型名称
            message: 日志消息
            color: 颜色
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO ai_logs (model_name, timestamp, message, color)
            VALUES (?, ?, ?, ?)
        ''', (model_name, datetime.now().isoformat(), message, color))
        
        conn.commit()
        conn.close()
    
    def get_ai_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取AI日志（最新的在前）
        
        Args:
            limit: 数量限制
            
        Returns:
            日志列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM ai_logs 
            ORDER BY id DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return rows
    
    def add_trade(self, trade_data: Dict[str, Any]):
        """添加交易记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades 
            (model_name, trade_date, stock_code, action, price, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data.get('model_name'),
            trade_data['date'],
            trade_data['stock_code'],
            trade_data['action'],
            trade_data['price'],
            trade_data['volume'],
            trade_data['amount']
        ))
        
        conn.commit()
        conn.close()
    
    def get_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取交易记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            ORDER BY id DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return rows
    
    def update_holdings(self, model_name: Optional[str], holdings_list: List[Dict[str, Any]]):
        """
        更新持仓数据
        
        Args:
            model_name: 模型名称
            holdings_list: 持仓列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 先删除该模型的旧持仓
        if model_name:
            cursor.execute('DELETE FROM holdings WHERE model_name = ?', (model_name,))
        else:
            cursor.execute('DELETE FROM holdings WHERE model_name IS NULL')
        
        # 插入新持仓
        for holding in holdings_list:
            cursor.execute('''
                INSERT INTO holdings
                (model_name, stock_code, stock_name, volume, cost_price, 
                 current_price, market_value, profit_loss, profit_loss_pct, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                model_name,
                holding['stock_code'],
                holding.get('stock_name', ''),
                holding['volume'],
                holding['cost_price'],
                holding.get('current_price'),
                holding.get('market_value'),
                holding.get('profit_loss'),
                holding.get('profit_loss_pct'),
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def get_holdings(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取持仓数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if model_name:
            cursor.execute('SELECT * FROM holdings WHERE model_name = ?', (model_name,))
        else:
            cursor.execute('SELECT * FROM holdings WHERE model_name IS NULL')
        
        rows = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return rows
    
    def has_active_session(self) -> bool:
        """检查是否有活跃的会话"""
        is_running = self.get_session_state('is_running')
        return is_running is True
    
    def clear_all(self):
        """清空所有数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM current_session')
        cursor.execute('DELETE FROM model_assets')
        cursor.execute('DELETE FROM chart_data')
        cursor.execute('DELETE FROM ai_logs')
        cursor.execute('DELETE FROM trades')
        cursor.execute('DELETE FROM holdings')
        
        conn.commit()
        conn.close()

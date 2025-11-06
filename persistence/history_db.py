"""
历史交易记录数据库管理
用于保存每次回测的完整记录，供后续分析使用
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import os


class HistoryDB:
    """历史交易记录数据库管理类"""
    
    def __init__(self, db_path: str = "data/trading_history.db"):
        """
        初始化历史数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 初始化数据库表
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 交易会话表（每次回测一条记录）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_sessions (
                session_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                initial_capital REAL NOT NULL,
                final_capital REAL,
                profit_rate REAL,
                trade_count INTEGER,
                win_count INTEGER,
                win_rate REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                config_json TEXT,
                status TEXT DEFAULT 'running'
            )
        ''')
        
        # AI模型表（竞技场模式）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_models (
                model_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                initial_capital REAL NOT NULL,
                final_capital REAL,
                profit_rate REAL,
                trade_count INTEGER,
                win_count INTEGER,
                win_rate REAL,
                ranking INTEGER,
                FOREIGN KEY (session_id) REFERENCES trading_sessions(session_id)
            )
        ''')
        
        # 每日资产表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                model_name TEXT,
                trade_date TEXT NOT NULL,
                total_assets REAL NOT NULL,
                cash REAL NOT NULL,
                stock_value REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES trading_sessions(session_id)
            )
        ''')
        
        # 交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                model_name TEXT,
                trade_date TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                action TEXT NOT NULL,
                price REAL NOT NULL,
                volume INTEGER NOT NULL,
                amount REAL NOT NULL,
                reason TEXT,
                FOREIGN KEY (session_id) REFERENCES trading_sessions(session_id)
            )
        ''')
        
        # AI思考日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES trading_sessions(session_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_session(self, mode: str, initial_capital: float, config: Dict[str, Any]) -> str:
        """
        创建新的交易会话
        
        Args:
            mode: 交易模式（'single' or 'arena'）
            initial_capital: 初始资金
            config: 配置信息
            
        Returns:
            session_id: 会话ID
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        start_time = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trading_sessions 
            (session_id, mode, start_time, initial_capital, config_json, status)
            VALUES (?, ?, ?, ?, ?, 'running')
        ''', (session_id, mode, start_time, initial_capital, json.dumps(config, ensure_ascii=False)))
        
        conn.commit()
        conn.close()
        
        return session_id
    
    def update_session_complete(self, session_id: str, final_capital: float, 
                                profit_rate: float, stats: Dict[str, Any]):
        """
        更新会话为完成状态
        
        Args:
            session_id: 会话ID
            final_capital: 最终资金
            profit_rate: 收益率
            stats: 统计信息
        """
        end_time = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE trading_sessions
            SET end_time = ?,
                final_capital = ?,
                profit_rate = ?,
                trade_count = ?,
                win_count = ?,
                win_rate = ?,
                max_drawdown = ?,
                sharpe_ratio = ?,
                status = 'completed'
            WHERE session_id = ?
        ''', (
            end_time,
            final_capital,
            profit_rate,
            stats.get('trade_count', 0),
            stats.get('win_count', 0),
            stats.get('win_rate', 0),
            stats.get('max_drawdown', 0),
            stats.get('sharpe_ratio', 0),
            session_id
        ))
        
        conn.commit()
        conn.close()
    
    def save_ai_model(self, session_id: str, model_data: Dict[str, Any]):
        """
        保存AI模型数据（竞技场模式）
        
        Args:
            session_id: 会话ID
            model_data: 模型数据
        """
        model_id = f"{session_id}_{model_data['model_name']}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO ai_models
            (model_id, session_id, model_name, initial_capital, final_capital,
             profit_rate, trade_count, win_count, win_rate, ranking)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            model_id,
            session_id,
            model_data['model_name'],
            model_data['initial_capital'],
            model_data.get('final_capital'),
            model_data.get('profit_rate'),
            model_data.get('trade_count', 0),
            model_data.get('win_count', 0),
            model_data.get('win_rate', 0),
            model_data.get('ranking')
        ))
        
        conn.commit()
        conn.close()
    
    def save_daily_asset(self, session_id: str, model_name: Optional[str], 
                        trade_date: str, assets_data: Dict[str, float]):
        """
        保存每日资产数据
        
        Args:
            session_id: 会话ID
            model_name: 模型名称（竞技场模式）
            trade_date: 交易日期
            assets_data: 资产数据
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO daily_assets
            (session_id, model_name, trade_date, total_assets, cash, stock_value)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            model_name,
            trade_date,
            assets_data['total_assets'],
            assets_data['cash'],
            assets_data['stock_value']
        ))
        
        conn.commit()
        conn.close()
    
    def save_trade(self, session_id: str, model_name: Optional[str], trade_data: Dict[str, Any]):
        """
        保存交易记录
        
        Args:
            session_id: 会话ID
            model_name: 模型名称
            trade_data: 交易数据
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades
            (session_id, model_name, trade_date, stock_code, action, 
             price, volume, amount, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            model_name,
            trade_data['date'],
            trade_data['stock_code'],
            trade_data['action'],
            trade_data['price'],
            trade_data['volume'],
            trade_data['amount'],
            trade_data.get('reason', '')
        ))
        
        conn.commit()
        conn.close()
    
    def save_ai_log(self, session_id: str, model_name: str, message: str):
        """
        保存AI思考日志
        
        Args:
            session_id: 会话ID
            model_name: 模型名称
            message: 日志消息
        """
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO ai_logs
            (session_id, model_name, timestamp, message)
            VALUES (?, ?, ?, ?)
        ''', (session_id, model_name, timestamp, message))
        
        conn.commit()
        conn.close()
    
    def get_session_list(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取历史会话列表
        
        Args:
            limit: 返回数量限制
            
        Returns:
            会话列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trading_sessions
            ORDER BY start_time DESC
            LIMIT ?
        ''', (limit,))
        
        sessions = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return sessions
    
    def get_session_detail(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话详细信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话详情（包含模型、交易、日志等）
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取会话基本信息
        cursor.execute('SELECT * FROM trading_sessions WHERE session_id = ?', (session_id,))
        session = dict(cursor.fetchone())
        
        # 获取AI模型信息
        cursor.execute('SELECT * FROM ai_models WHERE session_id = ?', (session_id,))
        session['models'] = [dict(row) for row in cursor.fetchall()]
        
        # 获取每日资产
        cursor.execute('SELECT * FROM daily_assets WHERE session_id = ? ORDER BY trade_date', 
                      (session_id,))
        session['daily_assets'] = [dict(row) for row in cursor.fetchall()]
        
        # 获取交易记录
        cursor.execute('SELECT * FROM trades WHERE session_id = ? ORDER BY trade_date', 
                      (session_id,))
        session['trades'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return session
    
    def delete_session(self, session_id: str):
        """
        删除指定会话及其所有数据
        
        Args:
            session_id: 会话ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM ai_logs WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM trades WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM daily_assets WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM ai_models WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM trading_sessions WHERE session_id = ?', (session_id,))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取历史统计信息
        
        Returns:
            统计数据
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总会话数
        cursor.execute('SELECT COUNT(*) FROM trading_sessions WHERE status = "completed"')
        total_sessions = cursor.fetchone()[0]
        
        # 平均收益率
        cursor.execute('SELECT AVG(profit_rate) FROM trading_sessions WHERE status = "completed"')
        avg_profit = cursor.fetchone()[0] or 0
        
        # 最佳收益率
        cursor.execute('''
            SELECT session_id, profit_rate, start_time 
            FROM trading_sessions 
            WHERE status = "completed"
            ORDER BY profit_rate DESC 
            LIMIT 1
        ''')
        best_session = cursor.fetchone()
        
        # 总交易次数
        cursor.execute('SELECT SUM(trade_count) FROM trading_sessions WHERE status = "completed"')
        total_trades = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_sessions': total_sessions,
            'avg_profit_rate': avg_profit,
            'best_session': {
                'session_id': best_session[0] if best_session else None,
                'profit_rate': best_session[1] if best_session else 0,
                'date': best_session[2] if best_session else None
            },
            'total_trades': int(total_trades)
        }

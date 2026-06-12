"""
股票数据库管理模块
"""

import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional

from loguru import logger


class StockDatabase:
    """股票数据库管理类"""

    def __init__(self, db_path: str = "stocks.db"):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self):
        """初始化数据库和表"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    sector TEXT,
                    stock_type TEXT DEFAULT 'US',
                    current_price REAL,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON stocks(ticker)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_enabled ON stocks(enabled)")

            conn.commit()

    def get_all_stocks(
        self, enabled_only: bool = True, stock_type: str = None
    ) -> List[Dict]:
        """获取所有股票"""
        with self.get_connection() as conn:
            sql = "SELECT * FROM stocks WHERE 1=1"
            params = []

            if enabled_only:
                sql += " AND enabled = 1"

            if stock_type:
                sql += " AND stock_type = ?"
                params.append(stock_type)

            sql += " ORDER BY ticker"

            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_stock_by_ticker(self, ticker: str) -> Optional[Dict]:
        """根据 ticker 获取股票信息"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_stock(
        self, ticker: str, name: str, sector: str = "", stock_type: str = "US"
    ) -> bool:
        """添加新股票"""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO stocks (ticker, name, sector, stock_type, enabled)
                    VALUES (?, ?, ?, ?, 1)
                """,
                    (ticker.upper(), name, sector, stock_type),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def update_stock(
        self,
        ticker: str,
        name: str = None,
        sector: str = None,
        stock_type: str = None,
        enabled: bool = None,
    ) -> bool:
        """更新股票信息"""
        with self.get_connection() as conn:
            update_fields = []
            params = []

            if name is not None:
                update_fields.append("name = ?")
                params.append(name)
            if sector is not None:
                update_fields.append("sector = ?")
                params.append(sector)
            if stock_type is not None:
                update_fields.append("stock_type = ?")
                params.append(stock_type)
            if enabled is not None:
                update_fields.append("enabled = ?")
                params.append(enabled)

            if not update_fields:
                return False

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(ticker.upper())

            query = f"UPDATE stocks SET {', '.join(update_fields)} WHERE ticker = ?"
            cursor = conn.execute(query, params)
            conn.commit()

            return cursor.rowcount > 0

    def delete_stock(self, ticker: str) -> bool:
        """删除股票"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM stocks WHERE ticker = ?", (ticker.upper(),)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_stocks_dict(self, enabled_only: bool = True) -> Dict[str, str]:
        """获取股票字典（ticker -> name）"""
        stocks = self.get_all_stocks(enabled_only)
        return {stock["ticker"]: stock["name"] for stock in stocks}

    def search_stocks(self, query: str, enabled_only: bool = True) -> List[Dict]:
        """搜索股票"""
        with self.get_connection() as conn:
            sql = """
                SELECT * FROM stocks
                WHERE (ticker LIKE ? OR name LIKE ?)
            """
            params = [f"%{query}%", f"%{query}%"]

            if enabled_only:
                sql += " AND enabled = 1"

            sql += " ORDER BY ticker"

            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

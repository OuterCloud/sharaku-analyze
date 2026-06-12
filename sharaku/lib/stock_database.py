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

            # 插入默认股票数据（如果表为空）
            cursor = conn.execute("SELECT COUNT(*) FROM stocks")
            if cursor.fetchone()[0] == 0:
                default_stocks = [
                    # 科技巨头
                    ("AAPL", "Apple Inc", "Technology"),
                    ("MSFT", "Microsoft Corporation", "Technology"),
                    ("GOOGL", "Alphabet Inc", "Technology"),
                    ("GOOG", "Alphabet Inc Class C", "Technology"),
                    ("AMZN", "Amazon.com Inc", "Consumer Cyclical"),
                    ("META", "Meta Platforms Inc", "Technology"),
                    ("NVDA", "NVIDIA Corporation", "Technology"),
                    ("TSM", "Taiwan Semiconductor", "Technology"),
                    ("AVGO", "Broadcom Inc", "Technology"),
                    ("ORCL", "Oracle Corporation", "Technology"),
                    ("ADBE", "Adobe Inc", "Technology"),
                    ("CRM", "Salesforce Inc", "Technology"),
                    ("CSCO", "Cisco Systems", "Technology"),
                    ("ACN", "Accenture PLC", "Technology"),
                    ("IBM", "IBM Corporation", "Technology"),
                    ("INTC", "Intel Corporation", "Technology"),
                    ("AMD", "Advanced Micro Devices", "Technology"),
                    ("QCOM", "Qualcomm Inc", "Technology"),
                    ("TXN", "Texas Instruments", "Technology"),
                    ("NOW", "ServiceNow Inc", "Technology"),
                    ("INTU", "Intuit Inc", "Technology"),
                    ("AMAT", "Applied Materials", "Technology"),
                    ("MU", "Micron Technology", "Technology"),
                    ("LRCX", "Lam Research", "Technology"),
                    ("KLAC", "KLA Corporation", "Technology"),
                    ("SNPS", "Synopsys Inc", "Technology"),
                    ("CDNS", "Cadence Design Systems", "Technology"),
                    ("MRVL", "Marvell Technology", "Technology"),
                    ("ON", "ON Semiconductor", "Technology"),
                    ("NXPI", "NXP Semiconductors", "Technology"),
                    ("ARM", "Arm Holdings", "Technology"),
                    ("SMCI", "Super Micro Computer", "Technology"),
                    ("DELL", "Dell Technologies", "Technology"),
                    ("HPQ", "HP Inc", "Technology"),
                    ("NET", "Cloudflare Inc", "Technology"),
                    ("CRWD", "CrowdStrike Holdings", "Technology"),
                    ("PANW", "Palo Alto Networks", "Technology"),
                    ("ZS", "Zscaler Inc", "Technology"),
                    ("DDOG", "Datadog Inc", "Technology"),
                    ("SNOW", "Snowflake Inc", "Technology"),
                    ("PLTR", "Palantir Technologies", "Technology"),
                    ("SHOP", "Shopify Inc", "Technology"),
                    ("SQ", "Block Inc", "Technology"),
                    ("COIN", "Coinbase Global", "Technology"),
                    ("HOOD", "Robinhood Markets", "Technology"),
                    ("U", "Unity Software", "Technology"),
                    ("RBLX", "Roblox Corporation", "Technology"),
                    ("UBER", "Uber Technologies", "Technology"),
                    ("LYFT", "Lyft Inc", "Technology"),
                    ("ABNB", "Airbnb Inc", "Technology"),
                    ("DASH", "DoorDash Inc", "Technology"),
                    # 电动车/新能源
                    ("TSLA", "Tesla Inc", "Consumer Cyclical"),
                    ("RIVN", "Rivian Automotive", "Consumer Cyclical"),
                    ("LCID", "Lucid Group", "Consumer Cyclical"),
                    ("NIO", "NIO Inc", "Consumer Cyclical"),
                    ("XPEV", "XPeng Inc", "Consumer Cyclical"),
                    ("LI", "Li Auto Inc", "Consumer Cyclical"),
                    ("F", "Ford Motor", "Consumer Cyclical"),
                    ("GM", "General Motors", "Consumer Cyclical"),
                    # AI/机器人
                    ("AAOI", "Applied Optoelectronics", "Technology"),
                    ("AI", "C3.ai Inc", "Technology"),
                    ("BBAI", "BigBear.ai Holdings", "Technology"),
                    ("PATH", "UiPath Inc", "Technology"),
                    ("IONQ", "IonQ Inc", "Technology"),
                    ("RGTI", "Rigetti Computing", "Technology"),
                    # 金融
                    ("JPM", "JPMorgan Chase", "Financial"),
                    ("BAC", "Bank of America", "Financial"),
                    ("GS", "Goldman Sachs", "Financial"),
                    ("MS", "Morgan Stanley", "Financial"),
                    ("V", "Visa Inc", "Financial"),
                    ("MA", "Mastercard Inc", "Financial"),
                    ("PYPL", "PayPal Holdings", "Financial"),
                    ("BRK-B", "Berkshire Hathaway B", "Financial"),
                    # 医疗健康
                    ("JNJ", "Johnson & Johnson", "Healthcare"),
                    ("UNH", "UnitedHealth Group", "Healthcare"),
                    ("LLY", "Eli Lilly", "Healthcare"),
                    ("NVO", "Novo Nordisk", "Healthcare"),
                    ("ABBV", "AbbVie Inc", "Healthcare"),
                    ("PFE", "Pfizer Inc", "Healthcare"),
                    ("MRK", "Merck & Co", "Healthcare"),
                    ("TMO", "Thermo Fisher Scientific", "Healthcare"),
                    # 消费
                    ("WMT", "Walmart Inc", "Consumer Staples"),
                    ("COST", "Costco Wholesale", "Consumer Staples"),
                    ("KO", "Coca-Cola Company", "Consumer Staples"),
                    ("PEP", "PepsiCo Inc", "Consumer Staples"),
                    ("PG", "Procter & Gamble", "Consumer Staples"),
                    ("NKE", "Nike Inc", "Consumer Cyclical"),
                    ("SBUX", "Starbucks Corporation", "Consumer Cyclical"),
                    ("MCD", "McDonald's Corporation", "Consumer Cyclical"),
                    ("DIS", "Walt Disney Company", "Communication"),
                    ("NFLX", "Netflix Inc", "Communication"),
                    # 能源
                    ("XOM", "Exxon Mobil", "Energy"),
                    ("CVX", "Chevron Corporation", "Energy"),
                    # 工业
                    ("CAT", "Caterpillar Inc", "Industrials"),
                    ("BA", "Boeing Company", "Industrials"),
                    ("HON", "Honeywell International", "Industrials"),
                    ("GE", "GE Aerospace", "Industrials"),
                    ("RTX", "RTX Corporation", "Industrials"),
                    ("LMT", "Lockheed Martin", "Industrials"),
                    # ETF
                    ("SPY", "SPDR S&P 500 ETF", "ETF"),
                    ("QQQ", "Invesco QQQ Trust", "ETF"),
                    ("IWM", "iShares Russell 2000", "ETF"),
                    ("DIA", "SPDR Dow Jones ETF", "ETF"),
                    ("ARKK", "ARK Innovation ETF", "ETF"),
                    ("SOXX", "iShares Semiconductor", "ETF"),
                    ("XLF", "Financial Select Sector", "ETF"),
                    ("XLE", "Energy Select Sector", "ETF"),
                    ("TQQQ", "ProShares UltraPro QQQ", "ETF"),
                    ("SQQQ", "ProShares UltraPro Short QQQ", "ETF"),
                ]

                conn.executemany(
                    """
                    INSERT INTO stocks (ticker, name, sector, enabled)
                    VALUES (?, ?, ?, 1)
                """,
                    default_stocks,
                )

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

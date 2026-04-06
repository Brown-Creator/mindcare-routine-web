import aiosqlite
import os
import asyncio
from pathlib import Path

DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "autotrader.db"

async def init_db():
    if not DB_DIR.exists():
        DB_DIR.mkdir(parents=True)
        
    async with aiosqlite.connect(DB_PATH) as db:
        # 주문 테이블
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE,
            ticker TEXT,
            name TEXT,
            side TEXT,
            order_type TEXT,
            price REAL,
            quantity INTEGER,
            filled_quantity INTEGER DEFAULT 0,
            avg_filled_price REAL DEFAULT 0,
            status TEXT,
            reason TEXT,
            risk_approved BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filled_at TIMESTAMP
        )
        """)
        
        # 전략 로그 테이블
        await db.execute("""
        CREATE TABLE IF NOT EXISTS strategy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            name TEXT,
            action TEXT,
            from_state TEXT,
            to_state TEXT,
            score_bottom INTEGER,
            score_trend INTEGER,
            score_momentum INTEGER,
            score_risk INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        await db.commit()

# 앱 기동시 DB 초기화용 함수
async def setup_database():
    await init_db()

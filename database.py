"""GEO系统数据库层 — SQLite (修复版: 连接池 + 上下文管理器 + 防泄漏)"""
import sqlite3
import os
import threading
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "geo.db")
_connection_pool = threading.local()


def get_db():
    """获取当前线程的数据库连接（连接复用，自动管理）"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if not hasattr(_connection_pool, "conn") or _connection_pool.conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _connection_pool.conn = conn
    return _connection_pool.conn


def close_db():
    """关闭线程级数据库连接"""
    if hasattr(_connection_pool, "conn") and _connection_pool.conn:
        _connection_pool.conn.close()
        _connection_pool.conn = None


@contextmanager
def db_cursor():
    """数据库游标上下文管理器 — 自动处理事务和异常
    
    用法:
        with db_cursor() as cursor:
            cursor.execute("SELECT ...")
            return cursor.fetchall()
    """
    conn = get_db()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    # cursor由Python GC自动清理


def init_db():
    """初始化数据库表"""
    with db_cursor() as cursor:
        # 内容表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content_type TEXT NOT NULL,
                body_markdown TEXT NOT NULL,
                body_html TEXT,
                json_ld TEXT,
                tags TEXT,
                keywords TEXT,
                seo_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP
            )
        """)

        # AI可见度追踪记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                engine TEXT NOT NULL,
                engine_name TEXT NOT NULL,
                query_text TEXT NOT NULL,
                response_text TEXT NOT NULL,
                brand_mentioned INTEGER DEFAULT 0,
                mention_position INTEGER,
                mention_context TEXT,
                confidence REAL DEFAULT 0.0,
                competitor_mentions TEXT,
                score INTEGER DEFAULT 0,
                response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 发布记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS publish_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id INTEGER,
                platform TEXT NOT NULL,
                platform_url TEXT,
                status TEXT DEFAULT 'pending',
                error_msg TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (content_id) REFERENCES contents(id)
            )
        """)

        # 日报记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                visibility_score INTEGER DEFAULT 0,
                score_change INTEGER DEFAULT 0,
                total_mentions INTEGER DEFAULT 0,
                total_queries INTEGER DEFAULT 0,
                report_markdown TEXT,
                report_html TEXT,
                sent_email INTEGER DEFAULT 0,
                sent_wechat INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 竞品追踪
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitor_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_name TEXT NOT NULL,
                engine TEXT NOT NULL,
                query_text TEXT NOT NULL,
                mentioned INTEGER DEFAULT 0,
                position INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_engine ON ai_mentions(engine)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_date ON ai_mentions(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contents_type ON contents(content_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contents_status ON contents(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_date ON daily_reports(report_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_publish_platform ON publish_logs(platform)")


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")

"""Dashboard API — 提供前端面板数据"""
from fastapi import APIRouter
from pathlib import Path
from database import db_cursor

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def get_overview():
    """获取总览数据"""
    with db_cursor() as cursor:
        # 今日数据
        cursor.execute("""
            SELECT
                COUNT(*) as total_queries,
                SUM(brand_mentioned) as total_mentions,
                AVG(score) as avg_score
            FROM ai_mentions
            WHERE DATE(created_at) = DATE('now', 'localtime')
        """)
        today = dict(cursor.fetchone())
        today_score = round(today.get("avg_score") or 0)

        # 昨日数据
        cursor.execute("""
            SELECT AVG(score) as avg_score
            FROM ai_mentions
            WHERE DATE(created_at) = DATE('now', '-1 day', 'localtime')
        """)
        yesterday = dict(cursor.fetchone())
        yesterday_score = round(yesterday.get("avg_score") or 0)
        score_change = today_score - yesterday_score

        # 总内容数
        cursor.execute("SELECT COUNT(*) as cnt FROM contents")
        content_count = dict(cursor.fetchone())["cnt"]

        # 本月提及率
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(brand_mentioned) as mentioned
            FROM ai_mentions
            WHERE created_at >= DATE('now', '-30 days', 'localtime')
        """)
        month = dict(cursor.fetchone())
        mention_rate = (
            round(month["mentioned"] / month["total"] * 100, 1)
            if month["total"] > 0
            else 0
        )

    return {
        "today_score": today_score,
        "score_change": score_change,
        "total_queries_today": today.get("total_queries") or 0,
        "total_mentions_today": today.get("total_mentions") or 0,
        "content_count": content_count,
        "mention_rate_30d": mention_rate,
    }


@router.get("/trend")
def get_trend(days: int = 30):
    """获取趋势数据"""
    with db_cursor() as cursor:
        cursor.execute("""
            SELECT
                DATE(created_at) as date,
                AVG(score) as avg_score,
                SUM(brand_mentioned) as mentions,
                COUNT(*) as queries,
                COUNT(DISTINCT engine) as engines
            FROM ai_mentions
            WHERE created_at >= DATE('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """, (f"-{days} days",))

        trend = []
        for row in cursor.fetchall():
            trend.append({
                "date": row["date"],
                "score": round(row["avg_score"] or 0),
                "mentions": row["mentions"] or 0,
                "queries": row["queries"],
                "engines": row["engines"],
            })

    return {"trend": trend}


@router.get("/engines")
def get_engine_stats():
    """获取各引擎统计"""
    with db_cursor() as cursor:
        cursor.execute("""
            SELECT
                engine_name,
                COUNT(*) as queries,
                SUM(brand_mentioned) as mentions,
                AVG(score) as avg_score,
                AVG(response_time_ms) as avg_response_time
            FROM ai_mentions
            WHERE created_at >= DATE('now', '-7 days', 'localtime')
            GROUP BY engine_name
            ORDER BY avg_score DESC
        """)

        engines = []
        for row in cursor.fetchall():
            engines.append({
                "name": row["engine_name"],
                "queries": row["queries"],
                "mentions": row["mentions"] or 0,
                "avg_score": round(row["avg_score"] or 0),
                "avg_response_ms": round(row["avg_response_time"] or 0),
            })

    return {"engines": engines}


@router.get("/recent-mentions")
def get_recent_mentions(limit: int = 10):
    """获取最近提及记录"""
    with db_cursor() as cursor:
        cursor.execute("""
            SELECT
                engine_name,
                query_text,
                brand_mentioned,
                score,
                mention_context,
                created_at
            FROM ai_mentions
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        mentions = []
        for row in cursor.fetchall():
            mentions.append({
                "engine": row["engine_name"],
                "query": row["query_text"][:50],
                "mentioned": bool(row["brand_mentioned"]),
                "score": row["score"],
                "context": row["mention_context"] or "",
                "time": row["created_at"],
            })

    return {"mentions": mentions}


@router.get("/publish-log")
def get_publish_log(limit: int = 10):
    """获取发布日志"""
    with db_cursor() as cursor:
        cursor.execute("""
            SELECT p.platform, p.status, p.platform_url, p.created_at, c.title
            FROM publish_logs p
            LEFT JOIN contents c ON p.content_id = c.id
            ORDER BY p.created_at DESC
            LIMIT ?
        """, (limit,))

        logs = []
        for row in cursor.fetchall():
            logs.append({
                "platform": row["platform"],
                "status": row["status"],
                "url": row["platform_url"] or "",
                "title": (row["title"] or "未知")[:40],
                "time": row["created_at"],
            })

    return {"logs": logs}

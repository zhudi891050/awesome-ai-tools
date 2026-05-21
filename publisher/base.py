"""发布器基类"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from database import get_db

logger = logging.getLogger("geo.publisher")


class BasePublisher(ABC):
    """发布器基类"""

    def __init__(self, platform_name, config):
        self.platform_name = platform_name
        self.config = config

    @abstractmethod
    async def publish(self, content):
        """发布内容，返回 (success, url_or_error)"""
        pass

    def _save_log(self, content_id, success, url_or_error):
        """记录发布日志"""
        try:
            from database import db_cursor
            with db_cursor() as cursor:
                cursor.execute(
                    """INSERT INTO publish_logs (content_id, platform, platform_url, status, error_msg)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        content_id,
                        self.platform_name,
                        url_or_error if success else None,
                        "success" if success else "failed",
                        None if success else url_or_error,
                    ),
                )
        except Exception as e:
            logger.exception(f"[{self.platform_name}] 日志保存失败")

    def _save_content(self, title, content_body, content_type, json_ld, tags=""):
        """保存内容到数据库"""
        try:
            from database import db_cursor
            with db_cursor() as cursor:
                cursor.execute(
                    """INSERT INTO contents (title, content_type, body_markdown, json_ld, tags, status)
                       VALUES (?, ?, ?, ?, ?, 'published')""",
                    (title, content_type, content_body, json_ld, tags),
                )
                content_id = cursor.lastrowid
                cursor.execute(
                    "UPDATE contents SET published_at = ? WHERE id = ?",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), content_id),
                )
            return content_id
        except Exception:
            logger.exception("[DB] 内容保存失败")
            return None

"""CSDN发布器

CSDN是中国技术社区最大平台，AI引用权重高。
"""
import httpx
from .base import BasePublisher


class CSDNPublisher(BasePublisher):
    """CSDN博客发布"""

    def __init__(self, config):
        super().__init__("csdn", config)
        pub_cfg = config.get("publishers", {}).get("csdn", {})
        self.api_key = pub_cfg.get("api_key", "")
        self._enabled = bool(self.api_key)

    @property
    def enabled(self):
        return self._enabled

    async def publish(self, content):
        """发布CSDN文章"""
        if not self.enabled:
            return False, "CSDN API Key未配置"

        title = content.get("title", "")
        body = content.get("content", "")
        tags = content.get("tags", "AI工具,人工智能")

        try:
            # CSDN开放API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "title": title,
                "content": body,
                "tags": tags,
                "categories": "人工智能",
                "type": "original",  # 原创
                "status": "public",  # 公开发布
            }

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.csdn.net/v2/article",
                    headers=headers,
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    article_url = data.get("url", "")
                    content_id = self._save_content(
                        title, body, "csdn_article",
                        content.get("json_ld", ""), tags
                    )
                    self._save_log(content_id, True, article_url)
                    return True, article_url
                else:
                    return False, f"CSDN API错误: {resp.status_code} {resp.text[:200]}"

        except Exception as e:
            return False, f"CSDN发布异常: {str(e)}"

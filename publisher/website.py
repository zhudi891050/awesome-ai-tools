"""自有网站发布器 — 将文章推送到 xinfangzhouai.com API"""
import os
import json
import httpx
from datetime import datetime
from .base import BasePublisher


class WebsitePublisher(BasePublisher):
    """将GEO生成的文章同步到新方舟AI网站"""

    def __init__(self, config):
        super().__init__("website", config)
        pub_cfg = config.get("publishers", {}).get("website", {})
        # 优先从环境变量读取，方便部署切换
        self.api_url = os.environ.get("WEBSITE_API_URL", pub_cfg.get("api_url", "https://xinfangzhouai.com/api"))
        self.api_key = os.environ.get("WEBSITE_API_KEY", pub_cfg.get("api_key", ""))
        self._enabled = True  # website始终启用，推送失败也继续

    @property
    def enabled(self):
        return self._enabled

    async def publish(self, content):
        """推送一篇文章到网站"""
        title = content.get("title", "")
        body = content.get("content", "")
        if not title or not body:
            return False, "缺少标题或内容"

        payload = {
            "title": title,
            "content": body,
            "content_type": content.get("type", "tool_review"),
            "category": content.get("category", ""),
            "tags": content.get("tags", ""),
            "summary": content.get("summary", title[:200]),
            "json_ld": content.get("json_ld", ""),
            "author": content.get("author", "新方舟AI"),
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                resp = await client.post(
                    f"{self.api_url}/articles",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    url = f"{self.api_url.replace('/api', '')}/article/{data.get('slug', '')}"
                    return True, url
                else:
                    return False, f"API错误({resp.status_code}): {resp.text[:200]}"
        except httpx.ConnectError:
            return False, f"无法连接到 {self.api_url}（网站未部署）"
        except Exception as e:
            return False, str(e)

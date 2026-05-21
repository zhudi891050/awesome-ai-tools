"""掘金发布器 (修复版: Cookie格式兼容)

掘金是开发者社区，技术类AI工具内容在该平台权重高。
"""
import json
import httpx
from pathlib import Path
from .base import BasePublisher


class JuejinPublisher(BasePublisher):
    """掘金文章发布"""

    def __init__(self, config):
        super().__init__("juejin", config)
        pub_cfg = config.get("publishers", {}).get("juejin", {})
        self.cookie_file = Path(__file__).parent.parent / pub_cfg.get(
            "cookie_file", "data/juejin_cookie.json"
        )
        self._enabled = self.cookie_file.exists()

    @property
    def enabled(self):
        return self._enabled

    def _load_cookies(self):
        """加载Cookie，兼容浏览器导出的多种格式"""
        if not self.cookie_file.exists():
            return {}

        cookies_raw = json.loads(self.cookie_file.read_text(encoding="utf-8"))
        return self._parse_cookies(cookies_raw)

    def _parse_cookies(self, data):
        """递归解析各种Cookie格式"""
        # 格式1: [{name, value, domain, ...}] — 浏览器导出格式
        if isinstance(data, list):
            result = {}
            for c in data:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    result[c["name"]] = c["value"]
            if result:
                return result
            return {}

        # 格式2: {"cookies": [...]} — 嵌套格式，递归解析内层
        if isinstance(data, dict) and "cookies" in data:
            return self._parse_cookies(data["cookies"])

        # 格式3: {name: value, ...} — httpx原生格式
        if isinstance(data, dict):
            sample_val = next(iter(data.values()), None)
            if isinstance(sample_val, str):
                return data
            # 值不是字符串，可能仍然是嵌套结构，尝试直接返回
            return data

        return {}

    async def publish(self, content):
        """发布掘金文章"""
        if not self.enabled:
            return False, "掘金发布未启用（需要手动配置Cookie文件）"

        title = content.get("title", "")
        body = content.get("content", "")

        try:
            cookies = self._load_cookies()
            if not cookies:
                return False, "Cookie文件为空或格式不正确"

            headers = {
                "Content-Type": "application/json",
                "Referer": "https://juejin.cn/",
            }

            payload = {
                "category_id": "6809637769959178254",  # 人工智能
                "tag_ids": ["6809640407484334093"],  # AI
                "title": title,
                "content": body,
            }

            async with httpx.AsyncClient(timeout=30) as client:
                # httpx.cookies需要设置为字典
                client.cookies.update(cookies)
                resp = await client.post(
                    "https://api.juejin.cn/content_api/v1/article_draft/create",
                    headers=headers,
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    article_id = data.get("data", {}).get("id", "")
                    url = f"https://juejin.cn/post/{article_id}" if article_id else ""
                    content_id = self._save_content(
                        title, body, "juejin_article",
                        content.get("json_ld", ""),
                        content.get("tags", "AI,人工智能")
                    )
                    self._save_log(content_id, True, url)
                    return True, url
                else:
                    error_msg = f"掘金API错误: {resp.status_code} {resp.text[:200]}"
                    return False, error_msg

        except Exception as e:
            return False, f"掘金发布异常: {str(e)}"

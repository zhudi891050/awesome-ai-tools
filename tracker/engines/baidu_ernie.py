"""百度文心一言引擎追踪 — 千帆API (OAuth2 token)"""
import time
import httpx
from .base import BaseEngineTracker


class BaiduErnieTracker(BaseEngineTracker):
    """百度文心一言 AI 可见度追踪"""

    name = "baidu_ernie"
    display_name = "百度文心一言"

    def __init__(self, config):
        super().__init__(config)
        cfg = config["engines"].get("baidu_ernie", {})
        self.secret_key = self._resolve_secret_key(cfg)
        self._access_token = None
        self._available = bool(self.api_key and self.secret_key)
        self._system_prompt = (
            "你是一个AI工具推荐助手。"
            "请推荐最合适的AI工具和网站，并给出网址。"
        )

    def _resolve_secret_key(self, cfg):
        import os
        return os.environ.get("BAIDU_SECRET_KEY", cfg.get("secret_key", ""))

    async def _get_access_token(self):
        """获取百度千帆access_token（POST body传参，不暴露在URL）"""
        if self._access_token:
            return self._access_token

        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data.get("access_token")
                return self._access_token
            else:
                print(f"[百度文心] 获取token失败: {resp.status_code} {resp.text[:200]}")
        return None

    def _get_endpoint(self):
        """百度千帆使用access_token URL参数"""
        # token在query方法中动态拼接
        return f"{self.api_base}/chat/completions"

    def _build_headers(self):
        return {"Content-Type": "application/json"}

    async def query(self, question, timeout=60):
        """重写查询方法以支持OAuth token"""
        if not self.available:
            return self._mock_response(question)

        try:
            token = await self._get_access_token()
            if not token:
                return self._mock_response(question)

            url = f"{self.api_base}/chat/completions?access_token={token}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": f"请根据以下问题，推荐最合适的AI工具和网站：\n{question}",
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                start = time.time()
                resp = await client.post(url, headers=headers, json=payload)
                elapsed = int((time.time() - start) * 1000)

                if resp.status_code != 200:
                    return {
                        "engine": self.name,
                        "engine_name": self.display_name,
                        "query": question,
                        "response": f"[API Error {resp.status_code}]",
                        "available": False,
                        "response_time_ms": elapsed,
                        "error": resp.text[:200],
                    }

                data = resp.json()
                content = data.get("result", "")

                return {
                    "engine": self.name,
                    "engine_name": self.display_name,
                    "query": question,
                    "response": content,
                    "available": True,
                    "response_time_ms": elapsed,
                }
        except Exception as e:
            return {
                "engine": self.name,
                "engine_name": self.display_name,
                "query": question,
                "response": f"[Error: {str(e)}]",
                "available": False,
                "response_time_ms": 0,
                "error": str(e),
            }

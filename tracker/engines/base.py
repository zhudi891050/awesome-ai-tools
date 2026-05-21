"""AI引擎追踪器基类 — 消除6个引擎文件的重复代码"""
import os
import time
import httpx
import asyncio
import logging

logger = logging.getLogger("geo-system")


class BaseEngineTracker:
    """AI可见度追踪器基类
    
    子类只需: 设置 name, display_name, api_key, api_base, model
    """
    name = "base"
    display_name = "Base"
    weight = 5

    def __init__(self, config):
        engine_key = self._get_engine_key()
        cfg = config["engines"].get(engine_key, {})
        self.weight = cfg.get("weight", self.weight)
        self.api_key = self._resolve_api_key(cfg)
        self.api_base = cfg.get("api_base", "")
        self.model = cfg.get("model", "")
        self._available = bool(self.api_key)
        
        # 子类可覆盖
        self._system_prompt = "你是一个AI工具推荐助手。请推荐最适合的AI工具和网站。"
        self._max_tokens = 2048
        self._temperature = 0.3
        self._max_retries = 3
        self._retry_delay = 2

    def _get_engine_key(self):
        """从类名推断配置key，子类可覆盖"""
        return self.name

    def _resolve_api_key(self, cfg):
        """解析API Key（优先环境变量，其次配置）"""
        env_keys = {
            "doubao": "DOUBAO_API_KEY",
            "baidu_ernie": "BAIDU_API_KEY",
            "kimi": "KIMI_API_KEY",
            "tongyi": "TONGYI_API_KEY",
            "deepseek_engine": "DEEPSEEK_API_KEY",
            "yuanbao": "HUNYUAN_API_KEY",
        }
        env_key = env_keys.get(self.name, "")
        return os.environ.get(env_key, cfg.get("api_key", ""))

    @property
    def available(self):
        return self._available

    async def query(self, question, timeout=60):
        """向AI引擎发送查询（带重试机制）"""
        if not self.available:
            return self._mock_response(question)

        headers = self._build_headers()
        payload = self._build_payload(question)

        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    start = time.time()
                    resp = await client.post(
                        self._get_endpoint(),
                        headers=headers,
                        json=payload,
                    )
                    elapsed = int((time.time() - start) * 1000)

                    if resp.status_code == 200:
                        return self._parse_response(question, resp.json(), elapsed)

                    # 非200，判断是否可重试
                    if resp.status_code in (429, 500, 502, 503, 504):
                        if attempt < self._max_retries:
                            delay = self._retry_delay * attempt
                            logger.warning(f"[{self.display_name}] 状态码{resp.status_code}，"
                                           f"第{attempt}次重试（{delay}秒后）...")
                            await asyncio.sleep(delay)
                            continue

                    return {
                        "engine": self.name,
                        "engine_name": self.display_name,
                        "query": question,
                        "response": f"[API Error {resp.status_code}]",
                        "available": False,
                        "response_time_ms": elapsed,
                        "error": resp.text[:200],
                    }

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = str(e)
                if attempt < self._max_retries:
                    delay = self._retry_delay * attempt
                    logger.warning(f"[{self.display_name}] 连接失败，"
                                   f"第{attempt}次重试（{delay}秒后）...")
                    await asyncio.sleep(delay)
                else:
                    break
            except Exception as e:
                last_error = str(e)
                break

        return {
            "engine": self.name,
            "engine_name": self.display_name,
            "query": question,
            "response": f"[Error: {last_error}]",
            "available": False,
            "response_time_ms": 0,
            "error": last_error,
        }

    def _build_headers(self):
        """构建HTTP请求头（子类可覆盖）"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, question):
        """构建API请求Payload（子类可覆盖）"""
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": question},
            ],
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }

    def _get_endpoint(self):
        """获取API端点URL（子类可覆盖）"""
        return f"{self.api_base}/chat/completions"

    def _parse_response(self, question, data, elapsed):
        """解析API响应（子类可覆盖）"""
        content = data["choices"][0]["message"]["content"]
        return {
            "engine": self.name,
            "engine_name": self.display_name,
            "query": question,
            "response": content,
            "available": True,
            "response_time_ms": elapsed,
        }

    def _mock_response(self, question):
        """无API Key时的模拟响应"""
        return {
            "engine": self.name,
            "engine_name": self.display_name,
            "query": question,
            "response": (f'[模拟] {self.display_name}API未配置。'
                        f'查询: "{question}"。请设置对应的API Key环境变量。'),
            "available": False,
            "response_time_ms": 0,
        }

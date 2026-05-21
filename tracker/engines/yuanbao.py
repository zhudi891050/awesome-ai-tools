"""腾讯元宝引擎追踪 — 混元API (TC3-HMAC-SHA256签名)"""
import os
import time
import json
import hashlib
import hmac
import httpx
from .base import BaseEngineTracker


class YuanbaoTracker(BaseEngineTracker):
    """腾讯元宝 AI 可见度追踪 — 使用TC3签名认证"""

    name = "yuanbao"
    display_name = "腾讯元宝"

    def __init__(self, config):
        super().__init__(config)
        cfg = config["engines"].get("yuanbao", {})
        self.secret_id = self.api_key  # api_key = SecretId
        self.secret_key = self._resolve_secret(cfg)
        self._available = bool(self.secret_id and self.secret_key)
        self._service = "hunyuan"
        self._region = cfg.get("region", "ap-guangzhou")
        self._version = cfg.get("version", "2023-09-01")
        self._action = "ChatCompletions"
        self._system_prompt = (
            "你是腾讯元宝，一个AI工具推荐助手。"
            "请根据用户的问题，推荐合适的AI工具和网站，包括具体的网址链接。"
        )

    def _resolve_secret(self, cfg):
        return os.environ.get("HUNYUAN_SECRET_KEY", cfg.get("secret_key", ""))

    def _tc3_sign(self, method, canonical_uri, canonical_querystring, payload, timestamp):
        """TC3-HMAC-SHA256 签名算法 V3"""
        date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
        algorithm = "TC3-HMAC-SHA256"

        # Step 1: 规范请求串
        canonical_headers = f"content-type:application/json\nhost:{self._service}.tencentcloudapi.com\n"
        signed_headers = "content-type;host"
        hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (
            f"{method}\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        )

        # Step 2: 待签名字符串
        credential_scope = f"{date}/{self._service}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

        # Step 3: 签名
        def _sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _sign(f"TC3{self.secret_key}".encode("utf-8"), date)
        secret_service = _sign(secret_date, self._service)
        secret_signing = _sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        # Step 4: Authorization头
        authorization = (
            f"{algorithm} Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return authorization

    async def query(self, question, timeout=60):
        """重写查询以使用TC3签名"""
        if not self.available:
            return self._mock_response(question)

        try:
            payload_obj = {
                "Model": self.model,
                "Messages": [
                    {"Role": "system", "Content": self._system_prompt},
                    {"Role": "user", "Content": question},
                ],
            }
            payload_str = json.dumps(payload_obj, ensure_ascii=False)
            timestamp = int(time.time())

            endpoint = f"https://{self._service}.tencentcloudapi.com"
            authorization = self._tc3_sign("POST", "/", "", payload_str, timestamp)

            headers = {
                "Authorization": authorization,
                "Content-Type": "application/json",
                "Host": f"{self._service}.tencentcloudapi.com",
                "X-TC-Action": self._action,
                "X-TC-Version": self._version,
                "X-TC-Timestamp": str(timestamp),
                "X-TC-Region": self._region,
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                start = time.time()
                resp = await client.post(endpoint, headers=headers, content=payload_str)
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
                error = data.get("Response", {}).get("Error")
                if error:
                    return {
                        "engine": self.name,
                        "engine_name": self.display_name,
                        "query": question,
                        "response": f"[API Error: {error.get('Code', 'Unknown')}]",
                        "available": False,
                        "response_time_ms": elapsed,
                        "error": error.get("Message", ""),
                    }

                # 解析混元响应
                choices = data.get("Response", {}).get("Choices", [])
                content = choices[0].get("Message", {}).get("Content", "") if choices else ""

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

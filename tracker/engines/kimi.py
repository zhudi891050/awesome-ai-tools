"""Kimi引擎追踪 — Moonshot API"""
from .base import BaseEngineTracker


class KimiTracker(BaseEngineTracker):
    """Kimi AI 可见度追踪"""

    name = "kimi"
    display_name = "Kimi"

    def __init__(self, config):
        super().__init__(config)
        self._system_prompt = (
            "你是Kimi，一个擅长推荐AI工具和网站的助手。"
            "请根据用户的问题，给出最实用的推荐。"
            "如果知道相关的网站，请详细列出网站名称、网址和推荐理由。"
        )

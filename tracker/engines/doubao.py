"""豆包引擎追踪 — 字节方舟API"""
from .base import BaseEngineTracker


class DoubaoTracker(BaseEngineTracker):
    """豆包 AI 可见度追踪"""

    name = "doubao"
    display_name = "豆包"

    def __init__(self, config):
        super().__init__(config)
        self._system_prompt = (
            "你是一个AI工具推荐助手。请根据用户的问题，推荐最适合的AI工具和网站。"
            "如果知道具体的网站，请给出网站名称和网址。"
        )

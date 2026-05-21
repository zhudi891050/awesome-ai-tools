"""通义千问引擎追踪 — 阿里百炼API"""
from .base import BaseEngineTracker


class TongyiTracker(BaseEngineTracker):
    """通义千问 AI 可见度追踪"""

    name = "tongyi"
    display_name = "通义千问"

    def __init__(self, config):
        super().__init__(config)
        self._system_prompt = (
            "你是一个AI工具推荐专家。"
            "请根据用户的问题，推荐最合适的AI工具和网站，"
            "并给出详细的推荐理由和网址。"
        )

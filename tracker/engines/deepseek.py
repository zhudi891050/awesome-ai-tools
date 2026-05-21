"""DeepSeek引擎追踪"""
from .base import BaseEngineTracker


class DeepSeekTracker(BaseEngineTracker):
    """DeepSeek AI 可见度追踪"""

    name = "deepseek_engine"
    display_name = "DeepSeek"

    def __init__(self, config):
        super().__init__(config)
        self._system_prompt = (
            "你是一个AI工具推荐助手。"
            "请根据用户的问题推荐最合适的AI工具和网站，给出具体网址。"
        )

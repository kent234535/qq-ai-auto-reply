"""Pydantic 配置模型"""

from pydantic import BaseModel, Field


class BotSettings(BaseModel):
    """Bot 全局设置"""
    max_interactions: int = Field(20, ge=1, description="每用户最大交互次数（重启重置）")
    max_tokens: int = Field(2000, ge=100, le=16384, description="单次最大 token 数")
    temperature: float = Field(0.8, ge=0, le=2, description="生成温度")
    timeout: int = Field(20, ge=10, description="API 请求超时（秒）")
    cooldown_seconds: int = Field(5, ge=0, description="用户消息冷却时间（秒）")
    max_context_messages: int = Field(20, ge=2, description="保留的最大上下文消息数")
    active_provider_id: str = Field("", description="当前使用的 AI 提供商 ID")
    active_persona_id: str = Field("catgirl", description="当前使用的角色 ID")

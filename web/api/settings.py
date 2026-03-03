"""设置 CRUD API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from config import config

router = APIRouter()


class SettingsUpdate(BaseModel):
    max_interactions: int | None = Field(None, ge=1)
    max_tokens: int | None = Field(None, ge=100, le=16384)
    temperature: float | None = Field(None, ge=0, le=2)
    timeout: int | None = Field(None, ge=10)
    cooldown_seconds: int | None = Field(None, ge=0)
    max_context_messages: int | None = Field(None, ge=2)
    active_provider_id: str | None = None
    active_persona_id: str | None = None


@router.get("")
async def get_settings():
    """获取当前设置"""
    return config.settings.model_dump()


@router.put("")
async def update_settings(body: SettingsUpdate):
    """更新设置"""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    # 校验 active ID 是否存在（空字符串表示清除，允许）
    if "active_provider_id" in updates and updates["active_provider_id"]:
        if not config.get_provider(updates["active_provider_id"]):
            raise HTTPException(422, "指定的模型不存在")
    if "active_persona_id" in updates and updates["active_persona_id"]:
        if not config.get_persona(updates["active_persona_id"]):
            raise HTTPException(422, "指定的角色不存在")
    try:
        updated = config.update_settings(**updates)
    except ValidationError as e:
        raise HTTPException(422, detail=e.errors())
    return updated.model_dump()

"""
AI 私聊自动回复插件（重构版）
- 仅响应私聊消息
- 通过 config 模块获取设置、人格、AI 提供商
- 支持上下文截断、冷却时间、可配置限制
"""

from __future__ import annotations

import time

from nonebot import on_message, logger
from nonebot.adapters.onebot.v11 import Bot, PrivateMessageEvent

from config import config
from providers import create_provider

# 内存状态（重启后清零）
_histories: dict[str, list[dict]] = {}   # {user_id: [message, ...]}
_counts: dict[str, int] = {}             # {user_id: 已交互次数}
_last_msg_time: dict[str, float] = {}    # {user_id: 上次消息时间戳}

private_msg = on_message(priority=10, block=False)


def _truncate_context(messages: list[dict], max_messages: int) -> list[dict]:
    """截断上下文，保留 system prompt + 最近 N 条消息"""
    if len(messages) <= max_messages:
        return messages
    # 保留第一条 system 消息 + 最近的消息
    system_msgs = [m for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]
    # 保留最近 max_messages - 1 条（给 system 留位置）
    keep = max_messages - len(system_msgs)
    return system_msgs + non_system[-keep:]


@private_msg.handle()
async def handle_private(bot: Bot, event: PrivateMessageEvent):
    user_id = str(event.user_id)
    user_text = event.get_plaintext().strip()

    if not user_text:
        return

    settings = config.settings

    # ── 冷却时间检查 ──
    if settings.cooldown_seconds > 0:
        last_time = _last_msg_time.get(user_id, 0)
        elapsed = time.time() - last_time
        if elapsed < settings.cooldown_seconds:
            remaining = int(settings.cooldown_seconds - elapsed)
            await private_msg.finish(f"请等待 {remaining} 秒后再发送消息～")
            return

    _last_msg_time[user_id] = time.time()

    # ── 交互次数检查 ──
    count = _counts.get(user_id, 0)
    if count >= settings.max_interactions:
        await private_msg.finish(
            f"今天已经聊了 {settings.max_interactions} 次啦，明天再来吧～"
        )
        return

    # ── 获取人格 ──
    persona = config.get_persona(settings.active_persona_id)
    system_prompt = persona["system_prompt"] if persona else "你是一个智能助手。"

    # ── 初始化 / 截断对话历史 ──
    if user_id not in _histories:
        _histories[user_id] = [{"role": "system", "content": system_prompt}]
    else:
        # 如果人格变更，更新 system prompt
        if _histories[user_id] and _histories[user_id][0]["role"] == "system":
            _histories[user_id][0]["content"] = system_prompt

    _histories[user_id].append({"role": "user", "content": user_text})
    _histories[user_id] = _truncate_context(
        _histories[user_id], settings.max_context_messages
    )

    # ── 获取 AI 提供商 ──
    provider_config = config.get_active_provider()
    if not provider_config:
        await private_msg.finish("尚未配置 AI 提供商，请在 Web 控制台添加。")
        return

    if not provider_config.get("api_key"):
        await private_msg.finish("AI 提供商未设置 API Key，请在 Web 控制台配置。")
        return

    # ── 调用 AI ──
    reply = None
    try:
        provider = create_provider(provider_config)
        reply = await provider.chat(
            _histories[user_id],
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            timeout=settings.timeout,
        )
    except Exception as e:
        logger.error(f"AI 调用异常 [{type(e).__name__}]: {e!r}")

    if reply is None:
        await private_msg.finish("AI 暂时无法回复，请稍后再试～")
        return

    # ── 更新状态 ──
    _histories[user_id].append({"role": "assistant", "content": reply})
    _counts[user_id] = count + 1
    remaining = settings.max_interactions - (count + 1)

    # 剩余次数提示（最后 3 次时提醒）
    if 0 < remaining <= 3:
        reply += f"\n\n（今天还可以聊 {remaining} 次哦～）"

    await private_msg.finish(reply)

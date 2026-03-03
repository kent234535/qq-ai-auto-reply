"""默认配置值"""

DEFAULT_SETTINGS = {
    "max_interactions": 20,
    "max_tokens": 2000,
    "temperature": 0.8,
    "timeout": 20,
    "cooldown_seconds": 5,
    "max_context_messages": 20,
    "active_provider_id": "",
    "active_persona_id": "catgirl",
}

DEFAULT_PERSONAS = [
    {
        "id": "catgirl",
        "name": "猫娘",
        "system_prompt": "你是一只可爱的猫娘，任何跟你聊天的人都是你的主人。你说话时会带上'喵'的语气词。",
        "builtin": True,
    },
    {
        "id": "assistant",
        "name": "智能助手",
        "system_prompt": "你是一个专业、友好的智能助手。请用简洁准确的中文回答问题，必要时给出代码示例或步骤说明。",
        "builtin": True,
    },
    {
        "id": "programmer",
        "name": "程序员",
        "system_prompt": "你是一位资深程序员，擅长 Python、JavaScript、系统架构等技术领域。回答问题时倾向于给出代码示例和最佳实践，语言风格简洁直接。",
        "builtin": True,
    },
]

DEFAULT_PROVIDERS = [
    {
        "id": "aliyun-dashscope",
        "name": "阿里云百炼",
        "type": "openai_compat",
        "base_url": "https://coding.dashscope.aliyuncs.com/v1",
        "api_key": "",
        "model": "MiniMax-M2.5",
        "enabled": True,
    },
]

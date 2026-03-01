# QQ Bot — 猫娘聊天机器人

基于 NoneBot2 + NapCat 的 QQ 聊天机器人，支持多 AI 提供商、多人格切换、Web 控制台管理。

## 快速开始

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 Bot（含 Web 控制台）
python bot.py
```

启动后：
- **NoneBot2** 监听 `127.0.0.1:8080`，等待 NapCat WebSocket 连入
- **Web 控制台** 访问 `http://127.0.0.1:8080/web/`
- **API 文档** 访问 `http://127.0.0.1:8080/docs`

## 项目结构

```
QQ_bot/
├── bot.py                  # NoneBot2 入口
├── .env                    # 框架配置（监听地址、端口）
├── config/                 # 配置系统
│   ├── __init__.py         # 配置加载器（单例）
│   ├── settings.py         # Pydantic 设置模型
│   └── defaults.py         # 默认值 + 内置预设
├── models/                 # 数据模型
│   ├── persona.py          # 人格模型
│   └── provider.py         # AI 提供商模型
├── providers/              # AI 提供商适配器
│   ├── base.py             # 抽象基类 AIProvider
│   ├── openai_compat.py    # OpenAI 兼容适配器（阿里云/DeepSeek/OpenRouter 等）
│   └── claude.py           # Anthropic Claude 适配器
├── plugins/
│   └── ai_chat.py          # 核心聊天插件
├── web/                    # Web 控制台后端
│   ├── __init__.py         # FastAPI 挂载
│   ├── api/                # REST API 路由
│   └── frontend/dist/      # Vue 3 构建产物
├── frontend/               # Vue 3 前端源码
├── data/                   # 运行时数据（gitignored）
└── napcat/                 # NapCat 安装器
```

## 配置说明

所有运行时配置通过 **Web 控制台** 管理，保存在 `data/` 目录：

| 文件 | 内容 |
|------|------|
| `data/settings.json` | 全局设置（交互次数限制、Token 限制、温度等） |
| `data/providers.json` | AI 提供商列表（API Key、模型、Base URL） |
| `data/personas.json` | 人格列表（System Prompt） |

首次运行自动生成默认配置。

## AI 提供商

支持两种适配器类型：

- **openai_compat** — 兼容 OpenAI Chat Completions API 的平台（阿里云百炼、DeepSeek、OpenRouter、SiliconFlow 等）
- **claude** — Anthropic Claude Messages API

通过 Web 控制台的「AI 提供商」页面添加和管理。

## 内置人格

| ID | 名称 | 描述 |
|----|------|------|
| `catgirl` | 猫娘 | 可爱猫娘，温柔撒娇 |
| `assistant` | 智能助手 | 通用专业助手 |
| `programmer` | 程序员 | 资深程序员，代码优先 |

可在 Web 控制台添加自定义人格。

## NapCat 管理

Web 控制台的「NapCat」页面支持：
- 启动 / 停止 NapCat（QQ --no-sandbox 模式）
- 获取登录二维码
- 查看运行状态

## 前端开发

```bash
cd frontend
npm install
npm run dev    # 开发模式，代理 API 到 :8080
npm run build  # 构建到 web/frontend/dist/
```

## 技术栈

- **后端**: NoneBot2 + FastAPI + Pydantic
- **前端**: Vue 3 + Vue Router + Axios + Vite
- **协议**: OneBot V11（NapCat 反向 WebSocket）
- **AI**: OpenAI 兼容 API / Anthropic Claude API

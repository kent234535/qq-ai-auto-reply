<p align="center">
  <h1 align="center">QQ Bot</h1>
  <p align="center">自带控制台的 QQ AI 自动回复机器人</p>
  <p align="center">自己的 API Key · 自己的角色人设 · 扫码即用 · 跨平台</p>
  <p align="center">
    <a href="#功能特性">功能</a> ·
    <a href="#快速开始">快速开始</a> ·
    <a href="#web-控制台">控制台</a> ·
    <a href="#项目结构">结构</a> ·
    <a href="#许可证">许可证</a>
  </p>
</p>

---

## 功能特性

- **自带 Web 控制台** — 浏览器里完成所有配置，不用编辑任何文件
- **自己配 API Key** — 支持 DeepSeek、阿里云百炼、OpenRouter、Claude 等任意平台，用自己的额度
- **自定义角色性格** — 内置猫娘 / 助手 / 程序员，也能随手创建自己的角色
- **扫码换号** — 控制台一键连接，扫码登录，随时切换 QQ 账号
- **上下文对话** — 自动回复私聊消息，记住最近对话内容
- **跨平台** — macOS 和 Windows 均可运行

## 快速开始

> 请先确保已安装 [QQ 桌面版（QQNT）](https://im.qq.com) 和 [NapCat](https://github.com/NapNeko/NapCatQQ)。

**选择你的操作系统：**

<a href="#macos-部署">
  <img src="https://img.shields.io/badge/macOS-部署教程-000000?style=for-the-badge&logo=apple&logoColor=white" alt="macOS">
</a>
&nbsp;&nbsp;
<a href="#windows-部署">
  <img src="https://img.shields.io/badge/Windows-部署教程-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
</a>

---

### macOS 部署

#### 1. 安装基础工具

```bash
# 安装 Xcode Command Line Tools（包含 Git）
xcode-select --install

# 安装 Homebrew（macOS 包管理器）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python
brew install python@3.12

# 验证
python3 --version   # 应输出 Python 3.12.x 或更高
```

#### 2. 安装 NapCat

前往 [NapCat-Mac-Installer Releases](https://github.com/NapNeko/NapCat-Mac-Installer/releases) 下载最新版 `.dmg` 安装器，打开并按提示完成安装。

> **备选**：也可使用命令行安装：
> ```bash
> curl -o napcat.sh https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.sh
> sudo bash napcat.sh --tui
> ```

验证安装：

```bash
ls ~/Library/Containers/com.tencent.qq/Data/Documents/loadNapCat.js 2>/dev/null \
  || ls ~/Library/Application\ Support/QQ/loadNapCat.js 2>/dev/null \
  && echo "NapCat 已安装" || echo "未找到 NapCat"
```

#### 3. 部署项目

```bash
cd ~/Desktop
git clone https://github.com/kent234535/QQ_bot.git
cd ~/Desktop/QQ_bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 4. 启动

```bash
cd ~/Desktop/QQ_bot
source venv/bin/activate
python bot.py
```

打开浏览器访问 **http://127.0.0.1:8080/web/** ，在控制台中配置 AI 模型、选择角色、点击连接扫码登录即可。

---

### Windows 部署

#### 1. 安装 Git

前往 https://git-scm.com/download/win 下载安装，全部默认选项。安装后在开始菜单搜索 **Git Bash** 打开。

> 后续所有命令均在 **Git Bash** 中执行。

#### 2. 安装 Python

```bash
# 在 Git Bash 中用 winget 安装（Windows 10 1709+ 自带）
winget install Python.Python.3.12

# 安装后重新打开 Git Bash，验证
python --version   # 应输出 Python 3.12.x 或更高
```

> 如果 `winget` 不可用，前往 https://www.python.org/downloads/ 下载安装，**务必勾选 "Add Python to PATH"**。

#### 3. 安装 NapCat

在 **PowerShell（管理员）** 中执行：

```powershell
curl -o install.ps1 https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.ps1
powershell -ExecutionPolicy ByPass -File ./install.ps1 -verb runas
```

> Windows 10 如果失败，前往 [NapCat-Installer Releases](https://github.com/NapNeko/NapCat-Installer/releases) 手动下载。

#### 4. 部署项目

回到 **Git Bash**：

```bash
cd ~/Desktop
git clone https://github.com/kent234535/QQ_bot.git
cd ~/Desktop/QQ_bot

python -m venv venv
source venv/Scripts/activate
python -m pip install -r requirements.txt
```

#### 5. 启动

**命令行**：

```bash
cd ~/Desktop/QQ_bot
source venv/Scripts/activate
python bot.py
```

**或双击** 项目根目录下的 `run.bat`。

打开浏览器访问 **http://127.0.0.1:8080/web/** ，在控制台中配置 AI 模型、选择角色、点击连接扫码登录即可。

> 如果连接时提示权限错误，请以管理员身份运行。

---

## Web 控制台

启动后访问 `http://127.0.0.1:8080/web/`，左侧菜单包含四个页面：

### 模型配置

添加你自己的 AI API Key，支持以下平台：

| 平台 | 类型 | Base URL | 模型示例 |
|------|------|----------|----------|
| DeepSeek | OpenAI 兼容 | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 阿里云百炼 | OpenAI 兼容 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| OpenRouter | OpenAI 兼容 | `https://openrouter.ai/api/v1` | `meta-llama/llama-3-70b` |
| Anthropic | Claude | `https://api.anthropic.com` | `claude-sonnet-4-20250514` |

> API Key 需到对应平台官网注册申请，大部分平台提供免费额度。

### 角色管理

内置猫娘、智能助手、程序员三个角色。支持自定义角色，编写你自己的 System Prompt 来定义 AI 的性格和行为。

### 连接管理

检测到多个 QQ 应用时可切换。点击连接后扫码登录，随时可断开并切换到其他 QQ 号。

### 参数设置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 每用户最大交互次数 | 每个用户每次重启前最多聊多少轮 | 20 |
| 单次最大 Token 数 | AI 单次回复的最大长度 | 2000 |
| 生成温度 | 越高越随机，越低越稳定 | 0.8 |
| API 超时 | 等待 AI 回复的最大秒数 | 20 |
| 消息冷却时间 | 同一用户两次发消息的最短间隔（秒） | 5 |
| 最大上下文消息数 | AI 记住最近多少条对话 | 20 |

---

## 日常使用

配置完成后，用**另一个 QQ 号**给机器人 QQ 发私聊消息即可收到 AI 回复。

每次使用只需启动程序并在控制台点击连接。按 `Ctrl + C` 停止。

---

## 技术栈

| 层 | 技术 |
|---|------|
| 后端框架 | NoneBot2 + FastAPI |
| 协议适配 | OneBot V11（NapCat 反向 WebSocket） |
| AI 接入 | OpenAI 兼容 API / Anthropic Claude API |
| 前端 | Vue 3 + TypeScript + Vite |
| 数据持久化 | JSON 文件（Pydantic 模型校验） |

## 项目结构

```
QQ_bot/
├── bot.py                      # NoneBot2 入口
├── .env                        # 框架配置（HOST / PORT / 日志级别）
├── requirements.txt            # Python 依赖
├── run.sh                      # macOS / Linux 启动脚本
├── run.bat                     # Windows 启动脚本
├── config/                     # 配置系统
│   ├── __init__.py             #   配置加载器（单例模式）
│   ├── settings.py             #   Pydantic 设置模型
│   └── defaults.py             #   默认值与内置角色预设
├── providers/                  # AI 提供商适配器
│   ├── base.py                 #   抽象基类 AIProvider
│   ├── openai_compat.py        #   OpenAI 兼容适配器
│   └── claude.py               #   Anthropic Claude 适配器
├── plugins/
│   └── ai_chat.py              # 核心聊天插件
├── web/                        # Web 控制台后端
│   ├── __init__.py             #   挂载 API + 静态文件到 FastAPI
│   ├── api/                    #   REST API 路由
│   └── frontend/dist/          #   Vue 3 前端构建产物
├── frontend/                   # Vue 3 前端源码
└── data/                       # 运行时数据（自动生成，不纳入版本控制）
```

## 前端开发

```bash
cd frontend
npm install
npm run dev      # 开发模式，API 代理到 :8080
npm run build    # 构建到 web/frontend/dist/
```

---

## 安全与公开仓库

为避免泄露风险，建议按以下规则使用：

1. **不要提交 `.env` 和 `data/`**：API Key 会保存在 `data/providers.json`，属于敏感信息。
2. **默认仅本机可访问 API**：项目默认拒绝远程访问 `/api/*`（防止误暴露后被调用）。
3. **如需远程访问**：在环境变量设置 `ALLOW_REMOTE_WEB=1`，并务必在反向代理层加鉴权（如 Basic Auth / OAuth / IP 白名单）。
4. **公开前自检**：执行 `git status --short`，确认没有 `data/*.json`、`.env`、私钥文件等待提交。
5. **密钥轮换**：如果历史上曾提交过 API Key，请在提供商后台立即重置密钥。

---

## 致谢

- **[NoneBot2](https://github.com/nonebot/nonebot2)** — 跨平台 Python 异步机器人框架
- **[NapCatQQ](https://github.com/NapNeko/NapCatQQ)** — 现代化的基于 NTQQ 的 Bot 协议端实现
- **[Vue.js](https://github.com/vuejs/core)** — 渐进式 JavaScript 框架
- **[Vite](https://github.com/vitejs/vite)** — 下一代前端构建工具
- **[FastAPI](https://github.com/fastapi/fastapi)** — 现代、高性能的 Python Web 框架
- **[Pydantic](https://github.com/pydantic/pydantic)** — 数据验证与设置管理

## 相关项目

| 项目 | 说明 |
|------|------|
| [NapCatQQ](https://github.com/NapNeko/NapCatQQ) | QQ 协议端实现 |
| [NapCat-Installer](https://github.com/NapNeko/NapCat-Installer) | NapCat 跨平台安装脚本 |
| [NapCat-Mac-Installer](https://github.com/NapNeko/NapCat-Mac-Installer) | NapCat macOS 安装器 |
| [NoneBot2 文档](https://nonebot.dev/) | NoneBot2 官方文档 |
| [OneBot V11 标准](https://github.com/botuniverse/onebot-11) | OneBot V11 协议规范 |

---

## 许可证

本项目采用 [Limited Redistribution License](./LICENSE)。

- 禁止商业用途
- 允许在保留许可证和版权信息的前提下再分发
- 修改后的代码不得公开发布

详见 [LICENSE](./LICENSE)。

## 免责声明

**使用本项目前，请务必阅读以下内容：**

1. **本项目仅供学习和个人使用**，不得用于商业用途或任何违反法律法规的场景。

2. **本项目依赖 [NapCatQQ](https://github.com/NapNeko/NapCatQQ) 实现 QQ 协议对接。** NapCat 通过修改 QQ 客户端实现功能，这可能违反腾讯 QQ 用户协议。使用本项目可能导致 QQ 账号被限制或封禁。

3. **作者不对因使用本项目而产生的任何直接或间接损失承担责任**，包括但不限于账号封禁、数据丢失、财产损失等。

4. **请勿在其他社区（包括其他协议端项目或相关应用项目的社区）中提及本项目**，以避免不必要的争议。如有建议，请通过 GitHub Issue 反馈。

5. **用户应自行遵守所在地区的法律法规。** 因滥用本项目而产生的一切问题，由使用者自行承担全部责任。

**下载、安装或使用本项目即表示您已阅读并同意上述声明。**

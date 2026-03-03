# QQ Bot — AI 聊天机器人

基于 NoneBot2 + NapCat 的 QQ 私聊 AI 机器人，支持多 AI 平台、多角色切换，自带 Web 控制台。

## 功能

- 私聊自动回复，支持上下文对话
- 支持 OpenAI 兼容 API（阿里云百炼、DeepSeek、OpenRouter、SiliconFlow 等）和 Anthropic Claude
- 多角色切换（猫娘、智能助手、程序员，可自定义）
- Web 控制台管理所有配置，无需手动编辑文件
- 一键启动 / 停止 NapCat，扫码登录 QQ
- 支持 macOS 和 Windows

## 部署教程

下面的步骤假设你的电脑上什么都还没装。请按你的操作系统选择对应的步骤。

---

### 第一步：安装 Git

Git 是用来下载本项目代码的工具。

**macOS：**

打开「终端」应用（在「启动台」→「其他」里），输入：

```bash
xcode-select --install
```

弹窗点「安装」，等待完成即可（会自动安装 Git）。

**Windows：**

1. 打开浏览器，访问 https://git-scm.com/download/win
2. 下载安装包，双击运行，一路点「Next」直到安装完成
3. 安装完后，在开始菜单搜索「Git Bash」，打开它（后续所有命令都在 Git Bash 里输入）

---

### 第二步：安装 Python

本项目需要 Python 3.10 或更高版本。

**macOS：**

```bash
# 安装 Homebrew（macOS 的包管理器）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python
brew install python@3.12
```

安装完后验证：

```bash
python3 --version
```

应该显示 `Python 3.12.x` 或更高。

**Windows：**

1. 访问 https://www.python.org/downloads/
2. 下载最新版 Python 安装包
3. 双击运行，**务必勾选底部的「Add Python to PATH」**，然后点「Install Now」
4. 安装完后在 Git Bash 里验证：

```bash
python --version
```

应该显示 `Python 3.12.x` 或更高。

> 注意：macOS 使用 `python3` 命令，Windows 使用 `python` 命令。下面的教程统一写 `python3`，Windows 用户请自行替换为 `python`。

---

### 第三步：安装 QQ 桌面版

访问 https://im.qq.com ，下载并安装 QQ 桌面版（QQNT 版本）。

安装完成后**不需要登录**，后续会通过 NapCat 启动并扫码登录。

---

### 第四步：安装 NapCat

NapCat 是让 QQ 支持机器人协议的工具。

1. 访问 https://github.com/NapNeko/NapCatQQ/releases
2. 下载对应你系统的安装包：
   - macOS：下载 `NapCatInstaller.app` 相关的压缩包
   - Windows：下载 `.exe` 安装程序
3. 运行安装程序，按提示完成安装

---

### 第五步：下载本项目

打开终端（macOS）或 Git Bash（Windows），输入：

```bash
git clone https://github.com/kent234535/QQ_bot.git
cd QQ_bot
```

---

### 第六步：安装 Python 依赖

```bash
# 创建虚拟环境（隔离项目依赖，不影响系统）
python3 -m venv venv

# 激活虚拟环境
# macOS / Linux：
source venv/bin/activate
# Windows（Git Bash）：
source venv/Scripts/activate

# 安装依赖包
pip install -r requirements.txt
```

激活成功后，命令行前面会出现 `(venv)` 字样。

---

### 第七步：启动机器人

```bash
python bot.py
```

看到类似下面的输出就说明启动成功了：

```
[QQ Bot] 启动中，监听 127.0.0.1:8080 ...
```

---

### 第八步：打开 Web 控制台进行配置

打开浏览器，访问：

```
http://127.0.0.1:8080/web/
```

你会看到一个控制台界面，左侧有四个菜单：角色、模型、连接、设置。

#### 8.1 配置 AI 模型

1. 点击左侧「模型」
2. 点击右上角「+ 添加模型」
3. 填写以下信息：
   - **名称**：随便起一个，比如 `DeepSeek`
   - **类型**：选择 `OpenAI 兼容`（大多数平台都选这个）
   - **Base URL**：填写 API 地址，例如：
     - DeepSeek：`https://api.deepseek.com/v1`
     - 阿里云百炼：`https://dashscope.aliyuncs.com/compatible-mode/v1`
     - OpenRouter：`https://openrouter.ai/api/v1`
   - **API Key**：填写你从对应平台申请的 API Key
   - **模型**：填写模型名称，例如 `deepseek-chat`、`qwen-plus`
4. 点击「保存」
5. 在模型卡片上点击「启用」

> 如果你还没有 API Key，需要去对应平台的官网注册账号并申请。大部分平台都有免费额度。

#### 8.2 选择角色

1. 点击左侧「角色」
2. 系统内置了三个角色：猫娘、智能助手、程序员
3. 在你想用的角色卡片上点击「启用」
4. 你也可以点「+ 添加角色」创建自定义角色

#### 8.3 启动 QQ 连接

1. 点击左侧「连接」
2. 如果检测到多个 QQ 应用，选择要使用的那个
3. 点击「连接」按钮，等待 QQ 启动
4. 出现二维码后，用手机 QQ 扫码登录
5. 状态变为「已连接」即可

#### 8.4 调整设置（可选）

点击左侧「设置」，可以调整：

| 设置项 | 说明 | 默认值 |
|--------|------|--------|
| 每用户最大交互次数 | 每个用户每次重启前最多聊多少轮 | 20 |
| 单次最大 Token 数 | AI 单次回复的最大长度 | 2000 |
| 生成温度 | 越高回答越随机，越低越稳定 | 0.8 |
| API 超时 | 等待 AI 回复的最大秒数 | 20 |
| 消息冷却时间 | 同一用户两次发消息的最短间隔 | 5 |
| 最大上下文消息数 | AI 记住最近多少条对话 | 20 |

---

### 第九步：开始使用

用**另一个 QQ 号**给机器人 QQ 发私聊消息，就能收到 AI 回复了。

---

## 日常使用

每次使用只需要：

```bash
cd QQ_bot

# 激活虚拟环境
# macOS / Linux：
source venv/bin/activate
# Windows（Git Bash）：
source venv/Scripts/activate

# 启动
python bot.py
```

然后打开 `http://127.0.0.1:8080/web/` 启动连接即可。

按 `Ctrl + C` 停止机器人。

---

## 项目结构

```
QQ_bot/
├── bot.py                  # NoneBot2 入口
├── .env                    # 框架配置（监听地址、端口）
├── config/                 # 配置系统
│   ├── __init__.py         # 配置加载器（单例）
│   ├── settings.py         # Pydantic 设置模型
│   └── defaults.py         # 默认值 + 内置预设
├── providers/              # AI 提供商适配器
│   ├── base.py             # 抽象基类
│   ├── openai_compat.py    # OpenAI 兼容适配器
│   └── claude.py           # Anthropic Claude 适配器
├── plugins/
│   └── ai_chat.py          # 核心聊天插件
├── web/                    # Web 控制台后端
│   ├── api/                # REST API 路由
│   └── frontend/dist/      # Vue 3 前端（已构建）
├── frontend/               # Vue 3 前端源码
└── data/                   # 运行时数据（自动生成，不上传）
```

## 前端开发

如果你想修改前端界面：

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

## 免责声明

- 本项目仅供学习和个人使用，不得用于商业用途
- 本项目依赖 NapCat 实现 QQ 协议对接，NapCat 通过修改 QQ 客户端实现功能，这可能违反腾讯 QQ 用户协议
- 使用本项目可能导致 QQ 账号被封禁，作者不承担任何责任
- 请自行承担使用风险

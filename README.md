# Feishu Agent

本地常驻 Python Agent Core，使用火山方舟 Responses API 和 `lark-cli` 控制飞书。

当前版本已经升级为：

- `AgentHarness` 运行时核心
- `capability` 运行时工具能力装配
- `.agents/skills` 标准 Agent Skill 指导
- 爱弥斯人格 + agent policy + Agent Skills + runtime capabilities 四层 prompt
- Shell、HTTP、飞书事件三种入口共用同一条执行链路

## 架构

核心分层：

- `AgentHarness`
  统一管理模型调用、会话、prompt 组装、Agent Skill 指导、capability 装配、工具执行、确认流、审计日志
- `.agents/skills`
  标准 Agent Skill 目录；每个 skill 必须有 `SKILL.md`，用于描述工作流和专业读法
- `capabilities`
  Python 运行时能力包；每个 capability 提供工具定义、执行入口和少量工具选择 guidance
- `ToolExecutor`
  把工具翻译成受控的 `lark-cli` 命令
- `SessionStore`
  持久化消息、待确认动作和工具调用日志

当前主文件：

- [harness.py](src/feishu_agent/harness.py)
- [capabilities](src/feishu_agent/capabilities)
- [.agents/skills](.agents/skills)
- [prompting.py](src/feishu_agent/prompting.py)
- [persona.py](src/feishu_agent/persona.py)
- [app.py](src/feishu_agent/app.py)
- [shell.py](src/feishu_agent/shell.py)
- [auto_reply.py](src/feishu_agent/auto_reply.py)

## 当前 Agent Skills、Capabilities 与工具

默认启用的 Agent Skills：

- `feishu-agent-workflows`

按需使用的专业 Agent Skills：

- `llm-paper-reader`

默认启用的 runtime capabilities：

- `conversation`
- `feishu_contact`
- `feishu_im`
- `feishu_calendar`
- `feishu_docs`
- `feishu_search`
- `paper_reader`

当前暴露给模型的工具：

- `search_user`
- `send_dm`
- `list_agenda`
- `create_doc`
- `search_messages`
- `read_paper_url_to_feishu_doc`

`create_doc` 使用 bot 身份创建文档，并通过 `lark-cli` 授予当前 CLI 用户管理权限。正文写入使用临时 Markdown 文件，避免 Windows 长参数导致空文档；如需写入本地图片或文件，可传 `media_files`，运行时会调用 `docs +media-insert` 插入飞书媒体块。

写操作策略：

- `send_dm` 需要确认
- `create_doc` 需要确认
- `read_paper_url_to_feishu_doc` 需要确认
- 读操作直接执行
- 自动回复入口不会绕过确认流

`paper_reader` capability 支持在飞书里发送直接 PDF 链接、DOI 链接、arXiv 链接或上传 PDF 附件，确认后会按 `.agents/skills/llm-paper-reader/SKILL.md` 的标准读取论文、生成中文 Markdown 论文阅读报告，并写入新的飞书文档。

## `.env` 配置

服务启动时会自动读取项目根目录下的 `.env`。

先复制模板：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```dotenv
ARK_API_KEY=replace-with-your-ark-api-key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=replace-with-your-endpoint-id
LARK_CLI_BIN=lark-cli
APP_DB_PATH=./data/app.db
COMMAND_TIMEOUT_SECONDS=30
MAX_HISTORY_MESSAGES=20
MAX_TOOL_ROUND_TRIPS=6
FEISHU_AGENT_BASE_URL=http://127.0.0.1:8000
AGENT_PERSONA=aemeath
ENABLED_CAPABILITIES=conversation,feishu_contact,feishu_im,feishu_calendar,feishu_docs,feishu_search,paper_reader
ENABLED_AGENT_SKILLS=feishu-agent-workflows
GROUP_REPLY_MODE=off
BOT_MENTION_IDS=
BOT_MENTION_NAMES=
TTS_REPLY_MODE=off
TTS_SPACE=Plachta/VITS-Umamusume-voice-synthesizer
TTS_API_NAME=/tts_fn
TTS_SPEAKER=特别周 Special Week (Umamusume Pretty Derby)
TTS_LANGUAGE=日本語
TTS_SPEED=1
TTS_IS_SYMBOL=false
TTS_OUTPUT_DIR=./data/tts
TTS_HF_TOKEN=
AUTO_REPLY_P2P_ONLY=true
```

关键字段：

- `ARK_MODEL`
  填你在火山方舟为 `doubao-seed-2.0-pro` 创建的推理接入点 `Endpoint ID`
- `AGENT_PERSONA`
  当前默认值是 `aemeath`
- `ENABLED_CAPABILITIES`
  控制加载哪些运行时 capability，逗号分隔
- `ENABLED_AGENT_SKILLS`
  控制加载哪些 `.agents/skills/<name>/SKILL.md` 指导，逗号分隔；当前默认 `feishu-agent-workflows`
- `GROUP_REPLY_MODE`
  `off | all | mention`
- `BOT_MENTION_IDS`
  群里 `@机器人` 时，若飞书事件里给的是机器人 `open_id`，这里填对应值
- `BOT_MENTION_NAMES`
  群里 `@机器人` 时，也可以按显示名命中
- `TTS_REPLY_MODE`
  预留给后续非飞书入口使用；当前飞书自动回复只发送文本
- `TTS_*`
  配置 Hugging Face Gradio TTS Space、接口名、角色、语言、语速和本地音频缓存目录

兼容旧配置：

- 如果没设置 `GROUP_REPLY_MODE`，旧的 `AUTO_REPLY_P2P_ONLY=true` 等价于 `off`
- `AUTO_REPLY_P2P_ONLY=false` 等价于 `all`

## 安装

```bash
cd /path/to/feishu-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## 运行方式

### 1. Shell 主入口

Shell 已经直接接入本地 `AgentHarness`，不依赖 HTTP 服务。

```bash
cd /path/to/feishu-agent
source .venv/bin/activate
feishu-agent-shell
```

进入后可以直接对话：

```text
feishu-agent> 你好
feishu-agent> 帮我查一下今天日程
feishu-agent> 给周灿宇发你好
```

如果返回待确认动作：

```text
feishu-agent> /confirm
```

取消：

```text
feishu-agent> /cancel
```

Shell 内置命令：

- `/help`
- `/health`
- `/history`
- `/pending`
- `/skills`
- `/capabilities`
- `/whoami`
- `/confirm`
- `/cancel`
- `/session <id>`
- `/exit`

### 2. HTTP API

如果你还要给别的客户端或桌宠 UI 使用，可以启动 HTTP 服务：

```bash
cd /path/to/feishu-agent
source .venv/bin/activate
feishu-agent
```

或者：

```bash
source .venv/bin/activate
uvicorn feishu_agent.app:create_app --factory --host 127.0.0.1 --port 8000
```

保留的外部接口：

- `POST /chat`
- `POST /actions/{id}/confirm`
- `GET /healthz`

### 3. 飞书自动回复

自动回复 worker 也调用同一个 `AgentHarness`。这意味着：

- shell、HTTP、飞书事件的行为一致
- 同一会话的确认流一致
- 不会再有单独一套“回复机器人”的旁路逻辑

前置条件：

1. 飞书开放平台里把应用订阅方式改成“长连接接收事件”
2. 开通事件 `im.message.receive_v1`
3. 开通权限 `im:message:receive_as_bot`
4. 机器人已经在目标私聊或群里可接收消息

启动：

```bash
cd /path/to/feishu-agent
source .venv/bin/activate
feishu-agent-reply-bot
```

默认行为：

- 默认只处理 `p2p` 私聊文本消息
- 机器人自己的消息不会再次进入处理，避免死循环
- 普通读请求会直接回复
- 当前飞书自动回复只发送文本，不发送语音或音频附件
- 写操作不会自动执行，只会先回复“待确认”
- 用户在飞书里回复 `确认` 或 `取消`，会走同一个确认流

群聊回复策略由 `.env` 里的 `GROUP_REPLY_MODE` 控制：

- `off`
  不回复群聊，只回私聊
- `all`
  回复群里的所有文本消息
- `mention`
  只回复 `@机器人` 的群消息

## API 示例

### 1. 聊天

```bash
curl -s http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "demo",
    "message": "给周灿宇发你好"
  }' | jq
```

可能返回：

```json
{
  "status": "pending_action",
  "session_id": "demo",
  "message": "待确认：向指定飞书用户发送私聊消息。",
  "pending_action": {
    "action_id": "4f7f...",
    "tool_name": "send_dm",
    "summary": "待确认：向指定飞书用户发送私聊消息。",
    "args_preview": {
      "user_open_id": "ou_xxx",
      "text": "你好",
      "send_as": "bot"
    }
  }
}
```

### 2. 确认执行

```bash
curl -s http://127.0.0.1:8000/actions/<ACTION_ID>/confirm \
  -H 'Content-Type: application/json' \
  -d '{"confirm": true}' | jq
```

## 开发说明

### 新增 Agent Skill

新增 Agent Skill 的最小要求：

1. 在 [.agents/skills](.agents/skills) 下新增目录
2. 必须包含 `SKILL.md`
3. `SKILL.md` 必须包含 YAML frontmatter：
   - `name`
   - `description`
4. 如需运行时默认加载，把 skill 名加入 `.env` 的 `ENABLED_AGENT_SKILLS`

### 新增 Runtime Capability

新增 capability 的最小要求：

1. 在 [capabilities](src/feishu_agent/capabilities) 下新增 capability 文件
2. 实现：
   - `get_tools()`
   - `get_guidance()`
   - `execute()`
3. 在 [capabilities/__init__.py](src/feishu_agent/capabilities/__init__.py) 里注册 factory
4. 把 capability 名加入 `.env` 的 `ENABLED_CAPABILITIES`

### Prompt 组成

完整 prompt 由四层组成：

1. persona prompt
2. policy prompt
3. Agent Skills (`.agents/skills/*/SKILL.md`)
4. runtime capability guidance

组装逻辑在 [prompting.py](src/feishu_agent/prompting.py)。

### 审计数据

SQLite 默认位置：

- [app.db](data/app.db)

主要表：

- `messages`
- `pending_actions`
- `tool_logs`

## 测试

```bash
cd /path/to/feishu-agent
source .venv/bin/activate
python -m pytest -q
```

当前测试覆盖：

- harness 主流程
- Agent Skill 与 capability 装配
- prompt 组成
- shell 命令
- auto reply
- app 路由
- 工具执行器

## launchd 模板

可参考 [deploy/com.by.feishu-agent.plist](deploy/com.by.feishu-agent.plist)。

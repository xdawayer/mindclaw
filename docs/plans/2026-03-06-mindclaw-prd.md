# MindClaw PRD - 个人全能 AI 助手框架

> 版本: v0.1 | 日期: 2026-03-06 | 作者: wzb + Claude

---

## 一、项目愿景

MindClaw 是一个从零构建的个人全能 AI 助手框架。它融合了 Nanobot 的极简哲学和 OpenClaw 的企业级能力，目标是打造一个**安全、可扩展、多渠道、多模型**的私人 AI 助手。

**核心理念：**
- 你的助手，你的规则 — 完全自主可控
- 安全第一 — 进程隔离、审批工作流、沙箱执行
- 渐进式架构 — 从最小可用开始，按需扩展
- AI 驱动开发 — 用 Claude Code 从零构建每一行代码

---

## 二、目标用户

主要用户：框架作者本人（wzb）

使用场景：
- 通过 Telegram/Slack/飞书/Discord/微信 随时与 AI 对话
- 管理日程、提醒、定时任务
- 读写 Obsidian 笔记、Notion 页面、网页收藏
- 执行文件操作、Shell 命令、网页搜索
- 知识管理与语义检索
- 复杂任务的多 Agent 并行处理

---

## 三、整体架构

```
                        ┌─────────────────┐
                        │    你 (用户)     │
                        └───┬─────────┬───┘
                            │         │
              ┌─────────────▼──┐  ┌───▼──────────────┐
              │ 路径A: 平台渠道 │  │ 路径B: 自有客户端  │
              │ Telegram/Slack │  │ CLI / Web UI      │
              │ 飞书/Discord/  │  │                   │
              │ 微信           │  │ ┌───────────────┐ │
              │                │  │ │Gateway        │ │
              │ (各平台SDK主动  │  │ │WebSocket+Token│ │
              │  推送消息)      │  │ │设备配对       │ │
              │                │  │ └───────────────┘ │
              └───────┬────────┘  └────────┬──────────┘
                      │                    │
                      └────────┬───────────┘
                               │
                  ┌────────────▼────────────┐
                  │ 渠道管理 (ChannelManager) │
                  │ 统一接口: BaseChannel     │
                  └────────────┬────────────┘
                               │
                  ┌────────────▼────────────┐
                  │   消息总线 (Message Bus)  │
                  │                          │
                  │  入站队列 (inbound)       │
                  │  出站队列 (outbound)      │
                  └────────────┬────────────┘
                                 │
         ┌───────────────────────▼───────────────────────┐
         │              编排层 (Orchestrator)              │
         │                                                │
         │  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
         │  │ 主 Agent  │ │子 Agent A│ │子 Agent B│       │
         │  │(独立进程) │ │(独立进程)│ │(独立进程) │       │
         │  └──────────┘ └──────────┘ └──────────┘       │
         │                                                │
         │  ACP 协议: 生命周期管理 / 任务分派 / 结果汇总    │
         └──────────┬────────────────────┬───────────────┘
                    │                    │
       ┌────────────▼──────┐  ┌─────────▼─────────┐
       │  大脑层 (LLM)      │  │  安全层 (Security) │
       │                    │  │                    │
       │  LiteLLM 统一路由  │  │  认证: Token +     │
       │  Claude / GPT /    │  │    设备配对 + 白名单│
       │  Gemini / Kimi /   │  │  执行: 审批工作流 + │
       │  DeepSeek ...      │  │    黑名单 + 沙箱   │
       │                    │  │  隔离: 进程隔离 +   │
       │  Prompt 缓存       │  │    MCP 沙箱        │
       │  自动降级 (容错)    │  │  存储: 密钥加密    │
       └────────────┬──────┘  └─────────┬─────────┘
                    │                    │
         ┌──────────▼────────────────────▼──────────┐
         │          工具层 (Tools) + 插件系统         │
         │                                           │
         │  内置工具:                                 │
         │    read_file / write_file / edit_file     │
         │    exec (Shell) / web_search / web_fetch  │
         │    list_dir / memory_save / memory_search │
         │    cron_add / cron_list / cron_remove     │
         │    spawn_task (子 Agent)                   │
         │                                           │
         │  插件机制:                                 │
         │    注册: 工具 / 渠道 / Hook / HTTP 路由    │
         │    Hook: before_tool / after_tool /       │
         │          on_message / on_error            │
         │                                           │
         │  MCP 协议: 外部工具服务器接入              │
         └──────────────────────┬────────────────────┘
                                │
         ┌──────────────────────▼────────────────────┐
         │            知识层 (Knowledge)               │
         │                                            │
         │  记忆系统:                                  │
         │    短期 → Session 消息历史 (JSONL)          │
         │    长期 → MEMORY.md (事实/偏好/习惯)        │
         │    语义 → 向量数据库 LanceDB (可选)         │
         │    审计 → HISTORY.md (可搜索操作日志)       │
         │                                            │
         │  知识源:                                    │
         │    Obsidian (本地 Markdown 读写)            │
         │    Notion (API 读写)                        │
         │    网页收藏 (Readability 抓取 + 存储)       │
         └────────────────────────────────────────────┘
```

---

## 四、分层详细设计

### 4.1 网关层 (Gateway)

**职责：** 为**自有客户端**（CLI、Web UI、未来的原生 App）提供 WebSocket 接入点。

> **重要区分：** Gateway 不负责管理平台渠道（Telegram/Slack 等）。平台渠道通过各自 SDK 直接接收消息，与 Gateway 是并列的两条接入路径，最终都汇入 ChannelManager → MessageBus。

| 特性 | 说明 |
|------|------|
| **协议** | WebSocket (长连接，实时双向通信) |
| **认证方式** | Gateway Token (启动时生成随机 Token) |
| **设备配对** | 新设备首次连接需通过已认证渠道确认 |
| **多客户端** | 支持多个自有客户端同时连接 |
| **心跳** | 定期 ping/pong 检测连接存活 |
| **API 风格** | JSON-RPC over WebSocket |

**两条接入路径：**
```
路径A (平台渠道): Telegram SDK → TelegramChannel → ChannelManager → MessageBus
路径B (自有客户端): CLI/WebUI → WebSocket → Gateway → GatewayChannel → ChannelManager → MessageBus
```

**设计参考：** OpenClaw 的 Gateway 架构，但简化为单进程 WebSocket Server。

---

### 4.2 渠道层 (Channel Layer)

**职责：** 适配各个聊天平台的 API，将平台特定消息转换为统一格式。

**统一接口 (BaseChannel)：**
```
BaseChannel (抽象基类)
├── start()        → 启动渠道，建立与平台的连接
├── stop()         → 停止渠道，清理资源
├── send()         → 向指定聊天发送消息
├── is_allowed()   → 检查发送者是否在白名单中
└── _handle_message() → 收到消息时的统一入口
```

**渠道实现计划：**

| 渠道 | SDK/库 | 优先级 | 备注 |
|------|--------|--------|------|
| CLI | prompt-toolkit | Phase 1 | 本地开发调试用 |
| Telegram | python-telegram-bot | Phase 6 | 第一个远程渠道 |
| Slack | slack-sdk | Phase 9 | 工作场景 |
| 飞书 | lark-oapi (WebSocket) | Phase 9 | 国内工作场景 |
| Discord | discord.py | Phase 9 | 社区/娱乐，使用社区标准库而非自实现 |
| 微信 | WhatsApp Bridge 思路 (Node.js) | Phase 11 | 复杂度最高 |

**每个渠道的安全配置：**
- `allowFrom`: 白名单 (用户ID / 群组ID)
- `allowGroups`: 是否允许群组消息
- 每个渠道独立的 API Token 管理

---

### 4.3 消息总线 (Message Bus)

**职责：** 解耦渠道层和 Agent 层，异步消息路由。

**核心结构：**
```
MessageBus
├── inbound_queue   → asyncio.Queue (渠道消息 → Agent)
├── outbound_queue  → asyncio.Queue (Agent 回复 → 渠道)
├── put_inbound()   → 渠道调用，投递用户消息
├── get_inbound()   → Agent 调用，获取待处理消息
├── put_outbound()  → Agent 调用，投递回复
└── get_outbound()  → 渠道调用，获取待发送回复
```

**消息格式：**
```python
@dataclass
class InboundMessage:
    channel: str          # 来源渠道 ("telegram", "slack", ...)
    chat_id: str          # 聊天/群组 ID
    user_id: str          # 发送者 ID
    username: str         # 发送者名称
    text: str             # 消息文本
    reply_to: str | None  # 引用的消息 ID
    attachments: list     # 附件 (图片/文件)
    timestamp: float      # 时间戳

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.chat_id}"

@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    text: str
    message_id: str          # 唯一消息 ID (UUID)
    reply_to: str | None
    attachments: list
    timestamp: float          # 发送时间戳 (用于审计追踪)
```

**增强特性 (相比 Nanobot，标记为后续优化，Phase 1 仅实现基础双队列)：**
- 消息去重 [Phase 6+]：基于消息 ID 去重，5 秒时间窗口内相同 channel+chat_id+text 视为重复
- 限流 [Phase 6+]：每个 session_key 每分钟最多 30 条消息，超限排队等待

---

### 4.4 编排层 (Orchestrator)

**职责：** 管理 Agent 的生命周期、任务分派和进程隔离。这是相比 Nanobot 的核心升级。

#### 4.4.1 Agent Control Protocol (ACP)

借鉴 OpenClaw 的 ACP 协议，实现 Agent 的进程级隔离。

**进程通信方式：** 使用 `asyncio.subprocess` 启动子进程，通过 **JSON over stdin/stdout** 通信（与 MCP stdio 传输一致），避免 multiprocessing 与 asyncio 混用的已知兼容性问题（event loop 不共享、pickle 序列化限制等）。

```
Orchestrator (主进程, asyncio event loop)
│
├── spawn_agent(task, tools, config)
│   → asyncio.create_subprocess_exec() 创建子进程
│   → JSON over stdin/stdout 通信 (与 MCP stdio 一致)
│   → 返回 AgentHandle
│
├── AgentHandle
│   ├── send(message)     → 写 JSON 到子进程 stdin
│   ├── receive()         → 从子进程 stdout 读 JSON
│   ├── stop()            → 发送 shutdown 指令 → 等待退出
│   ├── kill()            → 强制终止子进程
│   └── status            → running / completed / failed / timeout
│
└── 任务管理
    ├── task_queue         → 待执行任务队列
    ├── active_agents      → 活跃的 Agent 进程
    ├── max_concurrent     → 最大并发数 (默认 3)
    └── results            → 任务结果汇总
```

#### 4.4.2 主 Agent Loop (ReAct 模式)

核心推理循环，参考 Nanobot 的 ReAct 实现：

```
收到消息
  → 构建上下文 (系统提示 + 记忆 + 技能 + 历史消息)
  → 发送给 LLM
  → LLM 返回:
      ├── 纯文本回复 → 直接发给用户
      └── 工具调用 → 安全检查 → 执行工具 → 结果返回 LLM → 继续循环
  → 最多 40 次迭代 (防止死循环)
  → 保存对话到 Session
  → 触发记忆整合 (如果消息够多)
```

#### 4.4.3 子 Agent 任务

主 Agent 可以派发后台子任务：

```
主 Agent: "这个任务比较复杂，我拆成两个子任务并行处理"
  ├── 子 Agent A: 搜索相关资料 (独立进程)
  ├── 子 Agent B: 分析本地文件 (独立进程)
  └── 主 Agent: 等待结果 → 汇总 → 回复用户
```

**子 Agent 限制：**
- 不能发送消息给用户 (只能返回结果给主 Agent)
- 不能再派发子任务 (防止无限嵌套)
- 工具集受限 (无 message_user / spawn_task)
- 最多 15 次迭代
- 有超时限制

---

### 4.5 大脑层 (LLM Router)

**职责：** 统一管理 LLM 调用，支持多模型切换、缓存和容错。

#### 4.5.1 LiteLLM 统一路由

```
LLMRouter
├── chat(messages, model, tools)  → 统一调用接口
├── resolve_model(model_name)     → 解析模型前缀
├── apply_cache(messages)         → Anthropic Prompt 缓存
└── fallback(error)               → 自动降级
```

**支持的 Provider：**

| Provider | 前缀 | 模型示例 |
|----------|-------|---------|
| Anthropic | - (默认) | claude-sonnet-4-20250514 |
| OpenAI | openai/ | gpt-4o |
| Google | gemini/ | gemini-2.0-flash |
| DeepSeek | deepseek/ | deepseek-chat |
| Kimi (Moonshot) | openai/ | moonshot-v1-auto |
| 通义千问 | openai/ | qwen-max |
| OpenRouter | openrouter/ | 任意模型 |

**扩展方式：** 添加新 Provider 只需在 registry 中注册一条 ProviderSpec（约 10 行配置）。

#### 4.5.2 Prompt 缓存

针对 Anthropic 模型，在系统提示中注入 cache_control 标记，避免重复计算长系统提示的 token：

```
首次调用: 系统提示 (2000 tokens) → 缓存
后续调用: 系统提示 (命中缓存, 0 tokens 计费) → 节省 ~80% 成本
```

#### 4.5.3 自动降级

```
用户配置: primary_model = "claude-sonnet-4-20250514"
          fallback_model = "gpt-4o"

调用失败 → 自动切换到 fallback → 通知用户已降级
```

---

### 4.6 安全层 (Security)

**MindClaw 的安全设计是核心差异点，融合了 Nanobot 的简洁和 OpenClaw 的严谨。**

#### 4.6.1 三层认证体系

```
┌─────────────────────────────────────────┐
│ Layer 1: Gateway Token                   │
│ - 启动时生成随机 Token                    │
│ - 所有 WebSocket 连接必须携带            │
│ - 存储在本地配置文件 (权限 0600)          │
├─────────────────────────────────────────┤
│ Layer 2: 设备配对                        │
│ - 新设备首次连接 → 发送配对请求           │
│ - 已认证渠道收到通知 → 用户确认/拒绝      │
│ - 配对成功后该设备永久信任                │
├─────────────────────────────────────────┤
│ Layer 3: 渠道白名单 (allowFrom)          │
│ - 每个渠道独立配置允许的用户/群组         │
│ - 未在白名单中的消息直接丢弃             │
└─────────────────────────────────────────┘
```

#### 4.6.2 工具执行安全

**审批工作流 (借鉴 OpenClaw)：**

```
工具调用请求
  → 检查工具风险等级:
      ├── safe (read_file, web_search)     → 直接执行
      ├── moderate (write_file, edit_file) → 记录日志
      └── dangerous (exec, spawn_task)     → 需要用户审批
          → 生成审批 ID (approval_xxxx)
          → 发送审批请求到用户渠道 (附带审批 ID)
          → 等待用户回复
          → 审批通过才执行
```

**审批消息路由（防死锁设计）：**

审批回复不能进入正常 Agent Loop，否则会被当作新对话处理。解决方案：

```
用户回复 → ChannelManager 检查:
  ├── 匹配审批格式 ("yes/no/approve/reject" + 可选审批ID)
  │   且当前有 pending 审批
  │   → 路由到 ApprovalManager (不进入 Agent Loop)
  └── 不匹配 → 正常进入 MessageBus
```

**审批超时与并发：**
- 默认 5 分钟超时，超时自动拒绝并通知用户
- 同一时间最多 1 个 pending 审批（后续审批排队）
- 审批等待期间，其他消息正常排队处理，不阻塞

**命令黑名单 (借鉴 Nanobot)：**

```python
DENY_PATTERNS = [
    r"rm\s+-rf\s+/",          # 删除根目录
    r"dd\s+if=",              # 磁盘写入
    r"mkfs\.",                # 格式化
    r":\(\)\{.*\}",           # Fork bomb
    r">\s*/dev/sd",           # 覆写磁盘
    r"chmod\s+-R\s+777\s+/",  # 全局权限修改
]
```

**路径沙箱：**
- 所有文件操作限制在 workspace 目录内
- 路径遍历攻击检测 (`../` 等)
- 符号链接跟踪限制

**执行超时：**
- Shell 命令默认 30 秒超时
- 可在配置中调整
- 超时自动终止进程

#### 4.6.3 运行隔离

| 隔离层 | 机制 | 说明 |
|--------|------|------|
| Agent 隔离 | asyncio.subprocess | 子 Agent 在独立进程中运行，JSON over stdin/stdout 通信 |
| MCP 隔离 | asyncio.subprocess | MCP Server 在独立子进程中运行，同样使用 stdio 通信 |
| 密钥隔离 | 加密存储 + 环境变量 | API Keys 优先从环境变量读取，其次从加密配置文件读取 |

#### 4.6.4 Session 安全

- 错误响应不持久化到 Session (防止 Session 投毒)
- 工具结果截断 (默认 500 字符，防止上下文注入)
- 系统提示与用户消息严格分离

---

### 4.7 工具层 (Tools) + 插件系统

#### 4.7.1 内置工具

| 工具 | 功能 | 风险等级 |
|------|------|---------|
| `read_file` | 读取文件内容 | safe |
| `write_file` | 写入文件 | moderate |
| `edit_file` | 编辑文件 (基于行号) | moderate |
| `list_dir` | 列出目录内容 | safe |
| `exec` | 执行 Shell 命令 | dangerous |
| `web_search` | 网页搜索 (Brave API) | safe |
| `web_fetch` | 抓取网页内容 | safe |
| `memory_save` | 保存长期记忆 | moderate |
| `memory_search` | 搜索记忆/历史 | safe |
| `cron_add` | 添加定时任务 | moderate |
| `cron_list` | 查看定时任务 | safe |
| `cron_remove` | 删除定时任务 | moderate |
| `spawn_task` | 派发子 Agent 任务 | dangerous |
| `message_user` | 主动发消息给用户 | moderate |

**工具接口：**
```
Tool (抽象基类)
├── name: str                     → 工具名称
├── description: str              → 功能描述 (给 LLM 看)
├── parameters: dict              → JSON Schema 参数定义
├── risk_level: safe|moderate|dangerous
├── execute(params) → str         → 执行并返回结果
└── validate_params(params) → bool → 参数校验
```

#### 4.7.2 插件系统 (借鉴 OpenClaw)

**插件结构：**
```
plugins/
└── my_plugin/
    ├── manifest.json      → 插件元数据 (名称/版本/描述)
    ├── tools/             → 自定义工具
    ├── channels/          → 自定义渠道
    └── hooks/             → 生命周期钩子
```

**Hook 事件：**

| Hook | 触发时机 | 用途 |
|------|---------|------|
| `on_message` | 收到新消息时 | 消息过滤、预处理 |
| `before_tool` | 工具执行前 | 审批、参数修改、拦截 |
| `after_tool` | 工具执行后 | 结果处理、日志记录 |
| `on_reply` | 回复发出前 | 内容审核、格式转换 |
| `on_error` | 发生错误时 | 错误报告、自动恢复 |
| `on_start` | Gateway 启动时 | 初始化、健康检查 |
| `on_stop` | Gateway 关闭时 | 清理资源 |

**插件加载：**
- 启动时扫描 plugins/ 目录
- 动态导入 Python 模块
- 注册工具/渠道/Hook 到对应 Registry

#### 4.7.3 MCP 集成

支持 Model Context Protocol，接入外部工具服务器：

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
      "transport": "stdio"
    },
    "remote-api": {
      "url": "https://api.example.com/mcp",
      "transport": "http"
    }
  }
}
```

**支持的传输方式：**
- `stdio`: 本地子进程，通过 stdin/stdout 通信
- `http`: 远程 HTTP 服务器

---

### 4.8 知识层 (Knowledge)

#### 4.8.1 记忆系统

**四层记忆架构：**

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Session (短期记忆)                       │
│ - 当前对话的消息历史                               │
│ - 存储格式: JSONL (每行一条消息)                    │
│ - 按 session_key 分文件                           │
│ - 超过阈值触发 consolidation                      │
├─────────────────────────────────────────────────┤
│ Layer 2: MEMORY.md (长期记忆)                     │
│ - 用户偏好、关键事实、重要决定                      │
│ - LLM 驱动的自动整合 (从旧消息中提取)               │
│ - Markdown 格式，人类可直接阅读编辑                 │
├─────────────────────────────────────────────────┤
│ Layer 3: 向量数据库 (语义记忆) — 可选               │
│ - LanceDB 本地向量数据库                           │
│ - 对 MEMORY + HISTORY + 知识源做 embedding         │
│ - 支持语义搜索 ("我之前说过关于XX的话")              │
├─────────────────────────────────────────────────┤
│ Layer 4: HISTORY.md (审计日志)                     │
│ - 所有重要操作的时间线记录                          │
│ - 格式: [日期] 摘要                                │
│ - 可搜索，用于回溯和审计                            │
└─────────────────────────────────────────────────┘
```

**记忆整合流程：**
```
Session 消息数超过阈值 (如 20 条)
  → 提取旧消息
  → 发给 LLM: "从这些对话中提取值得记住的信息"
  → LLM 调用 save_memory 虚拟工具
  → 写入 MEMORY.md (追加/更新)
  → 写入 HISTORY.md (追加摘要)
  → 更新 consolidation 指针
  → 删除已整合的旧消息 (释放上下文空间)
```

#### 4.8.2 知识源集成

**Obsidian (深度集成)：**
```
obsidian_knowledge/
├── read_note(path)           → 读取指定笔记
├── write_note(path, content) → 创建/更新笔记
├── search_notes(query)       → 全文搜索笔记
├── list_notes(folder)        → 列出笔记目录
├── get_tags()                → 获取所有标签
└── get_links(note)           → 获取笔记的链接关系
```

**Notion (API 集成)：**
```
notion_knowledge/
├── read_page(page_id)        → 读取页面内容
├── create_page(parent, data) → 创建新页面
├── update_page(page_id, data)→ 更新页面
├── search(query)             → 搜索 Notion
└── list_databases()          → 列出数据库
```

**网页收藏：**
```
web_knowledge/
├── fetch_and_save(url)       → 抓取网页并保存为 Markdown
├── search_saved(query)       → 搜索已保存的网页
└── list_saved()              → 列出所有收藏
```

---

### 4.9 配置系统

**统一配置文件 (config.json)：**

```json
{
  "agent": {
    "defaultModel": "claude-sonnet-4-20250514",
    "fallbackModel": "gpt-4o",
    "maxIterations": 40,
    "subagentMaxIterations": 15
  },
  "gateway": {
    "host": "0.0.0.0",
    "port": 8765,
    "token": "auto-generated"
  },
  "channels": {
    "telegram": {
      "token": "BOT_TOKEN",
      "allowFrom": ["user_id_1"]
    },
    "slack": {
      "appToken": "xapp-...",
      "botToken": "xoxb-...",
      "allowFrom": ["U12345"]
    },
    "feishu": {
      "appId": "...",
      "appSecret": "...",
      "allowFrom": ["ou_xxxxx"]
    },
    "discord": {
      "token": "...",
      "allowFrom": ["user_id"]
    }
  },
  "providers": {
    "anthropic": { "apiKey": "sk-ant-..." },
    "openai": { "apiKey": "sk-..." },
    "deepseek": { "apiKey": "sk-...", "apiBase": "https://api.deepseek.com" }
  },
  "tools": {
    "exec": {
      "timeout": 30,
      "denyPatterns": ["rm -rf /", "dd if="],
      "restrictToWorkspace": true
    },
    "webSearch": {
      "provider": "brave",
      "apiKey": "..."
    }
  },
  "knowledge": {
    "obsidian": {
      "vaultPath": "/Users/wzb/obsidian"
    },
    "notion": {
      "apiKey": "secret_..."
    },
    "vectorDb": {
      "enabled": false,
      "provider": "lancedb",
      "embeddingModel": "text-embedding-3-small"
    }
  },
  "security": {
    "approvalRequired": ["exec", "spawn_task"],
    "sessionPoisoningProtection": true,
    "toolResultMaxChars": 500
  },
  "mcpServers": {}
}
```

**配置验证：** 使用 Pydantic 模型，支持 camelCase 和 snake_case 双向兼容。

**敏感信息处理（防止 API Key 泄露）：**
- 优先级：环境变量 > 加密配置文件 > 明文配置文件
- 配置文件中支持环境变量引用：`"apiKey": "$ANTHROPIC_API_KEY"`
- 配置文件权限强制为 0600（仅 owner 可读写）
- `.gitignore` 默认排除 `config.json`，仅提交 `config.example.json`
- 启动时检测配置文件中是否包含明文密钥，给出警告并建议迁移到环境变量

---

### 4.10 技能系统 (Skills)

**技能 = Markdown 文件，描述 Agent 如何完成特定任务。**

**技能格式 (SKILL.md)：**
```markdown
---
name: summarize-article
description: 总结文章的核心观点
dependencies:
  bins: []
  env: []
load: on_demand    # on_demand | always
---

# 总结文章

## 步骤
1. 用 web_fetch 抓取文章内容
2. 提取核心观点 (不超过 5 点)
3. 生成一段话的摘要
4. 如果用户指定了格式，按格式输出

## 输出格式
- 标题
- 核心观点 (bullet points)
- 一句话总结
```

**技能路由方式：** 由 LLM 自主决定使用哪个技能（不做硬编码的关键词匹配）。系统提示中注入所有技能的名称+描述摘要，LLM 判断当前任务需要哪个技能后，通过 `read_file` 加载完整内容。这种方式比关键词 trigger 更灵活，避免了中文分词、多技能冲突等问题。

**渐进式加载：**
- 系统提示中只包含技能摘要 (名称 + 描述)
- Agent 需要时通过 `read_file` 加载完整内容
- `always` 类型的技能完整内容始终在系统提示中

---

## 五、数据流示例

### 5.1 普通对话

```
用户在 Telegram 发送: "帮我搜一下 MindClaw 相关的开源项目"

1. Telegram Channel 收到消息
2. is_allowed() 检查白名单 → 通过
3. 创建 InboundMessage → 投入 inbound_queue
4. Agent Loop 从队列取出消息
5. 构建上下文: 系统提示 + MEMORY.md + 技能列表 + 历史消息
6. 发送给 Claude → 返回工具调用: web_search("MindClaw open source")
7. 安全检查: web_search 是 safe 级别 → 直接执行
8. 执行 web_search → 返回结果 (截断到 500 字符)
9. 结果发回 Claude → 返回文本回复
10. 创建 OutboundMessage → 投入 outbound_queue
11. Telegram Channel 从队列取出 → 发送到 Telegram
12. 保存完整对话到 Session JSONL
```

### 5.2 危险操作 (需审批)

```
用户: "删除 /tmp/old_files 目录下的所有文件"

1-5. (同上)
6. Claude → 工具调用: exec("rm -rf /tmp/old_files/*")
7. 安全检查:
   a. 命令黑名单匹配: rm -rf → 命中!
   b. 但目标不是 / 或系统目录 → 不直接拦截
   c. exec 是 dangerous 级别 → 触发审批
8. 发送审批请求到用户的 Telegram:
   "⚠️ MindClaw 请求执行危险操作:
    命令: rm -rf /tmp/old_files/*
    回复 yes 确认, no 拒绝"
9. 用户回复 "yes"
10. 执行命令 → 返回结果
11. 记录到 HISTORY.md: [2026-03-06] 用户审批并执行: rm -rf /tmp/old_files/*
```

### 5.3 子 Agent 并行任务

```
用户: "帮我调研一下 LangChain 和 LlamaIndex 的区别"

1-5. (同上)
6. Claude 决定拆分任务:
   → spawn_task("调研 LangChain 的核心特性和优劣")
   → spawn_task("调研 LlamaIndex 的核心特性和优劣")
7. Orchestrator 创建两个子 Agent 进程
8. 子 Agent A: web_search → web_fetch → 总结 LangChain
9. 子 Agent B: web_search → web_fetch → 总结 LlamaIndex
10. 两个子 Agent 并行执行，结果返回主 Agent
11. 主 Agent 汇总对比 → 生成回复
12. 发送给用户
```

---

## 六、项目结构

```
mindclaw/
├── mindclaw/                    # 主包
│   ├── __init__.py
│   ├── cli/                     # CLI 入口
│   │   └── commands.py          # typer 命令定义
│   │
│   ├── gateway/                 # 网关层
│   │   ├── server.py            # WebSocket Server
│   │   └── auth.py              # Token + 设备配对
│   │
│   ├── channels/                # 渠道层
│   │   ├── base.py              # BaseChannel 抽象类
│   │   ├── manager.py           # ChannelManager
│   │   ├── cli_channel.py       # CLI 渠道
│   │   ├── telegram.py          # Telegram
│   │   ├── slack.py             # Slack
│   │   ├── feishu.py            # 飞书
│   │   ├── discord.py           # Discord
│   │   └── wechat/              # 微信 (Node.js Bridge)
│   │
│   ├── bus/                     # 消息总线
│   │   ├── events.py            # 消息数据类
│   │   └── queue.py             # MessageBus
│   │
│   ├── orchestrator/            # 编排层
│   │   ├── agent_loop.py        # 主 Agent 循环 (ReAct)
│   │   ├── context.py           # 上下文构建
│   │   ├── acp.py               # Agent Control Protocol
│   │   └── subagent.py          # 子 Agent 管理
│   │
│   ├── llm/                     # 大脑层
│   │   ├── base.py              # LLMProvider 抽象类
│   │   ├── router.py            # LiteLLM 路由
│   │   ├── registry.py          # Provider 注册表
│   │   └── cache.py             # Prompt 缓存
│   │
│   ├── security/                # 安全层
│   │   ├── auth.py              # 认证管理
│   │   ├── approval.py          # 审批工作流
│   │   ├── sandbox.py           # 执行沙箱
│   │   └── crypto.py            # 密钥加密
│   │
│   ├── tools/                   # 工具层
│   │   ├── base.py              # Tool 抽象类
│   │   ├── registry.py          # ToolRegistry
│   │   ├── file_ops.py          # 文件操作工具
│   │   ├── shell.py             # Shell 执行工具
│   │   ├── web.py               # 网页搜索/抓取
│   │   ├── cron.py              # 定时任务
│   │   └── mcp.py               # MCP 客户端
│   │
│   ├── plugins/                 # 插件系统
│   │   ├── loader.py            # 插件加载器
│   │   ├── hooks.py             # Hook 管理
│   │   └── manifest.py          # 插件清单解析
│   │
│   ├── knowledge/               # 知识层
│   │   ├── memory.py            # 记忆系统
│   │   ├── session.py           # Session 管理
│   │   ├── vector.py            # 向量数据库
│   │   ├── obsidian.py          # Obsidian 集成
│   │   ├── notion.py            # Notion 集成
│   │   └── web_archive.py       # 网页收藏
│   │
│   ├── skills/                  # 内置技能
│   │   ├── summarize.md
│   │   ├── translate.md
│   │   └── ...
│   │
│   ├── templates/               # 模板
│   │   ├── SOUL.md              # AI 人格定义
│   │   └── AGENTS.md            # Agent 行为指引
│   │
│   └── config/                  # 配置
│       ├── schema.py            # Pydantic 配置模型
│       └── loader.py            # 配置加载器
│
├── plugins/                     # 用户插件目录
│
├── tests/                       # 测试
│   ├── test_bus.py
│   ├── test_agent_loop.py
│   ├── test_security.py
│   ├── test_tools.py
│   └── ...
│
├── docs/                        # 文档
│   └── plans/
│       └── 2026-03-06-mindclaw-prd.md  # 本文档
│
├── pyproject.toml               # 项目配置
├── README.md                    # 项目说明
└── config.example.json          # 配置示例
```

---

## 七、技术栈

| 类别 | 选择 | 理由 |
|------|------|------|
| **语言** | Python 3.12+ | AI 生态最强，Claude 写得最好 |
| **异步** | asyncio | Python 原生异步 |
| **CLI** | Typer + Rich | 美观的命令行界面 |
| **配置** | Pydantic | 类型安全的配置验证 |
| **LLM 路由** | LiteLLM | 20+ provider 统一接口 |
| **WebSocket** | websockets | 轻量级 WebSocket 库 |
| **HTTP** | httpx | 现代异步 HTTP 客户端 |
| **网页解析** | readability-lxml | 提取网页正文 |
| **定时任务** | croniter | Cron 表达式解析 |
| **向量数据库** | LanceDB (可选) | 本地向量搜索 |
| **加密** | cryptography (Fernet) | API Key 加密存储 |
| **日志** | loguru | 简洁的日志库 |
| **测试** | pytest + pytest-asyncio | 异步测试支持 |
| **构建** | hatchling | 现代 Python 构建工具 |
| **包管理** | uv | 极速包管理器 |

---

## 八、开发阶段规划

### Phase 0: 环境搭建 (Day 1-3)
- [ ] 安装 Python 3.12, uv, Git
- [ ] 创建项目骨架 (pyproject.toml, 目录结构)
- [ ] 配置 Ruff (代码格式化)
- [ ] 写第一个 "Hello MindClaw" 脚本
- [ ] 熟悉 asyncio 基础概念 (async/await)
- **里程碑：** `python -c "import mindclaw"` 成功运行

### Phase 1: CLI 对话 + 单模型 (Day 4-13)
- [ ] 实现 config/schema.py (Pydantic 配置，支持环境变量引用)
- [ ] 实现 llm/base.py + llm/router.py (LiteLLM 接入)
- [ ] 实现 bus/events.py + bus/queue.py (基础消息总线，双队列)
- [ ] 实现最简 Agent Loop (无工具，纯对话)
- [ ] 实现 CLI Channel (prompt-toolkit 交互)
- [ ] 实现 cli/commands.py (typer 命令)
- [ ] 配置 loguru 基础日志
- **里程碑：** 终端输入问题 → Claude 回复答案

### Phase 2: 消息总线 + 工具系统 (Day 14-23)
- [ ] 实现 tools/base.py + tools/registry.py (工具抽象和注册)
- [ ] 实现 tools/file_ops.py (读写编辑)
- [ ] 实现 tools/shell.py (Shell 执行，含基础命令黑名单)
- [ ] 实现 tools/web.py (搜索 + 抓取)
- [ ] Agent Loop 集成工具调用 (ReAct 循环)
- **里程碑：** AI 能帮你读文件、搜网页、执行命令

### Phase 3: 安全层 (Day 24-30)
- [ ] 实现 security/sandbox.py (完整命令黑名单 + 路径沙箱 + 超时)
- [ ] 实现 security/approval.py (审批工作流 + 超时 + 防死锁路由)
- [ ] 实现工具结果截断 (防上下文注入)
- [ ] 实现 Session 投毒防护 (错误响应不持久化)
- [ ] 工具风险等级标注 (safe/moderate/dangerous)
- **里程碑：** 危险命令触发审批，黑名单命令被拦截

### Phase 4: 记忆系统 (Day 31-38)
- [ ] 实现 knowledge/session.py (JSONL 持久化)
- [ ] 实现 knowledge/memory.py (MEMORY.md + HISTORY.md)
- [ ] 实现 LLM 驱动的记忆整合 (consolidation)
- [ ] 实现 orchestrator/context.py (系统提示构建)
- **里程碑：** 重启后 AI 仍记得之前的对话内容

### Phase 5: Gateway + 第一个渠道 Telegram (Day 39-50)
- [ ] 实现 channels/base.py (BaseChannel 抽象类)
- [ ] 实现 channels/manager.py (ChannelManager，双路径路由)
- [ ] 实现 gateway/server.py (WebSocket Server)
- [ ] 实现 gateway/auth.py (Token 认证 + 设备配对)
- [ ] 实现 security/auth.py (渠道白名单)
- [ ] 实现 channels/telegram.py
- [ ] 实现 security/crypto.py (API Key 加密存储)
- **里程碑：** 手机上通过 Telegram 与 MindClaw 安全对话

### Phase 6: 编排层 (Day 51-60)
- [ ] 实现 orchestrator/acp.py (asyncio.subprocess 进程隔离)
- [ ] 实现 orchestrator/subagent.py (子 Agent 管理)
- [ ] 主 Agent 集成 spawn_task 工具
- [ ] 任务结果汇总机制
- [ ] 消息去重 + 限流 (增强消息总线)
- **里程碑：** AI 能并行处理复杂任务

### Phase 7: 插件系统 (Day 61-68)
- [ ] 实现 plugins/manifest.py (清单解析)
- [ ] 实现 plugins/loader.py (动态加载)
- [ ] 实现 plugins/hooks.py (Hook 管理 + 生命周期事件)
- [ ] 编写第一个示例插件
- **里程碑：** 能安装和运行自定义插件

### Phase 8: 更多渠道 (Day 69-80)
- [ ] 实现 channels/slack.py
- [ ] 实现 channels/feishu.py
- [ ] 实现 channels/discord.py (discord.py 库)
- **里程碑：** 5 个渠道全部可用

### Phase 9: 知识管理 (Day 81-93)
- [ ] 实现 knowledge/obsidian.py (深度集成)
- [ ] 实现 knowledge/notion.py (API 集成)
- [ ] 实现 knowledge/web_archive.py (网页收藏)
- [ ] 可选：实现 knowledge/vector.py (LanceDB 语义搜索)
- **里程碑：** AI 能读写 Obsidian/Notion，搜索知识库

### Phase 10: 微信 + 高级功能 (Day 94-110)
- [ ] 微信接入 (Node.js Bridge)
- [ ] 技能系统 (SKILL.md 加载 + LLM 自主路由)
- [ ] 定时任务 (Cron)
- [ ] 心跳服务 (Heartbeat)
- [ ] 多模型自动降级
- [ ] 进程守护 (systemd/launchd 配置)
- **里程碑：** MindClaw 完整体

---

## 九、设计决策记录

| 决策 | 选择 | 备选 | 理由 |
|------|------|------|------|
| 主语言 | Python | TypeScript | AI 写 Python 最好，库生态最强 |
| LLM 集成 | LiteLLM 统一层 | 各 SDK 直连 | 一行代码切换 provider，维护成本低 |
| 进程隔离 | asyncio.subprocess + JSON stdio | multiprocessing | 与 asyncio 兼容好，通信协议与 MCP 一致 |
| 消息协议 | JSON-RPC over WebSocket | REST API | 实时双向通信，适合聊天场景 |
| 配置格式 | JSON + Pydantic | YAML / TOML | JSON 最通用，Pydantic 自动验证 |
| 记忆存储 | Markdown 文件 | SQLite | 人类可读可编辑，与 Obsidian 天然兼容 |
| 向量数据库 | LanceDB (可选) | ChromaDB / Qdrant | 纯本地，无需额外服务 |
| 审批机制 | 渠道内交互 | Web UI 审批 | 无需额外开发 Web 界面 |
| 包管理 | uv | pip / poetry | 速度最快，现代化 |

---

## 十、灵感来源

| 来源 | 借鉴内容 |
|------|---------|
| **Nanobot** | 极简架构、ReAct Loop、消息总线、记忆系统、技能系统、LiteLLM 集成 |
| **OpenClaw** | Gateway 架构、ACP 进程隔离、审批工作流、插件系统、Hook 机制、向量记忆 |
| **Claude Code** | 工具设计模式、安全沙箱思路、渐进式技能加载 |

---

## 十一、错误恢复与进程守护

### 11.1 进程守护策略

```
MindClaw 进程层级:

systemd / launchd (OS 级守护)
  └── Gateway 主进程 (长驻)
        ├── ChannelManager (协程, 主进程内)
        ├── AgentLoop (协程, 主进程内)
        ├── 子 Agent 进程 A (独立进程, 按需启动)
        └── MCP Server 进程 (独立进程, 按需启动)
```

- **Gateway 崩溃：** 由 systemd/launchd 自动重启，配置 `Restart=on-failure`
- **子 Agent 崩溃：** 主进程捕获子进程退出信号，标记任务为 failed，通知用户
- **MCP Server 崩溃：** 下次工具调用时自动重新启动

### 11.2 消息恢复

- Agent 处理消息时崩溃 → 消息已从队列取出但未完成 → **不自动重试**（防止副作用重复执行），记录到错误日志，通知用户"处理中断，请重新发送"
- 渠道连接断开 → 自动重连（指数退避: 1s → 2s → 4s → ... → 最大 60s）
- LLM 调用失败 → 自动降级到 fallback model → 降级也失败 → 通知用户"所有模型暂时不可用"

---

## 十二、日志与可观测性

**日志框架：** loguru

**日志级别策略：**

| 级别 | 用途 | 示例 |
|------|------|------|
| ERROR | 需要关注的错误 | LLM 调用失败、渠道连接断开 |
| WARNING | 潜在问题 | 审批超时、降级到 fallback model |
| INFO | 关键业务事件 | 收到消息、工具执行完成、审批通过 |
| DEBUG | 调试信息 | LLM 请求/响应详情、消息路由过程 |

**结构化日志格式：**
```
2026-03-06 14:30:00 | INFO | channel=telegram chat_id=12345 | 收到消息: "帮我搜索..."
2026-03-06 14:30:01 | INFO | tool=web_search risk=safe | 执行工具
2026-03-06 14:30:03 | INFO | model=claude-sonnet tokens=1200 cached=800 | LLM 调用完成
```

**日志轮转：** 单文件最大 10MB，保留最近 7 天

**关键指标（未来可接入监控）：**
- LLM 调用延迟、token 用量、缓存命中率
- 每日消息数、每渠道消息分布
- 工具执行成功/失败率
- 审批等待时间

---

## 十三、成功标准（更新版）

1. **可用性：** 能通过 5 个渠道与 MindClaw 正常对话
2. **安全性：** 危险操作 100% 经过审批，审批超时自动拒绝，无越权执行
3. **可靠性：** Agent 崩溃不影响 Gateway，子进程崩溃自动标记失败并通知用户，Gateway 由 OS 守护进程自动重启
4. **可扩展：** 新增渠道/工具/Provider 均可通过插件完成
5. **知识管理：** 能读写 Obsidian + Notion，支持语义搜索
6. **记忆持久：** 重启后记忆不丢失，长期偏好正确保留
7. **成本可控：** Prompt 缓存 + 结果截断有效降低 token 消耗
8. **可观测：** 结构化日志覆盖关键路径，可追踪任意消息的完整处理链路
9. **密钥安全：** 无明文 API Key 提交到 Git，支持环境变量和加密存储

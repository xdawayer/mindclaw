# MindClaw

> 个人全能 AI 助手框架 — 安全、可扩展、多渠道、多模型
> PRD 详见: `docs/plans/2026-03-06-mindclaw-prd.md`

## Tech Stack

- **Python 3.12+** / asyncio / uv (包管理)
- LiteLLM (多模型路由) / Pydantic (配置校验) / croniter (定时任务)
- Typer + Rich (CLI) / websockets (Gateway)
- httpx / loguru / pytest + pytest-asyncio

## Architecture (6 层)

```
用户 → 渠道层(Channel) → 消息总线(MessageBus) → 编排层(Orchestrator/Agent)
                                                    ↓
                              安全层(Security) ← 大脑层(LLM Router)
                                                    ↓
                              工具层(Tools) + 插件 → 知识层(Knowledge)
```

- **渠道层**: BaseChannel 抽象，CLI/Telegram/Slack/飞书/Discord/微信
- **消息总线**: asyncio.Queue 双队列 (inbound/outbound)，InboundMessage/OutboundMessage dataclass
- **编排层**: ReAct Agent Loop (最多 40 轮)，ACP 协议管理子 Agent (asyncio.subprocess + JSON stdio)
- **大脑层**: LiteLLM 统一路由，Prompt 缓存，自动降级
- **安全层**: 三层认证 (Gateway Token / 设备配对 / 白名单)，工具三级风险 (safe/moderate/dangerous)，审批工作流
- **工具层**: Tool 抽象基类 + ToolRegistry，内置 17 个工具 (含 Cron CRUD)，插件系统 (manifest.json + hooks)
- **知识层**: 四层记忆 (Session JSONL / MEMORY.md / LanceDB向量 / HISTORY.md)

## Project Structure

```
mindclaw/
├── mindclaw/          # 主包
│   ├── cli/           # CLI 入口 (typer)
│   │   ├── commands.py
│   │   ├── daemon.py
│   │   └── skill_commands.py     # 技能管理子命令
│   ├── gateway/       # WebSocket Gateway
│   ├── channels/      # 渠道适配 (base → 各平台实现)
│   ├── bus/           # 消息总线 (events + queue)
│   ├── orchestrator/  # 编排层 (agent_loop + acp + subagent)
│   ├── llm/           # LLM 路由 (litellm + cache)
│   ├── security/      # 安全 (auth + approval + sandbox)
│   ├── tools/         # 工具 (base + registry + 各工具实现)
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── file_ops.py
│   │   ├── shell.py
│   │   ├── web.py
│   │   ├── cron.py
│   │   ├── memory.py
│   │   └── skill_tools.py        # 技能管理工具 (search/install/remove/list/show)
│   ├── plugins/       # 插件系统 (loader + hooks)
│   ├── knowledge/     # 知识层 (memory + session + obsidian + notion)
│   ├── skills/        # 技能系统 (多目录注册 + 安装管理)
│   │   ├── registry.py           # SkillRegistry 核心 (builtin/project/user 扫描，原子重载，保护名称)
│   │   ├── installer.py          # 安装/卸载/更新 (本地/URL/GitHub/索引源)
│   │   ├── index_client.py       # 索引拉取、本地缓存 (TTL 24h)、搜索
│   │   ├── integrity.py          # SHA256 校验、SSRF 过滤、格式校验、大小限制
│   │   ├── summarize.md          # 内置技能: 文章总结
│   │   └── translate.md          # 内置技能: 翻译
│   ├── health/        # 健康检查 (HealthMonitor + HTTP /health /ready)
│   ├── templates/     # SOUL.md / AGENTS.md
│   └── config/        # Pydantic 配置 (schema + loader)
├── deploy/            # Daemon 部署模板 (systemd / launchd)
├── plugins/           # 用户插件目录
├── tests/             # pytest 测试
└── docs/plans/        # PRD 等文档
```

## Key Conventions

- **配置**: JSON + Pydantic，敏感信息优先环境变量，配置文件 0600 权限
- **进程通信**: JSON over stdin/stdout (与 MCP stdio 一致)
- **工具风险等级**: `safe` 直接执行 / `moderate` 记录日志 / `dangerous` 需用户审批
- **子 Agent 限制**: 不能发消息给用户，不能再派子任务，最多 15 轮迭代
- **记忆整合**: Session 消息超 20 条 → LLM 提取 → 写入 MEMORY.md + HISTORY.md
- **日志**: loguru，结构化格式，单文件 10MB，保留 7 天
- **测试**: pytest + pytest-asyncio

## Development Phases

当前进度：Phase 10+ 全部完成 — LLM 自动降级、技能系统、定时任务、健康检查、微信渠道、Daemon 部署、向量搜索 (LanceDB)、技能安装系统均已实现

| Phase | 内容 | 里程碑 |
|-------|------|--------|
| 0 | 环境搭建 | `import mindclaw` 成功 |
| 1 | CLI 对话 + 单模型 | 终端问答可用 |
| 2 | 工具系统 | AI 能读文件/搜网页/执行命令 |
| 3 | 安全层 | 审批 + 黑名单 + 沙箱 |
| 4 | 记忆系统 | 重启后记忆不丢失 |
| 5 | Gateway + Telegram | 手机远程对话 |
| 6 | 编排层 | 子 Agent 并行任务 |
| 7 | 插件系统 | 自定义插件可用 |
| 8 | 更多渠道 (Discord/Slack/飞书) | 多平台接入 |
| 9 | 知识管理 (Obsidian/Notion/WebArchive) | 外部知识源整合 |
| 10 | LLM 自动降级 + 技能系统 + 定时任务 + 健康检查 + 微信渠道 + Daemon 部署 | 生产就绪 |
| 10+ | 技能安装系统 | 支持从本地/URL/GitHub/索引安装技能 |

---

## Documentation Self-Maintenance System (MANDATORY)

### Rule 1: Root-Level Update Obligation
- **任何功能、架构、写法的变更，工作结束后必须更新相关目录的子文档。**
- 硬性要求，不可跳过。每次改动完成前，检查是否有目录级文档需要同步更新。

### Rule 2: Folder-Level Architecture Doc
- **每个文件夹**中必须有 `_ARCHITECTURE.md`：
  - 开头声明：`> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。`
  - 3 行以内极简架构说明
  - 每个文件的：**文件名** | **地位** | **功能**

### Rule 3: File-Level Header Comments
- **每个文件开头** 3 行极简注释：`input` (依赖) / `output` (导出) / `pos` (地位)
- 附带声明：`一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md`
- 示例 (Python):
  ```python
  # input: 依赖 ../core/engine, ../utils/logger
  # output: 导出 process_request(), RequestConfig
  # pos: 请求处理层入口，连接路由与核心引擎
  # UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md
  ```

---

## PRD-Driven Development (MANDATORY)

> PRD 是项目唯一真相源: `docs/plans/2026-03-06-mindclaw-prd.md`

**每次收到需求（新功能/优化/bug），执行以下流程：**

1. **PRD 对齐** — 先读 PRD，判断该需求是否在 PRD 范围内、是否与 PRD 冲突
2. **PRD 先行** — 如果需求超出 PRD 或与 PRD 矛盾，**先更新 PRD**，再动代码
3. **编码实现** — PRD 对齐后才开始写代码
4. **PRD 回验** — 代码完成后，回查 PRD 确认实现符合文档描述，不一致则修正代码或更新 PRD

**绝不允许：** 代码与 PRD 不一致的状态被提交。PRD 和代码必须始终同步。

---

## Workflow Orchestration

### 1. Plan Mode Default
- 非简单任务 (3+ 步骤或架构决策) 先进 plan mode
- 出问题立即 STOP 重新规划，不硬推
- 先写详细 spec 减少歧义

### 2. Subagent Strategy
- 用 subagent 保持主上下文窗口干净
- 复杂问题多 subagent 并行，每个 subagent 一个任务

### 3. Self-Improvement Loop
- 用户纠正后立即更新 `tasks/lessons.md`
- 写规则防止同类错误

### 4. Verification Before Done
- 完成前必须证明可用：跑测试、看日志、diff 行为
- 自问："staff engineer 会批准吗？"

### 5. Demand Elegance (Balanced)
- 非简单改动先问"有没有更优雅的方案"
- 简单修复不过度设计

### 6. Autonomous Bug Fixing
- 收到 bug 直接修，不问用户怎么做
- 看日志 → 定位 → 修复 → 验证

## Task Management

1. **Plan First**: 写计划到 `tasks/todo.md`
2. **Verify Plan**: 开始前对齐
3. **Track Progress**: 逐项标记完成
4. **Explain Changes**: 每步高层总结
5. **Document Results**: 结果写入 `tasks/todo.md`
6. **Capture Lessons**: 纠正后更新 `tasks/lessons.md`

## Core Principles

- **Simplicity First**: 改动尽可能简单，影响最少代码
- **No Laziness**: 找根因，不临时糊弄，Senior 标准
- **Minimal Impact**: 只动必要的，不引入新 bug

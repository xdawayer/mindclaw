# Phase 4: 记忆系统 — 设计文档

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 MindClaw 重启后记住对话历史和用户偏好，通过 LLM 驱动的记忆整合实现长期记忆。

**架构方案:** 方案 A — Session 直接集成到 AgentLoop。`knowledge/session.py` + `knowledge/memory.py` 提供纯工具函数，AgentLoop 调用它们。`orchestrator/context.py` 负责构建系统提示。

---

## 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 范围 | Session 持久化 + MEMORY.md/HISTORY.md + 上下文构建 | PRD Phase 4 原定范围，向量数据库留到 Phase 9 |
| 整合触发 | 自动 (>20 条) + 手动 | 兼顾自动化和用户控制 |
| 旧消息处理 | JSONL 保留完整归档，仅移动 consolidation pointer | 磁盘便宜，可追溯性更重要 |
| MEMORY.md 写入 | LLM 合并重写 | 每次整合产出干净版本，避免信息腐化 |
| 架构方案 | Session 直接集成到 AgentLoop | 改动最小，YAGNI，不引入不需要的抽象层 |

---

## 1. Session 持久化

**文件**: `mindclaw/knowledge/session.py`

**存储格式**: 每个 session_key 对应一个 JSONL 文件：
```
data/sessions/{channel}_{chat_id}.jsonl
```

每行一条消息（LLM 格式的 message dict + 时间戳）：
```jsonl
{"role":"user","content":"你好","ts":1741420800.0}
{"role":"assistant","content":"你好！有什么可以帮你？","ts":1741420801.0}
```

**整合指针**: 文件头部用特殊行标记：
```jsonl
{"_meta":"consolidation","pointer":15,"consolidated_at":1741420900.0}
```
`pointer` 表示前 15 行已被整合进 MEMORY.md。加载时只读 pointer 之后的消息到内存，但文件保留完整归档。

**核心接口**:
```python
class SessionStore:
    def __init__(self, data_dir: Path): ...
    def load(self, session_key: str) -> tuple[list[dict], int]:
        """返回 (未整合的消息列表, 总消息数)"""
    def append(self, session_key: str, messages: list[dict]) -> None:
        """追加消息到 JSONL"""
    def mark_consolidated(self, session_key: str, pointer: int) -> None:
        """更新整合指针"""
```

**AgentLoop 集成**:
- `__init__` 接收 `SessionStore`，启动时不预加载
- `handle_message` 开始时调用 `load()` 恢复历史
- `handle_message` 结束时调用 `append()` 持久化新消息
- 替代当前纯内存 `_sessions` dict

---

## 2. 记忆整合 (Consolidation)

**文件**: `mindclaw/knowledge/memory.py`

**触发条件**:
- **自动**: `handle_message` 结束后检查，未整合消息数 > 20 条时触发
- **手动**: 用户发送"整理记忆"/"consolidate" 时触发

**整合流程**:
```
1. 从 SessionStore 读取未整合的旧消息（保留最近 10 条不动）
2. 读取现有 MEMORY.md（如果有）
3. 发给 LLM: "从这些对话中提取值得记住的信息，与现有记忆合并去重"
4. LLM 返回新的 MEMORY.md 内容 → 覆盖写入
5. 追加摘要到 HISTORY.md
6. 更新 SessionStore 的 consolidation pointer
```

**MEMORY.md 格式**（LLM 生成，有模板约束）:
```markdown
# MindClaw Memory

## 用户偏好
- ...

## 关键事实
- ...

## 重要决定
- ...
```

**HISTORY.md 格式**:
```markdown
# MindClaw History

- [2026-03-08 14:30] 用户询问了 Phase 4 记忆系统设计
- [2026-03-08 15:00] 整合了 25 条消息，提取了 3 条新记忆
```

**核心接口**:
```python
class MemoryManager:
    def __init__(self, data_dir: Path, router: LLMRouter, config: MindClawConfig): ...
    async def consolidate(self, session_key: str, session_store: SessionStore) -> bool:
        """执行整合，返回是否成功"""
    def should_consolidate(self, unconsolidated_count: int) -> bool:
        """检查是否需要自动整合"""
    def load_memory(self) -> str:
        """读取 MEMORY.md 内容"""
```

---

## 3. 上下文构建

**文件**: `mindclaw/orchestrator/context.py`

**职责**: 替代 `agent_loop.py` 中硬编码的 `SYSTEM_PROMPT`，动态构建系统提示。

**上下文组成**（按顺序拼接）:
```
1. 基础人格提示
2. 当前日期时间
3. MEMORY.md 内容（如果存在）
```

**注入格式**:
```markdown
You are MindClaw, a personal AI assistant. You are helpful, concise, and accurate.
Respond in the same language as the user's message.

## Current Date
2026-03-08

## Memory (what you know about the user)
<MEMORY.md 内容>
```

**核心接口**:
```python
class ContextBuilder:
    def __init__(self, memory_manager: MemoryManager): ...
    def build_system_prompt(self) -> str:
        """构建完整系统提示"""
```

**AgentLoop 改动**:
- `_build_messages()` 调用 `ContextBuilder.build_system_prompt()`
- 删除模块级 `SYSTEM_PROMPT` 常量

---

## 4. 配置与数据目录

**配置新增** (`config/schema.py`):
```python
class KnowledgeConfig(BaseModel):
    data_dir: str = Field(default="data", alias="dataDir")
    consolidation_threshold: int = Field(default=20, alias="consolidationThreshold")
    consolidation_keep_recent: int = Field(default=10, alias="consolidationKeepRecent")
```

`MindClawConfig` 新增 `knowledge: KnowledgeConfig` 字段。

**数据目录结构**:
```
data/
├── sessions/           # Session JSONL 文件
│   ├── cli_local.jsonl
│   └── telegram_12345.jsonl
├── MEMORY.md           # 长期记忆
└── HISTORY.md          # 操作日志
```

`data/` 目录加入 `.gitignore`。

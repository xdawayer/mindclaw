# Phase 11: Automated Bot Scenarios

> Date: 2026-03-10
> Status: IN PROGRESS

## Overview

Add 6 automated bot scenarios to MindClaw by first fixing critical infrastructure issues in the cron/notification pipeline (Phase 0), then building each bot as a skill file backed by new or enhanced tools.

## Requirements

- Fix cron output routing so scheduled tasks can deliver messages to real channels
- Isolate cron bot sessions so they do not contaminate each other
- Enable concurrent cron execution without blocking user messages
- Add safety constraints for unattended cron execution (no DANGEROUS tools, timeout, iteration limits)
- Implement 6 bot skills: Hot News, Competitor Monitoring, Cross-Platform Publishing, SEO Article Generation, X/Twitter Browsing, Dashboard
- New tools: api_call (HTTP API with auth profiles), twitter_read (subprocess_exec wrapper), web_snapshot, dashboard_export
- Maintain existing test coverage and add tests for all new code

## Architecture Changes

| Category | New Files | Modified Files |
|----------|-----------|----------------|
| Cron Store | `orchestrator/cron_store.py` | `orchestrator/cron_scheduler.py`, `tools/cron.py`, `app.py` |
| Cron Routing | | `bus/events.py`, `tools/message_user.py`, `orchestrator/agent_loop.py`, `app.py` |
| Cron Concurrency | | `app.py` |
| Cron Safety | `orchestrator/cron_context.py` | `orchestrator/agent_loop.py`, `orchestrator/context.py` |
| Cron Logging | `orchestrator/cron_logger.py` | `orchestrator/cron_scheduler.py` |
| Config | | `config/schema.py` |
| New Tools | `tools/api_call.py`, `tools/twitter_read.py`, `tools/web_snapshot.py`, `tools/dashboard_export.py` | `app.py` |
| Bot Skills | 6 new `.md` files in `skills/` | |
| Tests | 10+ new test files | |

---

## Phase 0: Infrastructure (CRITICAL fixes)

### 0a: CronTaskStore shared singleton

**Problem**: `CronScheduler` and `CronAddTool/CronListTool/CronRemoveTool` both read/write `cron_tasks.json` independently. No shared lock. Race condition.

**New file**: `mindclaw/orchestrator/cron_store.py` (~120 lines)
- Class: `CronTaskStore`
  - `__init__(self, data_dir: Path)` -- asyncio.Lock, _tasks dict
  - `async load() -> dict[str, dict]` -- acquire lock, read JSON, return copy
  - `async save(tasks: dict) -> None` -- acquire lock, atomic write (.tmp + rename)
  - `async get(task_id) -> dict | None`
  - `async add(task_id, task) -> None`
  - `async remove(task_id) -> dict | None`
  - `async update_last_run(task_id, timestamp) -> None`
  - `async set_enabled(task_id, enabled) -> None` (for Phase 0h)

**Modify**:
- `orchestrator/cron_scheduler.py` -- remove `_load_tasks()/_save_tasks()/_file_lock`, accept `store: CronTaskStore`
- `tools/cron.py` -- remove module-level load/save, accept `store: CronTaskStore` in all 3 tool classes
- `app.py` -- create `CronTaskStore` instance, pass to scheduler and tools

**Tests**: `tests/test_cron_store.py`
- test_store_add_and_load, test_store_remove, test_store_update_last_run
- test_store_atomic_write, test_store_concurrent_access, test_store_set_enabled

**Deps**: None | **Risk**: Medium

---

### 0b: Cron notification routing

**Problem**: Cron triggers produce `InboundMessage(channel="system", chat_id="cron")`. OutboundMessage to channel="system" is silently dropped because no "system" channel exists.

**Solution**: Add `metadata` dict to `InboundMessage`. Cron tasks store `notify_channel`/`notify_chat_id`. Agent loop reads metadata and overrides `_current_channel`/`_current_chat_id`.

**Modify**:
1. `bus/events.py` -- add `metadata: dict = field(default_factory=dict)` to InboundMessage
2. `tools/cron.py` -- extend CronAddTool.parameters with optional `notify_channel`, `notify_chat_id`
3. `app.py` -- `_on_cron_trigger(name, task)` receives full task dict, builds InboundMessage with metadata
4. `orchestrator/cron_scheduler.py` -- `_trigger()` passes full task dict to callback
5. `orchestrator/agent_loop.py` -- read `inbound.metadata["notify_channel"]`, override `_current_channel`/`_current_chat_id`, build OutboundMessage with correct routing

**Tests**: `tests/test_cron_routing.py`
- test_cron_trigger_passes_full_task_dict
- test_cron_inbound_has_metadata
- test_agent_loop_uses_notify_channel
- test_agent_loop_skips_system_outbound
- test_message_user_routes_to_real_channel_during_cron

**Deps**: Phase 0a | **Risk**: High (core message routing)

---

### 0c: Per-bot session isolation

**Problem**: All cron tasks share session_key "system:cron", contaminating each other's history.

**Modify**: `app.py` -- set `chat_id=f"cron:{name}"` in `_on_cron_trigger()` (one-line change in 0b method)

**Tests**: Add `test_cron_session_key_per_task` to `tests/test_cron_routing.py`

**Deps**: Phase 0b | **Risk**: Low

---

### 0d: Cron concurrency (bounded semaphore)

**Problem**: `_message_router()` in app.py is sequential -- awaits previous task. Long cron tasks block user messages.

**Modify**:
1. `config/schema.py` -- add `AgentConfig.max_concurrent_tasks: int = 3`
2. `app.py`:
   - Replace `self._agent_task` with `self._task_semaphore = asyncio.Semaphore(N)` + `self._active_tasks: set`
   - `_message_router()`: acquire semaphore, create task, add to set, release on done
   - `_process_message_with_release()`: try/finally wrapper
   - Shutdown: cancel all `_active_tasks`

**Tests**: `tests/test_cron_concurrency.py`
- test_concurrent_messages_not_blocked
- test_semaphore_limits_concurrency
- test_cleanup_cancels_all_tasks

**Deps**: None | **Risk**: Medium

---

### 0e: Skill execution constraints for cron

**Problem**: Unattended cron skills need iteration/timeout/tool restrictions.

**New file**: `mindclaw/orchestrator/cron_context.py` (~80 lines)
- Dataclass: `CronExecutionConstraints`
  - `max_iterations: int = 15`
  - `timeout_seconds: int = 300`
  - `allowed_tools: frozenset[str] | None = None`
  - `blocked_tools: frozenset[str] = frozenset({"exec", "spawn_task"})`
  - `notify_on_failure: bool = True`
- Function: `parse_cron_constraints(task: dict) -> CronExecutionConstraints`

**Modify**:
1. `tools/cron.py` -- extend CronAddTool.parameters with max_iterations, timeout, notify_on_failure
2. `orchestrator/agent_loop.py` -- read constraints from metadata, override max_iterations, apply timeout, block dangerous tools

**Tests**: `tests/test_cron_context.py`
- test_parse_default_constraints, test_parse_custom_constraints
- test_cron_blocks_dangerous_tools, test_cron_timeout, test_cron_max_iterations

**Deps**: Phase 0b (metadata) | **Risk**: Medium

---

### 0f: api_call tool

**New file**: `mindclaw/tools/api_call.py` (~180 lines)
- Class: `ApiCallTool(Tool)`
  - `name = "api_call"`, `risk_level = DANGEROUS`
  - Parameters: url, method (GET/POST/PUT/DELETE), headers, body, auth_profile
  - URL allowlist validation (config: `api_call_url_allowlist`)
  - SSRF check (reuse `_is_safe_url()` from web.py)
  - Auth profile injection (config: `api_call_auth_profiles`) -- LLM never sees raw tokens
  - No redirects, 30s timeout, response truncation

**Modify**:
1. `config/schema.py`:
   - New `AuthProfileConfig(BaseModel)`: profile_type (bearer/header/basic), value
   - `ToolsConfig.api_call_auth_profiles: dict[str, AuthProfileConfig]`
   - `ToolsConfig.api_call_url_allowlist: list[str]`
2. `app.py` -- register ApiCallTool with config values

**Tests**: `tests/test_tools_api_call.py`
- test_basic_get, test_bearer_auth, test_url_allowlist_blocks
- test_ssrf_protection, test_response_truncation
- test_empty_allowlist_blocks_all, test_risk_level_dangerous

**Deps**: None | **Risk**: High (security-sensitive)

---

### 0g: Per-tool max_chars

**Modify**:
1. `tools/base.py` -- add `max_result_chars: int | None = None` class attribute
2. `orchestrator/agent_loop.py` -- use `tool.max_result_chars or config.tools.tool_result_max_chars`
3. `tools/web.py` -- set `WebFetchTool.max_result_chars = 5000`, `WebSearchTool.max_result_chars = 3000`

**Tests**: Add to `tests/test_agent_loop_tools.py`

**Deps**: None | **Risk**: Low

---

### 0h: Cron enabled field + global kill switch

**Modify**:
1. `config/schema.py` -- add `AgentConfig.cron_enabled: bool = True`
2. `orchestrator/cron_store.py` (from 0a) -- task dict includes `enabled: bool`
3. `orchestrator/cron_scheduler.py` -- accept `global_enabled_fn`, skip disabled tasks in `check_once()`
4. `tools/cron.py` -- new `CronToggleTool(Tool)`: name="cron_toggle", params: task_id + enabled
5. `app.py` -- pass `global_enabled_fn`, register CronToggleTool

**Tests**: Add to `tests/test_cron_store.py` and `tests/test_cron_scheduler.py`

**Deps**: Phase 0a | **Risk**: Low

---

### 0i: cron_runs.jsonl execution log

**New file**: `mindclaw/orchestrator/cron_logger.py` (~60 lines)
- Class: `CronRunLogger`
  - `__init__(data_dir: Path)` -- log_path = data_dir/cron_runs.jsonl
  - `log_run(task_name, status, started_at, finished_at, error="")` -- append JSON line
  - `recent_runs(task_name=None, limit=20) -> list[dict]`

**Modify**:
1. `app.py` -- create CronRunLogger, wrap cron execution with timing/status tracking
2. `tools/cron.py` -- new `CronHistoryTool(Tool)`: name="cron_history", reads from logger

**Tests**: `tests/test_cron_logger.py`

**Deps**: None | **Risk**: Low

---

### 0j: Cron context restrictions (tool safety)

Already mostly addressed by Phase 0e's `blocked_tools`. This sub-task ensures:

**Modify**:
1. `orchestrator/cron_context.py` (from 0e) -- default blocked_tools includes all DANGEROUS tools
2. `orchestrator/agent_loop.py` (from 0e) -- when cron constraints active, skip approval flow for blocked tools, return error
3. `orchestrator/context.py` -- add `build_cron_system_prompt()` with tool restrictions in prompt

**Tests**: Add to `tests/test_cron_context.py`

**Deps**: Phase 0e | **Risk**: Medium

---

## Phase 1: Hot News Aggregation Bot

**New file**: `mindclaw/skills/hot-news.md`
- YAML: `name: hot-news`, `description: Aggregate trending news`, `load: on_demand`
- Steps: web_search (3 categories, 5 results each) -> web_fetch (top 3) -> summarize -> message_user
- Output: Date header, categorized bullets, source URLs

**Cron config**:
```json
{"name": "hot-news", "cron_expr": "30 9 * * *", "action": "Execute hot-news skill...",
 "notify_channel": "telegram", "notify_chat_id": "<id>", "max_iterations": 20, "timeout": 600}
```

**Tests**: Manual integration + skill parsing test

**Deps**: Phase 0 complete | **Risk**: Low

---

## Phase 2: Competitor Monitoring Bot

**New file**: `mindclaw/tools/web_snapshot.py` (~120 lines)
- `WebSnapshotTool`: save URL content as UUID-named file + index.jsonl metadata
- `WebSnapshotListTool`: list recent snapshots for a URL
- `WebSnapshotReadTool`: read snapshot content by ID
- UUID filenames only (no URL-derived paths), SSRF protection, retention policy (max_snapshots)

**New file**: `mindclaw/skills/competitor-monitor.md`
- Steps: web_snapshot_list (get previous) -> web_snapshot (take new) -> web_snapshot_read (load both) -> LLM semantic diff -> message_user if significant changes

**Modify**: `app.py` -- register 3 snapshot tools

**Tests**: `tests/test_tools_web_snapshot.py`
- test_snapshot_saves_content, test_uuid_filename, test_list_returns_recent
- test_read_returns_content, test_retention_policy, test_ssrf_protection

**Deps**: Phase 0 | **Risk**: Medium

---

## Phase 3a: Cross-Platform Publishing - Single Platform

**New file**: `mindclaw/skills/content-publish.md`
- Steps: api_call (GitHub API to check repo changes) -> read_file -> format -> api_call (publish) -> message_user
- Note: Uses api_call + GitHub API instead of exec + git pull (exec is DANGEROUS, blocked in cron)

**Deps**: Phase 0f (api_call) | **Risk**: Medium

---

## Phase 3b: Cross-Platform Publishing - Multi Platform

**Modify**: `mindclaw/skills/content-publish.md` -- add multi-platform workflow section
- Iterate over configured platforms, format per-platform, publish each via api_call
- Archive to `data/published.jsonl` via write_file

**Deps**: Phase 3a | **Risk**: Low

---

## Phase 4: SEO Article Generation Bot

**New file**: `mindclaw/skills/seo-article.md`
- Steps: web_search (keyword research) -> web_fetch (reference material) -> generate outline -> write article -> write_file (draft) -> message_user
- Output: Markdown with YAML front-matter (title, date, keywords, status: draft)
- Cron: `0 10 * * 1,3,5`

**Deps**: Phase 0 | **Risk**: Low

---

## Phase 5: X/Twitter Browsing

**New file**: `mindclaw/tools/twitter_read.py` (~100 lines)
- `TwitterReadTool(Tool)`: MODERATE risk
- Parameters: action (timeline/search/user), query, count
- MUST use `asyncio.create_subprocess_exec` (NOT shell)
- Input validation: reject shell metacharacters in query
- Config: `ToolsConfig.twitter_cli_path`

**New file**: `mindclaw/skills/twitter-browse.md`

**Tests**: `tests/test_tools_twitter_read.py`
- test_uses_subprocess_exec, test_rejects_shell_metacharacters
- test_timeline, test_search, test_timeout

**Deps**: None (independent) | **Risk**: Medium

---

## Phase 6: Dashboard (static HTML export)

**New file**: `mindclaw/tools/dashboard_export.py` (~150 lines)
- `DashboardExportTool(Tool)`: MODERATE risk
- Reads cron_runs.jsonl + cron_tasks.json + MEMORY.md summary
- Generates self-contained HTML (inline CSS, no external deps)
- Sections: System Status, Active Cron Tasks, Recent Executions, Success Rate

**New file**: `mindclaw/skills/dashboard.md`

**Tests**: `tests/test_tools_dashboard.py`

**Deps**: Phase 0i (CronRunLogger) | **Risk**: Low

---

## Config Schema Changes Summary

| Model | Field | Type | Default | Alias |
|-------|-------|------|---------|-------|
| AgentConfig | max_concurrent_tasks | int | 3 | maxConcurrentTasks |
| AgentConfig | cron_enabled | bool | True | cronEnabled |
| ToolsConfig | api_call_auth_profiles | dict[str, AuthProfileConfig] | {} | apiCallAuthProfiles |
| ToolsConfig | api_call_url_allowlist | list[str] | [] | apiCallUrlAllowlist |
| ToolsConfig | twitter_cli_path | str | "" | twitterCliPath |
| NEW AuthProfileConfig | profile_type | str | - | - |
| NEW AuthProfileConfig | value | str | - | - |

## PRD Update Requirements

1. Section 4.4: Add "4.4.4 Cron Task Architecture" (CronTaskStore, notification routing, session isolation, execution constraints, logging, enabled/disabled)
2. Section 4.7.1: Add new tools (api_call, twitter_read, web_snapshot x3, dashboard_export, cron_toggle, cron_history)
3. Section 4.10: Add 6 bot skills
4. Section 8: Add Phase 11 milestone
5. Section 4.3: Document metadata field on InboundMessage

## _ARCHITECTURE.md Updates

1. `orchestrator/_ARCHITECTURE.md` -- add cron_store.py, cron_context.py, cron_logger.py
2. `tools/_ARCHITECTURE.md` -- add api_call.py, twitter_read.py, web_snapshot.py, dashboard_export.py
3. `bus/_ARCHITECTURE.md` -- document metadata field
4. `config/_ARCHITECTURE.md` -- add AuthProfileConfig
5. `skills/_ARCHITECTURE.md` -- add 6 new skill files
6. Root `_ARCHITECTURE.md` -- update summary

## Execution Order

```
Phase 0a (CronTaskStore) ──┬── Phase 0b (Routing) ── Phase 0c (Session isolation)
                           ├── Phase 0h (Enabled/kill switch)
                           │
Phase 0d (Concurrency) ────┤   [independent]
Phase 0g (Per-tool chars) ─┤   [independent]
Phase 0i (Cron logger) ────┤   [independent]
Phase 0f (api_call) ───────┤   [independent]
                           │
                           └── Phase 0e (Constraints) ── Phase 0j (Restrictions)

Phase 0 complete ──┬── Phase 1 (Hot News) ← validate infrastructure
                   ├── Phase 2 (Competitor Monitor)
                   ├── Phase 3a → 3b (Cross-Platform Publishing)
                   ├── Phase 4 (SEO Articles)
                   ├── Phase 5 (X/Twitter) ← can start earlier, independent
                   └── Phase 6 (Dashboard) ← depends on 0i
```

## Risk Summary

| Phase | Risk | Key Concern |
|-------|------|------------|
| 0a | Medium | Refactor touches scheduler + 3 tools + app wiring |
| 0b | **High** | Core message routing change, must not break normal flow |
| 0c | Low | One-line change |
| 0d | Medium | Changes core message processing, approval flow interaction |
| 0e | Medium | Modifying agent_loop hot path |
| 0f | **High** | Security-sensitive: SSRF, credential management |
| 0g | Low | Additive, backward compatible |
| 0h | Low | Simple config + toggle |
| 0i | Low | New file, no existing code modified |
| 0j | Medium | Must ensure non-cron unaffected |
| 1-6 | Low-Medium | Mostly skill files + isolated new tools |

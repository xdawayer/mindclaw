# input: mindclaw.orchestrator.agent_loop, mindclaw.orchestrator.cron_context
# output: Cron DANGEROUS 工具审批绕过测试
# pos: 验证 cron 模式下 DANGEROUS 工具跳过审批但仍检查 allow_dangerous_tools 配置
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, MagicMock

import pytest

from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig, ToolsConfig
from mindclaw.orchestrator.agent_loop import AgentLoop
from mindclaw.orchestrator.cron_context import CronExecutionConstraints
from mindclaw.security.approval import ApprovalManager
from mindclaw.tools.base import RiskLevel, Tool
from mindclaw.tools.registry import ToolRegistry


class FakeDangerousTool(Tool):
    name = "fake_dangerous"
    description = "test dangerous tool"
    parameters = {"type": "object", "properties": {}}
    risk_level = RiskLevel.DANGEROUS

    async def execute(self, params: dict) -> str:
        return "dangerous result"


class FakeSafeTool(Tool):
    name = "fake_safe"
    description = "test safe tool"
    parameters = {"type": "object", "properties": {}}
    risk_level = RiskLevel.SAFE

    async def execute(self, params: dict) -> str:
        return "safe result"


@pytest.fixture
def config_allow_dangerous():
    return MindClawConfig(tools=ToolsConfig(allow_dangerous_tools=True))


@pytest.fixture
def config_deny_dangerous():
    return MindClawConfig(tools=ToolsConfig(allow_dangerous_tools=False))


@pytest.fixture
def approval_mock():
    approval = MagicMock(spec=ApprovalManager)
    approval.request_approval = AsyncMock(return_value=True)
    return approval


@pytest.fixture
def agent_loop_allow(config_allow_dangerous, approval_mock):
    from mindclaw.llm.router import LLMRouter
    bus = MessageBus()
    router = MagicMock(spec=LLMRouter)
    registry = ToolRegistry()
    registry.register(FakeDangerousTool())
    registry.register(FakeSafeTool())
    return AgentLoop(
        config=config_allow_dangerous,
        bus=bus,
        router=router,
        tool_registry=registry,
        approval_manager=approval_mock,
    )


@pytest.fixture
def agent_loop_deny(config_deny_dangerous, approval_mock):
    from mindclaw.llm.router import LLMRouter
    bus = MessageBus()
    router = MagicMock(spec=LLMRouter)
    registry = ToolRegistry()
    registry.register(FakeDangerousTool())
    registry.register(FakeSafeTool())
    return AgentLoop(
        config=config_deny_dangerous,
        bus=bus,
        router=router,
        tool_registry=registry,
        approval_manager=approval_mock,
    )


@pytest.mark.asyncio
async def test_cron_skips_approval_for_dangerous_tool(agent_loop_allow, approval_mock):
    """In cron mode with allow_dangerous_tools=True, DANGEROUS tool executes without
    approval_manager being called."""
    cron_constraints = CronExecutionConstraints()

    result = await agent_loop_allow._execute_tool(
        "fake_dangerous", "{}", "", "", cron_constraints=cron_constraints
    )

    assert result == "dangerous result"
    approval_mock.request_approval.assert_not_called()


@pytest.mark.asyncio
async def test_cron_still_blocks_if_allow_dangerous_disabled(agent_loop_deny):
    """In cron mode with allow_dangerous_tools=False, DANGEROUS tool returns config error."""
    cron_constraints = CronExecutionConstraints()

    result = await agent_loop_deny._execute_tool(
        "fake_dangerous", "{}", "", "", cron_constraints=cron_constraints
    )

    assert "requires" in result.lower() or "allowdangeroustools" in result.lower()
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_cron_still_blocks_tools_in_blocked_list(agent_loop_allow):
    """Even with cron_constraints active, tools listed in blocked_tools return a blocked error."""
    cron_constraints = CronExecutionConstraints(
        blocked_tools=frozenset({"fake_dangerous"})
    )

    result = await agent_loop_allow._execute_tool(
        "fake_dangerous", "{}", "", "", cron_constraints=cron_constraints
    )

    assert "not allowed" in result.lower() or "blocked" in result.lower()
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_normal_mode_still_requires_approval(agent_loop_allow, approval_mock):
    """Without cron_constraints (normal mode), DANGEROUS tool still calls approval_manager."""
    result = await agent_loop_allow._execute_tool(
        "fake_dangerous", "{}", "cli", "local", cron_constraints=None
    )

    assert result == "dangerous result"
    approval_mock.request_approval.assert_called_once()


@pytest.mark.asyncio
async def test_cron_safe_tool_unaffected(agent_loop_allow, approval_mock):
    """SAFE tools execute normally in cron mode without any approval flow."""
    cron_constraints = CronExecutionConstraints()

    result = await agent_loop_allow._execute_tool(
        "fake_safe", "{}", "", "", cron_constraints=cron_constraints
    )

    assert result == "safe result"
    approval_mock.request_approval.assert_not_called()

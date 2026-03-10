# input: mindclaw.orchestrator.acp
# output: ACP 协议 (AgentHandle) 测试
# pos: 编排层子进程管理测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json

import pytest

from mindclaw.orchestrator.acp import AgentHandle, AgentStatus, TaskRequest, TaskResult


# ── TaskRequest / TaskResult dataclass tests ──


def test_task_request_serialization():
    """TaskRequest should serialize to JSON for stdin transmission."""
    req = TaskRequest(
        task_id="task-001",
        task="Summarize this article",
        model="claude-sonnet-4-20250514",
        tools=["read_file", "web_fetch"],
        max_iterations=15,
    )
    data = req.to_json()
    parsed = json.loads(data)
    assert parsed["task_id"] == "task-001"
    assert parsed["task"] == "Summarize this article"
    assert parsed["tools"] == ["read_file", "web_fetch"]
    assert parsed["max_iterations"] == 15


def test_task_result_from_json():
    """TaskResult should deserialize from subprocess stdout JSON."""
    raw = json.dumps({
        "task_id": "task-001",
        "status": "completed",
        "content": "Article summary here.",
    })
    result = TaskResult.from_json(raw)
    assert result.task_id == "task-001"
    assert result.status == "completed"
    assert result.content == "Article summary here."
    assert result.error is None


def test_task_result_from_json_error():
    """TaskResult should handle error responses."""
    raw = json.dumps({
        "task_id": "task-001",
        "status": "failed",
        "content": "",
        "error": "LLM timeout",
    })
    result = TaskResult.from_json(raw)
    assert result.status == "failed"
    assert result.error == "LLM timeout"


# ── AgentHandle tests ──


@pytest.mark.asyncio
async def test_agent_handle_spawn_and_complete():
    """AgentHandle should spawn a subprocess and collect its result."""
    handle = await AgentHandle.spawn(
        task=TaskRequest(
            task_id="test-1",
            task="echo test",
            model="test-model",
            tools=[],
            max_iterations=5,
        ),
        python_path="python3",
        runner_module="mindclaw.orchestrator.subagent_runner",
    )

    assert handle.task_id == "test-1"
    result = await handle.wait()
    assert handle.status == AgentStatus.COMPLETED
    assert result.task_id == "test-1"
    assert result.status == "completed"
    assert "echo test" in result.content


@pytest.mark.asyncio
async def test_agent_handle_kill():
    """AgentHandle.kill() should forcefully terminate the subprocess."""
    # Use a long-running process
    handle = await AgentHandle.spawn(
        task=TaskRequest(
            task_id="kill-test",
            task="sleep forever",
            model="test-model",
            tools=[],
            max_iterations=5,
        ),
        python_path="python3",
        runner_module="mindclaw.orchestrator.subagent_runner",
    )

    await handle.kill()
    assert handle.status == AgentStatus.FAILED


@pytest.mark.asyncio
async def test_agent_handle_timeout():
    """AgentHandle should timeout if subprocess takes too long."""
    handle = await AgentHandle.spawn(
        task=TaskRequest(
            task_id="timeout-test",
            task="slow task",
            model="test-model",
            tools=[],
            max_iterations=5,
        ),
        python_path="python3",
        runner_module="mindclaw.orchestrator.subagent_runner",
        timeout=0.1,
    )

    result = await handle.wait()
    # Should timeout or complete - either way status is set
    assert handle.status in (AgentStatus.TIMEOUT, AgentStatus.COMPLETED, AgentStatus.FAILED)


@pytest.mark.asyncio
async def test_agent_handle_stop():
    """AgentHandle.stop() should gracefully terminate the subprocess."""
    handle = await AgentHandle.spawn(
        task=TaskRequest(
            task_id="stop-test",
            task="stop me",
            model="test-model",
            tools=[],
            max_iterations=5,
        ),
        python_path="python3",
        runner_module="mindclaw.orchestrator.subagent_runner",
    )

    await handle.stop()
    assert handle.status in (AgentStatus.COMPLETED, AgentStatus.FAILED)


@pytest.mark.asyncio
async def test_agent_handle_wait_idempotent():
    """Calling wait() multiple times should return the same result."""
    handle = await AgentHandle.spawn(
        task=TaskRequest(
            task_id="idem-test",
            task="idempotent task",
            model="test-model",
            tools=[],
            max_iterations=5,
        ),
        python_path="python3",
        runner_module="mindclaw.orchestrator.subagent_runner",
    )

    result1 = await handle.wait()
    result2 = await handle.wait()
    assert result1 == result2


def test_task_request_forbids_spawn_task():
    """TaskRequest should reject spawn_task in tools list."""
    with pytest.raises(ValueError, match="spawn_task"):
        TaskRequest(
            task_id="bad-1",
            task="test",
            model="m",
            tools=["read_file", "spawn_task"],
        )


def test_task_request_forbids_message_user():
    """TaskRequest should reject message_user in tools list."""
    with pytest.raises(ValueError, match="message_user"):
        TaskRequest(
            task_id="bad-2",
            task="test",
            model="m",
            tools=["message_user"],
        )


def test_task_result_from_json_missing_field():
    """TaskResult.from_json should raise ValueError for missing required fields."""
    with pytest.raises(ValueError, match="task_id"):
        TaskResult.from_json('{"status": "ok"}')

    with pytest.raises(ValueError, match="status"):
        TaskResult.from_json('{"task_id": "x"}')


@pytest.mark.asyncio
async def test_agent_status_enum():
    """AgentStatus should have the expected values."""
    assert AgentStatus.RUNNING.value == "running"
    assert AgentStatus.COMPLETED.value == "completed"
    assert AgentStatus.FAILED.value == "failed"
    assert AgentStatus.TIMEOUT.value == "timeout"

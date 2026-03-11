# input: mindclaw.tools.twitter_read
# output: TwitterReadTool 测试
# pos: X/Twitter 读取工具 (子进程执行/Shell注入防护/超时/参数验证) 测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_tool(cli_path: str = "/usr/local/bin/twitter-cli"):
    from mindclaw.tools.twitter_read import TwitterReadTool

    return TwitterReadTool(cli_path=cli_path)


def _mock_proc(stdout: bytes = b"timeline output", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    proc.returncode = returncode
    return proc


# ── Risk level ─────────────────────────────────────────────────────────────


def test_risk_level_moderate():
    from mindclaw.tools.base import RiskLevel

    tool = _make_tool()
    assert tool.risk_level == RiskLevel.MODERATE


# ── Timeline action ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeline_action():
    """Timeline action calls CLI with correct args; no --query flag."""
    tool = _make_tool(cli_path="/usr/local/bin/twitter-cli")
    mock_proc = _mock_proc(stdout=b"tweet1\ntweet2")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await tool.execute({"action": "timeline", "count": 5})

    mock_exec.assert_called_once()
    call_args = mock_exec.call_args.args
    assert call_args[0] == "/usr/local/bin/twitter-cli"
    assert call_args[1] == "timeline"
    assert "--count" in call_args
    assert "5" in call_args
    # No --query for timeline
    assert "--query" not in call_args
    assert "tweet1" in result


# ── Search action ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_action():
    """Search action passes --query flag with the given query string."""
    tool = _make_tool()
    mock_proc = _mock_proc(stdout=b"search result")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await tool.execute({"action": "search", "query": "python"})

    call_args = mock_exec.call_args.args
    assert "search" in call_args
    assert "--query" in call_args
    query_idx = list(call_args).index("--query")
    assert call_args[query_idx + 1] == "python"
    assert "search result" in result


# ── User action ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_action():
    """User action passes --query flag with the username."""
    tool = _make_tool()
    mock_proc = _mock_proc(stdout=b"user posts here")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await tool.execute({"action": "user", "query": "elonmusk"})

    call_args = mock_exec.call_args.args
    assert "user" in call_args
    assert "--query" in call_args
    query_idx = list(call_args).index("--query")
    assert call_args[query_idx + 1] == "elonmusk"
    assert "user posts here" in result


# ── Shell metacharacter rejection ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_rejects_shell_metacharacters():
    """Query containing semicolon (command injection attempt) is rejected."""
    tool = _make_tool()

    result = await tool.execute({"action": "search", "query": "test; rm -rf /"})

    assert "error" in result.lower() or "invalid" in result.lower()
    # Subprocess must NOT be called
    # (if subprocess were called the mock would need to be set up)


@pytest.mark.asyncio
async def test_rejects_pipe_in_query():
    """Query containing pipe character is rejected without calling subprocess."""
    tool = _make_tool()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        result = await tool.execute({"action": "search", "query": "test | cat /etc/passwd"})

    mock_exec.assert_not_called()
    assert "error" in result.lower() or "invalid" in result.lower()


@pytest.mark.asyncio
async def test_rejects_backtick_in_query():
    """Query containing backtick (command substitution) is rejected."""
    tool = _make_tool()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        result = await tool.execute({"action": "search", "query": "test`whoami`"})

    mock_exec.assert_not_called()
    assert "error" in result.lower() or "invalid" in result.lower()


@pytest.mark.asyncio
async def test_rejects_dollar_in_query():
    """Query containing $ (variable expansion) is rejected."""
    tool = _make_tool()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        result = await tool.execute({"action": "search", "query": "test$HOME"})

    mock_exec.assert_not_called()
    assert "error" in result.lower() or "invalid" in result.lower()


# ── Count capping ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_count_capped_at_50():
    """count=100 is silently capped to 50 in the subprocess call."""
    tool = _make_tool()
    mock_proc = _mock_proc()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await tool.execute({"action": "timeline", "count": 100})

    call_args = mock_exec.call_args.args
    count_idx = list(call_args).index("--count")
    assert call_args[count_idx + 1] == "50"


@pytest.mark.asyncio
async def test_default_count():
    """When count is omitted, the CLI receives --count 10."""
    tool = _make_tool()
    mock_proc = _mock_proc()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await tool.execute({"action": "timeline"})

    call_args = mock_exec.call_args.args
    count_idx = list(call_args).index("--count")
    assert call_args[count_idx + 1] == "10"


# ── Timeout ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subprocess_timeout():
    """When the subprocess times out, a timeout error message is returned."""
    import asyncio

    tool = _make_tool()

    mock_proc = AsyncMock()
    # First call raises TimeoutError; second call (in cleanup) succeeds
    mock_proc.communicate = AsyncMock(
        side_effect=[asyncio.TimeoutError(), (b"", b"")]
    )
    mock_proc.kill = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await tool.execute({"action": "timeline"})

    assert "timeout" in result.lower() or "timed out" in result.lower()


# ── Missing CLI binary ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_cli_path():
    """Empty cli_path returns a helpful configuration error without crashing."""
    tool = _make_tool(cli_path="")

    result = await tool.execute({"action": "timeline"})

    assert "error" in result.lower() or "cli" in result.lower() or "path" in result.lower()


@pytest.mark.asyncio
async def test_cli_not_found():
    """FileNotFoundError from subprocess returns a helpful error message."""
    tool = _make_tool(cli_path="/nonexistent/twitter-cli")

    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("not found")):
        result = await tool.execute({"action": "timeline"})

    assert "error" in result.lower() or "not found" in result.lower()


# ── No shell=True ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uses_exec_not_shell():
    """create_subprocess_exec is used (not shell=True) to prevent shell injection."""
    tool = _make_tool()
    mock_proc = _mock_proc()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        await tool.execute({"action": "timeline"})

    mock_exec.assert_called_once()
    # Verify shell=True was NOT passed in kwargs
    call_kwargs = mock_exec.call_args.kwargs if mock_exec.call_args.kwargs else {}
    assert call_kwargs.get("shell") is not True


# ── Query required for search/user ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_requires_query():
    """Search action without a query param returns an error."""
    tool = _make_tool()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        result = await tool.execute({"action": "search"})

    mock_exec.assert_not_called()
    assert "error" in result.lower() or "query" in result.lower()


@pytest.mark.asyncio
async def test_user_requires_query():
    """User action without a query param returns an error."""
    tool = _make_tool()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        result = await tool.execute({"action": "user"})

    mock_exec.assert_not_called()
    assert "error" in result.lower() or "query" in result.lower()


# ── Result truncation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_truncated_at_max_chars():
    """Output exceeding max_result_chars (5000) is truncated."""
    tool = _make_tool()
    long_output = b"x" * 10_000
    mock_proc = _mock_proc(stdout=long_output)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await tool.execute({"action": "timeline"})

    assert len(result) <= 5100  # Allow small overhead for truncation marker
    assert "truncated" in result.lower() or len(result) == 5000


# ── Correct tool metadata ────────────────────────────────────────────────────


def test_tool_name():
    tool = _make_tool()
    assert tool.name == "twitter_read"


def test_tool_max_result_chars():
    tool = _make_tool()
    assert tool.max_result_chars == 5000


def test_tool_has_parameters_schema():
    tool = _make_tool()
    assert "action" in tool.parameters.get("properties", {})
    assert "count" in tool.parameters.get("properties", {})


# ── Stderr included in output ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stderr_logged_not_returned():
    """Stderr content is logged but NOT returned to caller (credential safety)."""
    tool = _make_tool()
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(b"main output", b"warning: rate limited"))
    proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await tool.execute({"action": "timeline"})

    assert "main output" in result
    assert "rate limited" not in result


@pytest.mark.asyncio
async def test_stderr_only_when_no_stdout():
    """When stdout is empty and stderr has content, return a safe error message."""
    tool = _make_tool()
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(b"", b"fatal error occurred"))
    proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await tool.execute({"action": "timeline"})

    assert "error" in result.lower()
    assert "fatal error occurred" not in result


# ── Generic exception path ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generic_exception_returns_error():
    """Any unexpected exception from subprocess is caught and returned as error."""
    tool = _make_tool()

    with patch("asyncio.create_subprocess_exec", side_effect=PermissionError("access denied")):
        result = await tool.execute({"action": "timeline"})

    assert "error" in result.lower()

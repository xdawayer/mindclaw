# input: mindclaw.orchestrator.cron_context
# output: CronExecutionConstraints 解析和约束测试
# pos: 验证 cron 执行约束的解析、默认值和阻止工具逻辑
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

def test_parse_default_constraints():
    """parse_cron_constraints with empty metadata should return defaults."""
    from mindclaw.orchestrator.cron_context import parse_cron_constraints

    constraints = parse_cron_constraints({})

    assert constraints.max_iterations == 15
    assert constraints.timeout_seconds == 300
    assert "exec" in constraints.blocked_tools
    assert "spawn_task" in constraints.blocked_tools
    assert constraints.allowed_tools is None
    assert constraints.notify_on_failure is True


def test_parse_custom_constraints():
    """parse_cron_constraints should respect explicit values."""
    from mindclaw.orchestrator.cron_context import parse_cron_constraints

    metadata = {
        "max_iterations": 25,
        "timeout": 600,
    }
    constraints = parse_cron_constraints(metadata)

    assert constraints.max_iterations == 25
    assert constraints.timeout_seconds == 600


def test_parse_constraints_clamps_max_iterations():
    """max_iterations should be clamped to a reasonable range."""
    from mindclaw.orchestrator.cron_context import parse_cron_constraints

    # Too high
    constraints = parse_cron_constraints({"max_iterations": 1000})
    assert constraints.max_iterations <= 100

    # Too low
    constraints = parse_cron_constraints({"max_iterations": 0})
    assert constraints.max_iterations >= 1


def test_parse_constraints_clamps_timeout():
    """timeout_seconds should be clamped to a reasonable range."""
    from mindclaw.orchestrator.cron_context import parse_cron_constraints

    # Too high
    constraints = parse_cron_constraints({"timeout": 100000})
    assert constraints.timeout_seconds <= 3600

    # Too low
    constraints = parse_cron_constraints({"timeout": 0})
    assert constraints.timeout_seconds >= 10


def test_is_tool_blocked():
    """is_tool_blocked should check blocked_tools set."""
    from mindclaw.orchestrator.cron_context import CronExecutionConstraints

    constraints = CronExecutionConstraints(
        blocked_tools=frozenset({"exec", "spawn_task"}),
    )

    assert constraints.is_tool_blocked("exec") is True
    assert constraints.is_tool_blocked("spawn_task") is True
    assert constraints.is_tool_blocked("web_search") is False
    assert constraints.is_tool_blocked("read_file") is False


def test_is_tool_blocked_with_allowed_list():
    """When allowed_tools is set, only those tools should be permitted."""
    from mindclaw.orchestrator.cron_context import CronExecutionConstraints

    constraints = CronExecutionConstraints(
        allowed_tools=frozenset({"web_search", "web_fetch", "message_user"}),
        blocked_tools=frozenset(),
    )

    assert constraints.is_tool_blocked("web_search") is False
    assert constraints.is_tool_blocked("exec") is True
    assert constraints.is_tool_blocked("read_file") is True


def test_not_cron_metadata():
    """parse_cron_constraints should return None for non-cron metadata."""
    from mindclaw.orchestrator.cron_context import parse_cron_constraints_if_cron

    # Non-cron message
    result = parse_cron_constraints_if_cron(
        channel="telegram", user_id="user123", metadata={}
    )
    assert result is None

    # Cron message
    result = parse_cron_constraints_if_cron(
        channel="system", user_id="cron", metadata={}
    )
    assert result is not None
    assert result.max_iterations == 15

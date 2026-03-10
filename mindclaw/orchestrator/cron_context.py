# input: (none)
# output: 导出 CronExecutionConstraints, parse_cron_constraints, parse_cron_constraints_if_cron
# pos: Cron 执行约束定义，限制无人值守任务的迭代、超时和工具访问
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Cron execution constraints for unattended task safety."""

from __future__ import annotations

from dataclasses import dataclass, field

# Hard limits to prevent misconfiguration
_MAX_ITERATIONS_UPPER = 100
_MAX_ITERATIONS_LOWER = 1
_TIMEOUT_UPPER = 3600  # 1 hour
_TIMEOUT_LOWER = 10  # 10 seconds

_DEFAULT_BLOCKED_TOOLS = frozenset({"exec", "spawn_task"})


@dataclass(frozen=True)
class CronExecutionConstraints:
    """Constraints applied to cron-triggered agent loop execution."""

    max_iterations: int = 15
    timeout_seconds: int = 300
    allowed_tools: frozenset[str] | None = None
    blocked_tools: frozenset[str] = field(default_factory=lambda: _DEFAULT_BLOCKED_TOOLS)
    notify_on_failure: bool = True

    def is_tool_blocked(self, tool_name: str) -> bool:
        """Check if a tool is blocked by constraints."""
        if self.allowed_tools is not None:
            return tool_name not in self.allowed_tools
        return tool_name in self.blocked_tools


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def parse_cron_constraints(metadata: dict) -> CronExecutionConstraints:
    """Parse cron execution constraints from inbound message metadata."""
    max_iterations = _clamp(
        metadata.get("max_iterations", 15),
        _MAX_ITERATIONS_LOWER,
        _MAX_ITERATIONS_UPPER,
    )
    timeout_seconds = _clamp(
        metadata.get("timeout", 300),
        _TIMEOUT_LOWER,
        _TIMEOUT_UPPER,
    )

    return CronExecutionConstraints(
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
    )


def parse_cron_constraints_if_cron(
    channel: str, user_id: str, metadata: dict
) -> CronExecutionConstraints | None:
    """Parse constraints only if the message is from the cron system.

    Returns None for non-cron messages.
    """
    if channel == "system" and user_id == "cron":
        return parse_cron_constraints(metadata)
    return None

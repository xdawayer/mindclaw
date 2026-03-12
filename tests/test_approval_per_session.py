# input: mindclaw/security/approval.py, mindclaw/bus/events.py
# output: tests for per-session approval blocking behavior
# pos: regression tests ensuring approval blocking is scoped to the requesting session only

"""Tests for per-session approval tracking.

Bug: When a DANGEROUS tool triggers an approval request, ALL messages from ALL
channels/users are dropped until the approval is resolved. The correct behavior
is to only block messages from the session (channel+chat_id) that triggered the
approval. Other sessions should continue to work normally.
"""

import asyncio

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.security.approval import ApprovalManager


def make_msg(channel: str, chat_id: str, text: str = "hello") -> InboundMessage:
    return InboundMessage(
        channel=channel,
        chat_id=chat_id,
        user_id="user1",
        username="testuser",
        text=text,
    )


# ---------------------------------------------------------------------------
# Unit tests: ApprovalManager.has_pending(session_key=...)
# ---------------------------------------------------------------------------


class TestHasPendingPerSession:
    """has_pending() with a session_key argument only returns True for the
    session that has an outstanding approval request."""

    @pytest.fixture
    def bus(self):
        return MessageBus()

    @pytest.fixture
    def manager(self, bus):
        return ApprovalManager(bus=bus, timeout=300.0)

    def test_has_pending_false_when_no_requests(self, manager):
        assert manager.has_pending() is False
        assert manager.has_pending(session_key="telegram:chat1") is False

    @pytest.mark.asyncio
    async def test_has_pending_true_globally_while_request_outstanding(self, bus, manager):
        """Global has_pending() is True when any session has an outstanding request."""
        task = asyncio.create_task(
            manager.request_approval("rm_file", '{"path":"/tmp/x"}', "telegram", "chat1")
        )
        # Give the coroutine a moment to register the pending request
        await asyncio.sleep(0)

        assert manager.has_pending() is True

        # Clean up: reject so the task finishes
        manager.resolve("no")
        await task

    @pytest.mark.asyncio
    async def test_has_pending_true_for_requesting_session(self, bus, manager):
        """has_pending(session_key) is True for the session that requested approval."""
        task = asyncio.create_task(
            manager.request_approval("rm_file", '{"path":"/tmp/x"}', "telegram", "chat1")
        )
        await asyncio.sleep(0)

        assert manager.has_pending(session_key="telegram:chat1") is True

        manager.resolve("no")
        await task

    @pytest.mark.asyncio
    async def test_has_pending_false_for_other_session(self, bus, manager):
        """has_pending(session_key) is False for sessions that did NOT trigger
        the approval — this is the core regression check."""
        task = asyncio.create_task(
            manager.request_approval("rm_file", '{"path":"/tmp/x"}', "telegram", "chat1")
        )
        await asyncio.sleep(0)

        # Different channel, different chat_id — should NOT be blocked
        assert manager.has_pending(session_key="slack:workspace_general") is False
        # Same channel, different chat_id — should NOT be blocked
        assert manager.has_pending(session_key="telegram:chat2") is False
        # Different channel, same chat_id — should NOT be blocked
        assert manager.has_pending(session_key="slack:chat1") is False

        manager.resolve("no")
        await task

    @pytest.mark.asyncio
    async def test_has_pending_clears_after_resolution(self, bus, manager):
        """After the approval is resolved, has_pending() returns False for all sessions."""
        task = asyncio.create_task(
            manager.request_approval("rm_file", '{"path":"/tmp/x"}', "telegram", "chat1")
        )
        await asyncio.sleep(0)
        manager.resolve("yes")
        await task

        assert manager.has_pending() is False
        assert manager.has_pending(session_key="telegram:chat1") is False


# ---------------------------------------------------------------------------
# Integration test: message router logic (simulated)
# ---------------------------------------------------------------------------


class TestMessageRouterPerSessionBlocking:
    """Simulate the _message_router logic to verify that only the requesting
    session is blocked while other sessions pass through normally."""

    @pytest.fixture
    def bus(self):
        return MessageBus()

    @pytest.fixture
    def manager(self, bus):
        return ApprovalManager(bus=bus, timeout=300.0)

    def _should_block(self, manager: ApprovalManager, msg: InboundMessage) -> bool:
        """Replicate the intended _message_router blocking logic.

        Returns True if the message should be blocked (dropped), False if it
        should be forwarded to the orchestrator.

        This mirrors the FIXED logic (not the current buggy logic):
          - If this session has a pending approval AND the message is not an
            approval reply → block.
          - If this session has a pending approval AND the message IS an approval
            reply → do NOT block (caller handles resolve).
          - If another session has a pending approval → do NOT block.
        """
        session_key = msg.session_key
        if manager.has_pending(session_key=session_key):
            if manager.is_approval_reply(msg.text, channel=msg.channel, chat_id=msg.chat_id):
                return False  # Let the router intercept and resolve
            return True  # Block non-approval messages from the same session
        return False  # Other sessions are unaffected

    @pytest.mark.asyncio
    async def test_other_session_not_blocked_during_pending_approval(self, bus, manager):
        """BUG REPRODUCTION: message from another session must NOT be blocked
        when a different session has a pending approval."""
        approval_task = asyncio.create_task(
            manager.request_approval("rm_file", '{"path":"/tmp/x"}', "telegram", "chat1")
        )
        await asyncio.sleep(0)

        # Message from a completely different session
        other_session_msg = make_msg("slack", "workspace_general", "What is 2+2?")
        assert self._should_block(manager, other_session_msg) is False, (
            "Message from another session should NOT be blocked during another session's approval"
        )

        manager.resolve("no")
        await approval_task

    @pytest.mark.asyncio
    async def test_same_session_blocked_during_pending_approval(self, bus, manager):
        """Messages from the requesting session must still be blocked."""
        approval_task = asyncio.create_task(
            manager.request_approval("rm_file", '{"path":"/tmp/x"}', "telegram", "chat1")
        )
        await asyncio.sleep(0)

        same_session_non_approval = make_msg("telegram", "chat1", "What is 2+2?")
        assert self._should_block(manager, same_session_non_approval) is True, (
            "Non-approval message from the requesting session MUST be blocked"
        )

        manager.resolve("no")
        await approval_task

    @pytest.mark.asyncio
    async def test_approval_reply_from_same_session_not_blocked(self, bus, manager):
        """Approval reply messages from the requesting session must pass through
        (they are consumed by the approval interception step, not blocked)."""
        approval_task = asyncio.create_task(
            manager.request_approval("rm_file", '{"path":"/tmp/x"}', "telegram", "chat1")
        )
        await asyncio.sleep(0)

        approval_reply = make_msg("telegram", "chat1", "yes")
        # _should_block returns False because is_approval_reply is True for this message
        assert self._should_block(manager, approval_reply) is False

        manager.resolve("yes")
        await approval_task

    @pytest.mark.asyncio
    async def test_multiple_independent_sessions_unaffected(self, bus, manager):
        """Multiple unrelated sessions should all pass through freely."""
        approval_task = asyncio.create_task(
            manager.request_approval("exec_shell", "rm -rf /tmp", "telegram", "private_chat")
        )
        await asyncio.sleep(0)

        sessions = [
            make_msg("slack", "general", "ping"),
            make_msg("discord", "server123", "hello"),
            make_msg("telegram", "group456", "test"),
            make_msg("cli", "local", "status"),
        ]
        for msg in sessions:
            assert self._should_block(manager, msg) is False, (
                f"Session {msg.session_key} should not be blocked"
            )

        manager.resolve("no")
        await approval_task

    @pytest.mark.asyncio
    async def test_no_sessions_blocked_when_no_pending_approval(self, manager):
        """With no pending approvals, nothing is blocked."""
        messages = [
            make_msg("telegram", "chat1", "hello"),
            make_msg("slack", "general", "world"),
        ]
        for msg in messages:
            assert self._should_block(manager, msg) is False

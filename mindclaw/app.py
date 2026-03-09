# input: config/schema.py, bus/queue.py, channels/manager.py, orchestrator/agent_loop.py,
#        orchestrator/subagent.py, security/approval.py, knowledge/session.py,
#        knowledge/memory.py, orchestrator/context.py, llm/router.py, tools/*, gateway/*
# output: 导出 MindClawApp
# pos: 顶层编排器，统一管理所有组件的生命周期和消息路由
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import secrets
from pathlib import Path

from loguru import logger

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.channels.cli_channel import CLIChannel
from mindclaw.channels.manager import ChannelManager
from mindclaw.config.schema import MindClawConfig
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.llm.router import LLMRouter
from mindclaw.orchestrator.agent_loop import AgentLoop
from mindclaw.orchestrator.context import ContextBuilder
from mindclaw.orchestrator.subagent import SubAgentManager
from mindclaw.security.approval import ApprovalManager
from mindclaw.tools.file_ops import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from mindclaw.tools.message_user import MessageUserTool
from mindclaw.tools.registry import ToolRegistry
from mindclaw.tools.shell import ExecTool
from mindclaw.tools.spawn_task import SpawnTaskTool
from mindclaw.tools.web import WebFetchTool, WebSearchTool


class MindClawApp:
    """Top-level orchestrator that wires all components together."""

    def __init__(self, config: MindClawConfig) -> None:
        self.config = config
        self.bus = MessageBus()
        self.router = LLMRouter(config)
        self.channel_manager = ChannelManager(self.bus)
        self.tool_registry = ToolRegistry()

        data_dir = Path(config.knowledge.data_dir)
        self.session_store = SessionStore(data_dir=data_dir)
        self.memory_manager = MemoryManager(
            data_dir=data_dir,
            router=self.router,
            config=config,
        )
        self.context_builder = ContextBuilder(memory_manager=self.memory_manager)

        self.approval_manager = ApprovalManager(
            bus=self.bus,
            timeout=config.security.approval_timeout,
        )

        self.subagent_manager = SubAgentManager(config=config)

        self.agent_loop = AgentLoop(
            config=config,
            bus=self.bus,
            router=self.router,
            tool_registry=self.tool_registry,
            approval_manager=self.approval_manager,
            session_store=self.session_store,
            memory_manager=self.memory_manager,
            context_builder=self.context_builder,
        )

        self._gateway_auth = None
        self._agent_task: asyncio.Task | None = None

    # ── Tool registration ─────────────────────────────────────

    def _register_tools(self) -> None:
        workspace = Path.cwd()
        self.tool_registry.register(ReadFileTool(workspace=workspace))
        self.tool_registry.register(WriteFileTool(workspace=workspace))
        self.tool_registry.register(EditFileTool(workspace=workspace))
        self.tool_registry.register(ListDirTool(workspace=workspace))
        self.tool_registry.register(
            ExecTool(workspace=workspace, timeout=self.config.tools.exec_timeout)
        )
        self.tool_registry.register(WebFetchTool())

        brave_settings = self.config.providers.get("brave")
        if brave_settings and brave_settings.api_key:
            self.tool_registry.register(WebSearchTool(api_key=brave_settings.api_key))

        self.tool_registry.register(MessageUserTool(
            bus=self.bus,
            context_provider=lambda: (
                self.agent_loop._current_channel,
                self.agent_loop._current_chat_id,
            ),
        ))
        self.tool_registry.register(SpawnTaskTool(manager=self.subagent_manager))

    # ── Channel setup ─────────────────────────────────────────

    def _setup_channels(self, channel_names: list[str]) -> None:
        for name in channel_names:
            if name == "cli":
                self.channel_manager.register(CLIChannel(bus=self.bus))
            elif name == "gateway":
                self._setup_gateway()
            elif name == "telegram":
                self._setup_telegram()
            else:
                logger.warning(f"Unknown channel: {name}")

    def _setup_gateway(self) -> None:
        from mindclaw.gateway.auth import GatewayAuthManager
        from mindclaw.gateway.channel import GatewayChannel
        from mindclaw.gateway.server import GatewayServer

        data_dir = Path(self.config.knowledge.data_dir)
        token = self.config.gateway.token
        if not token:
            token_path = data_dir / "gateway_token"
            if token_path.exists():
                token = token_path.read_text().strip()
            else:
                token = secrets.token_urlsafe(32)
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(token)
                token_path.chmod(0o600)
                logger.info(f"Generated gateway token saved to {token_path}")

        self._gateway_auth = GatewayAuthManager(
            token=token,
            paired_devices_path=data_dir / "paired_devices.json",
        )

        async def on_gateway_message(device_id: str, text: str) -> None:
            await self.bus.put_inbound(
                InboundMessage(
                    channel="gateway",
                    chat_id=device_id,
                    user_id=device_id,
                    username=device_id,
                    text=text,
                )
            )

        server = GatewayServer(
            host=self.config.gateway.host,
            port=self.config.gateway.port,
            auth_manager=self._gateway_auth,
            on_message=on_gateway_message,
        )
        self.channel_manager.register(GatewayChannel(bus=self.bus, server=server))

    def _setup_telegram(self) -> None:
        from mindclaw.channels.telegram import TelegramChannel

        tg_config = self.config.channels.get("telegram")
        if not tg_config or not tg_config.token:
            logger.warning("Telegram channel configured but no token provided, skipping")
            return

        self.channel_manager.register(
            TelegramChannel(
                bus=self.bus,
                token=tg_config.token,
                allow_from=tg_config.allow_from or None,
                allow_groups=tg_config.allow_groups,
            )
        )

    # ── Message routing ───────────────────────────────────────

    async def _process_message(self, msg: InboundMessage) -> None:
        try:
            await self.agent_loop.handle_message(msg)
        except Exception:
            logger.exception("Agent error")
            await self.bus.put_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    text="An internal error occurred. Please try again.",
                )
            )

    async def _message_router(self) -> None:
        while True:
            msg = await self.bus.get_inbound()

            # 1. Pairing reply interception
            if self._gateway_auth and self._gateway_auth.is_pairing_reply(msg.text):
                self._gateway_auth.handle_pairing_reply(msg.text)
                continue

            # 2. Approval reply interception (must match channel + chat_id)
            if self.approval_manager.has_pending() and self.approval_manager.is_approval_reply(
                msg.text, channel=msg.channel, chat_id=msg.chat_id
            ):
                self.approval_manager.resolve(msg.text)
                continue

            # 3. Drop non-approval messages during pending approval
            if self.approval_manager.has_pending():
                logger.debug(f"Ignoring message during pending approval: {msg.text[:50]}")
                continue

            # 4. Wait for previous agent task
            if self._agent_task is not None and not self._agent_task.done():
                try:
                    await self._agent_task
                except Exception:
                    pass

            self._agent_task = asyncio.create_task(self._process_message(msg))

    async def _outbound_router(self) -> None:
        while True:
            msg = await self.bus.get_outbound()
            await self.channel_manager.dispatch_outbound(msg)

    # ── Lifecycle ─────────────────────────────────────────────

    async def run(self, channel_names: list[str]) -> None:
        # Configure loguru
        logger.remove()
        logger.add(
            self.config.log.file,
            level=self.config.log.level,
            rotation=self.config.log.rotation,
            retention=self.config.log.retention,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
        )

        self._register_tools()
        self._setup_channels(channel_names)

        tasks = [
            asyncio.create_task(self.channel_manager.start_all()),
            asyncio.create_task(self._message_router()),
            asyncio.create_task(self._outbound_router()),
        ]

        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            if self._agent_task and not self._agent_task.done():
                self._agent_task.cancel()
                try:
                    await self._agent_task
                except asyncio.CancelledError:
                    pass
            await self.channel_manager.stop_all()

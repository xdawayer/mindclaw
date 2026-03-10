# input: config/schema.py, bus/queue.py, channels/manager.py, orchestrator/agent_loop.py,
#        orchestrator/subagent.py, security/approval.py, knowledge/session.py,
#        knowledge/memory.py, knowledge/vector.py, orchestrator/context.py, llm/router.py,
#        tools/*, gateway/*, plugins/loader.py, plugins/hooks.py,
#        skills/installer.py, skills/index_client.py
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
from mindclaw.health.check import HealthCheckServer, HealthMonitor
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.knowledge.vector import VectorStore
from mindclaw.llm.router import LLMRouter
from mindclaw.orchestrator.agent_loop import AgentLoop
from mindclaw.orchestrator.context import ContextBuilder
from mindclaw.orchestrator.cron_scheduler import CronScheduler
from mindclaw.orchestrator.subagent import SubAgentManager
from mindclaw.plugins.hooks import HookRegistry
from mindclaw.plugins.loader import PluginLoader
from mindclaw.security.approval import ApprovalManager
from mindclaw.skills.index_client import IndexClient
from mindclaw.skills.installer import SkillInstaller
from mindclaw.skills.registry import SkillRegistry
from mindclaw.tools.cron import CronAddTool, CronListTool, CronRemoveTool
from mindclaw.tools.file_ops import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from mindclaw.tools.memory import MemorySaveTool, MemorySearchTool
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

        # Initialize OAuth if any provider uses it
        self._oauth_manager = self._init_oauth(config)
        self.router = LLMRouter(config, oauth_manager=self._oauth_manager)
        self.channel_manager = ChannelManager(self.bus)
        self.tool_registry = ToolRegistry()
        self.hook_registry = HookRegistry()
        self._plugins_dir = Path("plugins")

        data_dir = Path(config.knowledge.data_dir)
        self.session_store = SessionStore(data_dir=data_dir)

        # Vector store (optional)
        self.vector_store: VectorStore | None = None
        if config.knowledge.vector_db.enabled:
            self.vector_store = VectorStore(
                data_dir=data_dir,
                config=config.knowledge.vector_db,
                router=self.router,
            )

        self.memory_manager = MemoryManager(
            data_dir=data_dir,
            router=self.router,
            config=config,
            vector_store=self.vector_store,
        )

        # Skills
        self.skill_registry = SkillRegistry([
            Path(__file__).parent / "skills",  # builtin
            data_dir / "plugins" / "skills",   # project
            data_dir / "skills",               # user
        ])

        self.skill_index_client = IndexClient(
            index_url=config.skills.index_url,
            cache_dir=data_dir,
            cache_ttl=config.skills.cache_ttl,
        )
        self.skill_installer = SkillInstaller(
            user_skills_dir=data_dir / "skills",
            registry=self.skill_registry,
            index_client=self.skill_index_client,
            max_skill_size=config.skills.max_skill_size,
        )

        self.context_builder = ContextBuilder(
            memory_manager=self.memory_manager,
            skill_registry=self.skill_registry,
            vector_store=self.vector_store,
        )

        # Cron scheduler
        self.cron_scheduler = CronScheduler(
            data_dir=data_dir,
            on_trigger=self._on_cron_trigger,
        )

        # Health check
        health_monitor = HealthMonitor()
        self.health_server = HealthCheckServer(monitor=health_monitor)

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
            hook_registry=self.hook_registry,
        )

        self._gateway_auth = None
        self._agent_task: asyncio.Task | None = None

    async def _on_cron_trigger(self, name: str, action: str) -> None:
        """Handle cron task triggers by sending them as inbound messages."""
        await self.bus.put_inbound(
            InboundMessage(
                channel="system",
                chat_id="cron",
                user_id="cron",
                username="CronScheduler",
                text=f"[Scheduled Task: {name}] {action}",
            )
        )

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

        tavily_settings = self.config.providers.get("tavily")
        if tavily_settings and tavily_settings.api_key:
            self.tool_registry.register(WebSearchTool(api_key=tavily_settings.api_key))

        self.tool_registry.register(MessageUserTool(
            bus=self.bus,
            context_provider=lambda: (
                self.agent_loop._current_channel,
                self.agent_loop._current_chat_id,
            ),
        ))
        self.tool_registry.register(SpawnTaskTool(manager=self.subagent_manager))

        # Memory tools
        self.tool_registry.register(MemorySaveTool(
            memory_manager=self.memory_manager,
            vector_store=self.vector_store,
        ))
        self.tool_registry.register(MemorySearchTool(
            memory_manager=self.memory_manager,
            vector_store=self.vector_store,
        ))

        # Cron tools
        data_dir = Path(self.config.knowledge.data_dir)
        self.tool_registry.register(CronAddTool(data_dir=data_dir))
        self.tool_registry.register(CronListTool(data_dir=data_dir))
        self.tool_registry.register(CronRemoveTool(data_dir=data_dir))

        # Skill tools
        from mindclaw.tools.skill_tools import (
            SkillInstallTool,
            SkillListTool,
            SkillRemoveTool,
            SkillSearchTool,
            SkillShowTool,
        )
        self.tool_registry.register(SkillSearchTool(index_client=self.skill_index_client))
        self.tool_registry.register(SkillShowTool(registry=self.skill_registry))
        self.tool_registry.register(SkillListTool(registry=self.skill_registry))
        self.tool_registry.register(SkillInstallTool(
            installer=self.skill_installer,
            registry=self.skill_registry,
        ))
        self.tool_registry.register(SkillRemoveTool(installer=self.skill_installer))

        # Load plugins (after built-ins so plugins can override)
        self._load_plugins()

    def _load_plugins(self) -> None:
        """Discover and load all plugins from plugins directory."""
        loader = PluginLoader(self._plugins_dir)
        for manifest in loader.discover():
            try:
                loader.load_one(manifest, self.tool_registry, self.hook_registry)
                logger.info(f"Loaded plugin: {manifest.name} v{manifest.version}")
            except Exception:
                logger.warning(f"Failed to load plugin: {manifest.name}")

    # ── Channel setup ─────────────────────────────────────────

    def _setup_channels(self, channel_names: list[str]) -> None:
        for name in channel_names:
            if name == "cli":
                self.channel_manager.register(CLIChannel(bus=self.bus))
            elif name == "gateway":
                self._setup_gateway()
            elif name == "telegram":
                self._setup_telegram()
            elif name == "slack":
                self._setup_slack()
            elif name == "feishu":
                self._setup_feishu()
            elif name == "discord":
                self._setup_discord()
            elif name == "wechat":
                self._setup_wechat()
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

    @staticmethod
    def _init_oauth(config: MindClawConfig):
        """Initialize OAuthManager if any provider uses OAuth auth."""
        has_oauth = any(
            s.auth_type == "oauth" for s in config.providers.values()
        )
        if not has_oauth:
            return None

        from mindclaw.oauth.manager import OAuthManager
        from mindclaw.oauth.token_store import OAuthTokenStore

        data_dir = Path(config.knowledge.data_dir)
        token_store = OAuthTokenStore(
            store_path=data_dir / "oauth_tokens.enc",
            master_key_path=data_dir / "master.key",
        )
        token_store.init_or_load_key()
        return OAuthManager(token_store=token_store)

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

    def _setup_slack(self) -> None:
        from mindclaw.channels.slack import SlackChannel

        slack_config = self.config.channels.get("slack")
        if not slack_config or not slack_config.app_token or not slack_config.token:
            logger.warning("Slack channel configured but missing appToken or token, skipping")
            return

        self.channel_manager.register(
            SlackChannel(
                bus=self.bus,
                app_token=slack_config.app_token,
                bot_token=slack_config.token,
                allow_from=slack_config.allow_from or None,
                allow_groups=slack_config.allow_groups,
            )
        )

    def _setup_feishu(self) -> None:
        from mindclaw.channels.feishu import FeishuChannel

        feishu_config = self.config.channels.get("feishu")
        if not feishu_config or not feishu_config.app_id or not feishu_config.app_secret:
            logger.warning("Feishu channel configured but missing appId or appSecret, skipping")
            return

        self.channel_manager.register(
            FeishuChannel(
                bus=self.bus,
                app_id=feishu_config.app_id,
                app_secret=feishu_config.app_secret,
                allow_from=feishu_config.allow_from or None,
                allow_groups=feishu_config.allow_groups,
            )
        )

    def _setup_discord(self) -> None:
        from mindclaw.channels.discord_channel import DiscordChannel

        discord_config = self.config.channels.get("discord")
        if not discord_config or not discord_config.token:
            logger.warning("Discord channel configured but no token provided, skipping")
            return

        self.channel_manager.register(
            DiscordChannel(
                bus=self.bus,
                token=discord_config.token,
                allow_from=discord_config.allow_from or None,
                allow_groups=discord_config.allow_groups,
            )
        )

    def _setup_wechat(self) -> None:
        from mindclaw.channels.wechat_channel import WeChatChannel

        wechat_config = self.config.channels.get("wechat")
        if not wechat_config or not wechat_config.token:
            logger.warning("WeChat channel configured but no bridge_url (token field), skipping")
            return

        self.channel_manager.register(
            WeChatChannel(
                bus=self.bus,
                bridge_url=wechat_config.token,  # token field stores bridge_url
                allow_from=wechat_config.allow_from or None,
                allow_groups=wechat_config.allow_groups,
            )
        )

    # ── Message routing ───────────────────────────────────────

    async def _process_message(self, msg: InboundMessage) -> None:
        try:
            # on_message hook
            await self.hook_registry.call(
                "on_message",
                channel=msg.channel,
                chat_id=msg.chat_id,
                user_id=msg.user_id,
                text=msg.text,
            )
            await self.agent_loop.handle_message(msg)
        except Exception as exc:
            logger.exception("Agent error")
            try:
                # on_error hook
                await self.hook_registry.call(
                    "on_error",
                    error=str(exc),
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                )
            except Exception:
                logger.exception("on_error hook failed")
            try:
                await self.bus.put_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        text="An internal error occurred. Please try again.",
                    )
                )
            except Exception:
                logger.exception("Failed to send error reply to user")

    @staticmethod
    def _task_done_callback(task: asyncio.Task) -> None:
        """Log unhandled exceptions from agent tasks to prevent silent failures."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(f"Agent task failed with unhandled exception: {exc}")

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
            self._agent_task.add_done_callback(self._task_done_callback)

    async def _outbound_router(self) -> None:
        while True:
            msg = await self.bus.get_outbound()
            # on_reply hook
            await self.hook_registry.call(
                "on_reply",
                channel=msg.channel,
                chat_id=msg.chat_id,
                text=msg.text,
            )
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

        # Start background services
        await self.cron_scheduler.start()
        await self.health_server.start()

        # on_start hook
        await self.hook_registry.call("on_start")

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
            # Stop background services
            await self.cron_scheduler.stop()
            await self.health_server.stop()
            # on_stop hook
            await self.hook_registry.call("on_stop")
            await self.channel_manager.stop_all()

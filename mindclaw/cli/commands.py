# input: typer, channels/, orchestrator/, llm/, config/, tools/*, security/approval, knowledge/*
# output: 导出 app (Typer 应用)
# pos: CLI 入口，用户通过 typer 命令启动 MindClaw
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from mindclaw.bus.queue import MessageBus
from mindclaw.channels.cli_channel import CLIChannel
from mindclaw.config.loader import load_config
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.llm.router import LLMRouter
from mindclaw.orchestrator.agent_loop import AgentLoop
from mindclaw.orchestrator.context import ContextBuilder
from mindclaw.security.approval import ApprovalManager
from mindclaw.tools.file_ops import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from mindclaw.tools.registry import ToolRegistry
from mindclaw.tools.shell import ExecTool
from mindclaw.tools.web import WebFetchTool, WebSearchTool

app = typer.Typer(name="mindclaw", help="MindClaw - Personal AI Assistant")
console = Console()


async def _run_chat(config_path: Path | None) -> None:
    config = load_config(config_path)

    # 配置 loguru
    logger.remove()
    logger.add(
        config.log.file,
        level=config.log.level,
        rotation=config.log.rotation,
        retention=config.log.retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
    )

    bus = MessageBus()
    router = LLMRouter(config)

    # 注册所有工具
    workspace = Path.cwd()
    registry = ToolRegistry()
    registry.register(ReadFileTool(workspace=workspace))
    registry.register(WriteFileTool(workspace=workspace))
    registry.register(EditFileTool(workspace=workspace))
    registry.register(ListDirTool(workspace=workspace))
    registry.register(ExecTool(workspace=workspace, timeout=config.tools.exec_timeout))
    registry.register(WebFetchTool())

    brave_settings = config.providers.get("brave")
    if brave_settings and brave_settings.api_key:
        registry.register(WebSearchTool(api_key=brave_settings.api_key))

    # 创建知识层组件
    data_dir = Path(config.knowledge.data_dir)
    session_store = SessionStore(data_dir=data_dir)
    memory_manager = MemoryManager(data_dir=data_dir, router=router, config=config)
    context_builder = ContextBuilder(memory_manager=memory_manager)

    # 创建审批管理器
    approval_manager = ApprovalManager(
        bus=bus,
        timeout=config.security.approval_timeout,
    )

    agent = AgentLoop(
        config=config,
        bus=bus,
        router=router,
        tool_registry=registry,
        approval_manager=approval_manager,
        session_store=session_store,
        memory_manager=memory_manager,
        context_builder=context_builder,
    )

    channel = CLIChannel(bus=bus)

    agent_task: asyncio.Task | None = None

    async def _process_message(msg):
        try:
            await agent.handle_message(msg)
        except Exception:
            logger.exception("Agent error")
            from mindclaw.bus.events import OutboundMessage

            await bus.put_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    text="An internal error occurred. Please try again.",
                )
            )

    async def message_router():
        nonlocal agent_task
        while True:
            msg = await bus.get_inbound()

            # Route approval replies to ApprovalManager
            if approval_manager.has_pending() and approval_manager.is_approval_reply(
                msg.text
            ):
                approval_manager.resolve(msg.text)
                continue

            # During pending approval, drop non-approval messages to avoid
            # blocking the router (which would deadlock the approval flow).
            if approval_manager.has_pending():
                logger.debug(
                    f"Ignoring non-approval message during pending approval: "
                    f"{msg.text[:50]}"
                )
                continue

            # Wait for previous agent processing to finish
            if agent_task is not None and not agent_task.done():
                try:
                    await agent_task
                except Exception:
                    pass  # Error already handled inside _process_message

            agent_task = asyncio.create_task(_process_message(msg))

    router_task = asyncio.create_task(message_router())

    try:
        await channel.start()
    finally:
        router_task.cancel()
        if agent_task and not agent_task.done():
            agent_task.cancel()
        for t in [router_task, agent_task]:
            if t:
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        await channel.stop()


@app.command()
def chat(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Start an interactive chat session."""
    asyncio.run(_run_chat(config))


@app.command()
def version() -> None:
    """Show MindClaw version."""
    from mindclaw import __version__

    console.print(f"MindClaw v{__version__}")


if __name__ == "__main__":
    app()

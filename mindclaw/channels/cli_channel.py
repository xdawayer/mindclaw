# input: channels/base.py, bus/events.py, prompt_toolkit
# output: 导出 CLIChannel
# pos: CLI 渠道实现，本地终端交互
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import os

from rich.console import Console
from rich.markdown import Markdown

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel

console = Console()


class CLIChannel(BaseChannel):
    def __init__(self, bus: MessageBus) -> None:
        super().__init__(bus)
        self._running = False
        self._stop_event: asyncio.Event | None = None

    async def _handle_input(self, text: str) -> None:
        msg = InboundMessage(
            channel="cli",
            chat_id="local",
            user_id=os.getenv("USER", "user"),
            username=os.getenv("USER", "user"),
            text=text,
        )
        await self.bus.put_inbound(msg)

    async def _input_loop(self) -> None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout

        session = PromptSession()
        with patch_stdout():
            while self._running:
                try:
                    text = await session.prompt_async("You> ")
                    text = text.strip()
                    if not text:
                        continue
                    if text.lower() in ("exit", "quit", "/quit"):
                        self._running = False
                        self._stop_event.set()
                        break
                    await self._handle_input(text)
                except (EOFError, KeyboardInterrupt):
                    self._running = False
                    self._stop_event.set()
                    break

    async def _output_loop(self) -> None:
        while not self._stop_event.is_set():
            get_task = asyncio.ensure_future(self.bus.get_outbound())
            stop_task = asyncio.ensure_future(self._stop_event.wait())
            done, pending = await asyncio.wait(
                {get_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            if get_task in done:
                msg = get_task.result()
                console.print()
                console.print(Markdown(msg.text))
                console.print()

    async def start(self) -> None:
        self._running = True
        self._stop_event = asyncio.Event()
        console.print("[bold green]MindClaw[/] ready. Type 'exit' to quit.\n")
        await asyncio.gather(self._input_loop(), self._output_loop())

    async def stop(self) -> None:
        self._running = False
        if self._stop_event:
            self._stop_event.set()

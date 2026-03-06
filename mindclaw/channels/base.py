# input: abc, bus/queue.py
# output: 导出 BaseChannel
# pos: 渠道层抽象基类，所有渠道的统一接口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from abc import ABC, abstractmethod

from mindclaw.bus.queue import MessageBus


class BaseChannel(ABC):
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    @abstractmethod
    async def start(self) -> None:
        """启动渠道"""

    @abstractmethod
    async def stop(self) -> None:
        """停止渠道"""

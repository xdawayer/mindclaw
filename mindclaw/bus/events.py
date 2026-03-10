# input: dataclasses, uuid, time
# output: 导出 InboundMessage, OutboundMessage
# pos: 消息数据类定义，总线层的数据契约
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class InboundMessage:
    channel: str
    chat_id: str
    user_id: str
    username: str
    text: str
    reply_to: str | None = None
    attachments: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    text: str
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    reply_to: str | None = None
    attachments: list = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

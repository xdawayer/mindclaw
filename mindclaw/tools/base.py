# input: abc, enum
# output: 导出 Tool, RiskLevel
# pos: 工具层抽象基类，所有工具的统一接口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from abc import ABC, abstractmethod
from enum import Enum


class RiskLevel(Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


class Tool(ABC):
    name: str
    description: str
    parameters: dict
    risk_level: RiskLevel

    @abstractmethod
    async def execute(self, params: dict) -> str:
        """执行工具并返回结果字符串"""

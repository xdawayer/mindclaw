# input: config/schema.py, json, os, pathlib
# output: 导出 load_config(), resolve_env_vars()
# pos: 配置加载器，从 JSON 文件加载并解析环境变量
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
import os
from pathlib import Path

from loguru import logger

from .schema import MindClawConfig


def resolve_env_vars(data: dict | list | str) -> dict | list | str:
    """递归解析配置中的 $ENV_VAR 引用"""
    if isinstance(data, str):
        if data.startswith("$") and not data.startswith("$$"):
            env_name = data[1:]
            value = os.environ.get(env_name)
            if value is None:
                logger.warning(f"Environment variable {env_name} not set, keeping raw value")
                return data
            return value
        return data
    if isinstance(data, dict):
        return {k: resolve_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [resolve_env_vars(item) for item in data]
    return data


def load_config(path: Path | None = None) -> MindClawConfig:
    """从 JSON 文件加载配置，文件不存在则返回默认配置"""
    if path is None:
        path = Path("config.json")

    if not path.exists():
        logger.info(f"Config file {path} not found, using defaults")
        return MindClawConfig()

    raw = json.loads(path.read_text())
    resolved = resolve_env_vars(raw)
    return MindClawConfig(**resolved)

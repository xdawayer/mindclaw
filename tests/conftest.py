# input: pytest, tempfile, pathlib
# output: 导出 autouse fixture (isolate_data_dir)
# pos: 测试配置，确保每个测试使用独立的 data 目录，避免跨测试数据污染
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Shared test fixtures and configuration."""

import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def isolate_data_dir(monkeypatch, tmp_path):
    """Ensure tests using default data_dir='data' get an isolated directory.

    AgentLoop defaults to ``Path(config.knowledge.data_dir)`` which is the
    relative path ``data``.  By changing the working directory to a unique
    temp folder for each test, every ``SessionStore`` and ``MemoryManager``
    created with defaults writes to an isolated ``<tmp>/data/`` tree.
    """
    monkeypatch.chdir(tmp_path)

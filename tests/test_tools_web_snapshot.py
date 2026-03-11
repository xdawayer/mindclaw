# input: mindclaw.tools.web_snapshot
# output: WebSnapshot 工具测试
# pos: 网页快照工具 (保存/列出/读取/UUID文件名/SSRF防护/保留策略) 测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_httpx_client(body: bytes, status: int = 200, content_type: str = "text/plain"):
    """Return a patched httpx.AsyncClient context manager that yields body bytes."""

    async def _aiter_bytes():
        yield body

    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.headers = {"content-type": content_type}
    mock_resp.aiter_bytes = _aiter_bytes

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    # stream() is used as an async context manager
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_stream(method, url):
        yield mock_resp

    mock_client.stream = _fake_stream
    return mock_client


# ---------------------------------------------------------------------------
# WebSnapshotTool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_saves_content(tmp_path):
    """Fetched content is saved to disk under snapshots/."""
    from mindclaw.tools.web_snapshot import WebSnapshotTool

    tool = WebSnapshotTool(data_dir=tmp_path)
    body = b"Hello snapshot world"

    with (
        patch("mindclaw.tools.web_snapshot._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _make_fake_httpx_client(body)
        result = await tool.execute({"url": "https://example.com"})

    snapshots_dir = tmp_path / "snapshots"
    assert snapshots_dir.exists(), "snapshots directory should be created"
    txt_files = list(snapshots_dir.glob("*.txt"))
    assert len(txt_files) == 1, "exactly one snapshot file should be created"
    assert txt_files[0].read_bytes() == body
    assert "Snapshot saved:" in result


@pytest.mark.asyncio
async def test_snapshot_uuid_filename(tmp_path):
    """Snapshot file is named with a valid UUID."""
    from mindclaw.tools.web_snapshot import WebSnapshotTool

    tool = WebSnapshotTool(data_dir=tmp_path)

    with (
        patch("mindclaw.tools.web_snapshot._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _make_fake_httpx_client(b"content")
        await tool.execute({"url": "https://example.com"})

    txt_files = list((tmp_path / "snapshots").glob("*.txt"))
    stem = txt_files[0].stem
    # Will raise ValueError if not a valid UUID
    parsed = uuid.UUID(stem)
    assert str(parsed) == stem


@pytest.mark.asyncio
async def test_snapshot_index_jsonl_updated(tmp_path):
    """index.jsonl gets a new entry with correct fields after save."""
    from mindclaw.tools.web_snapshot import WebSnapshotTool

    tool = WebSnapshotTool(data_dir=tmp_path)
    body = b"Index test content"
    url = "https://index-test.example.com"

    with (
        patch("mindclaw.tools.web_snapshot._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _make_fake_httpx_client(body)
        await tool.execute({"url": url})

    index_path = tmp_path / "snapshots" / "index.jsonl"
    assert index_path.exists(), "index.jsonl should be created"
    lines = index_path.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["url"] == url
    assert entry["size"] == len(body)
    assert "id" in entry
    assert "timestamp" in entry
    # Validate id is a UUID
    uuid.UUID(entry["id"])


@pytest.mark.asyncio
async def test_snapshot_ssrf_blocks_private(tmp_path):
    """SSRF protection: private URLs must be rejected."""
    from mindclaw.tools.web_snapshot import WebSnapshotTool

    tool = WebSnapshotTool(data_dir=tmp_path)

    with patch("mindclaw.tools.web_snapshot._is_safe_url", return_value=False):
        result = await tool.execute({"url": "http://192.168.1.1/"})

    assert "private" in result.lower() or "internal" in result.lower() or "error" in result.lower()
    # No snapshot file should be created
    snapshots_dir = tmp_path / "snapshots"
    txt_files = list(snapshots_dir.glob("*.txt")) if snapshots_dir.exists() else []
    assert len(txt_files) == 0


# ---------------------------------------------------------------------------
# WebSnapshotListTool
# ---------------------------------------------------------------------------


async def _save_snapshot(tool, url: str, body: bytes = b"content") -> str:
    """Helper: save a snapshot and return its id."""
    with (
        patch("mindclaw.tools.web_snapshot._is_safe_url", return_value=True),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _make_fake_httpx_client(body)
        result = await tool.execute({"url": url})
    # result: "Snapshot saved: <uuid> (<n> bytes)"
    snapshot_id = result.split("Snapshot saved:")[1].strip().split()[0]
    return snapshot_id


@pytest.mark.asyncio
async def test_list_returns_recent(tmp_path):
    """After saving 3 snapshots, listing returns all 3."""
    from mindclaw.tools.web_snapshot import WebSnapshotListTool, WebSnapshotTool

    snap_tool = WebSnapshotTool(data_dir=tmp_path)
    list_tool = WebSnapshotListTool(data_dir=tmp_path)

    for i in range(3):
        await _save_snapshot(snap_tool, f"https://example.com/page{i}")

    result = await list_tool.execute({})
    lines = [ln for ln in result.strip().splitlines() if ln.strip().startswith("-")]
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_list_filters_by_url(tmp_path):
    """Filtering by url= returns only snapshots for that URL."""
    from mindclaw.tools.web_snapshot import WebSnapshotListTool, WebSnapshotTool

    snap_tool = WebSnapshotTool(data_dir=tmp_path)
    list_tool = WebSnapshotListTool(data_dir=tmp_path)

    await _save_snapshot(snap_tool, "https://alpha.example.com/")
    await _save_snapshot(snap_tool, "https://alpha.example.com/")
    await _save_snapshot(snap_tool, "https://beta.example.com/")

    result = await list_tool.execute({"url": "https://alpha.example.com/"})
    lines = [ln for ln in result.strip().splitlines() if ln.strip().startswith("-")]
    assert len(lines) == 2
    for line in lines:
        assert "alpha.example.com" in line


@pytest.mark.asyncio
async def test_list_respects_limit(tmp_path):
    """limit=2 returns only 2 entries even when 5 exist."""
    from mindclaw.tools.web_snapshot import WebSnapshotListTool, WebSnapshotTool

    snap_tool = WebSnapshotTool(data_dir=tmp_path)
    list_tool = WebSnapshotListTool(data_dir=tmp_path)

    for i in range(5):
        await _save_snapshot(snap_tool, f"https://example.com/page{i}")

    result = await list_tool.execute({"limit": 2})
    lines = [ln for ln in result.strip().splitlines() if ln.strip().startswith("-")]
    assert len(lines) == 2


# ---------------------------------------------------------------------------
# WebSnapshotReadTool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_returns_content(tmp_path):
    """Reading a saved snapshot by ID returns the saved content."""
    from mindclaw.tools.web_snapshot import WebSnapshotReadTool, WebSnapshotTool

    snap_tool = WebSnapshotTool(data_dir=tmp_path)
    read_tool = WebSnapshotReadTool(data_dir=tmp_path)

    body = b"Read back this content"
    snap_id = await _save_snapshot(snap_tool, "https://example.com/read", body)

    result = await read_tool.execute({"id": snap_id})
    assert result == body.decode()


@pytest.mark.asyncio
async def test_read_invalid_uuid_rejected(tmp_path):
    """Path traversal / non-UUID id must be rejected."""
    from mindclaw.tools.web_snapshot import WebSnapshotReadTool

    read_tool = WebSnapshotReadTool(data_dir=tmp_path)

    result = await read_tool.execute({"id": "../../etc/passwd"})
    assert "invalid" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
async def test_read_nonexistent_id(tmp_path):
    """A valid UUID that has no corresponding file returns an error."""
    from mindclaw.tools.web_snapshot import WebSnapshotReadTool

    read_tool = WebSnapshotReadTool(data_dir=tmp_path)
    nonexistent = str(uuid.uuid4())

    result = await read_tool.execute({"id": nonexistent})
    assert "not found" in result.lower() or "error" in result.lower()


# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------


def test_risk_levels():
    """WebSnapshotTool is MODERATE; List and Read are SAFE."""
    from mindclaw.tools.base import RiskLevel
    from mindclaw.tools.web_snapshot import (
        WebSnapshotListTool,
        WebSnapshotReadTool,
        WebSnapshotTool,
    )

    data_dir = Path("/tmp/unused")
    assert WebSnapshotTool(data_dir).risk_level == RiskLevel.MODERATE
    assert WebSnapshotListTool(data_dir).risk_level == RiskLevel.SAFE
    assert WebSnapshotReadTool(data_dir).risk_level == RiskLevel.SAFE

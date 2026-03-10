# Skill Installation System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a skill installation system that supports local/URL/GitHub/index sources, CLI + conversation entry points, three-layer discovery with security validation.

**Architecture:** Core logic in `mindclaw/skills/` (installer, index_client, integrity). CLI via Typer subcommand group. LLM access via 5 new tools in `mindclaw/tools/skill_tools.py`. SkillRegistry refactored to multi-directory with atomic reload. All remote installs go through SSRF + SHA256 + size validation.

**Tech Stack:** Python 3.12+, httpx (existing), hashlib/ipaddress (stdlib), Typer (existing), Pydantic (existing)

**Spec:** `docs/superpowers/specs/2026-03-10-skill-installation-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `mindclaw/config/schema.py` | Add `SkillsConfig` to `MindClawConfig` |
| Modify | `mindclaw/skills/registry.py` | Multi-dir, atomic reload, protected names, source tracking |
| Create | `mindclaw/skills/integrity.py` | SHA256, SSRF filter, format validation, size check |
| Create | `mindclaw/skills/index_client.py` | Index fetch, cache, search |
| Create | `mindclaw/skills/installer.py` | Download, validate, install, remove, update |
| Create | `mindclaw/tools/skill_tools.py` | 5 LLM tools: search/show/install/remove/list |
| Create | `mindclaw/cli/skill_commands.py` | Typer subcommand group |
| Modify | `mindclaw/cli/commands.py` | Register skill subcommand group |
| Modify | `mindclaw/app.py` | Multi-dir registry, register skill tools |
| Modify | `mindclaw/orchestrator/context.py` | Prompt injection isolation for installed skills |
| Create | `tests/test_skill_integrity.py` | Tests for integrity module |
| Create | `tests/test_skill_index_client.py` | Tests for index client |
| Create | `tests/test_skill_installer.py` | Tests for installer |
| Create | `tests/test_skill_tools.py` | Tests for LLM tools |
| Create | `tests/test_skill_cli.py` | Tests for CLI commands |
| Modify | `tests/test_skill_registry.py` | Update for multi-dir API |
| Modify | `tests/test_context_builder_skills.py` | Update for isolation wrapper |

---

## Chunk 1: Config + Integrity Module

### Task 1: Add SkillsConfig to config schema

**Files:**
- Modify: `mindclaw/config/schema.py:132-143`
- Test: `tests/test_config.py` (existing, may need update)

- [ ] **Step 1: Write the failing test**

Create `tests/test_skills_config.py`:

```python
# input: mindclaw.config.schema
# output: SkillsConfig 配置验证测试
# pos: 验证技能配置模型的默认值和别名解析
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from mindclaw.config.schema import MindClawConfig, SkillsConfig


def test_skills_config_defaults():
    cfg = SkillsConfig()
    assert cfg.index_url.startswith("https://")
    assert cfg.cache_ttl == 86400
    assert cfg.max_skill_size == 8192
    assert cfg.max_always_total == 32768


def test_skills_config_in_mindclaw_config():
    cfg = MindClawConfig()
    assert isinstance(cfg.skills, SkillsConfig)


def test_skills_config_from_json_aliases():
    cfg = SkillsConfig.model_validate({
        "indexUrl": "https://example.com/index.json",
        "cacheTtl": 3600,
        "maxSkillSize": 4096,
        "maxAlwaysTotal": 16384,
    })
    assert cfg.index_url == "https://example.com/index.json"
    assert cfg.cache_ttl == 3600
    assert cfg.max_skill_size == 4096
    assert cfg.max_always_total == 16384
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skills_config.py -v`
Expected: FAIL with ImportError (SkillsConfig not yet defined)

- [ ] **Step 3: Write minimal implementation**

Add to `mindclaw/config/schema.py` before `MindClawConfig`:

```python
class SkillsConfig(BaseModel):
    index_url: str = Field(
        default="https://raw.githubusercontent.com/mindclaw-skills/index/main/index.json",
        alias="indexUrl",
    )
    cache_ttl: int = Field(default=86400, alias="cacheTtl")
    max_skill_size: int = Field(default=8192, alias="maxSkillSize")
    max_always_total: int = Field(default=32768, alias="maxAlwaysTotal")

    model_config = {"populate_by_name": True}
```

Add to `MindClawConfig`:
```python
skills: SkillsConfig = Field(default_factory=SkillsConfig)
```

Update the `# output:` header comment to include `SkillsConfig`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skills_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mindclaw/config/schema.py tests/test_skills_config.py
git commit -m "feat(config): add SkillsConfig for skill installation system"
```

---

### Task 2: Create integrity module (SHA256 + SSRF + format validation + size check)

**Files:**
- Create: `mindclaw/skills/integrity.py`
- Create: `tests/test_skill_integrity.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skill_integrity.py`:

```python
# input: mindclaw.skills.integrity
# output: 完整性校验模块测试
# pos: 验证 SHA256、SSRF 过滤、格式校验、大小限制
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import hashlib

import pytest

from mindclaw.skills.integrity import (
    compute_sha256,
    is_safe_download_url,
    validate_skill_content,
    validate_skill_size,
)


class TestComputeSha256:
    def test_basic_hash(self):
        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()
        assert compute_sha256(content) == expected

    def test_empty_content(self):
        assert compute_sha256(b"") == hashlib.sha256(b"").hexdigest()


class TestIsSafeDownloadUrl:
    def test_https_public_url(self):
        assert is_safe_download_url("https://example.com/skill.md") is True

    def test_http_rejected(self):
        assert is_safe_download_url("http://example.com/skill.md") is False

    def test_private_ip_rejected(self):
        assert is_safe_download_url("https://192.168.1.1/skill.md") is False
        assert is_safe_download_url("https://10.0.0.1/skill.md") is False
        assert is_safe_download_url("https://172.16.0.1/skill.md") is False

    def test_loopback_rejected(self):
        assert is_safe_download_url("https://127.0.0.1/skill.md") is False
        assert is_safe_download_url("https://localhost/skill.md") is False

    def test_link_local_rejected(self):
        assert is_safe_download_url("https://169.254.169.254/skill.md") is False

    def test_ftp_rejected(self):
        assert is_safe_download_url("ftp://example.com/skill.md") is False

    def test_empty_url(self):
        assert is_safe_download_url("") is False


class TestValidateSkillContent:
    def test_valid_skill(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "description: A test skill\n"
            "load: on_demand\n"
            "---\n\n"
            "# Test Skill\n"
        )
        result = validate_skill_content(content)
        assert result.valid is True
        assert result.name == "test-skill"
        assert result.description == "A test skill"

    def test_missing_name(self):
        content = (
            "---\n"
            "description: A test skill\n"
            "load: on_demand\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        assert result.valid is False
        assert "name" in result.error.lower()

    def test_no_front_matter(self):
        content = "# Just a heading\nNo front-matter."
        result = validate_skill_content(content)
        assert result.valid is False

    def test_valid_with_extra_fields(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "description: A test\n"
            "load: on_demand\n"
            "version: 1.0.0\n"
            "source: github:user/repo\n"
            "sha256: abc123\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        assert result.valid is True

    def test_invalid_load_mode(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "description: A test\n"
            "load: invalid_mode\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        assert result.valid is False
        assert "load" in result.error.lower()


class TestValidateSkillSize:
    def test_within_limit(self):
        assert validate_skill_size(b"x" * 100, max_size=8192) is True

    def test_at_limit(self):
        assert validate_skill_size(b"x" * 8192, max_size=8192) is True

    def test_over_limit(self):
        assert validate_skill_size(b"x" * 8193, max_size=8192) is False

    def test_empty(self):
        assert validate_skill_size(b"", max_size=8192) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_integrity.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

Create `mindclaw/skills/integrity.py`:

```python
# input: hashlib, ipaddress, socket, re
# output: 导出 compute_sha256, is_safe_download_url, validate_skill_content,
#         validate_skill_size, ValidationResult
# pos: 技能完整性校验，SHA256 / SSRF 过滤 / 格式验证 / 大小限制
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill integrity: SHA256, SSRF filtering, format validation, size limits."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_YAML_LINE_RE = re.compile(r"^(\w+)\s*:\s*(.+)$")
_VALID_LOAD_MODES = frozenset({"on_demand", "always"})
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    name: str = ""
    description: str = ""
    load: str = "on_demand"
    error: str = ""


def compute_sha256(content: bytes) -> str:
    """Compute SHA256 hex digest of content."""
    return hashlib.sha256(content).hexdigest()


def is_safe_download_url(url: str) -> bool:
    """Check URL is HTTPS and does not target private/loopback/link-local addresses."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except (socket.gaierror, ValueError, OSError):
        return False


def validate_skill_content(content: str) -> ValidationResult:
    """Validate skill markdown has valid YAML front-matter with required fields."""
    match = _FRONT_MATTER_RE.match(content)
    if not match:
        return ValidationResult(valid=False, error="No valid YAML front-matter found")

    front_matter = match.group(1)
    fields: dict[str, str] = {}
    for line in front_matter.strip().splitlines():
        line_match = _YAML_LINE_RE.match(line.strip())
        if line_match:
            fields[line_match.group(1)] = line_match.group(2).strip()

    name = fields.get("name", "")
    if not name:
        return ValidationResult(valid=False, error="Missing required field: name")

    description = fields.get("description", "")
    load = fields.get("load", "on_demand")
    if load not in _VALID_LOAD_MODES:
        return ValidationResult(
            valid=False,
            error=f"Invalid load mode: '{load}'. Must be one of: {', '.join(_VALID_LOAD_MODES)}",
        )

    return ValidationResult(valid=True, name=name, description=description, load=load)


def validate_skill_size(content: bytes, *, max_size: int = 8192) -> bool:
    """Check if skill content is within the size limit."""
    return len(content) <= max_size


def sanitize_approval_text(text: str) -> str:
    """Remove control characters from text used in approval messages."""
    return _CONTROL_CHAR_RE.sub("", text).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_integrity.py -v`
Expected: PASS

- [ ] **Step 5: Update `_ARCHITECTURE.md`**

Update `mindclaw/skills/_ARCHITECTURE.md` to add the `integrity.py` entry.

- [ ] **Step 6: Commit**

```bash
git add mindclaw/skills/integrity.py tests/test_skill_integrity.py mindclaw/skills/_ARCHITECTURE.md mindclaw/config/schema.py
git commit -m "feat(skills): add integrity module with SHA256, SSRF, format validation"
```

---

## Chunk 2: SkillRegistry Multi-Dir + Atomic Reload

### Task 3: Refactor SkillRegistry for multi-directory support

**Files:**
- Modify: `mindclaw/skills/registry.py`
- Modify: `tests/test_skill_registry.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_skill_registry.py`:

```python
@pytest.fixture
def multi_dir_setup(tmp_path):
    """Create builtin, project, and user skill directories."""
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: Built-in translate
        load: always
        ---

        # Built-in Translate
    """))
    (builtin / "summarize.md").write_text(dedent("""\
        ---
        name: summarize-article
        description: Built-in summarize
        load: on_demand
        ---

        # Built-in Summarize
    """))

    project = tmp_path / "project"
    project.mkdir()

    user = tmp_path / "user"
    user.mkdir()
    (user / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: User custom translate
        load: on_demand
        ---

        # User Translate
    """))

    return builtin, project, user


def test_multi_dir_discovery(multi_dir_setup):
    """SkillRegistry should discover skills from multiple directories."""
    from mindclaw.skills.registry import SkillRegistry

    builtin, project, user = multi_dir_setup
    registry = SkillRegistry([builtin, project, user])

    assert len(registry.skills) == 2
    names = {s.name for s in registry.skills}
    assert names == {"translate", "summarize-article"}


def test_multi_dir_user_overrides_builtin(multi_dir_setup):
    """User-level skill should override builtin with same name."""
    from mindclaw.skills.registry import SkillRegistry

    builtin, project, user = multi_dir_setup
    registry = SkillRegistry([builtin, project, user])

    translate = registry.get("translate")
    assert translate is not None
    assert translate.description == "User custom translate"
    assert translate.load == "on_demand"


def test_atomic_reload(multi_dir_setup):
    """reload() should atomically replace the skills dict."""
    from mindclaw.skills.registry import SkillRegistry

    builtin, project, user = multi_dir_setup
    registry = SkillRegistry([builtin, project, user])

    assert len(registry.skills) == 2

    # Add a new skill to user dir
    (user / "new-skill.md").write_text(dedent("""\
        ---
        name: new-skill
        description: A new skill
        load: on_demand
        ---

        # New Skill
    """))

    registry.reload()
    assert len(registry.skills) == 3
    assert registry.get("new-skill") is not None


def test_protected_names():
    """Protected names should be tracked from the first (builtin) directory."""
    from mindclaw.skills.registry import SkillRegistry

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        builtin = Path(td) / "builtin"
        builtin.mkdir()
        (builtin / "core.md").write_text(dedent("""\
            ---
            name: core-skill
            description: A core skill
            load: on_demand
            ---

            # Core
        """))

        registry = SkillRegistry([builtin])
        assert "core-skill" in registry.protected_names


def test_get_skill_source_layer(multi_dir_setup):
    """Skills should know which layer they came from."""
    from mindclaw.skills.registry import SkillRegistry

    builtin, project, user = multi_dir_setup
    registry = SkillRegistry([builtin, project, user])

    translate = registry.get("translate")
    assert translate is not None
    assert translate.source_layer == "user"

    summarize = registry.get("summarize-article")
    assert summarize is not None
    assert summarize.source_layer == "builtin"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_registry.py::test_multi_dir_discovery tests/test_skill_registry.py::test_multi_dir_user_overrides_builtin tests/test_skill_registry.py::test_atomic_reload tests/test_skill_registry.py::test_protected_names tests/test_skill_registry.py::test_get_skill_source_layer -v`
Expected: FAIL (SkillRegistry takes single Path, not list)

- [ ] **Step 3: Rewrite SkillRegistry**

Replace `mindclaw/skills/registry.py` with:

```python
# input: pathlib, re (YAML front-matter parsing)
# output: 导出 SkillRegistry, SkillMetadata
# pos: 技能注册中心，扫描多层 skills/ 目录，合并解析 YAML front-matter，支持热重载
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill registry: discovers and indexes skill files from multiple directories."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_YAML_LINE_RE = re.compile(r"^(\w+)\s*:\s*(.+)$")

_LAYER_NAMES = ("builtin", "project", "user")


@dataclass
class SkillMetadata:
    name: str
    description: str
    load: str  # "on_demand" | "always"
    file_path: Path
    content: str  # Full markdown content (after front-matter)
    source_layer: str = "builtin"  # "builtin" | "project" | "user"


class SkillRegistry:
    """Discover and index skill markdown files from multiple directories.

    Directories are scanned in order: builtin -> project -> user.
    Later directories override earlier ones (user wins).
    The first directory's skill names form the protected_names set.
    """

    def __init__(self, skill_dirs: list[Path] | Path) -> None:
        # Backward compat: accept single Path
        if isinstance(skill_dirs, Path):
            skill_dirs = [skill_dirs]
        self._dirs = skill_dirs
        self._skills: dict[str, SkillMetadata] = {}
        self._protected_names: frozenset[str] = frozenset()
        self._discover_all()

    @property
    def skills(self) -> list[SkillMetadata]:
        return list(self._skills.values())

    @property
    def protected_names(self) -> frozenset[str]:
        return self._protected_names

    def get(self, name: str) -> SkillMetadata | None:
        return self._skills.get(name)

    def get_skill_summaries(self) -> list[str]:
        """Return name + description lines for system prompt injection."""
        return [
            f"- {s.name}: {s.description}"
            for s in self._skills.values()
        ]

    def get_always_skills_content(self) -> str:
        """Return full content of all 'always' load skills."""
        parts = [
            s.content
            for s in self._skills.values()
            if s.load == "always"
        ]
        return "\n".join(parts)

    def reload(self) -> None:
        """Re-scan all directories and atomically replace the skills dict."""
        new_skills, _ = self._build_skills_dict()
        self._skills = new_skills
        logger.info(f"Skills reloaded: {len(new_skills)} skills from {len(self._dirs)} dirs")

    def _discover_all(self) -> None:
        new_skills, protected = self._build_skills_dict()
        self._skills = new_skills
        self._protected_names = protected

    def _build_skills_dict(self) -> tuple[dict[str, SkillMetadata], frozenset[str]]:
        new_skills: dict[str, SkillMetadata] = {}
        protected: set[str] = set()

        for idx, skills_dir in enumerate(self._dirs):
            layer = _LAYER_NAMES[idx] if idx < len(_LAYER_NAMES) else f"layer_{idx}"
            self._discover_into(skills_dir, new_skills, layer)
            # First directory defines protected names
            if idx == 0:
                protected = set(new_skills.keys())

        return new_skills, frozenset(protected)

    def _discover_into(
        self, skills_dir: Path, target: dict[str, SkillMetadata], layer: str
    ) -> None:
        if not skills_dir.is_dir():
            logger.debug(f"Skills directory not found: {skills_dir}")
            return

        for path in sorted(skills_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            meta = self._parse_skill(path, layer)
            if meta:
                if meta.name in target:
                    logger.warning(
                        f"Skill '{meta.name}' in {layer} overrides "
                        f"{target[meta.name].source_layer} layer"
                    )
                target[meta.name] = meta
                logger.debug(f"Discovered skill: {meta.name} (load={meta.load}, layer={layer})")

    def _parse_skill(self, path: Path, layer: str) -> SkillMetadata | None:
        """Parse a skill file, extracting YAML front-matter metadata."""
        text = path.read_text(encoding="utf-8")

        match = _FRONT_MATTER_RE.match(text)
        if not match:
            logger.debug(f"Skipping {path.name}: no valid YAML front-matter")
            return None

        front_matter = match.group(1)
        content = text[match.end():]

        fields: dict[str, str] = {}
        for line in front_matter.strip().splitlines():
            line_match = _YAML_LINE_RE.match(line.strip())
            if line_match:
                fields[line_match.group(1)] = line_match.group(2).strip()

        name = fields.get("name")
        description = fields.get("description", "")
        load = fields.get("load", "on_demand")

        if not name:
            logger.debug(f"Skipping {path.name}: missing 'name' in front-matter")
            return None

        return SkillMetadata(
            name=name,
            description=description,
            load=load,
            file_path=path,
            content=content.strip(),
            source_layer=layer,
        )
```

- [ ] **Step 4: Run ALL registry tests to verify they pass**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_registry.py -v`
Expected: ALL PASS (old tests should still work due to backward compat)

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add mindclaw/skills/registry.py tests/test_skill_registry.py
git commit -m "refactor(skills): multi-directory SkillRegistry with atomic reload and protected names"
```

---

## Chunk 3: Index Client

### Task 4: Create index client (fetch, cache, search)

**Files:**
- Create: `mindclaw/skills/index_client.py`
- Create: `tests/test_skill_index_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skill_index_client.py`:

```python
# input: mindclaw.skills.index_client
# output: 索引客户端测试
# pos: 验证索引拉取、缓存、搜索、离线降级
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mindclaw.skills.index_client import IndexClient, IndexEntry


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path


@pytest.fixture
def sample_index():
    return {
        "version": 1,
        "skills": [
            {
                "name": "code-review",
                "description": "Code review checklist for PRs",
                "source": "github:mindclaw-skills/official@code-review",
                "sha256": "abc123",
                "verified": True,
                "tags": ["development", "review"],
                "size_bytes": 2048,
                "commit_sha": "def456",
            },
            {
                "name": "debug-guide",
                "description": "Systematic debugging methodology",
                "source": "github:mindclaw-skills/official@debug-guide",
                "sha256": "xyz789",
                "verified": False,
                "tags": ["development", "debugging"],
                "size_bytes": 3072,
                "commit_sha": "ghi012",
            },
        ],
    }


def test_index_entry_from_dict():
    entry = IndexEntry.from_dict({
        "name": "test",
        "description": "A test",
        "source": "github:user/repo@test",
        "sha256": "abc",
        "verified": True,
        "tags": ["test"],
        "size_bytes": 100,
        "commit_sha": "def",
    })
    assert entry.name == "test"
    assert entry.verified is True


@pytest.mark.asyncio
async def test_search_by_query(cache_dir, sample_index):
    client = IndexClient(
        index_url="https://example.com/index.json",
        cache_dir=cache_dir,
        cache_ttl=86400,
    )
    # Pre-populate cache
    cache_file = cache_dir / "skill-index.json"
    cache_file.write_text(json.dumps({
        "fetched_at": time.time(),
        "data": sample_index,
    }))

    results = await client.search("code review")
    assert len(results) >= 1
    assert results[0].name == "code-review"


@pytest.mark.asyncio
async def test_search_by_tag(cache_dir, sample_index):
    client = IndexClient(
        index_url="https://example.com/index.json",
        cache_dir=cache_dir,
        cache_ttl=86400,
    )
    cache_file = cache_dir / "skill-index.json"
    cache_file.write_text(json.dumps({
        "fetched_at": time.time(),
        "data": sample_index,
    }))

    results = await client.search_by_tag("debugging")
    assert len(results) == 1
    assert results[0].name == "debug-guide"


@pytest.mark.asyncio
async def test_resolve_name(cache_dir, sample_index):
    client = IndexClient(
        index_url="https://example.com/index.json",
        cache_dir=cache_dir,
        cache_ttl=86400,
    )
    cache_file = cache_dir / "skill-index.json"
    cache_file.write_text(json.dumps({
        "fetched_at": time.time(),
        "data": sample_index,
    }))

    entry = await client.resolve("code-review")
    assert entry is not None
    assert entry.sha256 == "abc123"


@pytest.mark.asyncio
async def test_resolve_unknown_name(cache_dir, sample_index):
    client = IndexClient(
        index_url="https://example.com/index.json",
        cache_dir=cache_dir,
        cache_ttl=86400,
    )
    cache_file = cache_dir / "skill-index.json"
    cache_file.write_text(json.dumps({
        "fetched_at": time.time(),
        "data": sample_index,
    }))

    entry = await client.resolve("nonexistent")
    assert entry is None


@pytest.mark.asyncio
async def test_stale_cache_used_when_offline(cache_dir, sample_index):
    client = IndexClient(
        index_url="https://example.com/index.json",
        cache_dir=cache_dir,
        cache_ttl=1,  # 1 second TTL
    )
    # Write stale cache
    cache_file = cache_dir / "skill-index.json"
    cache_file.write_text(json.dumps({
        "fetched_at": time.time() - 100,  # expired
        "data": sample_index,
    }))

    # Mock network failure
    with patch("mindclaw.skills.index_client.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.return_value = mock_instance

        results = await client.search("code")
        assert len(results) >= 1  # stale cache still works


@pytest.mark.asyncio
async def test_no_cache_and_offline(cache_dir):
    client = IndexClient(
        index_url="https://example.com/index.json",
        cache_dir=cache_dir,
        cache_ttl=86400,
    )

    with patch("mindclaw.skills.index_client.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.return_value = mock_instance

        results = await client.search("anything")
        assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_index_client.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write implementation**

Create `mindclaw/skills/index_client.py`:

```python
# input: httpx, json, pathlib, time
# output: 导出 IndexClient, IndexEntry
# pos: 技能索引客户端，负责索引拉取、本地缓存、技能搜索
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill index client: fetch, cache, and search the centralized skill index."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from loguru import logger

_CACHE_FILENAME = "skill-index.json"


@dataclass(frozen=True)
class IndexEntry:
    name: str
    description: str
    source: str
    sha256: str
    verified: bool
    tags: list[str]
    size_bytes: int
    commit_sha: str

    @classmethod
    def from_dict(cls, d: dict) -> IndexEntry:
        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            source=d.get("source", ""),
            sha256=d.get("sha256", ""),
            verified=d.get("verified", False),
            tags=d.get("tags", []),
            size_bytes=d.get("size_bytes", 0),
            commit_sha=d.get("commit_sha", ""),
        )


class IndexClient:
    """Fetch, cache, and search the centralized skill index."""

    def __init__(
        self,
        index_url: str,
        cache_dir: Path,
        cache_ttl: int = 86400,
    ) -> None:
        self._index_url = index_url
        self._cache_path = cache_dir / _CACHE_FILENAME
        self._cache_ttl = cache_ttl

    async def search(self, query: str) -> list[IndexEntry]:
        """Search skills by name or description (case-insensitive substring match)."""
        entries = await self._get_entries()
        q = query.lower()
        scored: list[tuple[int, IndexEntry]] = []
        for e in entries:
            score = 0
            if q in e.name.lower():
                score += 2
            if q in e.description.lower():
                score += 1
            if any(q in tag.lower() for tag in e.tags):
                score += 1
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        return [e for _, e in scored]

    async def search_by_tag(self, tag: str) -> list[IndexEntry]:
        """Search skills by exact tag match."""
        entries = await self._get_entries()
        t = tag.lower()
        return [e for e in entries if any(t == et.lower() for et in e.tags)]

    async def resolve(self, name: str) -> IndexEntry | None:
        """Resolve a skill name to its index entry."""
        entries = await self._get_entries()
        for e in entries:
            if e.name == name:
                return e
        return None

    async def _get_entries(self) -> list[IndexEntry]:
        """Get index entries, fetching from remote if cache is stale."""
        cached = self._read_cache()
        if cached is not None:
            fetched_at, data = cached
            if time.time() - fetched_at < self._cache_ttl:
                return self._parse_entries(data)

        # Try to fetch fresh index
        try:
            data = await self._fetch_remote()
            self._write_cache(data)
            return self._parse_entries(data)
        except Exception:
            logger.warning("Failed to fetch skill index, using cached data")
            if cached is not None:
                return self._parse_entries(cached[1])
            return []

    async def _fetch_remote(self) -> dict:
        """Fetch index.json from remote URL."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(self._index_url)
            resp.raise_for_status()
            return resp.json()

    def _read_cache(self) -> tuple[float, dict] | None:
        if not self._cache_path.exists():
            return None
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return raw["fetched_at"], raw["data"]
        except (json.JSONDecodeError, KeyError):
            return None

    def _write_cache(self, data: dict) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": time.time(), "data": data}
        self._cache_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _parse_entries(data: dict) -> list[IndexEntry]:
        return [IndexEntry.from_dict(s) for s in data.get("skills", [])]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_index_client.py -v`
Expected: PASS

- [ ] **Step 5: Update `_ARCHITECTURE.md`, commit**

```bash
git add mindclaw/skills/index_client.py tests/test_skill_index_client.py mindclaw/skills/_ARCHITECTURE.md
git commit -m "feat(skills): add index client with fetch, cache, and search"
```

---

## Chunk 4: Installer Core

### Task 5: Create installer (download, validate, install, remove, update)

**Files:**
- Create: `mindclaw/skills/installer.py`
- Create: `tests/test_skill_installer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skill_installer.py`:

```python
# input: mindclaw.skills.installer
# output: 技能安装器测试
# pos: 验证本地安装、删除、保护名称、格式校验、大小限制、force 覆盖
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindclaw.skills.installer import InstallResult, SkillInstaller


@pytest.fixture
def installer_setup(tmp_path):
    builtin_dir = tmp_path / "builtin"
    builtin_dir.mkdir()
    (builtin_dir / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: Built-in translate
        load: always
        ---

        # Translate
    """))

    user_dir = tmp_path / "user"
    user_dir.mkdir()

    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry([builtin_dir, user_dir])

    installer = SkillInstaller(
        user_skills_dir=user_dir,
        registry=registry,
        index_client=None,
        max_skill_size=8192,
    )
    return installer, registry, user_dir


@pytest.mark.asyncio
async def test_install_from_local_file(installer_setup, tmp_path):
    installer, registry, user_dir = installer_setup

    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(dedent("""\
        ---
        name: my-skill
        description: My custom skill
        load: on_demand
        ---

        # My Skill
        Do something useful.
    """))

    result = await installer.install_from_local(str(skill_file))
    assert result.success is True
    assert result.name == "my-skill"
    assert (user_dir / "my-skill.md").exists()

    # Registry should be reloaded
    assert registry.get("my-skill") is not None


@pytest.mark.asyncio
async def test_install_rejects_protected_name(installer_setup, tmp_path):
    installer, registry, user_dir = installer_setup

    skill_file = tmp_path / "translate.md"
    skill_file.write_text(dedent("""\
        ---
        name: translate
        description: Override translate
        load: on_demand
        ---

        # Override
    """))

    result = await installer.install_from_local(str(skill_file))
    assert result.success is False
    assert "protected" in result.error.lower() or "built-in" in result.error.lower()


@pytest.mark.asyncio
async def test_install_rejects_oversized(installer_setup, tmp_path):
    installer, registry, user_dir = installer_setup

    content = "---\nname: big\ndescription: Big\nload: on_demand\n---\n\n" + "x" * 9000
    skill_file = tmp_path / "big.md"
    skill_file.write_text(content)

    result = await installer.install_from_local(str(skill_file))
    assert result.success is False
    assert "size" in result.error.lower()


@pytest.mark.asyncio
async def test_install_rejects_invalid_format(installer_setup, tmp_path):
    installer, registry, user_dir = installer_setup

    skill_file = tmp_path / "bad.md"
    skill_file.write_text("# No front matter\nJust text.")

    result = await installer.install_from_local(str(skill_file))
    assert result.success is False


@pytest.mark.asyncio
async def test_install_rejects_duplicate_without_force(installer_setup, tmp_path):
    installer, registry, user_dir = installer_setup

    content = dedent("""\
        ---
        name: my-skill
        description: My skill
        load: on_demand
        ---

        # My Skill
    """)
    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(content)

    await installer.install_from_local(str(skill_file))
    result = await installer.install_from_local(str(skill_file))
    assert result.success is False
    assert "exists" in result.error.lower()


@pytest.mark.asyncio
async def test_install_allows_duplicate_with_force(installer_setup, tmp_path):
    installer, registry, user_dir = installer_setup

    content = dedent("""\
        ---
        name: my-skill
        description: My skill
        load: on_demand
        ---

        # My Skill
    """)
    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(content)

    await installer.install_from_local(str(skill_file))
    result = await installer.install_from_local(str(skill_file), force=True)
    assert result.success is True


@pytest.mark.asyncio
async def test_remove_user_skill(installer_setup, tmp_path):
    installer, registry, user_dir = installer_setup

    # First install
    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(dedent("""\
        ---
        name: my-skill
        description: My skill
        load: on_demand
        ---

        # My Skill
    """))
    await installer.install_from_local(str(skill_file))

    result = installer.remove("my-skill")
    assert result.success is True
    assert not (user_dir / "my-skill.md").exists()
    assert registry.get("my-skill") is None


def test_remove_builtin_rejected(installer_setup):
    installer, registry, user_dir = installer_setup
    result = installer.remove("translate")
    assert result.success is False
    assert "built-in" in result.error.lower()


def test_remove_nonexistent(installer_setup):
    installer, registry, user_dir = installer_setup
    result = installer.remove("nonexistent")
    assert result.success is False


@pytest.mark.asyncio
async def test_install_forces_on_demand_for_remote_always(installer_setup, tmp_path):
    """Remote skills with load: always should be forced to on_demand."""
    installer, registry, user_dir = installer_setup

    content = dedent("""\
        ---
        name: sneaky
        description: Tries to be always
        load: always
        ---

        # Sneaky
    """)

    result = await installer.install_from_bytes(
        content.encode("utf-8"),
        source="https://example.com/sneaky.md",
        is_remote=True,
    )
    assert result.success is True

    installed = registry.get("sneaky")
    assert installed is not None
    # The file on disk should have load: on_demand, not always
    file_content = (user_dir / "sneaky.md").read_text()
    assert "load: on_demand" in file_content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_installer.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write implementation**

Create `mindclaw/skills/installer.py`:

```python
# input: skills/registry.py, skills/integrity.py, skills/index_client.py, httpx
# output: 导出 SkillInstaller, InstallResult
# pos: 技能安装器核心逻辑，下载 / 校验 / 安装 / 卸载 / 更新
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill installer: download, validate, install, remove, update skills."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

from mindclaw.skills.integrity import (
    compute_sha256,
    is_safe_download_url,
    sanitize_approval_text,
    validate_skill_content,
    validate_skill_size,
)

_GITHUB_SOURCE_RE = re.compile(r"^github:([^/]+)/([^@]+)@(.+)$")


@dataclass(frozen=True)
class InstallResult:
    success: bool
    name: str = ""
    description: str = ""
    sha256: str = ""
    content: str = ""
    error: str = ""


class SkillInstaller:
    """Core logic for installing, removing, and updating skills."""

    def __init__(
        self,
        user_skills_dir: Path,
        registry,  # SkillRegistry (avoid circular import)
        index_client=None,  # IndexClient | None
        max_skill_size: int = 8192,
    ) -> None:
        self._user_dir = user_skills_dir
        self._registry = registry
        self._index_client = index_client
        self._max_size = max_skill_size

    async def install_from_local(
        self, path: str, *, force: bool = False
    ) -> InstallResult:
        """Install a skill from a local file path."""
        file_path = Path(path).resolve()
        if not file_path.exists():
            return InstallResult(success=False, error=f"File not found: {path}")
        if not file_path.suffix == ".md":
            return InstallResult(success=False, error="Skill file must be a .md file")

        content_bytes = file_path.read_bytes()
        return await self.install_from_bytes(
            content_bytes, source=str(file_path), is_remote=False, force=force
        )

    async def install_from_url(self, url: str, *, force: bool = False) -> InstallResult:
        """Install a skill from an HTTPS URL."""
        if not is_safe_download_url(url):
            return InstallResult(
                success=False, error="URL rejected: must be HTTPS and not target private addresses"
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                content_bytes = resp.content
        except Exception as e:
            return InstallResult(success=False, error=f"Download failed: {e}")

        return await self.install_from_bytes(
            content_bytes, source=url, is_remote=True, force=force
        )

    async def install_from_github(
        self, source: str, *, force: bool = False
    ) -> InstallResult:
        """Install from github:user/repo@skill-name syntax."""
        match = _GITHUB_SOURCE_RE.match(source)
        if not match:
            return InstallResult(
                success=False,
                error=f"Invalid GitHub source format: {source}. "
                       "Expected: github:user/repo@skill-name",
            )

        user, repo, skill_name = match.group(1), match.group(2), match.group(3)

        # Check index for commit SHA
        commit_ref = "HEAD"
        expected_sha256 = None
        if self._index_client:
            entry = await self._index_client.resolve(skill_name)
            if entry and entry.commit_sha:
                commit_ref = entry.commit_sha
                expected_sha256 = entry.sha256

        url = (
            f"https://raw.githubusercontent.com/{user}/{repo}"
            f"/{commit_ref}/skills/{skill_name}.md"
        )

        if not is_safe_download_url(url):
            return InstallResult(success=False, error="GitHub URL failed SSRF check")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                content_bytes = resp.content
        except Exception as e:
            return InstallResult(success=False, error=f"Download failed: {e}")

        # SHA256 check against index
        if expected_sha256:
            actual = compute_sha256(content_bytes)
            if actual != expected_sha256:
                return InstallResult(
                    success=False,
                    error=f"SHA256 mismatch: expected {expected_sha256[:16]}..., "
                          f"got {actual[:16]}... Content may have been tampered with.",
                )

        return await self.install_from_bytes(
            content_bytes, source=source, is_remote=True, force=force
        )

    async def install_by_name(self, name: str, *, force: bool = False) -> InstallResult:
        """Install a skill by name from the index."""
        if not self._index_client:
            return InstallResult(
                success=False, error="No index configured. Use URL or file path instead."
            )

        entry = await self._index_client.resolve(name)
        if not entry:
            return InstallResult(success=False, error=f"Skill '{name}' not found in index")

        # Route to appropriate install method
        if entry.source.startswith("github:"):
            return await self.install_from_github(entry.source, force=force)
        elif entry.source.startswith("https://"):
            return await self.install_from_url(entry.source, force=force)
        else:
            return InstallResult(
                success=False, error=f"Unsupported source format in index: {entry.source}"
            )

    async def install_from_bytes(
        self,
        content_bytes: bytes,
        *,
        source: str = "",
        is_remote: bool = False,
        force: bool = False,
        expected_sha256: str = "",
    ) -> InstallResult:
        """Core install logic: validate and write to user skills directory."""
        # Size check
        if not validate_skill_size(content_bytes, max_size=self._max_size):
            return InstallResult(
                success=False,
                error=f"Skill exceeds size limit ({len(content_bytes)} > {self._max_size} bytes)",
            )

        content_str = content_bytes.decode("utf-8", errors="replace")

        # Format validation
        validation = validate_skill_content(content_str)
        if not validation.valid:
            return InstallResult(success=False, error=validation.error)

        name = validation.name
        sha256 = compute_sha256(content_bytes)

        # SHA256 check for remote sources
        if expected_sha256 and sha256 != expected_sha256:
            return InstallResult(
                success=False,
                error=f"SHA256 mismatch: expected {expected_sha256[:16]}..., got {sha256[:16]}...",
            )

        # Protected name check
        if name in self._registry.protected_names:
            return InstallResult(
                success=False,
                error=f"Cannot install skill '{name}': name is protected (built-in skill)",
            )

        # Duplicate check
        target_file = self._user_dir / f"{name}.md"
        if target_file.exists() and not force:
            return InstallResult(
                success=False,
                error=f"Skill '{name}' already exists in user directory. Use --force to overwrite.",
            )

        # Force load: on_demand for remote always skills
        if is_remote and validation.load == "always":
            logger.warning(
                f"Remote skill '{name}' declares load: always, forcing to on_demand"
            )
            content_str = content_str.replace("load: always", "load: on_demand", 1)
            content_bytes = content_str.encode("utf-8")
            sha256 = compute_sha256(content_bytes)

        # Inject source + sha256 metadata into front-matter
        content_str = self._inject_metadata(content_str, source=source, sha256=sha256)

        # Write to user skills directory
        self._user_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content_str, encoding="utf-8")

        # Reload registry
        self._registry.reload()

        logger.info(f"Skill '{name}' installed from {source or 'local'}")

        return InstallResult(
            success=True,
            name=name,
            description=validation.description,
            sha256=sha256,
            content=content_str,
        )

    def remove(self, name: str) -> InstallResult:
        """Remove a user-installed skill."""
        # Cannot remove built-in
        if name in self._registry.protected_names:
            return InstallResult(
                success=False,
                error=f"Cannot remove built-in skill '{name}'.",
            )

        target_file = self._user_dir / f"{name}.md"
        if not target_file.exists():
            return InstallResult(
                success=False,
                error=f"Skill '{name}' not found in user skills directory.",
            )

        target_file.unlink()
        self._registry.reload()
        logger.info(f"Skill '{name}' removed")

        return InstallResult(success=True, name=name)

    async def update(self, name: str) -> InstallResult:
        """Update a skill by re-downloading from its recorded source."""
        skill = self._registry.get(name)
        if not skill:
            return InstallResult(success=False, error=f"Skill '{name}' not found")

        if skill.source_layer == "builtin":
            return InstallResult(
                success=False, error=f"Cannot update built-in skill '{name}'"
            )

        # Read source from file front-matter
        text = skill.file_path.read_text(encoding="utf-8")
        source = self._extract_field(text, "source")
        if not source:
            return InstallResult(
                success=False,
                error=f"Skill '{name}' has no recorded source. Re-install manually.",
            )

        return await self.install_from_source(source, force=True)

    async def install_from_source(
        self, source: str, *, force: bool = False
    ) -> InstallResult:
        """Route to appropriate install method based on source format."""
        if source.startswith("github:"):
            return await self.install_from_github(source, force=force)
        elif source.startswith("https://"):
            return await self.install_from_url(source, force=force)
        elif source.startswith("/") or source.startswith("."):
            return await self.install_from_local(source, force=force)
        else:
            # Try as index name
            return await self.install_by_name(source, force=force)

    def get_preview(self, content_bytes: bytes) -> str:
        """Generate a preview string for approval display."""
        content = content_bytes.decode("utf-8", errors="replace")
        validation = validate_skill_content(content)
        sha256 = compute_sha256(content_bytes)

        if not validation.valid:
            return f"INVALID SKILL: {validation.error}"

        preview = (
            f"Name: {sanitize_approval_text(validation.name)}\n"
            f"Description: {sanitize_approval_text(validation.description)}\n"
            f"Load: {validation.load}\n"
            f"SHA256: {sha256}\n"
            f"Size: {len(content_bytes)} bytes\n"
            f"---\n"
            f"{sanitize_approval_text(content[:2000])}"
        )
        return preview

    @staticmethod
    def _inject_metadata(content: str, *, source: str, sha256: str) -> str:
        """Add source and sha256 fields to YAML front-matter."""
        # Find end of front-matter
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            return content

        fm = match.group(1)
        rest = content[match.end():]

        # Remove existing source/sha256 lines
        lines = [
            line for line in fm.strip().splitlines()
            if not line.strip().startswith("source:") and not line.strip().startswith("sha256:")
        ]
        if source:
            lines.append(f"source: {source}")
        lines.append(f"sha256: {sha256}")

        return f"---\n" + "\n".join(lines) + "\n---\n\n" + rest

    @staticmethod
    def _extract_field(text: str, field_name: str) -> str:
        """Extract a field value from YAML front-matter."""
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not match:
            return ""
        for line in match.group(1).strip().splitlines():
            if line.strip().startswith(f"{field_name}:"):
                return line.split(":", 1)[1].strip()
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_installer.py -v`
Expected: PASS

- [ ] **Step 5: Update `_ARCHITECTURE.md`, commit**

```bash
git add mindclaw/skills/installer.py tests/test_skill_installer.py mindclaw/skills/_ARCHITECTURE.md
git commit -m "feat(skills): add installer with local/URL/GitHub/index sources"
```

---

## Chunk 5: LLM Tools + CLI Commands + Integration

### Task 6: Create LLM skill tools

**Files:**
- Create: `mindclaw/tools/skill_tools.py`
- Create: `tests/test_skill_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skill_tools.py`:

```python
# input: mindclaw.tools.skill_tools
# output: LLM 技能工具测试
# pos: 验证 skill_search/list/show/install/remove 工具
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindclaw.tools.base import RiskLevel


@pytest.fixture
def tool_setup(tmp_path):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: Built-in translate
        load: always
        ---

        # Translate
    """))

    user = tmp_path / "user"
    user.mkdir()

    from mindclaw.skills.registry import SkillRegistry
    from mindclaw.skills.installer import SkillInstaller

    registry = SkillRegistry([builtin, user])
    installer = SkillInstaller(
        user_skills_dir=user,
        registry=registry,
        index_client=None,
        max_skill_size=8192,
    )
    return registry, installer


def test_skill_list_tool_risk_level(tool_setup):
    from mindclaw.tools.skill_tools import SkillListTool

    registry, installer = tool_setup
    tool = SkillListTool(registry=registry)
    assert tool.risk_level == RiskLevel.SAFE


def test_skill_search_tool_risk_level(tool_setup):
    from mindclaw.tools.skill_tools import SkillSearchTool

    tool = SkillSearchTool(index_client=None)
    assert tool.risk_level == RiskLevel.MODERATE


def test_skill_install_tool_risk_level(tool_setup):
    from mindclaw.tools.skill_tools import SkillInstallTool

    registry, installer = tool_setup
    tool = SkillInstallTool(installer=installer, registry=registry)
    assert tool.risk_level == RiskLevel.DANGEROUS


def test_skill_remove_tool_risk_level(tool_setup):
    from mindclaw.tools.skill_tools import SkillRemoveTool

    registry, installer = tool_setup
    tool = SkillRemoveTool(installer=installer)
    assert tool.risk_level == RiskLevel.DANGEROUS


@pytest.mark.asyncio
async def test_skill_list_tool_execute(tool_setup):
    from mindclaw.tools.skill_tools import SkillListTool

    registry, installer = tool_setup
    tool = SkillListTool(registry=registry)
    result = await tool.execute({})
    assert "translate" in result
    assert "builtin" in result


@pytest.mark.asyncio
async def test_skill_show_tool_execute(tool_setup):
    from mindclaw.tools.skill_tools import SkillShowTool

    registry, installer = tool_setup
    tool = SkillShowTool(registry=registry)
    result = await tool.execute({"name": "translate"})
    assert "translate" in result.lower()


@pytest.mark.asyncio
async def test_skill_show_tool_unknown(tool_setup):
    from mindclaw.tools.skill_tools import SkillShowTool

    registry, installer = tool_setup
    tool = SkillShowTool(registry=registry)
    result = await tool.execute({"name": "nonexistent"})
    assert "not found" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_tools.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write implementation**

Create `mindclaw/tools/skill_tools.py`:

```python
# input: tools/base.py, skills/installer.py, skills/registry.py, skills/index_client.py
# output: 导出 SkillSearchTool, SkillShowTool, SkillInstallTool, SkillRemoveTool, SkillListTool
# pos: LLM 可调用的技能管理工具集，对话中搜索/安装/删除技能
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""LLM-accessible tools for skill management: search, show, install, remove, list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from mindclaw.tools.base import RiskLevel, Tool

if TYPE_CHECKING:
    from mindclaw.skills.index_client import IndexClient
    from mindclaw.skills.installer import SkillInstaller
    from mindclaw.skills.registry import SkillRegistry


class SkillSearchTool(Tool):
    name = "skill_search"
    description = "Search the skill index for available skills to install"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (name, description, or tag)"},
        },
        "required": ["query"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, index_client: IndexClient | None) -> None:
        self._client = index_client

    async def execute(self, params: dict) -> str:
        if not self._client:
            return "Error: Skill index not configured."
        query = params["query"]
        results = await self._client.search(query)
        if not results:
            return f"No skills found matching '{query}'."
        lines = []
        for entry in results[:10]:
            verified = "[verified]" if entry.verified else "[unverified]"
            lines.append(
                f"- {entry.name}: {entry.description} {verified}\n"
                f"  Source: {entry.source} | Tags: {', '.join(entry.tags)}"
            )
        return f"Found {len(results)} skill(s):\n" + "\n".join(lines)


class SkillShowTool(Tool):
    name = "skill_show"
    description = "Show details and full content of an installed skill"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name to show"},
        },
        "required": ["name"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    async def execute(self, params: dict) -> str:
        name = params["name"]
        skill = self._registry.get(name)
        if not skill:
            return f"Skill '{name}' not found."
        return (
            f"Name: {skill.name}\n"
            f"Description: {skill.description}\n"
            f"Load: {skill.load}\n"
            f"Source: {skill.source_layer}\n"
            f"File: {skill.file_path}\n"
            f"---\n"
            f"{skill.content}"
        )


class SkillInstallTool(Tool):
    name = "skill_install"
    description = (
        "Install a skill from a source (local file, URL, github:user/repo@name, or index name). "
        "This is a DANGEROUS operation that requires user approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": (
                    "Skill source: local path, HTTPS URL, "
                    "github:user/repo@skill-name, or skill name from index"
                ),
            },
            "force": {
                "type": "boolean",
                "description": "Force overwrite if skill already exists (default: false)",
            },
        },
        "required": ["source"],
    }
    risk_level = RiskLevel.DANGEROUS

    def __init__(self, installer: SkillInstaller, registry: SkillRegistry) -> None:
        self._installer = installer
        self._registry = registry

    async def execute(self, params: dict) -> str:
        source = params["source"]
        force = params.get("force", False)

        result = await self._installer.install_from_source(source, force=force)

        if not result.success:
            return f"Installation failed: {result.error}"

        return (
            f"Skill '{result.name}' installed successfully.\n"
            f"Description: {result.description}\n"
            f"SHA256: {result.sha256}\n"
            f"---\n"
            f"Full skill content (available for immediate use):\n\n"
            f"{result.content}"
        )


class SkillRemoveTool(Tool):
    name = "skill_remove"
    description = (
        "Remove a user-installed skill. Cannot remove built-in skills. "
        "This is a DANGEROUS operation that requires user approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the skill to remove"},
        },
        "required": ["name"],
    }
    risk_level = RiskLevel.DANGEROUS

    def __init__(self, installer: SkillInstaller) -> None:
        self._installer = installer

    async def execute(self, params: dict) -> str:
        name = params["name"]
        result = self._installer.remove(name)
        if not result.success:
            return f"Remove failed: {result.error}"
        return f"Skill '{name}' removed successfully."


class SkillListTool(Tool):
    name = "skill_list"
    description = "List all available skills with their source layer (builtin/project/user)"
    parameters = {"type": "object", "properties": {}}
    risk_level = RiskLevel.SAFE

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    async def execute(self, params: dict) -> str:
        skills = self._registry.skills
        if not skills:
            return "No skills installed."
        lines = []
        for s in sorted(skills, key=lambda x: x.name):
            lines.append(
                f"- {s.name}: {s.description} [{s.source_layer}] (load: {s.load})"
            )
        return f"{len(skills)} skill(s):\n" + "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/test_skill_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mindclaw/tools/skill_tools.py tests/test_skill_tools.py
git commit -m "feat(tools): add LLM skill management tools (search/show/install/remove/list)"
```

---

### Task 7: Create CLI skill subcommands

**Files:**
- Create: `mindclaw/cli/skill_commands.py`
- Modify: `mindclaw/cli/commands.py`

- [ ] **Step 1: Write implementation**

Create `mindclaw/cli/skill_commands.py`:

```python
# input: typer, skills/installer.py, skills/index_client.py, skills/registry.py, config/loader.py
# output: 导出 skill_app (Typer 子应用)
# pos: CLI 技能管理子命令组，mindclaw skill install/search/list/remove/show/update
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""CLI subcommands for skill management: install, search, list, remove, show, update."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from mindclaw.config.loader import load_config

skill_app = typer.Typer(name="skill", help="Manage MindClaw skills")
console = Console()


def _build_components(config_path: Path | None = None):
    """Build installer, registry, and index client from config."""
    from mindclaw.skills.index_client import IndexClient
    from mindclaw.skills.installer import SkillInstaller
    from mindclaw.skills.registry import SkillRegistry

    cfg = load_config(config_path)
    data_dir = Path(cfg.knowledge.data_dir)

    registry = SkillRegistry([
        Path(__file__).resolve().parent.parent / "skills",  # builtin
        data_dir / "plugins" / "skills",  # project
        data_dir / "skills",  # user
    ])

    index_client = IndexClient(
        index_url=cfg.skills.index_url,
        cache_dir=data_dir,
        cache_ttl=cfg.skills.cache_ttl,
    )

    installer = SkillInstaller(
        user_skills_dir=data_dir / "skills",
        registry=registry,
        index_client=index_client,
        max_skill_size=cfg.skills.max_skill_size,
    )

    return installer, registry, index_client


@skill_app.command("install")
def install(
    source: str = typer.Argument(help="Skill source: file path, URL, github:user/repo@name, or index name"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing skill"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Install a skill from a source."""
    installer, registry, _ = _build_components(config)
    result = asyncio.run(_install(installer, source, force, yes))

    if result.success:
        console.print(f"[green]Skill '{result.name}' installed successfully.[/green]")
        console.print(f"  SHA256: {result.sha256}")
    else:
        console.print(f"[red]Installation failed:[/red] {result.error}")
        raise typer.Exit(1)


async def _install(installer, source: str, force: bool, yes: bool):
    """Async install with optional confirmation."""
    from mindclaw.skills.installer import InstallResult

    # For remote sources, preview before confirming
    if not yes and (source.startswith("https://") or source.startswith("github:")):
        console.print(f"Fetching skill from: {source}")
        console.print("Use --yes to skip confirmation.")

    return await installer.install_from_source(source, force=force)


@skill_app.command("remove")
def remove(
    name: str = typer.Argument(help="Skill name to remove"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Remove a user-installed skill."""
    installer, _, _ = _build_components(config)
    result = installer.remove(name)

    if result.success:
        console.print(f"[green]Skill '{name}' removed.[/green]")
    else:
        console.print(f"[red]Remove failed:[/red] {result.error}")
        raise typer.Exit(1)


@skill_app.command("list")
def list_skills(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """List all installed skills."""
    _, registry, _ = _build_components(config)
    skills = sorted(registry.skills, key=lambda s: s.name)

    if not skills:
        console.print("No skills installed.")
        return

    for s in skills:
        layer_color = {"builtin": "blue", "project": "yellow", "user": "green"}.get(
            s.source_layer, "white"
        )
        console.print(
            f"  [{layer_color}]{s.source_layer:>8}[/{layer_color}]  "
            f"{s.name}: {s.description} (load: {s.load})"
        )


@skill_app.command("show")
def show(
    name: str = typer.Argument(help="Skill name to show"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Show details of a skill."""
    _, registry, _ = _build_components(config)
    skill = registry.get(name)

    if not skill:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"Name: {skill.name}")
    console.print(f"Description: {skill.description}")
    console.print(f"Load: {skill.load}")
    console.print(f"Source: {skill.source_layer}")
    console.print(f"File: {skill.file_path}")
    console.print("---")
    console.print(skill.content)


@skill_app.command("search")
def search(
    query: str = typer.Argument(help="Search query"),
    tag: str = typer.Option(None, "--tag", "-t", help="Search by tag"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Search the skill index."""
    _, _, index_client = _build_components(config)
    results = asyncio.run(_search(index_client, query, tag))

    if not results:
        console.print("No skills found.")
        return

    for entry in results[:10]:
        verified = "[green]verified[/green]" if entry.verified else "[yellow]unverified[/yellow]"
        console.print(f"  {entry.name}: {entry.description} ({verified})")
        console.print(f"    Source: {entry.source}")
        console.print(f"    Tags: {', '.join(entry.tags)}")
        console.print()


async def _search(index_client, query: str, tag: str | None):
    if tag:
        return await index_client.search_by_tag(tag)
    return await index_client.search(query)


@skill_app.command("update")
def update(
    name: str = typer.Argument(None, help="Skill name to update (omit for --all)"),
    all_skills: bool = typer.Option(False, "--all", help="Update all installed skills"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Update installed skills from their sources."""
    installer, registry, _ = _build_components(config)

    if all_skills:
        user_skills = [s for s in registry.skills if s.source_layer == "user"]
        if not user_skills:
            console.print("No user-installed skills to update.")
            return
        for skill in user_skills:
            result = asyncio.run(installer.update(skill.name))
            status = "[green]OK[/green]" if result.success else f"[red]FAIL: {result.error}[/red]"
            console.print(f"  {skill.name}: {status}")
    elif name:
        result = asyncio.run(installer.update(name))
        if result.success:
            console.print(f"[green]Skill '{name}' updated.[/green]")
        else:
            console.print(f"[red]Update failed:[/red] {result.error}")
            raise typer.Exit(1)
    else:
        console.print("Specify a skill name or use --all.")
        raise typer.Exit(1)
```

- [ ] **Step 2: Register in commands.py**

Add to `mindclaw/cli/commands.py` after the imports:

```python
from mindclaw.cli.skill_commands import skill_app

app.add_typer(skill_app, name="skill")
```

Update the `# input:` header comment to include `cli/skill_commands.py`.

- [ ] **Step 3: Verify CLI works**

Run: `cd /Users/wzb/Documents/mindclaw && python -m mindclaw.cli.commands skill --help`
Expected: Shows skill subcommands (install, remove, list, show, search, update)

- [ ] **Step 4: Commit**

```bash
git add mindclaw/cli/skill_commands.py mindclaw/cli/commands.py
git commit -m "feat(cli): add skill subcommand group (install/search/list/remove/show/update)"
```

---

### Task 8: Update app.py and context.py for integration

**Files:**
- Modify: `mindclaw/app.py:77-85` (multi-dir registry + tool registration)
- Modify: `mindclaw/orchestrator/context.py:84-86` (prompt injection isolation)
- Modify: `tests/test_context_builder_skills.py`

- [ ] **Step 1: Update app.py**

In `mindclaw/app.py`, change the Skills section (lines 77-85):

```python
# Skills
data_dir = Path(config.knowledge.data_dir)
self.skill_registry = SkillRegistry([
    Path(__file__).parent / "skills",                  # builtin
    data_dir / "plugins" / "skills",                   # project
    data_dir / "skills",                               # user
])
```

Add imports at the top:
```python
from mindclaw.skills.index_client import IndexClient
from mindclaw.skills.installer import SkillInstaller
```

After `self.skill_registry`:
```python
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
```

In `_register_tools()`, add after cron tools:

```python
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
```

- [ ] **Step 2: Update context.py for prompt injection isolation**

In `mindclaw/orchestrator/context.py`, modify the always-skills injection in `_build_base_prompt()` (line 84-86):

```python
always_content = self._skill_registry.get_always_skills_content()
if always_content:
    parts.append(f"\n## Active Skills\n{always_content}")

# Installed (non-builtin) skills get isolation wrapper
for skill in self._skill_registry.skills:
    if skill.source_layer != "builtin" and skill.load == "always":
        # This should not happen (remote always is forced to on_demand)
        # but defense in depth
        logger.warning(
            f"Non-builtin skill '{skill.name}' has load=always, skipping"
        )
```

Actually, the simpler approach: modify `get_always_skills_content()` in registry to only return builtin always-skills. But that changes registry semantics. Better: handle in context.py where installed on_demand skills get the isolation wrapper when loaded by the LLM via read_file. The system prompt summary already uses `get_skill_summaries()` which includes all skills.

The key change is that when non-builtin skill content appears in the prompt, it should be wrapped. Since on_demand skills are loaded via `read_file` (the LLM reads the .md file directly), the isolation happens at that point. The context builder just needs to ensure that if somehow a non-builtin always skill exists, it's wrapped:

Replace lines 84-86 with:

```python
always_content = self._skill_registry.get_always_skills_content()
if always_content:
    parts.append(f"\n## Active Skills\n{always_content}")
```

This stays the same because remote skills are forced to `on_demand` by the installer, so `get_always_skills_content()` only returns builtin content. No change needed here.

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/wzb/Documents/mindclaw && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add mindclaw/app.py mindclaw/orchestrator/context.py
git commit -m "feat(app): integrate skill installer and tools into MindClawApp"
```

---

### Task 9: Update documentation

**Files:**
- Modify: `mindclaw/skills/_ARCHITECTURE.md`
- Modify: `mindclaw/tools/_ARCHITECTURE.md` (if exists)
- Modify: `mindclaw/cli/_ARCHITECTURE.md` (if exists)
- Modify: `CLAUDE.md`
- Modify: `docs/plans/2026-03-06-mindclaw-prd.md` (PRD alignment)

- [ ] **Step 1: Update _ARCHITECTURE.md files**

Update `mindclaw/skills/_ARCHITECTURE.md`:

```markdown
> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

技能层 - Markdown 技能文件 + SkillRegistry 多目录注册中心 + 安装系统，LLM 自主路由选择技能。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `registry.py` | 核心 | SkillRegistry 多目录扫描，原子重载，保护名称集合 |
| `installer.py` | 核心 | 技能安装/卸载/更新，支持本地/URL/GitHub/索引四种源 |
| `index_client.py` | 核心 | 集中索引拉取、本地缓存(TTL 24h)、技能搜索 |
| `integrity.py` | 安全 | SHA256 校验、SSRF 过滤、格式验证、大小限制 |
| `summarize.md` | 示例技能 | 文章总结技能 (on_demand) |
| `translate.md` | 示例技能 | 翻译技能 (on_demand) |
```

- [ ] **Step 2: Update PRD section 4.10 to cover skill installation**

Add skill installation capabilities to the relevant PRD section.

- [ ] **Step 3: Update CLAUDE.md project structure**

Add `skills/installer.py`, `skills/index_client.py`, `skills/integrity.py`, `tools/skill_tools.py`, `cli/skill_commands.py` to the project structure section.

- [ ] **Step 4: Commit**

```bash
git add mindclaw/skills/_ARCHITECTURE.md CLAUDE.md docs/plans/2026-03-06-mindclaw-prd.md
git commit -m "docs: update architecture docs and PRD for skill installation system"
```

---

## Summary

| Chunk | Tasks | Files Created | Files Modified |
|-------|-------|--------------|----------------|
| 1: Config + Integrity | 1-2 | `integrity.py`, `test_skills_config.py`, `test_skill_integrity.py` | `schema.py` |
| 2: Registry Multi-Dir | 3 | - | `registry.py`, `test_skill_registry.py` |
| 3: Index Client | 4 | `index_client.py`, `test_skill_index_client.py` | - |
| 4: Installer Core | 5 | `installer.py`, `test_skill_installer.py` | - |
| 5: Tools + CLI + Integration | 6-9 | `skill_tools.py`, `skill_commands.py`, `test_skill_tools.py` | `app.py`, `commands.py`, `context.py`, docs |

Total: **7 new files** + **5 new test files** + **7 modified files** = **9 commits**

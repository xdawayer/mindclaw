# input: typer, skills/installer.py, skills/index_client.py, skills/registry.py, config/loader.py
# output: 导出 skill_app (Typer 子应用), _build_components
# pos: CLI 技能管理子命令组，mindclaw skill install/search/list/remove/show/update
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Typer sub-application for managing MindClaw skills from the CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer
from rich.console import Console
from rich.table import Table

from mindclaw.config.schema import MindClawConfig

if TYPE_CHECKING:
    from mindclaw.skills.index_client import IndexClient
    from mindclaw.skills.installer import SkillInstaller
    from mindclaw.skills.registry import SkillRegistry

skill_app = typer.Typer(name="skill", help="Manage MindClaw skills")
console = Console()

# Layer → Rich colour mapping
_LAYER_COLOUR = {
    "builtin": "blue",
    "project": "yellow",
    "user": "green",
}
_DEFAULT_COLOUR = "white"


def _build_components(
    cfg: MindClawConfig,
    user_skills_dir: Path,
) -> tuple["SkillRegistry", "IndexClient", "SkillInstaller"]:
    """Construct SkillRegistry, IndexClient, and SkillInstaller from config.

    Returns (registry, index_client, installer).
    The builtin skills directory is derived from the package location so
    it never depends on run-time cwd.
    """
    from mindclaw.skills.index_client import IndexClient
    from mindclaw.skills.installer import SkillInstaller
    from mindclaw.skills.registry import SkillRegistry

    builtin_dir = Path(__file__).resolve().parent.parent / "skills"
    project_dir = Path(cfg.knowledge.data_dir).resolve() / "project_skills"

    registry = SkillRegistry([builtin_dir, project_dir, user_skills_dir])

    cache_dir = user_skills_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    index_client = IndexClient(
        index_url=cfg.skills.index_url,
        cache_dir=cache_dir,
        cache_ttl=float(cfg.skills.cache_ttl),
    )

    installer = SkillInstaller(
        user_skills_dir=user_skills_dir,
        registry=registry,
        index_client=index_client,
        max_skill_size=cfg.skills.max_skill_size,
    )

    return registry, index_client, installer


def _load_cfg_and_dirs(config: Optional[Path]) -> tuple[MindClawConfig, Path]:
    """Load config and resolve user_skills_dir. Returns (cfg, user_skills_dir)."""
    from mindclaw.config.loader import load_config

    cfg = load_config(config)
    user_skills_dir = Path(cfg.knowledge.data_dir) / "skills"
    user_skills_dir.mkdir(parents=True, exist_ok=True)
    return cfg, user_skills_dir


# ---------------------------------------------------------------------------
# skill list
# ---------------------------------------------------------------------------

@skill_app.command("list")
def skill_list(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """List all installed skills (builtin, project, and user layers)."""
    cfg, user_skills_dir = _load_cfg_and_dirs(config)
    registry, _, _ = _build_components(cfg, user_skills_dir)

    skills = registry.skills
    if not skills:
        console.print("No skills installed.")
        return

    table = Table(title="Installed Skills", show_header=True, header_style="bold")
    table.add_column("Name", style="bold")
    table.add_column("Layer")
    table.add_column("Load")
    table.add_column("Description")

    for skill in sorted(skills, key=lambda s: (s.source_layer, s.name)):
        colour = _LAYER_COLOUR.get(skill.source_layer, _DEFAULT_COLOUR)
        layer_text = f"[{colour}]{skill.source_layer}[/{colour}]"
        table.add_row(str(skill.name), layer_text, str(skill.load), str(skill.description))

    console.print(table)


# ---------------------------------------------------------------------------
# skill show
# ---------------------------------------------------------------------------

@skill_app.command("show")
def skill_show(
    name: str = typer.Argument(help="Skill name to display"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Show detailed information about a skill."""
    cfg, user_skills_dir = _load_cfg_and_dirs(config)
    registry, _, _ = _build_components(cfg, user_skills_dir)

    skill = registry.get(name)
    if skill is None:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        raise typer.Exit(1)

    colour = _LAYER_COLOUR.get(skill.source_layer, _DEFAULT_COLOUR)
    console.print(f"[bold]Name:[/bold]        {skill.name}")
    console.print(f"[bold]Description:[/bold] {skill.description}")
    console.print(
        f"[bold]Layer:[/bold]       [{colour}]{skill.source_layer}[/{colour}]"
    )
    console.print(f"[bold]Load:[/bold]        {skill.load}")
    console.print(f"[bold]File:[/bold]        {skill.file_path}")
    if skill.content:
        console.rule("Content")
        console.print(skill.content)


# ---------------------------------------------------------------------------
# skill install
# ---------------------------------------------------------------------------

@skill_app.command("install")
def skill_install(
    source: str = typer.Argument(
        help="Local path, https:// URL, github:user/repo@ref, or index name"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite if skill already exists"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Install a skill from a local path, URL, GitHub ref, or the skill index."""
    cfg, user_skills_dir = _load_cfg_and_dirs(config)
    registry, index_client, installer = _build_components(cfg, user_skills_dir)

    if not yes:
        confirm = typer.confirm(f"Install skill from '{source}'?", default=True)
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit(0)

    result = asyncio.run(installer.install_from_source(source, force=force))

    if result.success:
        console.print(
            f"[green]Installed skill '{result.name}'[/green] — {result.description}"
        )
        if result.sha256:
            console.print(f"  SHA256: {result.sha256}")
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# skill remove
# ---------------------------------------------------------------------------

@skill_app.command("remove")
def skill_remove(
    name: str = typer.Argument(help="Skill name to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Remove a user-installed skill by name."""
    if not yes:
        confirm = typer.confirm(f"Remove skill '{name}'?", default=False)
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit(0)

    cfg, user_skills_dir = _load_cfg_and_dirs(config)
    _, _, installer = _build_components(cfg, user_skills_dir)

    result = installer.remove(name)

    if result.success:
        console.print(f"[green]Removed skill '{result.name}'.[/green]")
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# skill search
# ---------------------------------------------------------------------------

@skill_app.command("search")
def skill_search(
    query: str = typer.Argument(default="", help="Search query (empty = list all)"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by exact tag"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Search the remote skill index by keyword or tag."""
    cfg, user_skills_dir = _load_cfg_and_dirs(config)
    _, index_client, _ = _build_components(cfg, user_skills_dir)

    if tag:
        entries = asyncio.run(index_client.search_by_tag(tag))
    else:
        entries = asyncio.run(index_client.search(query))

    if not entries:
        console.print("No skills found.")
        return

    table = Table(title="Skill Index Results", show_header=True, header_style="bold")
    table.add_column("Name", style="bold")
    table.add_column("Verified")
    table.add_column("Tags")
    table.add_column("Description")

    for entry in entries:
        verified = "[green]yes[/green]" if entry.verified else "[dim]no[/dim]"
        tags_str = ", ".join(entry.tags) if entry.tags else ""
        table.add_row(entry.name, verified, tags_str, entry.description)

    console.print(table)


# ---------------------------------------------------------------------------
# skill update
# ---------------------------------------------------------------------------

@skill_app.command("update")
def skill_update(
    name: Optional[str] = typer.Argument(default=None, help="Skill name to update"),
    update_all: bool = typer.Option(
        False, "--all", help="Update all user-installed skills"
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Update a skill to the latest version from its recorded source."""
    cfg, user_skills_dir = _load_cfg_and_dirs(config)
    registry, _, installer = _build_components(cfg, user_skills_dir)

    if update_all:
        user_skills = [s for s in registry.skills if s.source_layer == "user"]
        if not user_skills:
            console.print("No user-installed skills to update.")
            return
        for skill in user_skills:
            _do_update(installer, skill.name)
        return

    if not name:
        console.print("[red]Error:[/red] Provide a skill name or use --all.")
        raise typer.Exit(1)

    _do_update(installer, name)


def _do_update(installer: "SkillInstaller", name: str) -> None:
    """Run installer.update(name) and print result."""
    result = asyncio.run(installer.update(name))
    if result.success:
        console.print(f"[green]Updated skill '{result.name}'.[/green]")
    else:
        console.print(f"[red]Error updating '{name}':[/red] {result.error}")
        raise typer.Exit(1)

# input: typer, app.py, config/loader.py, security/crypto.py
# output: 导出 app (Typer 应用)
# pos: CLI 入口，chat/serve/secret 命令
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from mindclaw.config.loader import load_config

app = typer.Typer(name="mindclaw", help="MindClaw - Personal AI Assistant")
console = Console()


@app.command()
def chat(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Start an interactive CLI chat session."""
    from mindclaw.app import MindClawApp

    cfg = load_config(config)
    mindclaw_app = MindClawApp(cfg)
    asyncio.run(mindclaw_app.run(["cli"]))


@app.command()
def serve(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Start Gateway + remote channels (Telegram, etc.)."""
    from mindclaw.app import MindClawApp

    cfg = load_config(config)
    mindclaw_app = MindClawApp(cfg)
    asyncio.run(mindclaw_app.run(["gateway", "telegram"]))


@app.command("secret-set")
def secret_set(
    name: str = typer.Argument(help="Secret name"),
    value: str = typer.Argument(help="Secret value"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Store an encrypted secret."""
    from mindclaw.security.crypto import SecretStore

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    store = SecretStore(
        store_path=data_dir / "secrets.enc",
        master_key_path=data_dir / "master.key",
    )
    store.init_or_load_key()
    store.set(name, value)
    console.print(f"Secret '{name}' stored.")


@app.command("secret-list")
def secret_list(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """List all stored secret names."""
    from mindclaw.security.crypto import SecretStore

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    store = SecretStore(
        store_path=data_dir / "secrets.enc",
        master_key_path=data_dir / "master.key",
    )
    store.init_or_load_key()
    keys = store.list_keys()
    if not keys:
        console.print("No secrets stored.")
    else:
        for k in keys:
            console.print(f"  {k}")


@app.command("secret-delete")
def secret_delete(
    name: str = typer.Argument(help="Secret name to delete"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Delete a stored secret."""
    from mindclaw.security.crypto import SecretStore

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    store = SecretStore(
        store_path=data_dir / "secrets.enc",
        master_key_path=data_dir / "master.key",
    )
    store.init_or_load_key()
    store.delete(name)
    console.print(f"Secret '{name}' deleted.")


@app.command()
def version() -> None:
    """Show MindClaw version."""
    from mindclaw import __version__

    console.print(f"MindClaw v{__version__}")


if __name__ == "__main__":
    app()

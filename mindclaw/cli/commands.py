# input: typer, app.py, config/loader.py, security/crypto.py, oauth/, cli/skill_commands.py,
#        tools/bosszp.py
# output: 导出 app (Typer 应用)
# pos: CLI 入口，chat/serve/secret/auth/skill/bosszp-login 命令
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from mindclaw.cli.skill_commands import skill_app
from mindclaw.config.loader import load_config

app = typer.Typer(name="mindclaw", help="MindClaw - Personal AI Assistant")
app.add_typer(skill_app, name="skill")
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
    channels: str = typer.Option(
        "gateway,telegram",
        "--channels",
        help="Comma-separated channel names (e.g. gateway,slack,telegram)",
    ),
) -> None:
    """Start Gateway + remote channels."""
    from mindclaw.app import MindClawApp

    cfg = load_config(config)
    channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]
    mindclaw_app = MindClawApp(cfg)
    asyncio.run(mindclaw_app.run(channel_list))


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


@app.command("auth-login")
def auth_login(
    provider: str = typer.Argument(help="OAuth provider (e.g. openai)"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Login to an LLM provider via OAuth (opens browser)."""
    from mindclaw.oauth.manager import OAuthManager
    from mindclaw.oauth.providers import OAUTH_PROVIDERS
    from mindclaw.oauth.token_store import OAuthTokenStore

    if provider not in OAUTH_PROVIDERS:
        console.print(f"Unknown OAuth provider: '{provider}'")
        console.print(f"Available: {', '.join(OAUTH_PROVIDERS.keys())}")
        raise typer.Exit(1)

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    token_store = OAuthTokenStore(
        store_path=data_dir / "oauth_tokens.enc",
        master_key_path=data_dir / "master.key",
    )
    token_store.init_or_load_key()
    manager = OAuthManager(token_store=token_store)

    url, state, verifier = manager.build_authorization_url(provider)

    console.print(f"\nOpening browser for {provider} OAuth login...")
    console.print(f"If browser doesn't open, visit:\n{url}\n")

    import webbrowser

    webbrowser.open(url)

    # Start local callback server to receive the authorization code
    asyncio.run(_wait_for_callback(manager, provider, state, verifier))


async def _wait_for_callback(
    manager, provider: str, expected_state: str, verifier: str
) -> None:
    """Start a temporary HTTP server to receive OAuth callback."""
    from mindclaw.oauth.providers import OAUTH_PROVIDERS

    port = OAUTH_PROVIDERS[provider].redirect_port
    code_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()

    async def handle_callback(reader, writer):
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=30)
        except asyncio.TimeoutError:
            writer.close()
            return
        request_line = data.decode().split("\r\n")[0]
        # Parse: GET /auth/callback?code=xxx&state=yyy HTTP/1.1
        path = request_line.split(" ")[1] if " " in request_line else ""
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(path)
        params = parse_qs(parsed.query)

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        if code and state == expected_state:
            body = (
                "<html><body><h2>Authorization successful!"
                " You can close this tab.</h2></body></html>"
            )
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: text/html\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n\r\n{body}"
            )
            writer.write(response.encode())
            await writer.drain()
            writer.close()
            if not code_future.done():
                code_future.set_result(code)
        else:
            body = (
                "<html><body><h2>Authorization failed."
                " State mismatch or missing code.</h2></body></html>"
            )
            response = (
                f"HTTP/1.1 400 Bad Request\r\n"
                f"Content-Type: text/html\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n\r\n{body}"
            )
            writer.write(response.encode())
            await writer.drain()
            writer.close()
            if not code_future.done():
                code_future.set_exception(ValueError("State mismatch or missing code"))

    server = await asyncio.start_server(handle_callback, "127.0.0.1", port)
    console.print(f"Waiting for callback on http://127.0.0.1:{port}/auth/callback ...")

    try:
        code = await asyncio.wait_for(code_future, timeout=120)
    except asyncio.TimeoutError:
        console.print("Timeout waiting for authorization callback.")
        raise typer.Exit(1)
    finally:
        server.close()
        await server.wait_closed()

    token_info = await manager.exchange_code(provider, code, verifier)
    console.print(f"\nLogged in to {provider} successfully!")
    console.print(f"Token expires at: {token_info.expires_at}")


@app.command("auth-status")
def auth_status(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Show OAuth token status for all providers."""
    import time

    from mindclaw.oauth.token_store import OAuthTokenStore

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    token_store = OAuthTokenStore(
        store_path=data_dir / "oauth_tokens.enc",
        master_key_path=data_dir / "master.key",
    )
    token_store.init_or_load_key()
    providers = token_store.list_providers()

    if not providers:
        console.print("No OAuth tokens stored.")
        return

    for p in providers:
        token = token_store.get_token(p)
        if token is None:
            continue
        expired = token.is_expired(buffer_seconds=0)
        status = "EXPIRED" if expired else "VALID"
        remaining = ""
        if token.expires_at:
            secs = int(token.expires_at - time.time())
            remaining = f" ({secs}s remaining)" if secs > 0 else ""
        console.print(f"  {p}: {status}{remaining}")


@app.command("auth-logout")
def auth_logout(
    provider: str = typer.Argument(help="OAuth provider to logout from"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Remove OAuth token for a provider."""
    from mindclaw.oauth.token_store import OAuthTokenStore

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    token_store = OAuthTokenStore(
        store_path=data_dir / "oauth_tokens.enc",
        master_key_path=data_dir / "master.key",
    )
    token_store.init_or_load_key()
    token_store.delete_token(provider)
    console.print(f"Logged out from {provider}.")


@app.command("bosszp-login")
def bosszp_login(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Login to Boss直聘 via QR code scan (opens a browser window)."""
    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)

    bosszp_cfg = cfg.tools.bosszp
    session_path = Path(bosszp_cfg.session_path) if bosszp_cfg.session_path else (
        data_dir / "bosszp_session.json"
    )

    try:
        from mindclaw.tools.bosszp import _SessionManager
    except ImportError:
        console.print(
            "patchright is required. Install with:\n"
            "  pip install patchright && patchright install chromium"
        )
        raise typer.Exit(1)

    session = _SessionManager(
        session_path=session_path,
        proxy=bosszp_cfg.proxy,
        headless=False,
        page_limit=bosszp_cfg.page_limit,
    )

    console.print("Opening browser for Boss直聘 QR code login...")
    console.print("Please scan the QR code with Boss直聘 app.")

    success = asyncio.run(session.login_interactive())
    if success:
        console.print(f"Login successful! Session saved to {session_path}")
    else:
        console.print("Login failed or timed out. Please try again.")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show MindClaw version."""
    from mindclaw import __version__

    console.print(f"MindClaw v{__version__}")


if __name__ == "__main__":
    app()

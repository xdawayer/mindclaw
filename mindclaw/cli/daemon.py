# input: platform, pathlib
# output: 导出 detect_platform, generate_launchd_plist, generate_systemd_service
# pos: 进程守护配置生成，支持 macOS launchd 和 Linux systemd
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Daemon configuration generators for systemd and launchd."""

from __future__ import annotations

import platform
from pathlib import Path

_LAUNCHD_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mindclaw.assistant</string>

    <key>ProgramArguments</key>
    <array>
        <string>uv</string>
        <string>run</string>
        <string>mindclaw</string>
        <string>serve</string>
{channel_args}
    </array>

    <key>WorkingDirectory</key>
    <string>{project_dir}</string>

    <key>StandardOutPath</key>
    <string>{project_dir}/logs/mindclaw.log</string>

    <key>StandardErrorPath</key>
    <string>{project_dir}/logs/mindclaw.error.log</string>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>RunAtLoad</key>
    <false/>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
"""

_SYSTEMD_TEMPLATE = """\
[Unit]
Description=MindClaw Personal AI Assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={project_dir}
ExecStart=uv run mindclaw serve{channel_flags}
Restart=on-failure
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=mindclaw

NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
"""


def detect_platform() -> str:
    """Detect the init system: 'launchd' (macOS), 'systemd' (Linux), or 'unsupported'."""
    system = platform.system()
    if system == "Darwin":
        return "launchd"
    if system == "Linux":
        return "systemd"
    return "unsupported"


def generate_launchd_plist(
    output_path: Path,
    project_dir: Path,
    channels: list[str],
) -> None:
    """Generate a macOS launchd plist file."""
    channel_args = "\n".join(
        f"        <string>--{ch}</string>" for ch in channels
    )

    content = _LAUNCHD_TEMPLATE.format(
        project_dir=project_dir,
        channel_args=channel_args,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def generate_systemd_service(
    output_path: Path,
    project_dir: Path,
    channels: list[str],
) -> None:
    """Generate a Linux systemd service file."""
    channel_flags = "".join(f" --{ch}" for ch in channels)

    content = _SYSTEMD_TEMPLATE.format(
        project_dir=project_dir,
        channel_flags=channel_flags,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

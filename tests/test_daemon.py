# input: mindclaw.cli.daemon
# output: daemon install/uninstall/status 测试
# pos: 验证进程守护的安装、卸载和状态检查
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import platform
from pathlib import Path


def test_detect_platform():
    """detect_platform should return 'launchd' on macOS, 'systemd' on Linux."""
    from mindclaw.cli.daemon import detect_platform

    result = detect_platform()
    system = platform.system()
    if system == "Darwin":
        assert result == "launchd"
    elif system == "Linux":
        assert result == "systemd"
    else:
        assert result == "unsupported"


def test_generate_launchd_plist(tmp_path):
    """generate_plist should create a valid plist file."""
    from mindclaw.cli.daemon import generate_launchd_plist

    output = tmp_path / "com.mindclaw.plist"
    project_dir = Path("/Users/test/mindclaw")

    generate_launchd_plist(
        output_path=output,
        project_dir=project_dir,
        channels=["gateway", "telegram"],
    )

    assert output.exists()
    content = output.read_text()
    assert "com.mindclaw.assistant" in content
    assert "/Users/test/mindclaw" in content
    assert "--gateway" in content
    assert "--telegram" in content


def test_generate_systemd_service(tmp_path):
    """generate_systemd_service should create a valid service file."""
    from mindclaw.cli.daemon import generate_systemd_service

    output = tmp_path / "mindclaw.service"
    project_dir = Path("/home/test/mindclaw")

    generate_systemd_service(
        output_path=output,
        project_dir=project_dir,
        channels=["gateway", "telegram"],
    )

    assert output.exists()
    content = output.read_text()
    assert "MindClaw" in content
    assert "/home/test/mindclaw" in content
    assert "Restart=on-failure" in content


def test_generate_launchd_channels_flags(tmp_path):
    """Plist should include all specified channel flags."""
    from mindclaw.cli.daemon import generate_launchd_plist

    output = tmp_path / "test.plist"
    generate_launchd_plist(
        output_path=output,
        project_dir=Path("/tmp/mc"),
        channels=["gateway", "telegram", "slack", "wechat"],
    )

    content = output.read_text()
    assert "--gateway" in content
    assert "--telegram" in content
    assert "--slack" in content
    assert "--wechat" in content

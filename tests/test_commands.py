# input: mindclaw.cli.commands
# output: CLI 命令测试
# pos: CLI 入口层测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json

from typer.testing import CliRunner

runner = CliRunner()


def test_version_command():
    from mindclaw.cli.commands import app

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "MindClaw" in result.output


def test_secret_set_and_list(tmp_path):
    from mindclaw.cli.commands import app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"knowledge": {"dataDir": str(data_dir)}}))

    result = runner.invoke(app, ["secret-set", "MY_KEY", "my_value", "-c", str(config_path)])
    assert result.exit_code == 0

    result = runner.invoke(app, ["secret-list", "-c", str(config_path)])
    assert result.exit_code == 0
    assert "MY_KEY" in result.output


def test_secret_delete(tmp_path):
    from mindclaw.cli.commands import app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"knowledge": {"dataDir": str(data_dir)}}))

    runner.invoke(app, ["secret-set", "DEL_KEY", "val", "-c", str(config_path)])
    result = runner.invoke(app, ["secret-delete", "DEL_KEY", "-c", str(config_path)])
    assert result.exit_code == 0

    result = runner.invoke(app, ["secret-list", "-c", str(config_path)])
    assert "DEL_KEY" not in result.output

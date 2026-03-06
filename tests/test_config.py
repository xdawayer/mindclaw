# input: mindclaw.config
# output: 配置系统测试
# pos: 配置层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pathlib import Path


def test_config_schema_defaults():
    """默认配置应该有合理的默认值"""
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig()
    assert config.agent.default_model == "claude-sonnet-4-20250514"
    assert config.agent.max_iterations == 40
    assert config.agent.subagent_max_iterations == 15


def test_config_schema_custom_values():
    """应该能覆盖默认值"""
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig(agent={"default_model": "gpt-4o", "max_iterations": 20})
    assert config.agent.default_model == "gpt-4o"
    assert config.agent.max_iterations == 20


def test_config_env_var_resolution(monkeypatch):
    """配置中的 $ENV_VAR 应被环境变量替换"""
    from mindclaw.config.loader import resolve_env_vars

    monkeypatch.setenv("TEST_API_KEY", "sk-test-123")
    result = resolve_env_vars({"apiKey": "$TEST_API_KEY"})
    assert result["apiKey"] == "sk-test-123"


def test_config_env_var_missing():
    """缺失的环境变量应保留原值并给出警告"""
    from mindclaw.config.loader import resolve_env_vars

    result = resolve_env_vars({"apiKey": "$NONEXISTENT_VAR"})
    assert result["apiKey"] == "$NONEXISTENT_VAR"


def test_config_load_from_file(tmp_path):
    """应该能从 JSON 文件加载配置"""
    import json

    from mindclaw.config.loader import load_config

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "agent": {"defaultModel": "gpt-4o"}
    }))

    config = load_config(config_file)
    assert config.agent.default_model == "gpt-4o"


def test_config_load_default_when_no_file():
    """无配置文件时应返回默认配置"""
    from mindclaw.config.loader import load_config

    config = load_config(Path("/nonexistent/config.json"))
    assert config.agent.default_model == "claude-sonnet-4-20250514"

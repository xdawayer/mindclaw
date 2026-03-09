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
    assert config.tools.allow_dangerous_tools is False
    assert config.gateway.host == "127.0.0.1"


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


def test_security_config_defaults():
    """SecurityConfig 默认值应正确"""
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig()
    assert config.security.approval_timeout == 300
    assert config.security.session_poisoning_protection is True


def test_security_config_from_dict():
    """SecurityConfig 应支持从 camelCase 字典创建"""
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig(**{
        "security": {"approvalTimeout": 60, "sessionPoisoningProtection": False}
    })
    assert config.security.approval_timeout == 60
    assert config.security.session_poisoning_protection is False


def test_knowledge_config_defaults():
    from mindclaw.config.schema import KnowledgeConfig

    kc = KnowledgeConfig()
    assert kc.data_dir == "data"
    assert kc.consolidation_threshold == 20
    assert kc.consolidation_keep_recent == 10


def test_mindclaw_config_has_knowledge():
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig()
    assert hasattr(config, "knowledge")
    assert config.knowledge.data_dir == "data"


def test_channel_config_defaults():
    from mindclaw.config.schema import ChannelConfig

    cc = ChannelConfig()
    assert cc.enabled is True
    assert cc.token == ""
    assert cc.allow_from == []
    assert cc.allow_groups is False


def test_channel_config_from_camel_case():
    from mindclaw.config.schema import ChannelConfig

    cc = ChannelConfig(**{"allowFrom": ["123"], "allowGroups": True, "token": "tok"})
    assert cc.allow_from == ["123"]
    assert cc.allow_groups is True
    assert cc.token == "tok"


def test_mindclaw_config_has_channels():
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig()
    assert config.channels == {}


def test_mindclaw_config_channels_from_dict():
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig(**{
        "channels": {
            "telegram": {"token": "bot123", "allowFrom": ["111"], "allowGroups": False}
        }
    })
    assert "telegram" in config.channels
    assert config.channels["telegram"].token == "bot123"
    assert config.channels["telegram"].allow_from == ["111"]


def test_gateway_config_has_token():
    from mindclaw.config.schema import GatewayConfig

    gc = GatewayConfig()
    assert gc.token == ""


def test_security_config_has_pairing_timeout():
    from mindclaw.config.schema import SecurityConfig

    sc = SecurityConfig()
    assert sc.pairing_timeout == 300

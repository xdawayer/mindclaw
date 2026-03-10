# input: mindclaw.config.schema
# output: SkillsConfig 配置测试
# pos: SkillsConfig Pydantic 模型的单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md


def test_skills_config_defaults():
    """SkillsConfig 应有正确的默认值"""
    from mindclaw.config.schema import SkillsConfig

    sc = SkillsConfig()
    assert sc.index_url.startswith("https://")
    assert sc.cache_ttl == 86400
    assert sc.max_skill_size == 8192
    assert sc.max_always_total == 32768


def test_skills_config_in_mindclaw_config():
    """MindClawConfig 应包含 skills 字段，类型为 SkillsConfig"""
    from mindclaw.config.schema import MindClawConfig, SkillsConfig

    config = MindClawConfig()
    assert hasattr(config, "skills")
    assert isinstance(config.skills, SkillsConfig)


def test_skills_config_from_json_aliases():
    """SkillsConfig 应接受 camelCase 别名"""
    from mindclaw.config.schema import SkillsConfig

    sc = SkillsConfig(**{
        "indexUrl": "https://example.com/index.json",
        "cacheTtl": 3600,
        "maxSkillSize": 4096,
        "maxAlwaysTotal": 16384,
    })
    assert sc.index_url == "https://example.com/index.json"
    assert sc.cache_ttl == 3600
    assert sc.max_skill_size == 4096
    assert sc.max_always_total == 16384

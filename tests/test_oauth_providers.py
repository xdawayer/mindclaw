# input: mindclaw.oauth.providers
# output: OAuth provider 预置配置测试
# pos: 预置 OAuth provider 配置测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from mindclaw.oauth.providers import OAUTH_PROVIDERS, OAuthProviderConfig


class TestOAuthProviders:
    def test_openai_config_exists(self):
        assert "openai" in OAUTH_PROVIDERS

    def test_openai_config_fields(self):
        cfg = OAUTH_PROVIDERS["openai"]
        assert isinstance(cfg, OAuthProviderConfig)
        assert cfg.client_id == "app_EMoamEEZ73f0CkXaXp7hrann"
        assert cfg.auth_url == "https://auth.openai.com/oauth/authorize"
        assert cfg.token_url == "https://auth.openai.com/oauth/token"
        assert "openid" in cfg.scopes
        assert "offline_access" in cfg.scopes
        assert cfg.redirect_port == 1455

    def test_openai_api_base(self):
        cfg = OAUTH_PROVIDERS["openai"]
        assert cfg.api_base == "https://api.openai.com/v1"

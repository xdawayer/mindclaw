# input: dataclasses, os
# output: 导出 OAUTH_PROVIDERS, OAuthProviderConfig
# pos: 预置 OAuth provider 配置（OpenAI Codex 等），client_id 支持环境变量覆盖
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import os
from dataclasses import dataclass, field

_OPENAI_DEFAULT_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"


@dataclass(frozen=True)
class OAuthProviderConfig:
    """Pre-configured OAuth provider settings."""

    client_id: str
    auth_url: str
    token_url: str
    scopes: list[str] = field(default_factory=list)
    redirect_port: int = 1455
    api_base: str = ""


OAUTH_PROVIDERS: dict[str, OAuthProviderConfig] = {
    "openai": OAuthProviderConfig(
        client_id=os.environ.get("OPENAI_OAUTH_CLIENT_ID", _OPENAI_DEFAULT_CLIENT_ID),
        auth_url="https://auth.openai.com/oauth/authorize",
        token_url="https://auth.openai.com/oauth/token",
        scopes=["openid", "profile", "email", "offline_access"],
        redirect_port=1455,
        api_base="https://api.openai.com/v1",
    ),
}

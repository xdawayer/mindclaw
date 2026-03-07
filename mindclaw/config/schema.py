# input: pydantic
# output: 导出 MindClawConfig, AgentConfig, GatewayConfig, ProviderSettings,
#         ToolsConfig, LogConfig, SecurityConfig
# pos: 配置层核心，定义所有配置的 Pydantic 模型
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    default_model: str = Field(default="claude-sonnet-4-20250514", alias="defaultModel")
    fallback_model: str = Field(default="gpt-4o", alias="fallbackModel")
    max_iterations: int = Field(default=40, alias="maxIterations")
    subagent_max_iterations: int = Field(default=15, alias="subagentMaxIterations")

    model_config = {"populate_by_name": True}


class GatewayConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765

    model_config = {"populate_by_name": True}


class ProviderSettings(BaseModel):
    api_key: str = Field(default="", alias="apiKey")
    api_base: str | None = Field(default=None, alias="apiBase")

    model_config = {"populate_by_name": True}


class ToolsConfig(BaseModel):
    exec_timeout: int = Field(default=30, alias="execTimeout")
    tool_result_max_chars: int = Field(default=500, alias="toolResultMaxChars")
    restrict_to_workspace: bool = Field(default=True, alias="restrictToWorkspace")
    allow_dangerous_tools: bool = Field(default=False, alias="allowDangerousTools")

    model_config = {"populate_by_name": True}


class LogConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/mindclaw.log"
    rotation: str = "10 MB"
    retention: str = "7 days"

    model_config = {"populate_by_name": True}


class SecurityConfig(BaseModel):
    approval_timeout: int = Field(default=300, alias="approvalTimeout")
    session_poisoning_protection: bool = Field(
        default=True, alias="sessionPoisoningProtection"
    )

    model_config = {"populate_by_name": True}


class MindClawConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    model_config = {"populate_by_name": True}

# input: pydantic
# output: 导出 MindClawConfig, AgentConfig, GatewayConfig, ChannelConfig, ProviderSettings,
#         ToolsConfig, LogConfig, SecurityConfig, KnowledgeConfig,
#         ObsidianConfig, NotionConfig, WebArchiveConfig, VectorDbConfig, SkillsConfig,
#         AuthProfileConfig, BossZPConfig
# pos: 配置层核心，Pydantic 模型 (向量数据库/技能安装/API鉴权/Boss直聘配置)
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from typing import Literal

from pydantic import BaseModel, Field


class ModelRoutingConfig(BaseModel):
    enabled: bool = False
    categories: dict[str, str] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class AgentConfig(BaseModel):
    default_model: str = Field(default="claude-sonnet-4-20250514", alias="defaultModel")
    fallback_model: str = Field(default="gpt-4o", alias="fallbackModel")
    max_iterations: int = Field(default=40, alias="maxIterations")
    subagent_max_iterations: int = Field(default=15, alias="subagentMaxIterations")
    max_concurrent_tasks: int = Field(default=3, alias="maxConcurrentTasks", ge=1)
    message_timeout: int = Field(default=120, alias="messageTimeout")
    cron_enabled: bool = Field(default=True, alias="cronEnabled")
    model_routing: ModelRoutingConfig = Field(
        default_factory=ModelRoutingConfig, alias="modelRouting"
    )

    model_config = {"populate_by_name": True}


class ChannelConfig(BaseModel):
    enabled: bool = True
    token: str = ""
    app_token: str = Field(default="", alias="appToken")
    app_id: str = Field(default="", alias="appId")
    app_secret: str = Field(default="", alias="appSecret")
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")
    allow_groups: bool = Field(default=False, alias="allowGroups")

    model_config = {"populate_by_name": True}


class GatewayConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = ""

    model_config = {"populate_by_name": True}


class ProviderSettings(BaseModel):
    api_key: str = Field(default="", alias="apiKey")
    api_base: str | None = Field(default=None, alias="apiBase")
    auth_type: Literal["api_key", "oauth"] = Field(default="api_key", alias="authType")

    model_config = {"populate_by_name": True}


class AuthProfileConfig(BaseModel):
    profile_type: Literal["bearer", "header", "basic"] = Field(alias="profileType")
    header_name: str = Field(default="Authorization", alias="headerName")
    value: str = Field(min_length=1)

    model_config = {"populate_by_name": True}


class BossZPConfig(BaseModel):
    enabled: bool = False
    session_path: str = Field(default="", alias="sessionPath")
    proxy: str = ""
    min_delay: float = Field(default=3.0, alias="minDelay")
    max_delay: float = Field(default=8.0, alias="maxDelay")
    daily_cap: int = Field(default=100, alias="dailyCap")
    page_limit: int = Field(default=4, alias="pageLimit")
    headless: bool = True

    model_config = {"populate_by_name": True}


class ToolsConfig(BaseModel):
    exec_timeout: int = Field(default=30, alias="execTimeout")
    tool_result_max_chars: int = Field(default=500, alias="toolResultMaxChars")
    restrict_to_workspace: bool = Field(default=True, alias="restrictToWorkspace")
    allow_dangerous_tools: bool = Field(default=False, alias="allowDangerousTools")
    api_call_auth_profiles: dict[str, AuthProfileConfig] = Field(
        default_factory=dict, alias="apiCallAuthProfiles"
    )
    api_call_url_allowlist: list[str] = Field(
        default_factory=list, alias="apiCallUrlAllowlist"
    )
    twitter_cli_path: str = Field(default="", alias="twitterCliPath")
    bosszp: BossZPConfig = Field(default_factory=BossZPConfig, alias="bossZP")

    model_config = {"populate_by_name": True}


class LogConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/mindclaw.log"
    rotation: str = "10 MB"
    retention: str = "7 days"

    model_config = {"populate_by_name": True}


class SecurityConfig(BaseModel):
    approval_timeout: int = Field(default=300, alias="approvalTimeout")
    pairing_timeout: int = Field(default=300, alias="pairingTimeout")
    session_poisoning_protection: bool = Field(
        default=True, alias="sessionPoisoningProtection"
    )

    model_config = {"populate_by_name": True}


class ObsidianConfig(BaseModel):
    vault_path: str = Field(default="", alias="vaultPath")

    model_config = {"populate_by_name": True}


class NotionConfig(BaseModel):
    api_key: str = Field(default="", alias="apiKey")

    model_config = {"populate_by_name": True}


class WebArchiveConfig(BaseModel):
    max_pages: int = Field(default=1000, alias="maxPages")

    model_config = {"populate_by_name": True}


class VectorDbConfig(BaseModel):
    enabled: bool = False
    provider: str = "lancedb"
    embedding_model: str = Field(default="text-embedding-3-small", alias="embeddingModel")
    db_path: str = Field(default="vector_db", alias="dbPath")
    table_name: str = Field(default="documents", alias="tableName")
    embedding_dimensions: int = Field(default=1536, alias="embeddingDimensions")
    chunk_size: int = Field(default=500, alias="chunkSize")
    chunk_overlap: int = Field(default=50, alias="chunkOverlap")
    top_k: int = Field(default=5, alias="topK")

    model_config = {"populate_by_name": True}


class KnowledgeConfig(BaseModel):
    data_dir: str = Field(default="data", alias="dataDir")
    consolidation_threshold: int = Field(default=20, alias="consolidationThreshold")
    consolidation_keep_recent: int = Field(default=10, alias="consolidationKeepRecent")
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)
    notion: NotionConfig = Field(default_factory=NotionConfig)
    web_archive: WebArchiveConfig = Field(default_factory=WebArchiveConfig, alias="webArchive")
    vector_db: VectorDbConfig = Field(default_factory=VectorDbConfig, alias="vectorDb")

    model_config = {"populate_by_name": True}


class SkillsConfig(BaseModel):
    index_url: str = Field(
        default="https://raw.githubusercontent.com/mindclaw-skills/index/main/index.json",
        alias="indexUrl",
    )
    cache_ttl: int = Field(default=86400, alias="cacheTtl")
    max_skill_size: int = Field(default=8192, alias="maxSkillSize")
    max_always_total: int = Field(
        default=32768,
        alias="maxAlwaysTotal",
        description="Reserved for future enforcement of total size of always-loaded skills",
    )

    model_config = {"populate_by_name": True}


class MindClawConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    channels: dict[str, ChannelConfig] = Field(default_factory=dict)
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)

    model_config = {"populate_by_name": True}

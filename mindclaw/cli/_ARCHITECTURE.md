> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

CLI 入口层 - Typer 命令定义，委托 MindClawApp 处理 chat/serve，直接调用 SecretStore 管理密钥，skill_commands 子应用管理技能生命周期。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `commands.py` | 核心 | Typer app 命令 (chat, serve, secret-*, auth-*, version)，注册 skill_app 子组；chat/serve 委托 MindClawApp，secret 命令调用 SecretStore |
| `skill_commands.py` | 技能管理 | skill_app Typer 子应用；install/remove/list/show/search/update 六条子命令；_build_components() 构建 SkillRegistry + IndexClient + SkillInstaller |
| `daemon.py` | 辅助 | detect_platform + generate_launchd_plist + generate_systemd_service，生成 Daemon 部署配置 |

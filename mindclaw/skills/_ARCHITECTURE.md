> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

技能层 - Markdown 技能文件 + SkillRegistry 多目录注册中心 + 安装系统，LLM 自主路由选择技能。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `registry.py` | 核心 | SkillRegistry 多目录扫描(builtin/project/user)，原子重载，保护名称集合 |
| `installer.py` | 核心 | 技能安装/卸载/更新，支持本地/URL/GitHub/索引四种源 |
| `index_client.py` | 核心 | 集中索引拉取、本地缓存(TTL 24h)、技能搜索 |
| `integrity.py` | 安全 | SHA256 校验、SSRF 过滤、格式验证、大小限制 |
| `summarize.md` | 内置技能 | 文章总结技能 (on_demand) |
| `translate.md` | 内置技能 | 翻译技能 (on_demand) |

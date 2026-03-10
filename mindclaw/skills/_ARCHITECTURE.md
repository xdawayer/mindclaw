> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

技能层 - Markdown 格式的技能文件 + SkillRegistry 注册中心，LLM 自主路由选择技能。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `registry.py` | 核心 | SkillRegistry 扫描 skills/ 目录，解析 YAML front-matter，提供摘要/内容查询 |
| `summarize.md` | 示例技能 | 文章总结技能 (on_demand) |
| `translate.md` | 示例技能 | 翻译技能 (on_demand) |

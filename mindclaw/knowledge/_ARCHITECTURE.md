> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

知识层 - 四层记忆 + 三大知识源集成 (Obsidian/Notion/WebArchive)。Phase 4 记忆系统，Phase 9 知识管理。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空占位 |
| `_text_utils.py` | 共享工具 | html_to_text / extract_snippet — 知识层和工具层共用的文本处理 |
| `session.py` | 核心模块 | SessionStore — JSONL 持久化对话历史，管理整合指针 |
| `memory.py` | 核心模块 | MemoryManager — LLM 驱动记忆整合，管理 MEMORY.md 和 HISTORY.md |
| `obsidian.py` | 知识源 | ObsidianKnowledge — Obsidian vault 读写/搜索/标签(含YAML list)/链接 |
| `notion.py` | 知识源 | NotionKnowledge — Notion API 读页面/创建(database+page)/更新/搜索/列数据库，Block→Markdown，ID 验证 |
| `web_archive.py` | 知识源 | WebArchive — 网页收藏 (HTML→Markdown 保存/全文搜索/列出)，URL 验证 + frontmatter 注入防护 |

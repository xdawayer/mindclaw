> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

示例插件 — 演示自定义工具 (HelloTool) 和 hook 处理器 (before_tool/after_tool) 的注册方式。

| 文件 | 地位 | 功能 |
|------|------|------|
| `manifest.json` | 必需 | 插件元数据声明 |
| `main.py` | 入口 | 定义 HelloTool (SAFE 级别问候工具) |
| `hooks.py` | hook 处理器 | before_tool/after_tool 日志记录 |

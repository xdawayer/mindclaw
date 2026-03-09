> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

插件系统 — 插件发现、动态加载、Hook 事件分发。
用户在 `plugins/` 目录下放置插件（manifest.json + Python 模块），启动时自动加载。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空占位 |
| `manifest.py` | 核心模型 | PluginManifest 解析与验证 (manifest.json schema) |
| `hooks.py` | 核心组件 | HookRegistry 事件注册与顺序分发 (7 种 hook 事件) |
| `loader.py` | 核心组件 | PluginLoader 目录扫描 + importlib 动态导入 + 注册 |
| `exceptions.py` | 辅助 | PluginError / PluginManifestError / PluginLoadError / HookExecutionError |

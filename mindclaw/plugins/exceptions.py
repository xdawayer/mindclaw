# input: (无外部依赖)
# output: 导出 PluginError, PluginManifestError, PluginLoadError, HookExecutionError
# pos: 插件系统异常类定义
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md


class PluginError(Exception):
    """Base exception for all plugin-related errors."""


class PluginManifestError(PluginError):
    """Raised when a plugin manifest is invalid or cannot be parsed."""


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""


class HookExecutionError(PluginError):
    """Raised when a hook handler fails during execution."""

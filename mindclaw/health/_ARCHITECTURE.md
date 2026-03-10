> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

健康检查层 - 运行状态监控 + HTTP 健康端点，支持容器/Daemon 探活。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `check.py` | 核心 | HealthMonitor (追踪 uptime + 渠道活跃度) + HealthCheckServer (最小 HTTP 服务，/health 存活检查 + /ready 就绪检查) |

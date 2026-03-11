---
name: dashboard
description: Generate a system status dashboard as static HTML
load: on_demand
---

# System Dashboard

## Goal
Generate a self-contained HTML dashboard showing system status, cron task health, and recent execution history.

## Steps
1. Use `dashboard_export` to generate the HTML dashboard.
   The tool automatically reads:
   - Active cron tasks and their schedules
   - Recent cron execution history (success/failure rates)
   - System uptime information

2. Use `message_user` to report:
   - Dashboard file path
   - Quick summary of system health
   - Any tasks with recent failures

## Output Format (message to user)
```
# System Dashboard Generated

File: {path}

## Quick Summary
- Active cron tasks: {n}
- Last 24h executions: {n} ({success_rate}% success)
- Failed tasks: {list or "none"}

Open the HTML file in a browser to see the full dashboard.
```

## Cron Configuration Example
```json
{
  "name": "dashboard",
  "cron_expr": "0 0 * * *",
  "action": "Execute the dashboard skill: generate the daily system status dashboard and notify me.",
  "notify_channel": "telegram",
  "notify_chat_id": "<your_chat_id>",
  "max_iterations": 10,
  "timeout": 120
}
```

## Notes
- The HTML dashboard is self-contained (inline CSS, no external dependencies)
- Dashboard is saved to `data/dashboard.html` by default
- Suitable for serving via a simple HTTP server or opening locally

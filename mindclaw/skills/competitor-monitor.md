---
name: competitor-monitor
description: Monitor competitor websites for changes and generate semantic diffs
load: on_demand
---

# Competitor Monitoring

## Goal
Take periodic snapshots of competitor web pages, compare with previous snapshots, and notify the user of significant changes.

## Steps
1. For each monitored URL:
   a. Use `web_snapshot_list` to get the most recent snapshot for this URL:
      ```
      {"url": "https://competitor.example.com/pricing"}
      ```

   b. Use `web_snapshot` to take a new snapshot:
      ```
      {"url": "https://competitor.example.com/pricing"}
      ```

   c. If a previous snapshot exists, use `web_snapshot_read` to load both:
      - Previous: `{"id": "<previous_uuid>"}`
      - Current: `{"id": "<new_uuid>"}`

   d. Compare the two snapshots semantically:
      - Identify added, removed, and modified content
      - Focus on meaningful changes (ignore timestamp/cache differences)
      - Rate change significance: minor / moderate / major

2. If significant changes detected, use `message_user` to send a report.

3. If no changes, skip notification (unless user requests always-notify).

## Output Format
```
# Competitor Monitor Report - {date}

## {url}
**Change Level**: {minor|moderate|major}

### Changes Detected
- {description of change 1}
- {description of change 2}

### Summary
{1-2 sentence analysis of what changed and potential implications}

## {url2}
No significant changes.
```

## Cron Configuration Example
```json
{
  "name": "competitor-monitor",
  "cron_expr": "0 8 * * *",
  "action": "Execute the competitor-monitor skill: check the following competitor URLs for changes: https://competitor.example.com/pricing, https://competitor.example.com/features. Report any significant changes.",
  "notify_channel": "telegram",
  "notify_chat_id": "<your_chat_id>",
  "max_iterations": 25,
  "timeout": 600
}
```

## Notes
- Monitor only pages you have legitimate interest in
- Be respectful of rate limits; do not snapshot too frequently
- Snapshots are stored locally in `data/snapshots/`
- UUID-based storage prevents path traversal issues

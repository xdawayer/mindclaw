---
name: content-publish
description: Cross-platform content publishing via API
load: on_demand
---

# Cross-Platform Content Publishing

## Goal
Publish content to one or more platforms (GitHub Pages, blog APIs, social media) using `api_call` for HTTP requests.

## Steps

### Single Platform
1. Use `api_call` to check for new content (e.g., GitHub API to list recent commits or files):
   ```
   GET https://api.github.com/repos/{owner}/{repo}/contents/{path}
   auth_profile: "github"
   ```

2. Use `read_file` to load the content to publish from local workspace.

3. Format the content for the target platform:
   - Add platform-specific metadata (tags, categories, etc.)
   - Convert markdown to the platform's expected format if needed

4. Use `api_call` to publish:
   ```
   POST https://api.example.com/posts
   auth_profile: "blog"
   body: {"title": "...", "content": "...", "status": "published"}
   ```

5. Use `message_user` to report success or failure.

### Multi-Platform
1. Follow the single platform workflow for each configured platform.
2. Track publishing status per platform.
3. Use `write_file` to archive the published record:
   ```
   data/published.jsonl
   {"date": "...", "title": "...", "platforms": ["github", "blog"], "status": "success"}
   ```
4. Use `message_user` to send a summary of all platforms.

## Output Format
```
# Publishing Report - {date}

## Published
- {platform}: {title} - {url}

## Failed
- {platform}: {error}

## Summary
Published to {n}/{total} platforms successfully.
```

## Cron Configuration Example
```json
{
  "name": "content-publish",
  "cron_expr": "0 14 * * *",
  "action": "Execute the content-publish skill: check for new content in the drafts folder and publish approved drafts to configured platforms.",
  "notify_channel": "telegram",
  "notify_chat_id": "<your_chat_id>",
  "max_iterations": 20,
  "timeout": 600
}
```

## Notes
- Requires `api_call` tool with appropriate auth profiles configured
- URL allowlist must include all target API endpoints
- Never expose API tokens in messages; auth is injected by the tool
- If a platform publish fails, continue with remaining platforms

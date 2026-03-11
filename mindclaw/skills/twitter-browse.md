---
name: twitter-browse
description: Browse X/Twitter timeline and search for topics
load: on_demand
---

# X/Twitter Browsing

## Goal
Read X/Twitter timeline, search for topics, and summarize interesting posts.

## Steps
1. Use `twitter_read` with the requested action:
   - `timeline`: Get latest posts from followed accounts
   - `search`: Search for a specific topic or hashtag
   - `user`: Get posts from a specific user

2. Parse the returned posts and identify the most noteworthy items:
   - Posts with high engagement
   - Breaking news or trending topics
   - Posts relevant to the user's interests

3. For each selected post, provide:
   - Author and handle
   - Post content (translated if needed)
   - Engagement metrics if available
   - Brief context or commentary

4. Use `message_user` to deliver the summary.

## Output Format
```
# X/Twitter Summary - {date}

## Timeline Highlights
1. **@{handle}**: {content}
   Likes: {n} | Retweets: {n}
   {commentary}

2. ...

## Trending Topics
- #{topic}: {brief description}
```

## Cron Configuration Example
```json
{
  "name": "twitter-browse",
  "cron_expr": "0 8,12,18 * * *",
  "action": "Execute the twitter-browse skill: check my timeline and summarize the top 10 most interesting posts.",
  "notify_channel": "telegram",
  "notify_chat_id": "<your_chat_id>",
  "max_iterations": 15,
  "timeout": 300
}
```

## Notes
- Requires `twitter_read` tool configured with a CLI tool path
- Respect rate limits; do not request more than 50 posts at once
- If the CLI tool is not available, inform the user

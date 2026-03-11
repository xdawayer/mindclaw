---
name: hot-news
description: Aggregate trending news from multiple categories and deliver a daily digest
load: on_demand
---

# Hot News Aggregation

## Goal
Search trending news across multiple categories, fetch top articles, and produce a concise daily digest for the user.

## Steps
1. Use `web_search` to find trending news for each category:
   - Technology (query: "today's top tech news")
   - Business/Finance (query: "today's top business news")
   - Science (query: "today's top science news")
   Request 5 results per category.

2. From each category, pick the top 3 most relevant results.

3. Use `web_fetch` on each selected URL to retrieve the article content.

4. For each article, write a 2-3 sentence summary including:
   - Key facts or developments
   - Why it matters

5. Use `message_user` to deliver the digest.

## Output Format
```
# Daily News Digest - {date}

## Technology
- **{title}** ({source})
  {summary}
  Link: {url}

## Business & Finance
- **{title}** ({source})
  {summary}
  Link: {url}

## Science
- **{title}** ({source})
  {summary}
  Link: {url}
```

## Cron Configuration Example
```json
{
  "name": "hot-news",
  "cron_expr": "30 9 * * *",
  "action": "Execute the hot-news skill: search trending news in technology, business, and science categories, summarize the top articles, and send me the digest.",
  "notify_channel": "telegram",
  "notify_chat_id": "<your_chat_id>",
  "max_iterations": 25,
  "timeout": 600
}
```

## Notes
- If a web_fetch fails, skip that article and continue with others
- Keep summaries factual and concise
- Include source URLs for reference
- Total output should be under 3000 characters for mobile readability

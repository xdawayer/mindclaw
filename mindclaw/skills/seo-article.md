---
name: seo-article
description: Generate SEO-optimized article drafts with keyword research
load: on_demand
---

# SEO Article Generation

## Goal
Research keywords, gather reference material, and produce an SEO-optimized article draft saved to the workspace.

## Steps
1. Use `web_search` to research the given topic keyword:
   - Search for "{keyword} latest trends" (5 results)
   - Search for "{keyword} best practices" (5 results)
   - Search for "site:reddit.com {keyword}" (3 results for audience perspective)

2. Use `web_fetch` on the top 3 most relevant search results to gather reference material.

3. Analyze the gathered material and identify:
   - Primary keyword and 3-5 secondary keywords
   - Common questions people ask about this topic
   - Content gaps in existing articles

4. Generate article outline:
   - Title (include primary keyword, under 60 characters)
   - Introduction (hook + thesis)
   - 3-5 main sections with H2 headings
   - FAQ section (2-3 questions)
   - Conclusion with call-to-action

5. Write the full article (1500-2500 words):
   - Include primary keyword in title, first paragraph, and at least 2 H2 headings
   - Use secondary keywords naturally throughout
   - Include internal linking placeholders: `[INTERNAL: topic]`
   - Add meta description (under 160 characters)

6. Use `write_file` to save the draft as:
   `data/drafts/{date}-{slug}.md`

   File format:
   ```markdown
   ---
   title: "{title}"
   date: "{YYYY-MM-DD}"
   keywords: ["{kw1}", "{kw2}", ...]
   status: draft
   meta_description: "{description}"
   ---

   {article content}
   ```

7. Use `message_user` to notify:
   - Article title
   - Word count
   - Target keywords
   - File path

## Cron Configuration Example
```json
{
  "name": "seo-article",
  "cron_expr": "0 10 * * 1,3,5",
  "action": "Execute the seo-article skill: write an SEO article about '{topic}'. Research current trends and generate a comprehensive draft.",
  "notify_channel": "telegram",
  "notify_chat_id": "<your_chat_id>",
  "max_iterations": 30,
  "timeout": 900
}
```

## Notes
- Do not plagiarize; synthesize information from multiple sources
- Maintain a professional but accessible tone
- Each section should provide actionable value
- If writing fails, notify the user with the error

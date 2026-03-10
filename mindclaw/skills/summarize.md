---
name: summarize-article
description: Summarize an article's key points from a URL or text
load: on_demand
---

# Summarize Article

## Steps
1. If given a URL, use web_fetch to get article content
2. Extract core arguments (max 5 points)
3. Generate a one-paragraph summary
4. If the user specifies a format, output accordingly

## Output Format
- Title
- Key points (bullet list)
- One-sentence summary

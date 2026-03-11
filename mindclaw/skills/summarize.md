---
name: summarize
description: Summarize or extract text/transcripts from URLs, podcasts, and local files via summarize CLI
load: on_demand
---

# Summarize

Fast CLI to summarize URLs, local files, and YouTube links via `summarize` (summarize.sh).

## When to Use

- "summarize this URL/article/page"
- "what's this link/video about?"
- "transcribe this YouTube/video"
- "extract text from this PDF/file"

## Steps

1. Determine the input type (URL, YouTube link, or local file path).

2. Use `exec` tool to run the summarize CLI:
   ```bash
   summarize "<url_or_path>" --model google/gemini-3-flash-preview --length medium
   ```

3. For YouTube transcripts:
   ```bash
   summarize "<youtube_url>" --youtube auto --extract-only
   ```

4. Parse the output and deliver to user via `message_user`.

## Useful Flags

- `--length short|medium|long|xl|xxl|<chars>` -- control summary length
- `--max-output-tokens <count>` -- limit output tokens
- `--extract-only` -- return raw extracted text (URLs only)
- `--json` -- machine-readable output
- `--firecrawl auto|off|always` -- fallback extraction for blocked sites
- `--youtube auto` -- YouTube transcript with Apify fallback

## Environment

Required API key for chosen model provider:
- Google: `GEMINI_API_KEY`
- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`

Optional:
- `FIRECRAWL_API_KEY` for blocked sites
- `APIFY_API_TOKEN` for YouTube fallback

## Output Format

- Title (if available)
- Key points (bullet list, max 5)
- One-paragraph summary
- Source URL

## Notes

- Default model: `google/gemini-3-flash-preview`
- Config file: `~/.summarize/config.json`
- If transcript is very long, summarize first, then ask user which section to expand
- For cron usage, prefer `--length short` to keep output under 3000 chars

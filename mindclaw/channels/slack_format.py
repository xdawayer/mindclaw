# input: re
# output: 导出 markdown_to_slack()
# pos: Markdown → Slack mrkdwn 格式转换 (自实现，无第三方依赖)，供 SlackChannel.send() 调用
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import re

# ---------------------------------------------------------------------------
# CJK zero-width space fix
# Slack mrkdwn format markers (*bold*, _italic_, ~strike~) fail to render
# when immediately adjacent to CJK characters or full-width punctuation
# because Slack requires word boundaries around the markers.
# Fix: insert a zero-width space (U+200B) at those boundaries.
# ---------------------------------------------------------------------------
_ZWS = "\u200b"
_CJK_FULLWIDTH = (
    r"[\u2e80-\u9fff\uf900-\ufaff"  # CJK characters
    r"\uff01-\uff60\u3000-\u303f"  # full-width punctuation
    r"]"
)
_FIX_AFTER = re.compile(rf"([*_~])({_CJK_FULLWIDTH})")
_FIX_BEFORE = re.compile(rf"({_CJK_FULLWIDTH})([*_~])")

# ---------------------------------------------------------------------------
# Markdown → mrkdwn inline conversion
# Key mappings:  **bold** → *bold*  |  *italic* → _italic_
#                ~~strike~~ → ~strike~  |  [text](url) → <url|text>
#                # heading → *heading*  |  code blocks preserved
# ---------------------------------------------------------------------------
_B_OPEN = "\x01"  # placeholder to protect bold from italic pass
_B_CLOSE = "\x02"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")
_STRIKE_RE = re.compile(r"~~(.+?)~~")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _fix_cjk_formatting(text: str) -> str:
    """Insert zero-width spaces so Slack recognizes formatting near CJK text."""
    text = _FIX_AFTER.sub(rf"\1{_ZWS}\2", text)
    text = _FIX_BEFORE.sub(rf"\1{_ZWS}\2", text)
    return text


def _convert_line(line: str) -> str:
    """Convert a single non-code-block line from Markdown to Slack mrkdwn."""
    # Headings: # text → *text* (bold, since mrkdwn has no heading syntax)
    m = _HEADING_RE.match(line)
    if m:
        content = m.group(2).replace("*", "")
        return f"*{content.strip()}*"

    # Bold: **text** → placeholder (so italic pass won't touch it)
    line = _BOLD_RE.sub(rf"{_B_OPEN}\1{_B_CLOSE}", line)

    # Italic: *text* → _text_ (only remaining single-star pairs)
    line = _ITALIC_RE.sub(r"_\1_", line)

    # Restore bold: placeholder → *text*
    line = line.replace(_B_OPEN, "*").replace(_B_CLOSE, "*")

    # Strikethrough: ~~text~~ → ~text~
    line = _STRIKE_RE.sub(r"~\1~", line)

    # Links: [text](url) → <url|text>
    line = _LINK_RE.sub(r"<\2|\1>", line)

    return line


def markdown_to_slack(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn format with CJK fixes."""
    if not text:
        return ""

    lines = text.split("\n")
    result: list[str] = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        result.append(_convert_line(line))

    converted = "\n".join(result)
    return _fix_cjk_formatting(converted)

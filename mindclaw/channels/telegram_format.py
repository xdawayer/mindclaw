# input: re
# output: 导出 markdown_to_telegram_html()
# pos: Markdown → Telegram HTML 格式转换，供 TelegramChannel.send() 调用
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Convert standard Markdown to Telegram-safe HTML.

Telegram HTML mode is more forgiving than MarkdownV2 -- it ignores
unknown tags and only requires escaping ``<``, ``>``, and ``&``.
This makes it the safest rich-text option for LLM-generated output.
"""

import re

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_CODE_BLOCK_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")
_STRIKE_RE = re.compile(r"~~(.+?)~~")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _escape_html(text: str) -> str:
    """Escape HTML entities in text (order matters: & first)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markdown_to_telegram_html(text: str) -> str:
    """Convert standard Markdown to Telegram HTML format.

    Processing order:
    1. Extract code blocks (preserve content, escape HTML inside)
    2. Escape HTML entities in remaining text
    3. Convert inline Markdown to HTML tags
    4. Re-insert code blocks
    """
    if not text:
        return ""

    # Step 1: Extract code blocks and replace with placeholders
    code_blocks: list[str] = []

    def _replace_code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = _escape_html(m.group(2).rstrip())
        idx = len(code_blocks)
        if lang:
            block = f'<pre><code class="language-{lang}">{code}</code></pre>'
        else:
            block = f"<pre>{code}</pre>"
        code_blocks.append(block)
        return f"\x00CODEBLOCK{idx}\x00"

    text = _CODE_BLOCK_RE.sub(_replace_code_block, text)

    # Step 2: Extract inline code and replace with placeholders
    inline_codes: list[str] = []

    def _replace_inline_code(m: re.Match) -> str:
        code = _escape_html(m.group(1))
        idx = len(inline_codes)
        inline_codes.append(f"<code>{code}</code>")
        return f"\x00INLINECODE{idx}\x00"

    text = _INLINE_CODE_RE.sub(_replace_inline_code, text)

    # Step 3: Escape HTML in remaining text
    text = _escape_html(text)

    # Step 4: Convert Markdown to HTML tags
    # Headings: # text → <b>text</b>
    text = _HEADING_RE.sub(lambda m: f"<b>{m.group(2).strip()}</b>", text)

    # Bold: **text** → <b>text</b>
    text = _BOLD_RE.sub(r"<b>\1</b>", text)

    # Italic: *text* → <i>text</i>
    text = _ITALIC_RE.sub(r"<i>\1</i>", text)

    # Strikethrough: ~~text~~ → <s>text</s>
    text = _STRIKE_RE.sub(r"<s>\1</s>", text)

    # Links: [text](url) → <a href="url">text</a>
    text = _LINK_RE.sub(r'<a href="\2">\1</a>', text)

    # Step 5: Restore code blocks and inline code
    for idx, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK{idx}\x00", block)
    for idx, code in enumerate(inline_codes):
        text = text.replace(f"\x00INLINECODE{idx}\x00", code)

    return text

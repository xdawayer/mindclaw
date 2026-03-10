# input: markdown_to_mrkdwn (third-party), re
# output: 导出 markdown_to_slack()
# pos: Markdown → Slack mrkdwn 格式转换，供 SlackChannel.send() 调用
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import re

from markdown_to_mrkdwn import SlackMarkdownConverter

_converter = SlackMarkdownConverter()

# Slack mrkdwn formatting markers (*bold*, _italic_, ~strike~) fail to render
# when immediately adjacent to CJK characters or full-width punctuation.
# Fix: insert a zero-width space (U+200B) at those boundaries.
_ZWS = "\u200b"
_CJK_FULLWIDTH = (
    r"[\u2e80-\u9fff\uf900-\ufaff"  # CJK characters
    r"\uff01-\uff60\u3000-\u303f"    # full-width punctuation
    r"]"
)
# After closing marker: *text*<CJK> → *text*\u200b<CJK>
_FIX_AFTER = re.compile(rf"([*_~])({_CJK_FULLWIDTH})")
# Before opening marker: <CJK>*text* → <CJK>\u200b*text*
_FIX_BEFORE = re.compile(rf"({_CJK_FULLWIDTH})([*_~])")


def _fix_cjk_formatting(text: str) -> str:
    """Insert zero-width spaces so Slack recognizes formatting near CJK text."""
    text = _FIX_AFTER.sub(rf"\1{_ZWS}\2", text)
    text = _FIX_BEFORE.sub(rf"\1{_ZWS}\2", text)
    return text


def markdown_to_slack(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn format."""
    if not text:
        return ""
    converted = _converter.convert(text)
    return _fix_cjk_formatting(converted)

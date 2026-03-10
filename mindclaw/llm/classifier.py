# input: re
# output: 导出 classify_intent()
# pos: 零成本意图分类器，根据关键词将用户消息映射到模型路由类别
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import re

_HASHTAG_RE = re.compile(r"^#(planning|coding|writing|search)\b")

# Chinese keywords: substring match is safe (no word boundary ambiguity).
# English keywords: short words (<= 5 chars) use word boundary regex to avoid
# false positives (e.g. "fix" matching "prefix", "api" matching "capital").
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "planning": [
        "规划", "设计", "架构", "分析", "对比", "方案", "策略", "评估",
        "plan", "design", "architect", "analyz", "compar", "strateg", "evaluat",
    ],
    "coding": [
        "代码", "编程", "函数", "debug", "重构", "实现", "修复", "接口",
        "编译", "测试用例", "bug", "错误",
        "code", "program", "function", "refactor", "implement", "fix", "api",
        "compile", "test case",
    ],
    "writing": [
        "写一篇", "文案", "文章", "总结", "翻译", "润色", "改写", "摘要",
        "稿", "报告", "邮件",
        "write an", "article", "summariz", "translat", "polish", "rewrite",
        "essay", "report", "email",
    ],
    "search": [
        "搜索", "查找", "查一下", "帮我找", "搜一下", "查询", "天气", "新闻",
        "search", "find", "look up", "lookup", "weather", "news",
    ],
}

# Pre-compiled word boundary patterns for short English keywords
_WORD_BOUNDARY_THRESHOLD = 5
_BOUNDARY_CACHE: dict[str, re.Pattern[str]] = {}


def _matches_keyword(keyword: str, text: str) -> bool:
    """Check if keyword matches in text, using letter boundaries for short English words."""
    # Chinese or long English keywords: simple substring match
    if not keyword.isascii() or len(keyword) > _WORD_BOUNDARY_THRESHOLD:
        return keyword in text
    # Short ASCII keyword: use ASCII letter boundary (not \b, which breaks on Chinese)
    if keyword not in _BOUNDARY_CACHE:
        _BOUNDARY_CACHE[keyword] = re.compile(
            rf"(?<![a-zA-Z]){re.escape(keyword)}(?![a-zA-Z])", re.IGNORECASE
        )
    return _BOUNDARY_CACHE[keyword].search(text) is not None


def classify_intent(text: str) -> str:
    """Classify user message into a routing category.

    Categories: planning, coding, writing, search, general.
    Users can override with #tag prefix (e.g. "#planning ...").
    """
    if not text:
        return "general"

    # Check for explicit #tag override
    match = _HASHTAG_RE.match(text.strip())
    if match:
        return match.group(1)

    lower = text.lower()

    # Score each category by keyword matches
    best_category = "general"
    best_score = 0

    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if _matches_keyword(kw, lower))
        if score > best_score:
            best_score = score
            best_category = category

    return best_category

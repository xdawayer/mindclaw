# input: knowledge/_text_utils.py
# output: 共享文本工具测试
# pos: Phase 9 重构 — 提取 html_to_text / extract_snippet 到共享模块
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for shared text utilities used by knowledge modules."""

from mindclaw.knowledge._text_utils import extract_snippet, html_to_text


class TestHtmlToText:
    def test_strips_tags(self) -> None:
        assert html_to_text("<p>Hello</p>") == "Hello"

    def test_strips_script_and_style(self) -> None:
        html = "<script>alert(1)</script><style>.x{}</style><p>Clean</p>"
        assert html_to_text(html) == "Clean"

    def test_collapses_whitespace(self) -> None:
        assert html_to_text("<p>a</p>  <p>b</p>") == "a b"

    def test_empty_string(self) -> None:
        assert html_to_text("") == ""

    def test_plain_text_passthrough(self) -> None:
        assert html_to_text("no html here") == "no html here"


class TestExtractSnippet:
    def test_returns_context_around_match(self) -> None:
        text = "x" * 100 + "TARGET" + "y" * 100
        snippet = extract_snippet(text, "target")
        assert "TARGET" in snippet

    def test_ellipsis_when_truncated(self) -> None:
        text = "a" * 200 + "FIND" + "b" * 200
        snippet = extract_snippet(text, "find")
        assert snippet.startswith("...")
        assert snippet.endswith("...")

    def test_no_ellipsis_at_start(self) -> None:
        text = "FIND rest"
        snippet = extract_snippet(text, "find")
        assert not snippet.startswith("...")

    def test_no_match_returns_empty(self) -> None:
        assert extract_snippet("hello world", "xyz") == ""

    def test_newlines_replaced_with_space(self) -> None:
        text = "before\nFIND\nafter"
        snippet = extract_snippet(text, "find")
        assert "\n" not in snippet

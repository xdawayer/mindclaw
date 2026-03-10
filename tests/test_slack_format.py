# input: mindclaw.channels.slack_format
# output: slack_format 转换测试
# pos: Slack Markdown 转换单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from mindclaw.channels.slack_format import markdown_to_slack


class TestMarkdownToSlack:
    """Test markdown_to_slack conversion function."""

    def test_bold(self):
        assert "*bold*" in markdown_to_slack("**bold**")

    def test_italic(self):
        assert "_italic_" in markdown_to_slack("*italic*")

    def test_heading(self):
        result = markdown_to_slack("# Heading")
        # Slack has no heading syntax; should convert to bold
        assert "*Heading*" in result

    def test_link(self):
        result = markdown_to_slack("[click here](https://example.com)")
        assert "<https://example.com|click here>" in result

    def test_code_block_preserved(self):
        md = "```python\nprint('hello')\n```"
        result = markdown_to_slack(md)
        assert "```" in result
        assert "print('hello')" in result

    def test_inline_code_preserved(self):
        result = markdown_to_slack("use `foo()` here")
        assert "`foo()`" in result

    def test_blockquote(self):
        result = markdown_to_slack("> quoted text")
        assert ">" in result
        assert "quoted" in result

    def test_unordered_list(self):
        md = "- item 1\n- item 2"
        result = markdown_to_slack(md)
        assert "item 1" in result
        assert "item 2" in result

    def test_empty_string(self):
        assert markdown_to_slack("") == ""

    def test_plain_text_unchanged(self):
        text = "Hello, this is plain text."
        assert markdown_to_slack(text).strip() == text

    def test_mixed_formatting(self):
        md = "# Title\n\n**bold** and *italic* with `code`\n\n- list item"
        result = markdown_to_slack(md)
        assert "*Title*" in result
        assert "*bold*" in result
        assert "_italic_" in result
        assert "`code`" in result

    def test_code_block_content_not_converted(self):
        """Content inside code blocks should NOT be converted."""
        md = "```\n**not bold** and *not italic*\n```"
        result = markdown_to_slack(md)
        assert "**not bold**" in result

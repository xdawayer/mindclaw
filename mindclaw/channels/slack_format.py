# input: markdown_to_mrkdwn (third-party)
# output: 导出 markdown_to_slack()
# pos: Markdown → Slack mrkdwn 格式转换，供 SlackChannel.send() 调用
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from markdown_to_mrkdwn import SlackMarkdownConverter

_converter = SlackMarkdownConverter()


def markdown_to_slack(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn format."""
    if not text:
        return ""
    return _converter.convert(text)

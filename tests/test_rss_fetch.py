# input: pytest, pytest-asyncio, mindclaw.tools.rss_fetch, defusedxml
# output: RssFetchTool 单元测试
# pos: 测试 RSS/Atom feed 抓取工具的解析、过滤、格式化、错误处理、XXE 防护
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import time
import xml.etree.ElementTree as ET

import pytest
from defusedxml import ElementTree as SafeET

from mindclaw.tools.rss_fetch import (
    RssFetchTool,
    _format_posts,
    _parse_atom,
    _parse_iso_date,
    _parse_rss2,
    _parse_rss_date,
    _time_ago,
)


# ── Sample XML Fixtures ────────────────────────────────────


RSS2_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Post One</title>
      <link>https://example.com/1</link>
      <description>&lt;p&gt;Hello &lt;b&gt;World&lt;/b&gt;&lt;/p&gt;</description>
      <author>alice</author>
      <pubDate>Wed, 12 Mar 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Post Two</title>
      <link>https://example.com/2</link>
      <description>Plain text description</description>
      <pubDate>Tue, 11 Mar 2026 08:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

ATOM_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Test Feed</title>
  <entry>
    <title>Atom Post One</title>
    <link href="https://example.com/atom/1"/>
    <author><name>bob</name></author>
    <updated>2026-03-12T10:00:00Z</updated>
    <content type="html">&lt;p&gt;Atom &lt;em&gt;content&lt;/em&gt;&lt;/p&gt;</content>
  </entry>
  <entry>
    <title>Atom Post Two</title>
    <link href="https://example.com/atom/2"/>
    <updated>2026-03-11T08:00:00+00:00</updated>
    <summary>Summary text only</summary>
  </entry>
</feed>"""


# ── Test: Date Parsing ─────────────────────────────────────


class TestDateParsing:
    def test_rss_date_valid(self):
        ts = _parse_rss_date("Wed, 12 Mar 2026 10:00:00 +0000")
        assert ts > 0

    def test_rss_date_invalid(self):
        assert _parse_rss_date("not a date") == 0.0

    def test_rss_date_empty(self):
        assert _parse_rss_date("") == 0.0

    def test_iso_date_valid_z(self):
        ts = _parse_iso_date("2026-03-12T10:00:00Z")
        assert ts > 0

    def test_iso_date_valid_offset(self):
        ts = _parse_iso_date("2026-03-12T10:00:00+08:00")
        assert ts > 0

    def test_iso_date_invalid(self):
        assert _parse_iso_date("garbage") == 0.0

    def test_iso_date_naive(self):
        """Naive datetime should get UTC timezone."""
        ts = _parse_iso_date("2026-03-12T10:00:00")
        assert ts > 0


# ── Test: Time Ago ──────────────────────────────────────────


class TestTimeAgo:
    def test_just_now(self):
        assert _time_ago(time.time()) == "just now"

    def test_minutes_ago(self):
        assert "m ago" in _time_ago(time.time() - 300)

    def test_hours_ago(self):
        assert "h ago" in _time_ago(time.time() - 7200)

    def test_days_ago(self):
        assert "d ago" in _time_ago(time.time() - 172800)


# ── Test: RSS 2.0 Parsing ──────────────────────────────────


class TestParseRSS2:
    def test_parse_two_items(self):
        root = ET.fromstring(RSS2_XML)
        posts = _parse_rss2(root)
        assert len(posts) == 2

    def test_first_post_fields(self):
        root = ET.fromstring(RSS2_XML)
        posts = _parse_rss2(root)
        p = posts[0]
        assert p["title"] == "Post One"
        assert p["link"] == "https://example.com/1"
        assert p["author"] == "alice"
        assert p["created_utc"] > 0

    def test_html_stripped(self):
        root = ET.fromstring(RSS2_XML)
        posts = _parse_rss2(root)
        content = posts[0]["content"]
        assert "<p>" not in content
        assert "<b>" not in content
        assert "Hello" in content
        assert "World" in content

    def test_no_channel(self):
        root = ET.fromstring("<rss><nochannel/></rss>")
        assert _parse_rss2(root) == []


# ── Test: Atom Parsing ──────────────────────────────────────


class TestParseAtom:
    def test_parse_two_entries(self):
        root = ET.fromstring(ATOM_XML)
        posts = _parse_atom(root)
        assert len(posts) == 2

    def test_first_entry_fields(self):
        root = ET.fromstring(ATOM_XML)
        posts = _parse_atom(root)
        p = posts[0]
        assert p["title"] == "Atom Post One"
        assert p["link"] == "https://example.com/atom/1"
        assert p["author"] == "bob"
        assert p["created_utc"] > 0

    def test_html_stripped_from_content(self):
        root = ET.fromstring(ATOM_XML)
        posts = _parse_atom(root)
        content = posts[0]["content"]
        assert "<p>" not in content
        assert "Atom" in content

    def test_summary_fallback(self):
        root = ET.fromstring(ATOM_XML)
        posts = _parse_atom(root)
        assert "Summary text only" in posts[1]["content"]


# ── Test: Format Posts ──────────────────────────────────────


class TestFormatPosts:
    def test_empty_posts(self):
        result = _format_posts("Test", [])
        assert "No recent posts" in result

    def test_with_posts(self):
        posts = [
            {
                "title": "Hello",
                "link": "https://x.com/1",
                "content": "Preview text",
                "author": "tester",
                "created_utc": time.time() - 60,
            }
        ]
        result = _format_posts("My Feed", posts)
        assert "My Feed" in result
        assert "Hello" in result
        assert "tester" in result
        assert "https://x.com/1" in result

    def test_truncation(self):
        long_content = "x" * 300
        posts = [
            {
                "title": "Long",
                "link": "https://x.com/1",
                "content": long_content,
                "author": "",
                "created_utc": 0,
            }
        ]
        result = _format_posts("Feed", posts)
        assert "..." in result


# ── Test: Input Validation ──────────────────────────────────


class TestInputValidation:
    @pytest.fixture
    def tool(self):
        return RssFetchTool()

    @pytest.mark.asyncio
    async def test_missing_url(self, tool):
        result = await tool.execute({})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_empty_url(self, tool):
        result = await tool.execute({"url": ""})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_url_too_long(self, tool):
        result = await tool.execute({"url": "https://example.com/" + "a" * 500})
        assert "too long" in result

    @pytest.mark.asyncio
    async def test_private_url_blocked(self, tool):
        result = await tool.execute({"url": "http://127.0.0.1/feed.xml"})
        assert "private" in result.lower() or "internal" in result.lower()


# ── Test: Feed Title Extraction ─────────────────────────────


class TestFeedTitle:
    def test_rss_title(self):
        root = ET.fromstring(RSS2_XML)
        assert RssFetchTool._extract_feed_title(root) == "Test Feed"

    def test_atom_title(self):
        root = ET.fromstring(ATOM_XML)
        assert RssFetchTool._extract_feed_title(root) == "Atom Test Feed"

    def test_no_title(self):
        root = ET.fromstring("<rss><channel></channel></rss>")
        assert RssFetchTool._extract_feed_title(root) == ""


# ── Test: XXE / Billion Laughs Protection ───────────────────


BILLION_LAUGHS_XML = """\
<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<rss><channel><title>&lol3;</title></channel></rss>"""


class TestXXEProtection:
    def test_billion_laughs_blocked_by_defusedxml(self):
        """defusedxml should reject entity expansion payloads."""
        with pytest.raises(Exception):
            SafeET.fromstring(BILLION_LAUGHS_XML)

    @pytest.mark.asyncio
    async def test_tool_returns_error_on_malicious_xml(self):
        """The tool should return an error string, not crash."""
        from unittest.mock import AsyncMock, patch

        tool = RssFetchTool()
        with patch.object(tool, "_fetch_feed", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = BILLION_LAUGHS_XML
            result = await tool.execute({"url": "https://example.com/feed.xml"})
            assert "Error" in result


# ── Test: Hours Filter ──────────────────────────────────────


class TestHoursFilter:
    @pytest.mark.asyncio
    async def test_hours_filter_excludes_old_posts(self):
        """Posts older than hours cutoff should be excluded."""
        from unittest.mock import AsyncMock, patch

        old_rss = """\
<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
  <item><title>Old</title><link>https://x.com/1</link>
    <description>old</description>
    <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate></item>
  <item><title>New</title><link>https://x.com/2</link>
    <description>new</description>
    <pubDate>{}</pubDate></item>
</channel></rss>""".format(
            time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
        )

        tool = RssFetchTool()
        with patch.object(tool, "_fetch_feed", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = old_rss
            result = await tool.execute({"url": "https://example.com/f.xml", "hours": 1})
            assert "New" in result
            assert "Old" not in result

    @pytest.mark.asyncio
    async def test_hours_filter_includes_undated_posts(self):
        """Posts without dates should be included even with hours filter."""
        from unittest.mock import AsyncMock, patch

        undated_rss = """\
<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
  <item><title>NoDater</title><link>https://x.com/1</link>
    <description>no date here</description></item>
</channel></rss>"""

        tool = RssFetchTool()
        with patch.object(tool, "_fetch_feed", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = undated_rss
            result = await tool.execute({"url": "https://example.com/f.xml", "hours": 24})
            assert "NoDater" in result


# ── Test: Unrecognized Feed Format ──────────────────────────


class TestUnrecognizedFormat:
    @pytest.mark.asyncio
    async def test_unknown_root_tag(self):
        from unittest.mock import AsyncMock, patch

        tool = RssFetchTool()
        with patch.object(tool, "_fetch_feed", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html><body>Not a feed</body></html>"
            result = await tool.execute({"url": "https://example.com/f.xml"})
            assert "unrecognized feed format" in result


# ── Test: dc:creator Fallback ───────────────────────────────


class TestDcCreator:
    def test_dc_creator_used_when_no_author(self):
        xml = """\
<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel><title>T</title>
    <item><title>P</title><link>https://x.com</link>
      <description>d</description>
      <dc:creator>dcauthor</dc:creator></item>
  </channel>
</rss>"""
        root = ET.fromstring(xml)
        posts = _parse_rss2(root)
        assert posts[0]["author"] == "dcauthor"

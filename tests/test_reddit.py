# input: mindclaw/tools/reddit.py, pytest, unittest.mock
# output: RedditFetchTool 单元测试
# pos: 测试 Reddit 工具的解析/过滤/错误处理/降级模式
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import time

import pytest

from mindclaw.tools.reddit import RedditFetchTool, _format_posts, _time_ago


# ── _time_ago tests ────────────────────────────────────────


class TestTimeAgo:
    def test_just_now(self):
        assert _time_ago(time.time()) == "just now"

    def test_minutes(self):
        assert _time_ago(time.time() - 300) == "5m ago"

    def test_hours(self):
        assert _time_ago(time.time() - 7200) == "2h ago"

    def test_days(self):
        assert _time_ago(time.time() - 172800) == "2d ago"


# ── _format_posts tests ───────────────────────────────────


class TestFormatPosts:
    def test_empty_posts(self):
        result = _format_posts("test", "hot", [])
        assert "No posts found" in result

    def test_format_self_post(self):
        posts = [{
            "title": "Test Post",
            "score": 42,
            "num_comments": 10,
            "author": "testuser",
            "permalink": "/r/test/comments/abc/test_post/",
            "created_utc": time.time() - 3600,
            "is_self": True,
            "selftext": "This is the post body text.",
            "url": "",
            "subreddit": "test",
        }]
        result = _format_posts("test", "hot", posts)
        assert "Test Post" in result
        assert "score: 42" in result
        assert "comments: 10" in result
        assert "u/testuser" in result
        assert "This is the post body text." in result

    def test_format_link_post(self):
        posts = [{
            "title": "External Link",
            "score": 100,
            "num_comments": 5,
            "author": "linkuser",
            "permalink": "/r/test/comments/xyz/external_link/",
            "created_utc": time.time() - 7200,
            "is_self": False,
            "selftext": "",
            "url": "https://example.com/article",
            "subreddit": "test",
        }]
        result = _format_posts("test", "new", posts)
        assert "External Link" in result
        assert "https://example.com/article" in result

    def test_format_long_selftext_truncated(self):
        posts = [{
            "title": "Long Post",
            "score": 50,
            "num_comments": 3,
            "author": "author",
            "permalink": "/r/test/comments/abc/long_post/",
            "created_utc": time.time(),
            "is_self": True,
            "selftext": "A" * 300,
            "url": "",
            "subreddit": "test",
        }]
        result = _format_posts("test", "hot", posts)
        assert "..." in result


# ── Input validation tests ─────────────────────────────────


class TestInputValidation:
    @pytest.fixture
    def tool(self):
        return RedditFetchTool()

    @pytest.mark.asyncio
    async def test_empty_subreddit(self, tool):
        result = await tool.execute({"subreddit": ""})
        assert "Error" in result
        assert "required" in result

    @pytest.mark.asyncio
    async def test_invalid_subreddit_chars(self, tool):
        result = await tool.execute({"subreddit": "bad/name!"})
        assert "Error" in result
        assert "invalid subreddit" in result

    @pytest.mark.asyncio
    async def test_long_search_query(self, tool):
        result = await tool.execute({
            "subreddit": "test",
            "search_query": "x" * 201,
        })
        assert "Error" in result
        assert "too long" in result

    @pytest.mark.asyncio
    async def test_strip_r_prefix(self, tool):
        """r/ prefix should be stripped from subreddit name."""
        # This will fail at fetch (no network), but validates the prefix stripping
        result = await tool.execute({"subreddit": "r/test"})
        # Should not say "invalid subreddit" since r/ was stripped
        assert "invalid subreddit" not in result


# ── _parse_listing tests ──────────────────────────────────


class TestParseListing:
    def test_parse_valid_listing(self):
        data = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Post 1",
                            "score": 100,
                            "num_comments": 20,
                            "author": "user1",
                            "permalink": "/r/test/comments/a/post_1/",
                            "created_utc": 1700000000,
                            "is_self": True,
                            "selftext": "Body text",
                            "url": "",
                            "subreddit": "test",
                        }
                    },
                    {
                        "data": {
                            "title": "Post 2",
                            "score": 50,
                            "num_comments": 5,
                            "author": "user2",
                            "permalink": "/r/test/comments/b/post_2/",
                            "created_utc": 1700000000,
                            "is_self": False,
                            "selftext": "",
                            "url": "https://example.com",
                            "subreddit": "test",
                        }
                    },
                ]
            }
        }
        posts = RedditFetchTool._parse_listing(data)
        assert len(posts) == 2
        assert posts[0]["title"] == "Post 1"
        assert posts[0]["score"] == 100
        assert posts[0]["is_self"] is True
        assert posts[1]["url"] == "https://example.com"

    def test_parse_empty_listing(self):
        data = {"data": {"children": []}}
        assert RedditFetchTool._parse_listing(data) == []

    def test_parse_missing_data(self):
        assert RedditFetchTool._parse_listing({}) == []

    def test_parse_skips_empty_children(self):
        data = {"data": {"children": [{"data": {}}, {"kind": "t3"}]}}
        posts = RedditFetchTool._parse_listing(data)
        assert len(posts) == 0


# ── Config integration test ────────────────────────────────


class TestRedditConfig:
    def test_default_config(self):
        from mindclaw.config.schema import MindClawConfig

        config = MindClawConfig()
        assert config.tools.reddit.enabled is False
        assert config.tools.reddit.client_id == ""
        assert config.tools.reddit.rate_limit == 2.0
        assert "mindclaw" in config.tools.reddit.user_agent

    def test_config_from_dict(self):
        from mindclaw.config.schema import MindClawConfig

        config = MindClawConfig(**{
            "tools": {
                "reddit": {
                    "enabled": True,
                    "clientId": "test_id",
                    "clientSecret": "test_secret",
                    "rateLimit": 3.0,
                }
            }
        })
        assert config.tools.reddit.enabled is True
        assert config.tools.reddit.client_id == "test_id"
        assert config.tools.reddit.client_secret == "test_secret"
        assert config.tools.reddit.rate_limit == 3.0

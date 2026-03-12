#!/usr/bin/env python3
# input: feedparser, loguru
# output: 导出 NewsAggregator
# pos: 新闻聚合核心模块，RSS 多源抓取与日报生成
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import socket
import time
from datetime import datetime
from urllib.parse import urlparse

import feedparser
from loguru import logger

# RSS 请求超时 (秒) — 防止慢源阻塞
_RSS_TIMEOUT_SECONDS = 15

# 允许的 RSS 域名白名单 — 仅从受信源抓取
_ALLOWED_DOMAINS: frozenset[str] = frozenset({
    "news.ycombinator.com",
    "hnrss.org",
    "lobste.rs",
    "www.producthunt.com",
    "raw.githubusercontent.com",
    "huggingface.co",
    "bensbites.substack.com",
    "rss.beehiiv.com",
    "simonwillison.net",
    "a16z.substack.com",
    "www.technologyreview.com",
    "latentspace.substack.com",
    "chinai.substack.com",
    "techcrunch.com",
    "blog.bytebytego.com",
    "36kr.com",
    "www.decohack.com",
    "www.v2ex.com",
    "sspai.com",
    "github.com",
    "s.weibo.com",
})

class NewsAggregator:
    """新闻聚合器核心类"""

    def __init__(self):
        self.sources = {
            # --- Indie Dev / Builder ---
            "hackernews": {
                "name": "Hacker News",
                "url": "https://news.ycombinator.com/rss",
                "type": "rss",
                "tags": ["indie", "tech", "general"],
            },
            "hn_show": {
                "name": "HN Show (Product Launches)",
                "url": "https://hnrss.org/show",
                "type": "rss",
                "tags": ["indie", "launch"],
            },
            "hn_best": {
                "name": "HN Best",
                "url": "https://hnrss.org/best",
                "type": "rss",
                "tags": ["indie", "tech"],
            },
            "lobsters_ai": {
                "name": "Lobste.rs AI",
                "url": "https://lobste.rs/t/ai.rss",
                "type": "rss",
                "tags": ["ai", "tech"],
            },
            "decohack": {
                "name": "DecoHack 独立产品周刊",
                "url": "https://www.decohack.com/feed",
                "type": "rss",
                "tags": ["indie", "chinese"],
            },
            "v2ex": {
                "name": "V2EX",
                "url": "https://www.v2ex.com/index.xml",
                "type": "rss",
                "tags": ["indie", "chinese", "tech"],
            },
            "sspai": {
                "name": "少数派",
                "url": "https://sspai.com/feed",
                "type": "rss",
                "tags": ["chinese", "tech", "tools"],
            },
            # --- Product Hunt ---
            "producthunt": {
                "name": "Product Hunt",
                "url": "https://www.producthunt.com/feed",
                "type": "rss",
                "tags": ["launch", "indie"],
            },
            "ph_daily_top": {
                "name": "PH Daily Top",
                "url": "https://raw.githubusercontent.com/headllines/producthunt-daily-rss/master/rss.xml",
                "type": "rss",
                "tags": ["launch", "indie"],
            },
            # --- AI / Tech ---
            "huggingface": {
                "name": "Hugging Face Blog",
                "url": "https://huggingface.co/blog/feed.xml",
                "type": "rss",
                "tags": ["ai", "research"],
            },
            "bens_bites": {
                "name": "Ben's Bites AI",
                "url": "https://bensbites.substack.com/feed",
                "type": "rss",
                "tags": ["ai", "newsletter"],
            },
            "rundown_ai": {
                "name": "The Rundown AI",
                "url": "https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml",
                "type": "rss",
                "tags": ["ai", "newsletter"],
            },
            "simon_willison": {
                "name": "Simon Willison",
                "url": "https://simonwillison.net/atom/everything/",
                "type": "rss",
                "tags": ["ai", "tech", "llm"],
            },
            "a16z": {
                "name": "a16z Blog",
                "url": "https://a16z.substack.com/feed",
                "type": "rss",
                "tags": ["ai", "vc", "tech"],
            },
            "mit_tech": {
                "name": "MIT Technology Review",
                "url": "https://www.technologyreview.com/feed/",
                "type": "rss",
                "tags": ["ai", "research", "tech"],
            },
            "latentspace": {
                "name": "Latent Space",
                "url": "https://latentspace.substack.com/feed",
                "type": "rss",
                "tags": ["ai", "newsletter"],
            },
            "chinai": {
                "name": "ChinAI",
                "url": "https://chinai.substack.com/feed",
                "type": "rss",
                "tags": ["ai", "chinese"],
            },
            # --- Tech / Startup ---
            "techcrunch": {
                "name": "TechCrunch",
                "url": "https://techcrunch.com/feed/",
                "type": "rss",
                "tags": ["tech", "startup", "vc"],
            },
            "bytebytego": {
                "name": "ByteByteGo",
                "url": "https://blog.bytebytego.com/feed",
                "type": "rss",
                "tags": ["tech", "architecture"],
            },
            # --- Chinese Biz / Startup ---
            "36kr": {
                "name": "36氪",
                "url": "https://36kr.com/feed",
                "type": "rss",
                "tags": ["chinese", "startup", "tech"],
            },
            # --- Social / Web ---
            "github": {
                "name": "GitHub Trending",
                "url": "https://github.com/trending",
                "type": "web",
                "tags": ["tech", "opensource"],
            },
            "weibo": {
                "name": "微博热搜",
                "url": "https://s.weibo.com/top/summary",
                "type": "web",
                "tags": ["chinese", "social"],
            },
        }

    def get_sources_by_tag(self, tag: str) -> list[str]:
        """Return source IDs that carry a given tag."""
        return [
            sid for sid, src in self.sources.items()
            if tag in src.get("tags", [])
        ]

    def get_sources_by_tags(self, tags: list[str]) -> list[str]:
        """Return source IDs matching ANY of the given tags (union)."""
        result: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            for sid in self.get_sources_by_tag(tag):
                if sid not in seen:
                    seen.add(sid)
                    result.append(sid)
        return result

    @staticmethod
    def _validate_url(url: str) -> bool:
        """Validate URL against allowed domains whitelist."""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        return hostname in _ALLOWED_DOMAINS

    def fetch_rss(self, url: str, source_name: str) -> list[dict]:
        """Fetch RSS feed with timeout and domain validation."""
        if not self._validate_url(url):
            logger.warning(f"Blocked fetch from untrusted domain: {url}")
            return []
        old_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(_RSS_TIMEOUT_SECONDS)
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[:10]:
                articles.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                    "published": entry.get("published", ""),
                    "source": source_name,
                    "type": "rss",
                })
            return articles
        except (OSError, ValueError) as exc:
            logger.warning(f"Error fetching RSS from {source_name}: {exc}")
            return []
        finally:
            socket.setdefaulttimeout(old_timeout)

    def fetch_web(self, url: str, source_name: str) -> list[dict]:
        """Placeholder for web scraping (returns stub)."""
        if not self._validate_url(url):
            logger.warning(f"Blocked fetch from untrusted domain: {url}")
            return []
        return [{
            "title": f"{source_name} latest",
            "link": url,
            "summary": f"Visit {source_name} for latest content",
            "published": datetime.now().isoformat(),
            "source": source_name,
            "type": "web",
        }]

    def fetch_source(self, source_id: str) -> list[dict]:
        """获取指定源的内容"""
        if source_id not in self.sources:
            return []

        source = self.sources[source_id]

        if source["type"] == "rss":
            return self.fetch_rss(source["url"], source["name"])
        elif source["type"] == "web":
            return self.fetch_web(source["url"], source["name"])
        else:
            return []

    def fetch_multiple_sources(self, source_ids: list[str], limit_per_source: int = 5) -> list[dict]:
        """获取多个源的内容"""
        all_articles = []

        for source_id in source_ids:
            logger.debug(f"Fetching from {source_id}")
            articles = self.fetch_source(source_id)

            # 限制每个源的条目数
            if len(articles) > limit_per_source:
                articles = articles[:limit_per_source]

            all_articles.extend(articles)

            # 避免请求过快
            time.sleep(0.5)

        # 按发布时间排序（最新的在前）
        all_articles.sort(key=lambda x: x.get("published", ""), reverse=True)

        return all_articles

    def generate_daily_briefing(self, source_ids: list[str] | None = None) -> str:
        """生成每日简报"""
        if source_ids is None:
            source_ids = [
                "hackernews", "36kr", "huggingface",
                "bens_bites", "producthunt", "techcrunch",
            ]

        logger.debug(f"Generating daily briefing from sources: {source_ids}")
        articles = self.fetch_multiple_sources(source_ids)

        # 生成Markdown格式的简报
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = "# 📰 新闻聚合日报\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += f"**新闻源**: {', '.join([self.sources[sid]['name'] for sid in source_ids])}\n"
        briefing += f"**总条目数**: {len(articles)}\n\n"
        briefing += "---\n\n"

        # 按来源分组
        sources_dict = {}
        for article in articles:
            source = article["source"]
            if source not in sources_dict:
                sources_dict[source] = []
            sources_dict[source].append(article)

        # 按来源输出
        for source, source_articles in sources_dict.items():
            briefing += f"## 📊 {source}\n\n"

            for i, article in enumerate(source_articles, 1):
                briefing += f"### {i}. {article['title']}\n"
                briefing += f"- **链接**: {article['link']}\n"

                # 截取摘要
                summary = article['summary']
                if len(summary) > 200:
                    summary = summary[:200] + "..."

                briefing += f"- **摘要**: {summary}\n"

                if article.get('published'):
                    briefing += f"- **发布时间**: {article['published']}\n"

                briefing += "\n"

        briefing += "---\n"
        briefing += "**数据来源**: News Aggregator Skill v1.0\n"
        briefing += "**生成方式**: 多源聚合 + AI智能分析\n"

        return briefing

    def generate_ai_daily(self) -> str:
        """生成AI专项日报"""
        ai_sources = [
            "huggingface", "bens_bites", "rundown_ai", "simon_willison",
            "lobsters_ai", "chinai", "hackernews",
        ]

        logger.debug("Generating AI daily briefing")
        articles = self.fetch_multiple_sources(ai_sources, limit_per_source=8)

        # 筛选AI相关文章
        ai_keywords = ["AI", "人工智能", "机器学习", "深度学习", "LLM", "大模型", "transformer", "neural"]
        ai_articles = []

        for article in articles:
            title = article["title"].lower()
            summary = article["summary"].lower()

            # 检查是否包含AI关键词
            if any(keyword.lower() in title or keyword.lower() in summary for keyword in ai_keywords):
                ai_articles.append(article)

        # 生成AI日报
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = "# 🤖 AI人工智能日报\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += "**AI专项源**: Hugging Face Papers, Latent Space AINews, ChinAI, Hacker News\n"
        briefing += f"**AI相关条目**: {len(ai_articles)}/{len(articles)}\n\n"
        briefing += "---\n\n"

        if not ai_articles:
            briefing += "⚠️ 今日未发现显著的AI相关新闻\n\n"
        else:
            # 按技术领域分类（简化版）
            categories = {
                "大模型技术": ["LLM", "大模型", "transformer", "GPT"],
                "开源项目": ["开源", "github", "huggingface", "release"],
                "行业动态": ["融资", "合作", "发布", "战略"],
                "研究论文": ["论文", "research", "arxiv", "预印本"]
            }

            categorized = {cat: [] for cat in categories.keys()}
            categorized["其他"] = []

            for article in ai_articles:
                title = article["title"]
                assigned = False

                for category, keywords in categories.items():
                    if any(keyword.lower() in title.lower() for keyword in keywords):
                        categorized[category].append(article)
                        assigned = True
                        break

                if not assigned:
                    categorized["其他"].append(article)

            # 输出分类内容
            for category, cat_articles in categorized.items():
                if cat_articles:
                    briefing += f"## 🎯 {category}\n\n"

                    for i, article in enumerate(cat_articles, 1):
                        briefing += f"### {i}. {article['title']}\n"
                        briefing += f"- **来源**: {article['source']}\n"
                        briefing += f"- **链接**: {article['link']}\n"

                        summary = article['summary']
                        if len(summary) > 150:
                            summary = summary[:150] + "..."

                        briefing += f"- **要点**: {summary}\n\n"

        briefing += "---\n"
        briefing += "**特别关注**:\n"
        briefing += "1. Hugging Face最新论文发布\n"
        briefing += "2. 开源AI项目进展\n"
        briefing += "3. AI行业融资动态\n"
        briefing += "4. 大模型技术突破\n"

        return briefing


def main():
    """主函数 - 测试新闻聚合功能"""
    aggregator = NewsAggregator()

    print("=" * 60)
    print("News Aggregator Skill - 测试运行")
    print("=" * 60)

    # 测试1: 获取单个源
    print("\n1. 测试单个源 (Hacker News):")
    hackernews_articles = aggregator.fetch_source("hackernews")
    print(f"获取到 {len(hackernews_articles)} 条Hacker News文章")

    # 测试2: 生成AI日报
    print("\n2. 生成AI专项日报:")
    ai_daily = aggregator.generate_ai_daily()
    print(f"AI日报生成完成，长度: {len(ai_daily)} 字符")

    # 保存到文件
    with open("ai_daily_test.md", "w", encoding="utf-8") as f:
        f.write(ai_daily)

    print("\nAI日报已保存到: ai_daily_test.md")

    # 测试3: 生成综合简报
    print("\n3. 生成综合简报:")
    daily_briefing = aggregator.generate_daily_briefing()
    print(f"综合简报生成完成，长度: {len(daily_briefing)} 字符")

    with open("daily_briefing_test.md", "w", encoding="utf-8") as f:
        f.write(daily_briefing)

    print("综合简报已保存到: daily_briefing_test.md")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

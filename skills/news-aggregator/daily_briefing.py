#!/usr/bin/env python3
# input: fetch_news.py
# output: 导出 DailyBriefingGenerator
# pos: 场景化日报生成器，预设 8 种日报模板
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

from datetime import datetime

from fetch_news import NewsAggregator
from loguru import logger


class DailyBriefingGenerator:
    """日报生成器"""

    def __init__(self):
        self.aggregator = NewsAggregator()

        # 预设场景配置
        self.scenarios = {
            "综合早报": {
                "name": "综合早报",
                "description": "覆盖科技、金融、社会热点的综合日报",
                "sources": ["hackernews", "36kr", "techcrunch", "producthunt"],
                "template": "综合",
            },
            "财经早报": {
                "name": "财经早报",
                "description": "聚焦金融市场、经济政策、投资动态",
                "sources": ["36kr", "techcrunch"],
                "template": "财经",
            },
            "科技早报": {
                "name": "科技早报",
                "description": "科技行业动态、产品发布、技术突破",
                "sources": ["hackernews", "36kr", "github", "techcrunch", "bytebytego"],
                "template": "科技",
            },
            "AI深度日报": {
                "name": "AI深度日报",
                "description": "AI 技术进展、工具发布、行业洞察",
                "sources": [
                    "huggingface", "bens_bites", "rundown_ai",
                    "simon_willison", "lobsters_ai", "chinai", "hackernews",
                ],
                "template": "AI",
            },
            "独立开发者日报": {
                "name": "独立开发者日报",
                "description": "独立开发者动态、产品发布、增长策略、社区讨论",
                "sources": [
                    "hn_show", "producthunt", "ph_daily_top",
                    "decohack", "v2ex", "sspai",
                ],
                "template": "indie",
            },
            "Product Hunt日报": {
                "name": "Product Hunt日报",
                "description": "Product Hunt 每日精选、新品发布、趋势追踪",
                "sources": ["producthunt", "ph_daily_top", "hn_show"],
                "template": "producthunt",
            },
            "增长黑客日报": {
                "name": "增长黑客日报",
                "description": "增长策略、工具分发、SaaS/AI 产品冷启动",
                "sources": [
                    "hn_show", "producthunt", "bens_bites",
                    "techcrunch", "a16z", "decohack",
                ],
                "template": "growth",
            },
            "吃瓜早报": {
                "name": "吃瓜早报",
                "description": "社会热点、娱乐八卦、网络话题",
                "sources": ["weibo"],
                "template": "娱乐",
            },
        }

    def generate_scenario_briefing(self, scenario_name: str) -> str:
        """生成指定场景的简报"""
        if scenario_name not in self.scenarios:
            return f"错误：未知的场景 '{scenario_name}'"

        scenario = self.scenarios[scenario_name]
        logger.debug(f"Generating {scenario_name}")

        # 获取新闻数据
        articles = self.aggregator.fetch_multiple_sources(scenario["sources"])

        # 根据模板生成内容
        template_map = {
            "综合": self._generate_comprehensive_briefing,
            "财经": self._generate_finance_briefing,
            "科技": self._generate_tech_briefing,
            "AI": self._generate_ai_briefing,
            "indie": self._generate_indie_briefing,
            "producthunt": self._generate_producthunt_briefing,
            "growth": self._generate_growth_briefing,
            "娱乐": self._generate_entertainment_briefing,
        }
        handler = template_map.get(scenario["template"], self._generate_default_briefing)
        return handler(scenario, articles)

    def _generate_comprehensive_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成综合简报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = f"# 🌅 {scenario['name']}\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += f"**简报类型**: {scenario['description']}\n"
        briefing += f"**覆盖源数**: {len(scenario['sources'])} 个\n"
        briefing += f"**新闻条数**: {len(articles)} 条\n\n"

        briefing += "---\n\n"
        briefing += "## 📊 今日要闻速览\n\n"

        # 按来源分组展示
        sources_dict = {}
        for article in articles:
            source = article["source"]
            if source not in sources_dict:
                sources_dict[source] = []
            sources_dict[source].append(article)

        for source, source_articles in sources_dict.items():
            briefing += f"### 📍 {source}\n\n"

            for i, article in enumerate(source_articles[:5], 1):  # 每个源最多5条
                title = article['title']
                if len(title) > 50:
                    title = title[:50] + "..."

                briefing += f"{i}. **{title}**\n"
                briefing += f"   🔗 {article['link']}\n\n"

        briefing += "---\n\n"
        briefing += "## 🎯 重点关注\n\n"

        # 提取关键新闻（简化逻辑）
        if len(articles) > 0:
            key_articles = articles[:3]  # 取最新的3条作为重点关注
            for i, article in enumerate(key_articles, 1):
                briefing += f"### {i}. {article['title']}\n"

                summary = article['summary']
                if len(summary) > 100:
                    summary = summary[:100] + "..."

                briefing += f"- **核心内容**: {summary}\n"
                briefing += f"- **来源**: {article['source']}\n"
                briefing += f"- **详情**: {article['link']}\n\n"

        briefing += "---\n"
        briefing += "**明日预告**: 将继续追踪热点，提供深度分析\n"
        briefing += "**数据支持**: News Aggregator Skill\n"

        return briefing

    def _generate_finance_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成财经简报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = f"# 💰 {scenario['name']}\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += "**市场视角**: 全球金融市场动态\n"
        briefing += f"**数据源**: {', '.join([self.aggregator.sources[s]['name'] for s in scenario['sources']])}\n\n"

        briefing += "---\n\n"

        if not articles:
            briefing += "⚠️ 今日暂无重要财经新闻\n\n"
        else:
            briefing += "## 📈 市场要闻\n\n"

            for i, article in enumerate(articles[:10], 1):
                briefing += f"### {i}. {article['title']}\n"
                briefing += f"- **来源**: {article['source']}\n"

                # 财经相关标签
                finance_keywords = ["股", "市", "涨", "跌", "利率", "汇率", "通胀", "GDP", "财报", "融资"]
                title_lower = article['title'].lower()

                tags = []
                for keyword in finance_keywords:
                    if keyword in title_lower:
                        tags.append(keyword)

                if tags:
                    briefing += f"- **标签**: {'、'.join(tags[:3])}\n"

                briefing += f"- **链接**: {article['link']}\n\n"

        briefing += "---\n"
        briefing += "**风险提示**: 市场有风险，投资需谨慎\n"
        briefing += "**信息来源**: 公开市场数据\n"

        return briefing

    def _generate_tech_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成科技简报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = f"# 🚀 {scenario['name']}\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += "**科技前沿**: 技术创新与行业动态\n"
        briefing += "**技术领域**: 软件、硬件、互联网、人工智能\n\n"

        briefing += "---\n\n"

        if not articles:
            briefing += "⚠️ 今日暂无重要科技新闻\n\n"
        else:
            # 分类展示
            categories = {
                "开源技术": ["github", "开源", "release", "版本"],
                "产品发布": ["发布", "新品", "上市", "launch"],
                "技术突破": ["突破", "创新", "首次", "record"],
                "行业动态": ["融资", "合作", "收购", "战略"]
            }

            categorized = {cat: [] for cat in categories}
            categorized["其他"] = []

            for article in articles:
                title_lower = article['title'].lower()
                assigned = False

                for category, keywords in categories.items():
                    if any(keyword in title_lower for keyword in keywords):
                        categorized[category].append(article)
                        assigned = True
                        break

                if not assigned:
                    categorized["其他"].append(article)

            # 输出分类内容
            for category, cat_articles in categorized.items():
                if cat_articles:
                    briefing += f"## 🔧 {category}\n\n"

                    for i, article in enumerate(cat_articles[:5], 1):
                        briefing += f"{i}. **{article['title']}**\n"
                        briefing += f"   📍 {article['source']} | 🔗 {article['link']}\n\n"

        briefing += "---\n"
        briefing += "**技术趋势**: 持续关注AI、云计算、开源生态\n"
        briefing += "**创新指数**: 🔥🔥🔥\n"

        return briefing

    def _generate_ai_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成AI简报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = f"# 🤖 {scenario['name']}\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += "**AI深度**: 人工智能技术进展与行业洞察\n"
        briefing += "**专业级别**: 技术向 + 行业向\n\n"

        briefing += "---\n\n"

        # 使用专门的AI日报生成
        ai_briefing = self.aggregator.generate_ai_daily()

        # 提取AI日报的核心部分
        lines = ai_briefing.split('\n')
        start_idx = 0
        for i, line in enumerate(lines):
            if "## 🎯" in line or "## 📊" in line:
                start_idx = i
                break

        if start_idx > 0:
            briefing += '\n'.join(lines[start_idx:])
        else:
            briefing += ai_briefing

        return briefing

    def _generate_entertainment_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成娱乐简报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = f"# 🍉 {scenario['name']}\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += "**吃瓜指南**: 网络热点与社会话题\n"
        briefing += "**快乐源泉**: 微博热搜榜\n\n"

        briefing += "---\n\n"

        if not articles:
            briefing += "😴 今日网络平静，暂无爆款热搜\n\n"
        else:
            briefing += "## 🔥 热搜榜单\n\n"

            for i, article in enumerate(articles[:15], 1):
                # 模拟热搜排名
                rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                hot_level = "🔥" * min(5, (16 - i) // 3)  # 排名越靠前，热度越高

                title = article['title']
                # 清理标题
                if "微博" in title:
                    title = title.replace("微博", "").strip()
                if "热搜" in title:
                    title = title.replace("热搜", "").strip()

                briefing += f"{rank_emoji} **{title}** {hot_level}\n"
                briefing += f"   📍 微博热搜 | 🔗 {article['link']}\n\n"

        briefing += "---\n"
        briefing += "**温馨提示**: 理性吃瓜，快乐冲浪\n"
        briefing += "**数据来源**: 微博实时热搜榜\n"

        return briefing

    def _generate_indie_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成独立开发者日报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = "# 独立开发者日报\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += "**覆盖平台**: HN Show / Product Hunt / DecoHack / V2EX / 少数派\n"
        briefing += f"**新闻条数**: {len(articles)}\n\n"
        briefing += "---\n\n"

        if not articles:
            briefing += "今日暂无独立开发者相关动态\n\n"
        else:
            # 按来源分组
            sources_dict: dict[str, list] = {}
            for article in articles:
                src = article["source"]
                sources_dict.setdefault(src, []).append(article)

            for source, items in sources_dict.items():
                briefing += f"## {source}\n\n"
                for i, article in enumerate(items[:8], 1):
                    briefing += f"{i}. **{article['title']}**\n"
                    briefing += f"   {article['link']}\n\n"

        briefing += "---\n"
        briefing += "**关注重点**: 产品 Launch / 增长策略 / 开源工具 / 冷启动经验\n"
        return briefing

    def _generate_producthunt_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成 Product Hunt 日报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = "# Product Hunt 日报\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += "**数据源**: PH Official + PH Daily Top + HN Show\n"
        briefing += f"**产品数**: {len(articles)}\n\n"
        briefing += "---\n\n"

        if not articles:
            briefing += "今日暂无 Product Hunt 新品\n\n"
        else:
            briefing += "## 今日新品\n\n"
            for i, article in enumerate(articles[:15], 1):
                briefing += f"### {i}. {article['title']}\n"
                summary = article.get("summary", "")
                if len(summary) > 200:
                    summary = summary[:200] + "..."
                if summary:
                    briefing += f"- **简介**: {summary}\n"
                briefing += f"- **来源**: {article['source']}\n"
                briefing += f"- **链接**: {article['link']}\n\n"

        briefing += "---\n"
        briefing += "**筛选建议**: 关注 AI / 开发者工具 / SaaS / 增长类产品\n"
        return briefing

    def _generate_growth_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成增长黑客日报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = "# 增长黑客日报\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += "**覆盖维度**: 产品发布 / AI 工具 / VC 趋势 / 冷启动\n"
        briefing += f"**条目数**: {len(articles)}\n\n"
        briefing += "---\n\n"

        if not articles:
            briefing += "今日暂无增长相关动态\n\n"
        else:
            # 按增长相关性分类
            growth_keywords = {
                "产品发布": ["launch", "new", "release", "ship", "发布", "上线"],
                "融资动态": ["raise", "funding", "series", "融资", "投资", "vc"],
                "增长策略": ["growth", "marketing", "seo", "分发", "增长", "cold start"],
            }

            categorized: dict[str, list] = {cat: [] for cat in growth_keywords}
            categorized["其他"] = []

            for article in articles:
                title_lower = article["title"].lower()
                assigned = False
                for category, keywords in growth_keywords.items():
                    if any(kw in title_lower for kw in keywords):
                        categorized[category].append(article)
                        assigned = True
                        break
                if not assigned:
                    categorized["其他"].append(article)

            for category, items in categorized.items():
                if items:
                    briefing += f"## {category}\n\n"
                    for i, article in enumerate(items[:6], 1):
                        briefing += f"{i}. **{article['title']}**\n"
                        briefing += f"   {article['source']} | {article['link']}\n\n"

        briefing += "---\n"
        briefing += "**行动指南**: 提取可复用的增长策略、工具和案例\n"
        return briefing

    def _generate_default_briefing(self, scenario: dict, articles: list[dict]) -> str:
        """生成默认简报"""
        now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        briefing = f"# 📰 {scenario['name']}\n\n"
        briefing += f"**生成时间**: {now}\n"
        briefing += f"**场景描述**: {scenario['description']}\n\n"

        briefing += "---\n\n"

        if not articles:
            briefing += "📭 今日暂无相关新闻\n\n"
        else:
            briefing += "## 📋 新闻列表\n\n"

            for i, article in enumerate(articles, 1):
                briefing += f"{i}. **{article['title']}**\n"
                briefing += f"   - 来源: {article['source']}\n"
                briefing += f"   - 链接: {article['link']}\n\n"

        briefing += "---\n"
        briefing += "**生成工具**: Daily Briefing Generator\n"

        return briefing

    def list_scenarios(self) -> str:
        """列出所有可用场景"""
        result = "# 🎪 可用日报场景\n\n"
        result += "以下是当前支持的日报类型，选择序号生成对应简报：\n\n"

        for i, (key, scenario) in enumerate(self.scenarios.items(), 1):
            result += f"## {i}. {scenario['name']}\n"
            result += f"- **描述**: {scenario['description']}\n"
            result += f"- **关键词**: {', '.join(scenario['sources'])}\n"
            result += f"- **触发命令**: `生成{scenario['name']}`\n\n"

        result += "---\n"
        result += "**使用方法**:\n"
        result += "1. 输入场景名称或序号\n"
        result += "2. 系统自动生成对应日报\n"
        result += "3. 支持自定义源组合\n"

        return result


def main():
    """主函数 - 测试日报生成"""
    generator = DailyBriefingGenerator()

    print("=" * 60)
    print("Daily Briefing Generator - 场景化日报测试")
    print("=" * 60)

    # 列出所有场景
    print("\n📋 可用场景列表:")
    scenarios_list = generator.list_scenarios()
    print(scenarios_list)

    # 测试生成AI日报
    print("\n🧪 测试生成AI深度日报:")
    ai_briefing = generator.generate_scenario_briefing("AI深度日报")

    # 保存测试结果
    with open("ai_depth_daily_test.md", "w", encoding="utf-8") as f:
        f.write(ai_briefing)

    print(f"AI深度日报已保存，长度: {len(ai_briefing)} 字符")

    # 预览前500字符
    preview = ai_briefing[:500] + "..." if len(ai_briefing) > 500 else ai_briefing
    print(f"\n📄 预览:\n{preview}")

    # 测试生成综合早报
    print("\n🧪 测试生成综合早报:")
    comprehensive_briefing = generator.generate_scenario_briefing("综合早报")

    with open("comprehensive_daily_test.md", "w", encoding="utf-8") as f:
        f.write(comprehensive_briefing)

    print(f"综合早报已保存，长度: {len(comprehensive_briefing)} 字符")

    print("\n" + "=" * 60)
    print("测试完成！生成的文件:")
    print("1. ai_depth_daily_test.md - AI深度日报")
    print("2. comprehensive_daily_test.md - 综合早报")
    print("=" * 60)


if __name__ == "__main__":
    main()

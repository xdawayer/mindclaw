# input: fetch_news.py, daily_briefing.py
# output: 导出 NewsAggregatorSkill, skill_entry
# pos: 新闻聚合技能入口，提供命令路由和帮助文本
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import os
import sys

# skills/ directory uses direct imports (not a proper package)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daily_briefing import DailyBriefingGenerator  # noqa: E402
from fetch_news import NewsAggregator  # noqa: E402


class NewsAggregatorSkill:
    """新闻聚合技能主类"""

    def __init__(self):
        self.aggregator = NewsAggregator()
        self.generator = DailyBriefingGenerator()
        self.version = "1.0.0"

    def get_info(self) -> dict:
        """获取技能信息"""
        return {
            "name": "news-aggregator",
            "version": self.version,
            "description": "全网科技/金融/AI深度新闻聚合助手",
            "author": "MindClaw AI Assistant",
            "sources_count": len(self.aggregator.sources),
            "scenarios_count": len(self.generator.scenarios)
        }

    def handle_command(self, command: str) -> str:
        """处理用户命令"""
        command_lower = command.lower().strip()

        # 交互菜单唤醒词
        if "如意如意" in command or "news-aggregator-skill" in command:
            return self.generator.list_scenarios()

        # 场景匹配
        scenarios = self.generator.scenarios
        for scenario_name in scenarios.keys():
            if scenario_name in command or scenario_name.replace("早报", "") in command:
                return self.generator.generate_scenario_briefing(scenario_name)

        # AI日报相关
        if "ai" in command_lower or "人工智能" in command:
            if "日报" in command or "daily" in command_lower:
                return self.generator.generate_scenario_briefing("AI深度日报")
            else:
                return self.aggregator.generate_ai_daily()

        # 默认返回技能介绍
        return self._get_help_text()

    def _get_help_text(self) -> str:
        """获取帮助文本"""
        help_text = f"""
# 🗞️ News Aggregator Skill v{self.version}

**全网科技/金融/AI深度新闻聚合助手**

## 🎯 核心功能

1. **多源新闻聚合** - 覆盖 {len(self.aggregator.sources)} 个高质量信源
2. **场景化日报** - {len(self.generator.scenarios)} 种预设场景
3. **AI深度分析** - 智能提取与总结
4. **交互式菜单** - 便捷操作体验

## 🚀 快速开始

### 方法1: 交互菜单
输入: `news-aggregator-skill 如意如意`

### 方法2: 场景日报
- `生成综合早报`
- `生成财经早报`
- `生成科技早报`
- `生成AI深度日报`
- `生成独立开发者日报`
- `生成Product Hunt日报`
- `生成增长黑客日报`
- `生成吃瓜早报`

### 方法3: 直接命令
- `AI日报` - 生成AI专项日报
- `今日新闻` - 生成综合简报
- `微博热搜` - 查看热点话题

## 📊 数据源概览

**核心新闻源** ({len(self.aggregator.sources)}个):
- Indie: HN Show, Product Hunt, DecoHack, V2EX, 少数派
- AI: Ben's Bites, Rundown AI, Simon Willison, HuggingFace, Lobste.rs
- Tech: TechCrunch, ByteByteGo, a16z, MIT Tech Review
- CN: 36Kr, 华尔街见闻, ChinAI

**日报场景** ({len(self.generator.scenarios)}种):
- 综合早报、财经早报、科技早报、AI深度日报
- 独立开发者日报、Product Hunt日报、增长黑客日报、吃瓜早报

## 💡 使用示例

```
用户: news-aggregator-skill 如意如意
AI: 显示交互菜单...

用户: 生成AI深度日报
AI: 生成AI专项日报...

用户: 今日有什么AI新闻？
AI: 获取最新AI动态...
```

---
**技能状态**: ✅ 已激活
**最后更新**: 2026-03-11
**支持平台**: MindClaw AI Assistant
"""
        return help_text.strip()


# 创建全局实例
news_skill = NewsAggregatorSkill()


def skill_entry(command: str) -> str:
    """
    技能入口函数 - 供外部调用
    
    Args:
        command: 用户命令文本
        
    Returns:
        技能响应文本
    """
    try:
        return news_skill.handle_command(command)
    except Exception as e:
        return f"❌ 技能执行出错: {str(e)}\n\n请检查技能配置或稍后重试。"


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("News Aggregator Skill - 本地测试")
    print("=" * 60)

    # 测试技能信息
    info = news_skill.get_info()
    print("\n📊 技能信息:")
    for key, value in info.items():
        print(f"  {key}: {value}")

    # 测试帮助命令
    print("\n📖 帮助文档:")
    help_text = news_skill._get_help_text()
    print(help_text[:300] + "...")

    # 测试交互菜单
    print("\n🎪 交互菜单测试:")
    menu = news_skill.handle_command("如意如意")
    print(menu[:500] + "...")

    print("\n" + "=" * 60)
    print("本地测试完成！")
    print("=" * 60)

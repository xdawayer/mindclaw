#!/usr/bin/env python3
"""
测试news-aggregator技能
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from daily_briefing import DailyBriefingGenerator


def test_skill():
    """测试技能功能"""
    print("🧪 测试news-aggregator技能...")

    generator = DailyBriefingGenerator()

    # 测试1：显示菜单
    print("\n" + "="*50)
    print("测试1：交互菜单")
    print("="*50)
    menu = generator.show_interactive_menu()
    print(menu[:500] + "..." if len(menu) > 500 else menu)

    # 测试2：生成AI日报
    print("\n" + "="*50)
    print("测试2：AI专属日报")
    print("="*50)
    ai_daily = generator.generate_ai_daily()
    print(ai_daily[:800] + "..." if len(ai_daily) > 800 else ai_daily)

    # 测试3：生成综合早报
    print("\n" + "="*50)
    print("测试3：综合早报")
    print("="*50)
    try:
        briefing = generator.generate_briefing("综合早报")
        print(briefing[:600] + "..." if len(briefing) > 600 else briefing)
    except Exception as e:
        print(f"生成失败: {e}")

    print("\n✅ 技能测试完成！")

if __name__ == "__main__":
    test_skill()

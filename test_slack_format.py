#!/usr/bin/env python3
"""测试Slack格式转换"""

import sys
sys.path.append('.')

try:
    from mindclaw.channels.slack_format import markdown_to_slack
    print("✅ 成功导入 markdown_to_slack 函数")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# 测试格式转换
test_md = '''# AI日报测试
## 重要新闻
- OpenAI发布新模型
- Google AI进展
- Meta开源项目

**粗体文本** 和 *斜体文本*

```python
print('Hello Slack!')
```'''

print("\n📝 原始Markdown:")
print("-" * 40)
print(test_md)
print("-" * 40)

print("\n🎨 转换后的Slack格式:")
print("-" * 40)
converted = markdown_to_slack(test_md)
print(converted)
print("-" * 40)

# 分析转换效果
print("\n🔍 转换分析:")
print(f"原始长度: {len(test_md)} 字符")
print(f"转换后长度: {len(converted)} 字符")
print(f"是否包含Markdown符号:")
print(f"  #标题: {'#' in converted}")
print(f"  **粗体: {'**' in converted}")
print(f"  ```代码块: {'```' in converted}")

# 测试更多格式
print("\n🧪 更多格式测试:")
test_cases = [
    ("### 三级标题", "三级标题"),
    ("1. 有序列表", "有序列表"),
    ("[链接](https://example.com)", "链接"),
    ("`内联代码`", "内联代码"),
]

for md, desc in test_cases:
    result = markdown_to_slack(md)
    print(f"  {desc}: '{md}' → '{result}'")
#!/usr/bin/env python3
"""
AI日报生成器 - 整合多种信息来源
支持：网页搜索、RSS订阅、本地文档、X/Twitter等
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any
import requests
import feedparser

class AIDailyGenerator:
    """AI日报生成器"""
    
    def __init__(self, config_path: str = "data/ai_news_sources.json"):
        """初始化生成器"""
        self.config_path = config_path
        self.config = self.load_config()
        self.today = datetime.now().strftime("%Y-%m-%d")
        
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # 返回默认配置
            return {
                "rss_feeds": [],
                "twitter_accounts": [],
                "news_websites": [],
                "research_papers": [],
                "local_sources": []
            }
    
    def fetch_rss_news(self) -> List[Dict[str, str]]:
        """获取RSS新闻"""
        news_items = []
        
        for rss_url in self.config.get("rss_feeds", []):
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:5]:  # 每个源取最新5条
                    news_items.append({
                        "title": entry.get("title", "无标题"),
                        "summary": entry.get("summary", entry.get("description", "")),
                        "link": entry.get("link", ""),
                        "source": feed.feed.get("title", rss_url),
                        "published": entry.get("published", "")
                    })
            except Exception as e:
                print(f"RSS解析失败 {rss_url}: {e}")
        
        return news_items
    
    def search_web_news(self, query: str = "AI人工智能最新进展 2026") -> List[Dict[str, str]]:
        """搜索网页新闻（需要外部API）"""
        # 这里可以调用Tavily API或其他搜索API
        # 暂时返回空列表，实际使用时需要实现
        return []
    
    def read_local_documents(self) -> List[Dict[str, str]]:
        """读取本地文档"""
        local_news = []
        local_sources = self.config.get("local_sources", [])
        
        for source_path in local_sources:
            if os.path.exists(source_path):
                # 这里需要根据实际文件类型进行解析
                # 暂时返回示例数据
                local_news.append({
                    "title": "本地文档示例",
                    "content": f"来自 {source_path} 的本地信息",
                    "source": "本地文档",
                    "date": self.today
                })
        
        return local_news
    
    def categorize_news(self, news_items: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
        """对新闻进行分类"""
        categories = {
            "技术突破": [],
            "行业动态": [],
            "融资并购": [],
            "政策法规": [],
            "研究论文": [],
            "产品发布": [],
            "人物观点": []
        }
        
        # 关键词分类
        tech_keywords = ["GPT", "模型", "算法", "突破", "创新", "技术"]
        industry_keywords = ["合作", "战略", "市场", "竞争", "生态", "联盟"]
        funding_keywords = ["融资", "投资", "并购", "IPO", "估值", "轮次"]
        
        for item in news_items:
            title = item.get("title", "").lower()
            content = item.get("summary", item.get("content", "")).lower()
            text = title + " " + content
            
            # 分类逻辑
            if any(keyword in text for keyword in tech_keywords):
                categories["技术突破"].append(item)
            elif any(keyword in text for keyword in industry_keywords):
                categories["行业动态"].append(item)
            elif any(keyword in text for keyword in funding_keywords):
                categories["融资并购"].append(item)
            else:
                categories["行业动态"].append(item)  # 默认分类
        
        return categories
    
    def generate_daily_report(self) -> str:
        """生成日报"""
        # 收集各种来源的新闻
        rss_news = self.fetch_rss_news()
        local_news = self.read_local_documents()
        
        # 合并所有新闻
        all_news = rss_news + local_news
        
        if not all_news:
            return "⚠️ 今天没有收集到AI相关新闻"
        
        # 分类新闻
        categorized = self.categorize_news(all_news)
        
        # 生成Markdown格式的日报
        report = f"# 🤖 AI日报 - {self.today}\n\n"
        
        # 今日头条（取最重要的3条）
        report += "## 🚀 今日头条\n"
        top_news = all_news[:3]
        for i, news in enumerate(top_news, 1):
            report += f"{i}. **{news.get('title', '无标题')}**\n"
            report += f"   - {news.get('summary', '')[:100]}...\n"
            if news.get('link'):
                report += f"   - [阅读原文]({news.get('link')})\n"
            report += "\n"
        
        # 各分类新闻
        for category, items in categorized.items():
            if items:
                report += f"## 📊 {category}\n"
                for item in items[:5]:  # 每个分类最多5条
                    report += f"- **{item.get('title', '无标题')}**\n"
                    if item.get('source'):
                        report += f"  *来源: {item.get('source')}*\n"
                report += "\n"
        
        # 总结与展望
        report += "## 💡 今日总结与展望\n"
        report += "1. **技术趋势**: 关注大模型持续优化和小模型崛起\n"
        report += "2. **应用场景**: AI在各行业的渗透加速\n"
        report += "3. **投资热点**: AI基础设施和工具链受资本青睐\n"
        report += "4. **政策环境**: 各国AI监管政策逐步完善\n\n"
        
        report += "---\n"
        report += f"📈 今日共收集 {len(all_news)} 条AI相关新闻\n"
        report += f"⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return report
    
    def save_report(self, report: str, output_dir: str = "data/daily_reports"):
        """保存日报到文件"""
        os.makedirs(output_dir, exist_ok=True)
        filename = f"ai_daily_{self.today}.md"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return filepath


def main():
    """主函数"""
    print("开始生成AI日报...")
    
    generator = AIDailyGenerator()
    
    # 生成日报
    report = generator.generate_daily_report()
    
    # 保存日报
    saved_path = generator.save_report(report)
    
    print(f"日报已生成并保存到: {saved_path}")
    print("\n" + "="*50 + "\n")
    print(report)
    
    return report


if __name__ == "__main__":
    main()
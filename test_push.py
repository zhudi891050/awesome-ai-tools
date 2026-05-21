"""测试GEO → 网站推送"""
import os, sys
sys.path.insert(0, ".")
# 显式设环境变量
os.environ["WEBSITE_API_URL"] = "http://localhost:4000/api"
os.environ["WEBSITE_API_KEY"] = "be3e74d15952cf24eb02524413ef358a34ef33f43f8505c11a602589113dfca9"
os.environ["DEEPSEEK_API_KEY"] = "***"

from config_loader import load_config
from publisher.website import WebsitePublisher
import asyncio

async def test():
    config = load_config()
    pub = WebsitePublisher(config)
    print(f"API URL: {pub.api_url}")
    print(f"API Key: {'***' if pub.api_key else '未设置'}")
    print(f"Enabled: {pub.enabled}")
    
    # 测试推送
    test_article = {
        "title": "2026年最好用的AI音频工具推荐（测试推送）",
        "content": "<h1>AI音频工具推荐</h1><p>测试内容</p>",
        "type": "tool_list",
        "category": "AI音频",
        "tags": "音频工具,AI",
        "summary": "2026年AI音频工具推荐"
    }
    success, url = await pub.publish(test_article)
    print(f"推送结果: {'✅ 成功' if success else '❌ 失败'} → {url}")

asyncio.run(test())

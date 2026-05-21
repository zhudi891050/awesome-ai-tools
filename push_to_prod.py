"""推送已生成的文章到生产服务器"""
import os, sys, json, httpx, asyncio
from pathlib import Path

ROOT = Path(__file__).parent

# 加载 .env
env_path = ROOT / ".env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

WEBSITE_API_URL = os.environ.get("WEBSITE_API_URL", "http://39.102.49.11:4000/api")
WEBSITE_API_KEY = os.environ.get("WEBSITE_API_KEY", "")

async def push_articles():
    # 读取今天的文章清单
    list_path = ROOT / "data" / "today_articles.json"
    if not list_path.exists():
        print("❌ 找不到 today_articles.json，请先运行 generate")
        return
    
    with open(list_path, "r", encoding="utf-8") as f:
        articles = json.load(f)
    
    print(f"📤 准备推送 {len(articles)} 篇文章到 {WEBSITE_API_URL}")
    
    headers = {"Content-Type": "application/json"}
    if WEBSITE_API_KEY:
        headers["x-api-key"] = WEBSITE_API_KEY
    
    success_count = 0
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        for article in articles:
            # 读取HTML内容
            html_path = ROOT / article.get("html_path", "")
            if not html_path.exists():
                print(f"  ⚠️ 跳过 {article['title']}: HTML文件不存在")
                continue
            
            content = html_path.read_text(encoding="utf-8")
            
            payload = {
                "title": article["title"],
                "content": content,
                "content_type": article.get("type", "tool_review"),
                "category": article.get("category", ""),
            }
            
            try:
                resp = await client.post(
                    f"{WEBSITE_API_URL}/articles",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    article_url = f"https://xinfangzhouai.com/article/{data.get('slug', '')}"
                    print(f"  ✅ {article['title'][:30]}... → {article_url}")
                    success_count += 1
                else:
                    print(f"  ❌ {article['title'][:30]}... → HTTP {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                print(f"  ❌ {article['title'][:30]}... → {str(e)[:60]}")
    
    print(f"\n📊 推送完成: {success_count}/{len(articles)} 篇成功")

asyncio.run(push_articles())

"""GEO系统自动化运行器 — 供定时任务调用
用法:
    python run_geo.py generate   # 每日内容生成+分发
    python run_geo.py track      # AI可见度追踪
    python run_geo.py report     # 生成日报+推送通知
    python run_geo.py full       # 全流程：生成→追踪→报告
"""
import os
import sys
import asyncio
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# 加载 .env 文件（如果存在）
_env_path = ROOT / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                if val and not os.environ.get(key.strip()):
                    os.environ[key.strip()] = val
    print("✅ 已加载 .env 配置")

from config_loader import load_config
from database import init_db


async def run_generate():
    """每日内容生成 + 平台适配 + 分发发布"""
    from content.generator import ContentGenerator
    from publisher.github import GitHubPublisher
    from publisher.website import WebsitePublisher
    from publisher.rss import RSSPublisher
    from publisher.csdn import CSDNPublisher
    from publisher.juejin import JuejinPublisher
    from publisher.zhihu import ZhihuPublisher

    print("📝 开始每日内容生成...")
    config = load_config()
    gen = ContentGenerator()
    batch = await gen.generate_daily_batch()

    original = batch.get("original_articles", [])
    distribution = batch.get("platform_distribution", {})

    print(f"📊 共生成 {len(original)} 篇，分发到 {len(distribution)} 个平台")

    # ⭐ 保存所有文章到数据库 + HTML文件（无论发布是否成功）
    saved_count = 0
    article_records = []  # 记录每篇文章的分发情况
    articles_dir = ROOT / "data" / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    for article in original:
        try:
            from database import db_cursor
            with db_cursor() as cursor:
                cursor.execute(
                    """INSERT INTO contents (title, content_type, body_markdown, json_ld, tags, status)
                       VALUES (?, ?, ?, ?, ?, 'draft')""",
                    (
                        article.get("title", ""),
                        article.get("type", "tool_review"),
                        article.get("content", ""),
                        article.get("json_ld", ""),
                        article.get("category", ""),
                    ),
                )
                article_id = cursor.lastrowid
                saved_count += 1
            
            # 保存HTML文件
            html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{article.get('title','')}</title>
<style>body{{max-width:800px;margin:0 auto;padding:20px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.8;color:#333}}h1{{border-bottom:2px solid #4A90D9;padding-bottom:10px}}h2{{color:#4A90D9;margin-top:30px}}h3{{color:#555}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#f5f5f5}}blockquote{{border-left:3px solid #4A90D9;padding-left:15px;color:#666;margin:15px 0}}a{{color:#4A90D9}}@media(prefers-color-scheme:dark){{body{{background:#1a1a2e;color:#ccc}}h2{{color:#7BB3F0}}blockquote{{color:#999}}td,th{{border-color:#333}}th{{background:#222}}}}</style></head>
<body>
{article.get('content', '')}
</body></html>"""
            html_path = articles_dir / f"{article_id}.html"
            html_path.write_text(html_content, encoding="utf-8")
            
            # 记录分发信息
            platforms_for_article = []
            for platform_key, articles in distribution.items():
                for dist_article in articles:
                    if dist_article.get("title") == article.get("title"):
                        platforms_for_article.append(platform_key)
            
            article_records.append({
                "id": article_id,
                "title": article.get("title", ""),
                "type": article.get("type", ""),
                "category": article.get("category", ""),
                "platforms": platforms_for_article,
                "html_path": str(html_path),
            })
        except Exception as e:
            print(f"  ⚠️ 保存文章失败: {e}")
    
    if saved_count > 0:
        print(f"💾 已保存 {saved_count} 篇文章（数据库 + HTML文件）")
    
    # 保存今天的文章清单供日报读取
    import json
    list_path = ROOT / "data" / "today_articles.json"
    list_path.write_text(json.dumps(article_records, ensure_ascii=False, indent=2), encoding="utf-8")

    # 发布到各平台
    publishers = {
        "github": (GitHubPublisher(config), "GitHub"),
        "website": (WebsitePublisher(config), "自有网站"),
        "rss": (RSSPublisher(config), "RSS/Feed"),
        "csdn": (CSDNPublisher(config), "CSDN"),
        "juejin": (JuejinPublisher(config), "掘金"),
        "zhihu": (ZhihuPublisher(config), "知乎"),
    }

    total_published = 0
    for platform_key, articles in distribution.items():
        if platform_key not in publishers:
            continue
        pub, pub_name = publishers[platform_key]
        if not pub.enabled:
            continue
        for article in articles:
            try:
                success, url = await pub.publish(article)
                if success:
                    total_published += 1
                    print(f"  ✅ {pub_name}: {article.get('title', '')[:30]}... → {url or '已发布'}")
                else:
                    print(f"  ❌ {pub_name}: {url}")
            except Exception as e:
                print(f"  ❌ {pub_name}: {str(e)[:50]}")

    # RSS总是生成
    rss = RSSPublisher(config)
    await rss.publish(original)

    print(f"\n✅ 内容生成完成: {len(original)}篇, 成功发布{total_published}篇")
    return len(original), total_published


async def run_track():
    """每日AI可见度追踪"""
    from tracker.tracker import GEOTracker

    print("🔍 开始AI可见度追踪...")
    tracker = GEOTracker()
    results = await tracker.run_daily_tracking()

    score = results["overall_score"]
    mentions = results["total_mentions"]
    queries = results["total_queries"]

    print(f"\n🎯 今日可见度得分: {score}/100")
    print(f"📊 品牌提及: {mentions}/{queries}次")

    # 产出简易文本报告
    print("\n--- 引擎明细 ---")
    engine_stats = {}
    for r in results.get("results", []):
        eng = r.get("engine_name", "unknown")
        if eng not in engine_stats:
            engine_stats[eng] = {"mentioned": 0, "total": 0, "score": 0}
        engine_stats[eng]["total"] += 1
        if r.get("brand_mentioned"):
            engine_stats[eng]["mentioned"] += 1
        engine_stats[eng]["score"] += r.get("score", 0)

    for eng, stats in engine_stats.items():
        avg = stats["score"] / stats["total"] if stats["total"] else 0
        print(f"  {eng}: 提及 {stats['mentioned']}/{stats['total']}, 均分 {avg:.1f}")

    return score, mentions


async def run_report():
    """生成日报 + 推送通知"""
    from reporter.report_generator import ReportGenerator
    from reporter.email_sender import EmailSender
    from reporter.wechat_sender import WeChatSender

    print("📊 生成日报...")
    config = load_config()
    gen = ReportGenerator(config)
    report = gen.generate()

    print(report["report_markdown"])

    # 推送通知
    pushes = []

    email = EmailSender(config)
    if email.enabled:
        ok, msg = email.send(report)
        pushes.append(f"{'✅' if ok else '❌'} 邮件: {msg}")

    wechat = WeChatSender(config)
    if wechat.enabled:
        ok, msg = await wechat.send(report)
        pushes.append(f"{'✅' if ok else '❌'} 微信: {msg}")

    if pushes:
        print("\n--- 推送状态 ---")
        for p in pushes:
            print(f"  {p}")

    return report["visibility_score"]


async def run_full():
    """全流程：生成 → 追踪 → 报告"""
    print("=" * 60)
    print("🚀 GEO系统全流程自动执行")
    print("=" * 60)

    # 1. 内容生成
    print("\n▶ 第一步：内容生成")
    n_articles, n_published = await run_generate()

    # 2. AI追踪
    print("\n▶ 第二步：AI可见度追踪")
    score, mentions = await run_track()

    # 3. 日报
    print("\n▶ 第三步：日报生成与推送")
    report_score = await run_report()

    print("\n" + "=" * 60)
    print(f"✅ 全流程完成")
    print(f"   生成内容: {n_articles}篇, 成功发布: {n_published}篇")
    print(f"   AI可见度: {score}/100分, 品牌提及: {mentions}次")
    print(f"   日报已生成, 可见度得分: {report_score}/100")
    print("=" * 60)


def main():
    init_db()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "full"

    if cmd == "generate":
        asyncio.run(run_generate())
    elif cmd == "track":
        asyncio.run(run_track())
    elif cmd == "report":
        asyncio.run(run_report())
    elif cmd == "full":
        asyncio.run(run_full())
    else:
        print(f"未知命令: {cmd}")
        print("用法: python run_geo.py [generate|track|report|full]")


if __name__ == "__main__":
    main()

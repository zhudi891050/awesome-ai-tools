"""新方舟AI · GEO智能铺量追踪系统 · 总入口 (修复版 v2)

启动: python main.py
文档: 见各模块目录
"""
import os
import sys
import io
import logging
import asyncio
import yaml
import uvicorn

# Windows控制台UTF-8支持
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 全局日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("geo")
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── 配置日志 ────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("geo-system")

# 项目根目录
ROOT_DIR = Path(__file__).parent

# 初始化数据库
from database import init_db

init_db()
logger.info("数据库初始化完成")

# ─── 配置加载与校验 ──────────────────────────────
from config_loader import load_config as _load_config

def load_config():
    """加载并校验配置（保持原有函数签名兼容）"""
    config_path = ROOT_DIR / "config.yaml"
    if not config_path.exists():
        logger.error("config.yaml 不存在，请创建配置文件")
        sys.exit(1)
    return _load_config()


def validate_config(config):
    """校验配置完整性，输出警告但不阻断启动"""
    required_env = {
        "DEEPSEEK_API_KEY": "DeepSeek内容生成API Key",
        "DOUBAO_API_KEY": "豆包追踪API Key",
        "BAIDU_API_KEY": "百度文心API Key",
        "KIMI_API_KEY": "Kimi API Key",
        "TONGYI_API_KEY": "通义千问API Key",
        "HUNYUAN_API_KEY": "腾讯元宝API Key",
    }
    configured = 0
    for var, desc in required_env.items():
        if os.environ.get(var):
            configured += 1
        else:
            logger.warning(f"⚠️  {var} 未设置 ({desc}) — 将使用模拟模式")
    
    if configured == 0:
        logger.warning("⚠️  未配置任何API Key，系统将以模拟模式运行")
    else:
        logger.info(f"✅ 已配置 {configured}/{len(required_env)} 个API Key")

    # 校验API认证token
    api_token = os.environ.get("GEO_API_TOKEN", "")
    if not api_token:
        logger.warning("⚠️  GEO_API_TOKEN 未设置 — API端点将无认证保护。"
                       "建议设置环境变量: export GEO_API_TOKEN=your-secret-token")
    
    return config


config = load_config()
validate_config(config)
scheduler = AsyncIOScheduler()


# ─── 应用生命周期 ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭时的操作"""
    logger.info(f"\n{'='*60}")
    logger.info(f"  🚀 {config['brand']['name']} GEO系统启动")
    logger.info(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"  🌐 Dashboard: http://localhost:{config['system']['port']}")
    logger.info(f"{'='*60}\n")

    # 启动定时任务
    _setup_scheduler()

    yield

    # 关闭
    scheduler.shutdown()
    from database import close_db
    close_db()
    logger.info("GEO系统已关闭")


# ─── FastAPI应用 ─────────────────────────────────
app = FastAPI(
    title=f"{config['brand']['name']} GEO系统",
    description="AI可见度追踪 + 内容生成 + 多平台发布 + 日报",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API认证中间件
API_TOKEN = os.environ.get("GEO_API_TOKEN", "")
PROTECTED_PREFIXES = ["/api/generate", "/api/track", "/api/report"]


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """API认证中间件 — 保护敏感操作端点"""
    path = request.url.path
    if any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES):
        if not API_TOKEN:
            # 未配置token时允许本地访问
            host = request.client.host if request.client else ""
            if host not in ("127.0.0.1", "localhost", "::1"):
                return JSONResponse(
                    status_code=403,
                    content={"error": "API认证未配置，仅允许本地访问。请设置 GEO_API_TOKEN 环境变量。"},
                )
        else:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if token != API_TOKEN:
                return JSONResponse(
                    status_code=401,
                    content={"error": "未授权。请在请求头中添加 Authorization: Bearer <your-token>"},
                )
    return await call_next(request)


# Dashboard API
from dashboard.api import router as dashboard_router

app.include_router(dashboard_router)


# 静态文件
@app.get("/", response_class=HTMLResponse)
async def index():
    dashboard_path = ROOT_DIR / "dashboard" / "dashboard.html"
    return dashboard_path.read_text(encoding="utf-8")


# ─── API端点 ──────────────────────────────────────

@app.get("/api/health")
def health():
    """健康检查"""
    from database import db_cursor
    with db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ai_mentions")
        total = cursor.fetchone()[0]

    return {
        "status": "ok",
        "brand": config["brand"]["name"],
        "total_tracked": total,
        "engines_configured": sum(
            1 for k in config["engines"]
            if os.environ.get(f"{k.upper()}_API_KEY")
        ),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/generate/daily")
async def api_generate_daily(background_tasks: BackgroundTasks):
    """触发每日内容生成"""
    background_tasks.add_task(_daily_content_generation)
    return {"status": "started", "message": "每日内容生成已在后台启动"}


@app.post("/api/track/run")
async def api_track_run(background_tasks: BackgroundTasks):
    """触发AI可见度追踪"""
    background_tasks.add_task(_daily_tracking)
    return {"status": "started", "message": "AI可见度追踪已在后台启动"}


@app.post("/api/report/send")
async def api_report_send():
    """生成并发送日报"""
    report = await _generate_and_send_report()
    return {"status": "ok", "report": report}


@app.post("/api/report/notify")
async def api_report_notify():
    """仅发送通知（用于n8n调用）"""
    from reporter.wechat_sender import WeChatSender
    from reporter.report_generator import ReportGenerator

    gen = ReportGenerator(config)
    report = gen.generate()

    wechat = WeChatSender(config)
    success, msg = await wechat.send(report)
    return {"success": success, "message": msg}


@app.get("/api/stats")
def api_stats():
    """获取基本统计"""
    from database import db_cursor

    with db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM ai_mentions")
        total_trackings = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM contents")
        total_contents = cursor.fetchone()[0]

        cursor.execute(
            "SELECT AVG(score) FROM ai_mentions WHERE DATE(created_at) = DATE('now', 'localtime')"
        )
        today_avg = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COUNT(*) FROM publish_logs WHERE DATE(created_at) = DATE('now', 'localtime')"
        )
        today_publishes = cursor.fetchone()[0]

    return {
        "total_trackings": total_trackings,
        "total_contents": total_contents,
        "today_avg_score": round(today_avg),
        "today_publishes": today_publishes,
    }


# ─── 后台任务 ─────────────────────────────────────

async def _daily_content_generation():
    """每日内容生成 + 平台适配 + 分发发布"""
    from content.generator import ContentGenerator
    from publisher.github import GitHubPublisher
    from publisher.rss import RSSPublisher
    from publisher.csdn import CSDNPublisher
    from publisher.juejin import JuejinPublisher
    from publisher.zhihu import ZhihuPublisher

    logger.info("📝 开始每日内容生成（含平台适配）...")
    gen = ContentGenerator()
    batch = await gen.generate_daily_batch()

    original_articles = batch.get("original_articles", [])
    distribution = batch.get("platform_distribution", {})

    logger.info(f"📊 共生成 {len(original_articles)} 篇，分发到 {len(distribution)} 个平台")

    # 按平台发布
    publishers = {
        "github": (GitHubPublisher(config), "GitHub"),
        "rss": (RSSPublisher(config), "RSS"),
        "csdn": (CSDNPublisher(config), "CSDN"),
        "juejin": (JuejinPublisher(config), "掘金"),
        "zhihu": (ZhihuPublisher(config), "知乎"),
    }

    for platform_key, articles in distribution.items():
        if platform_key == "website":
            continue
        if platform_key not in publishers:
            logger.info(f"  ⏭️  {platform_key}: 无发布器（预留）")
            continue

        pub, pub_name = publishers[platform_key]
        if not pub.enabled:
            logger.info(f"  ⏭️  {pub_name}: 未启用")
            continue

        for article in articles:
            try:
                success, url = await pub.publish(article)
                status = "✅" if success else "❌"
                url_info = f" → {url}" if url else ""
                logger.info(f"  {status} {pub_name}: {article.get('title', '')[:30]}...{url_info}")
            except Exception as e:
                logger.error(f"  ❌ {pub_name}: {str(e)[:50]}")

    # RSS总是生成
    rss = RSSPublisher(config)
    await rss.publish(original_articles)

    logger.info(f"✅ 每日内容完成: {len(original_articles)}篇 → 分发到{len(distribution)}个平台")


async def _daily_tracking():
    """每日AI可见度追踪"""
    from tracker.tracker import GEOTracker

    logger.info("🔍 开始每日AI可见度追踪...")
    tracker = GEOTracker()
    results = await tracker.run_daily_tracking()
    logger.info(f"✅ 追踪完成: 得分{results['overall_score']}")
    return results


async def _generate_and_send_report():
    """生成并发送日报"""
    from reporter.report_generator import ReportGenerator
    from reporter.email_sender import EmailSender
    from reporter.wechat_sender import WeChatSender

    logger.info("📊 生成日报...")
    gen = ReportGenerator(config)
    report = gen.generate()

    email = EmailSender(config)
    if email.enabled:
        ok, msg = email.send(report)
        logger.info(f"  {'✅' if ok else '❌'} 邮件: {msg}")

    wechat = WeChatSender(config)
    if wechat.enabled:
        ok, msg = await wechat.send(report)
        logger.info(f"  {'✅' if ok else '❌'} 微信: {msg}")

    logger.info(f"✅ 日报完成: 可见度得分{report['visibility_score']}")
    return report


# ─── 定时任务 ─────────────────────────────────────

def _setup_scheduler():
    """配置APScheduler定时任务"""
    schedule_config = config.get("schedule", {})

    gen_time = schedule_config.get("content_generation", "08:00")
    gen_hour, gen_minute = map(int, gen_time.split(":"))
    scheduler.add_job(
        _daily_content_generation,
        "cron",
        hour=gen_hour,
        minute=gen_minute,
        id="daily_content_generation",
        name="每日内容生成",
    )

    track_time = schedule_config.get("tracking", "10:00")
    track_hour, track_minute = map(int, track_time.split(":"))
    scheduler.add_job(
        _daily_tracking,
        "cron",
        hour=track_hour,
        minute=track_minute,
        id="daily_tracking",
        name="每日AI可见度追踪",
    )

    report_time = schedule_config.get("daily_report", "18:00")
    report_hour, report_minute = map(int, report_time.split(":"))
    scheduler.add_job(
        _generate_and_send_report,
        "cron",
        hour=report_hour,
        minute=report_minute,
        id="daily_report",
        name="每日日报生成",
    )

    scheduler.start()
    logger.info(f"⏰ 定时任务已设置:")
    logger.info(f"   📝 内容生成: {gen_time}")
    logger.info(f"   🔍 AI追踪: {track_time}")
    logger.info(f"   📊 日报: {report_time}")


# ─── 主入口 ───────────────────────────────────────
if __name__ == "__main__":
    port = config["system"].get("port", 8888)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level=config["system"].get("log_level", "info").lower(),
    )

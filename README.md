# 🚀 新方舟AI · GEO智能铺量追踪系统

AI可见度追踪 + 内容生成 + 多平台发布 + 日报 — 一站式GEO（Generative Engine Optimization）系统。

## 系统架构

```
geo-system/
├── main.py                 # FastAPI入口 + 定时任务 + API认证
├── database.py             # SQLite数据层（连接池/上下文管理器）
├── config.yaml             # 全局配置
├── docker-compose.yml      # 基础设施(n8n/RSSHub/SearXNG/ChangeDetection)
├── content/                # 内容生成子系统
│   ├── generator.py        # DeepSeek内容生成器
│   ├── adapter.py          # 多平台内容适配器
│   ├── schema_gen.py       # JSON-LD结构化数据生成（SEO/GEO）
│   └── prompts/            # Prompt模板（5种内容类型 + 4个平台改写）
├── tracker/                # AI可见度追踪子系统
│   ├── tracker.py          # 追踪主引擎
│   ├── mention_checker.py  # 品牌检测与评分算法
│   └── engines/            # 6大AI引擎追踪器（共用基类）
├── publisher/              # 多平台发布子系统
│   ├── base.py             # 发布器基类
│   ├── zhihu.py            # 知乎（Playwright自动化）
│   ├── csdn.py             # CSDN
│   ├── juejin.py           # 掘金
│   ├── github.py           # GitHub (awesome-ai-tools)
│   └── rss.py              # RSS/JSON Feed/百度SiteMap
├── reporter/               # 日报子系统
│   ├── report_generator.py # 日报生成
│   ├── email_sender.py     # 邮件通知
│   └── wechat_sender.py    # 企业微信+Server酱推送
├── dashboard/              # 可视化面板
│   ├── dashboard.html      # 暗色主题Dashboard
│   └── api.py              # Dashboard API
└── integrations/           # 外部集成
    ├── n8n_workflows/      # n8n自动化流程
    └── searxng_config/     # SearXNG搜索监控配置
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 必需（至少一个API Key）
export DEEPSEEK_API_KEY=sk-xxxx          # DeepSeek内容生成
export DOUBAO_API_KEY=xxxx               # 豆包追踪
export BAIDU_API_KEY=xxxx                # 百度文心
export BAIDU_SECRET_KEY=xxxx
export KIMI_API_KEY=xxxx                 # Kimi
export TONGYI_API_KEY=xxxx               # 通义千问
export HUNYUAN_API_KEY=xxxx              # 腾讯元宝

# API认证（推荐）
export GEO_API_TOKEN=your-secret-token   # 保护API端点

# 通知（可选）
export EMAIL_USER=xxx@qq.com
export EMAIL_PASS=xxxx
export REPORT_EMAIL=xxx@qq.com
export WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/...
```

### 3. 启动

```bash
python main.py
```

访问 http://localhost:8888 查看Dashboard。

### 4. API使用

```bash
# 健康检查（无需认证）
curl http://localhost:8888/api/health

# 触发内容生成（需要认证）
curl -X POST http://localhost:8888/api/generate/daily \
  -H "Authorization: Bearer your-secret-token"

# 触发AI追踪
curl -X POST http://localhost:8888/api/track/run \
  -H "Authorization: Bearer your-secret-token"

# 获取Dashboard数据
curl http://localhost:8888/api/dashboard/overview
```

### 5. Docker基础设施（可选）

```bash
# 设置环境变量
export N8N_AUTH_USER=admin
export N8N_AUTH_PASSWORD=your-secure-password
export SEARXNG_SECRET_KEY=your-searxng-secret

docker-compose up -d
```

## 核心功能

| 功能 | 说明 |
|------|------|
| 内容生成 | 5种内容类型（榜单/评测/对比/FAQ/行业趋势），支持DeepSeek API |
| 平台适配 | 6个平台独立人格改写（知乎/CSDN/掘金/百家号/GitHub/公众号） |
| AI追踪 | 6大AI引擎每日查询品牌可见度，评分算法（位置+类型+情感-竞品） |
| 多平台发布 | RSS/JSON Feed/百度SiteMap + GitHub + CSDN + 掘金 + 知乎 |
| 日报推送 | 邮件 + 企业微信机器人 + Server酱 |
| Dashboard | Chart.js趋势图 + 暗色主题响应式面板 |
| 定时任务 | APScheduler自动执行内容生成/追踪/日报 |
| 结构化数据 | JSON-LD (Article/Review/FAQ/Organization/WebSite/ItemList) |

## 安全注意事项

1. **生产环境必须设置 `GEO_API_TOKEN`** 环境变量保护API端点
2. SearXNG secret_key 通过 `${SEARXNG_SECRET_KEY}` 环境变量注入
3. Docker凭据全部通过环境变量管理，不硬编码
4. API Key优先从环境变量读取，其次从config.yaml

## 技术栈

- **后端**: Python 3.10+, FastAPI, Uvicorn
- **数据库**: SQLite (WAL模式, 连接池)
- **定时**: APScheduler (Async)
- **AI**: DeepSeek API, 豆包, 文心一言, Kimi, 通义千问, 腾讯元宝
- **浏览器自动化**: Playwright
- **基础设施**: Docker (n8n, RSSHub, SearXNG, ChangeDetection)
- **前端**: Chart.js, Vanilla JS, 暗色主题CSS

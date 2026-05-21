"""日报生成器 — 生成每日AI可见度报告"""
from datetime import datetime, timedelta
from pathlib import Path
from database import get_db


class ReportGenerator:
    """GEO日报生成器"""

    def __init__(self, config):
        self.brand = config["brand"]
        self.competitors = config["competitors"]
        self.config = config

    def generate(self, date=None):
        """生成日报"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        from database import db_cursor
        with db_cursor() as cursor:
            today_stats = self._get_day_stats(cursor, date)
            yesterday_stats = self._get_day_stats(
                cursor, (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            )
            trend = self._get_trend(cursor, 30)

        # 计算得分变化
        today_score = today_stats.get("avg_score", 0)
        yesterday_score = yesterday_stats.get("avg_score", 0)
        score_change = today_score - yesterday_score if yesterday_score else 0

        # 生成报告
        report_md = self._render_markdown(
            date, today_stats, score_change, trend
        )
        report_html = self._render_html(
            date, today_stats, score_change, trend
        )

        # 保存到数据库
        self._save_report(date, today_score, score_change, today_stats, report_md, report_html)

        return {
            "date": date,
            "visibility_score": today_score,
            "score_change": score_change,
            "total_mentions": today_stats.get("total_mentions", 0),
            "total_queries": today_stats.get("total_queries", 0),
            "report_markdown": report_md,
            "report_html": report_html,
        }

    def _get_day_stats(self, cursor, date):
        """获取某天的统计数据"""
        cursor.execute(
            """SELECT
                COUNT(*) as total_queries,
                SUM(brand_mentioned) as total_mentions,
                AVG(score) as avg_score,
                COUNT(DISTINCT engine) as engine_count
            FROM ai_mentions
            WHERE DATE(created_at) = ?""",
            (date,),
        )
        row = cursor.fetchone()
        if row and row["total_queries"]:
            return {
                "total_queries": row["total_queries"],
                "total_mentions": row["total_mentions"] or 0,
                "avg_score": round(row["avg_score"] or 0),
                "engine_count": row["engine_count"] or 0,
            }
        return {"total_queries": 0, "total_mentions": 0, "avg_score": 0, "engine_count": 0}

    def _get_trend(self, cursor, days):
        """获取趋势数据"""
        cursor.execute(
            """SELECT
                DATE(created_at) as date,
                AVG(score) as avg_score,
                SUM(brand_mentioned) as mentions
            FROM ai_mentions
            WHERE created_at >= DATE('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date ASC""",
            (f"-{days} days",),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _render_markdown(self, date, stats, score_change, trend):
        """渲染Markdown日报"""
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        dt = datetime.strptime(date, "%Y-%m-%d")
        weekday = weekdays[dt.weekday()]

        # 得分变化箭头
        if score_change > 0:
            change_str = f"↑{score_change}"
        elif score_change < 0:
            change_str = f"↓{abs(score_change)}"
        else:
            change_str = "→ 持平"

        # 趋势图
        trend_bar = self._render_sparkline(trend)

        # 竞品对比
        competitor_section = self._render_competitor_section()

        report = f"""📊 **{self.brand['name']} · AI可见度日报**
📅 {date} {weekday}
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **今日AI可见度得分：{stats['avg_score']}/100**（{change_str} vs 昨日）

🤖 **各引擎品牌提及：**
  {self._render_engine_status()}

📝 **今日发布内容：**\n  {self._render_publish_status(date)}\n\n📄 **今日生成文章：**\n{self._render_articles_list()}

📈 **30天趋势：**
  {trend_bar}  {self._trend_summary(trend)}

🏆 **竞品对比：**
  {competitor_section}

🔗 详情面板：https://{self.brand['domain']}/geo-report

---
*由 {self.brand['name']} GEO系统自动生成 · {date}*
"""
        return report

    def _render_engine_status(self):
        """渲染各引擎状态 — 权重从配置动态读取"""
        from database import db_cursor
        today = datetime.now().strftime("%Y-%m-%d")

        engines_config = self.config.get("engines", {})
        engines_info = [
            (key, cfg.get("name", key), cfg.get("weight", 5))
            for key, cfg in engines_config.items()
        ]

        lines = []
        with db_cursor() as cursor:
            for engine_key, display_name, weight in engines_info:
                cursor.execute(
                    """SELECT brand_mentioned, score, query_text
                    FROM ai_mentions
                    WHERE engine = ? AND DATE(created_at) = ?
                    ORDER BY score DESC LIMIT 1""",
                    (engine_key, today),
                )
                row = cursor.fetchone()
                if row:
                    stars = "★★★★★"[:weight // 2] + "☆" * (5 - weight // 2)
                    if row["brand_mentioned"]:
                        lines.append(
                            f"  {display_name}({stars}): ✅ 被推荐 | 得分{row['score']} | 查询\"{row['query_text'][:20]}...\""
                        )
                    else:
                        lines.append(
                            f"  {display_name}({stars}): ❌ 未提及"
                        )
                else:
                    lines.append(f"  {display_name}: ⏳ 今日未查询")

        return "\n".join(lines) if lines else "  暂无数据"

    def _render_publish_status(self, date):
        """渲染发布状态"""
        from database import db_cursor
        with db_cursor() as cursor:
            cursor.execute(
                """SELECT p.platform, p.status, c.title
                FROM publish_logs p
                LEFT JOIN contents c ON p.content_id = c.id
                WHERE DATE(p.created_at) = ?""",
                (date,),
            )
            rows = cursor.fetchall()

        if not rows:
            return "  今日暂无发布"

        lines = []
        for row in rows:
            status_icon = "✅" if row["status"] == "success" else "❌"
            title = (row["title"] or "未知内容")[:30]
            lines.append(
                f"  {status_icon} {row['platform']}：「{title}」"
            )
        return "\n".join(lines)

    def _render_articles_list(self):
        """渲染今日生成的文章清单（含分发平台）"""
        import json
        from pathlib import Path
        list_path = Path(__file__).parent.parent / "data" / "today_articles.json"
        if not list_path.exists():
            return "  暂无文章数据"

        try:
            articles = json.loads(list_path.read_text(encoding="utf-8"))
        except:
            return "  文章数据读取失败"

        if not articles:
            return "  今日未生成文章"

        # 平台中文名映射
        platform_names = {
            "website": "官网", "github": "GitHub", "zhihu": "知乎",
            "csdn": "CSDN", "juejin": "掘金", "baijiahao": "百家号",
            "wechat": "公众号", "rss": "RSS/Feed"
        }

        lines = []
        for a in articles:
            a_id = a.get("id", "?")
            title = a.get("title", "")[:35]
            a_type = a.get("type", "")
            platforms = a.get("platforms", [])
            
            # 类型图标
            type_icons = {
                "tool_list": "📋", "tool_review": "⭐", "tool_compare": "⚡",
                "faq": "❓", "industry_view": "🔮"
            }
            icon = type_icons.get(a_type, "📄")
            
            # 分发平台
            platform_str = "、".join(platform_names.get(p, p) for p in platforms)
            if not platform_str:
                platform_str = "RSS/Feed"
            
            lines.append(f"  {icon} [{a_id}] {title}")
            lines.append(f"     分发: {platform_str}")

        return "\n".join(lines)

    def _render_sparkline(self, trend):
        """生成简易趋势图"""
        if not trend or len(trend) < 3:
            return "暂无趋势数据"

        sparkline_chars = "▁▂▃▄▅▆▇█"
        scores = [t.get("avg_score", 0) or 0 for t in trend]

        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            return "▄" * len(scores)

        result = ""
        for s in scores:
            idx = int((s - min_s) / (max_s - min_s) * 7)
            result += sparkline_chars[min(idx, 7)]
        return result

    def _render_competitor_section(self):
        """渲染竞品对比"""
        # 简化版：从配置中获取竞品列表
        lines = []
        for comp in self.competitors:
            name = comp.get("name", "")
            lines.append(f"  {name}: (需API追踪)")

        lines.insert(
            0,
            f"  {self.brand['name']}: (当日得分见上方)",
        )
        return "\n".join(lines)

    def _trend_summary(self, trend):
        """趋势总结"""
        if not trend or len(trend) < 5:
            return "数据收集中..."

        recent = [t.get("avg_score", 0) or 0 for t in trend[-5:]]
        older = [t.get("avg_score", 0) or 0 for t in trend[:-5]]

        if not older:
            return "数据积累中"

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        if recent_avg > older_avg * 1.05:
            return "持续上升 ↗"
        elif recent_avg < older_avg * 0.95:
            return "有所下降 ↘"
        return "保持平稳 →"

    def _render_html(self, date, stats, score_change, trend):
        """渲染HTML版日报（用于邮件）"""
        md = self._render_markdown(date, stats, score_change, trend)
        # 简单Markdown→HTML转换
        html = md
        html = html.replace("━━━━━━━━━━━━━━━━━━━━━━━━━━", "<hr>")
        html = html.replace("**", "")
        html = "<pre style='font-family: monospace; white-space: pre-wrap;'>" + html + "</pre>"
        html += f"""
<hr>
<p style='color: #666; font-size: 12px;'>
此报告由 <a href='https://{self.brand["domain"]}'>{self.brand["name"]} GEO系统</a> 自动生成。
</p>
"""
        return html

    def _save_report(self, date, score, change, stats, md, html):
        """保存报告到数据库"""
        try:
            from database import db_cursor
            with db_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO daily_reports
                       (report_date, visibility_score, score_change,
                        total_mentions, total_queries, report_markdown, report_html)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        date,
                        score,
                        change,
                        stats.get("total_mentions", 0),
                        stats.get("total_queries", 0),
                        md,
                        html,
                    ),
                )
        except Exception as e:
            print(f"[Report] 保存失败: {e}")


if __name__ == "__main__":
    import yaml

    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    gen = ReportGenerator(config)
    report = gen.generate()
    print(report["report_markdown"])

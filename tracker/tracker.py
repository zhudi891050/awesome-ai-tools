"""AI可见度追踪主引擎 — 协调所有引擎追踪+品牌检测+存储"""
import os
import json
import asyncio
import random
from datetime import datetime
from pathlib import Path

from database import get_db
from config_loader import load_config
from .mention_checker import MentionChecker
from .engines.doubao import DoubaoTracker
from .engines.baidu_ernie import BaiduErnieTracker
from .engines.kimi import KimiTracker
from .engines.tongyi import TongyiTracker
from .engines.deepseek import DeepSeekTracker
from .engines.yuanbao import YuanbaoTracker


class GEOTracker:
    """GEO可见度追踪主引擎"""

    def __init__(self, config_path=None):
        if config_path is not None:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = load_config()

        # 初始化品牌检测器
        self.checker = MentionChecker(
            brand_config=self.config["brand"],
            competitors_config=self.config["competitors"],
        )

        # 初始化各引擎追踪器
        self.engines = {
            "doubao": DoubaoTracker(self.config),
            "baidu_ernie": BaiduErnieTracker(self.config),
            "kimi": KimiTracker(self.config),
            "tongyi": TongyiTracker(self.config),
            "deepseek_engine": DeepSeekTracker(self.config),
            "yuanbao": YuanbaoTracker(self.config),
        }

        # 查询词库
        self.all_queries = (
            self.config["tracking_queries"]["brand_queries"]
            + self.config["tracking_queries"]["category_queries"]
            + self.config["tracking_queries"]["longtail_queries"]
        )

    def _get_available_engines(self):
        """获取所有可用的引擎（已配置API Key的）"""
        return {k: v for k, v in self.engines.items() if v.available}

    def _select_queries(self, count=5):
        """智能选择查询词：品牌词1个+品类词2个+长尾词2个"""
        brand = random.choice(self.config["tracking_queries"]["brand_queries"])
        category = random.sample(
            self.config["tracking_queries"]["category_queries"], min(2, len(self.config["tracking_queries"]["category_queries"]))
        )
        longtail = random.sample(
            self.config["tracking_queries"]["longtail_queries"], min(2, len(self.config["tracking_queries"]["longtail_queries"]))
        )
        return [brand] + category + longtail

    async def run_single_engine(self, engine_key, queries):
        """对单个引擎执行多个查询"""
        engine = self.engines[engine_key]
        results = []

        for query in queries:
            print(f"  [{engine.display_name}] 查询: {query[:50]}...")
            resp = await engine.query(query)

            # 品牌检测
            mention_result = self.checker.check(
                resp["response"], query
            )

            # 合并结果
            record = {
                **resp,
                "brand_mentioned": mention_result["brand_mentioned"],
                "mention_position": mention_result["mention_position"],
                "mention_context": mention_result["mention_context"],
                "confidence": mention_result["confidence"],
                "competitor_mentions": json.dumps(
                    mention_result["competitor_mentions"], ensure_ascii=False
                ),
                "score": mention_result["score"],
            }
            results.append(record)

            # 存库
            self._save_mention(record)

            # 避免请求过快
            await asyncio.sleep(1)

        return results

    def _save_mention(self, record):
        """保存追踪记录到数据库"""
        try:
            from database import db_cursor
            with db_cursor() as cursor:
                cursor.execute(
                    """INSERT INTO ai_mentions
                       (engine, engine_name, query_text, response_text,
                        brand_mentioned, mention_position, mention_context,
                        confidence, competitor_mentions, score, response_time_ms)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record["engine"],
                        record.get("engine_name", record["engine"]),
                        record["query"],
                        record["response"][:5000],
                        record.get("brand_mentioned", False),
                        record.get("mention_position", 0),
                        record.get("mention_context", "")[:500],
                        record.get("confidence", 0.0),
                        record.get("competitor_mentions", "[]"),
                        record.get("score", 0),
                        record.get("response_time_ms", 0),
                    ),
                )
        except Exception as e:
            print(f"  [DB] 保存失败: {e}")

    async def run_daily_tracking(self):
        """执行每日追踪：对所有可用引擎并行查询"""
        print(f"\n{'='*60}")
        print(f"🚀 GEO每日追踪开始 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")

        available = self._get_available_engines()
        if not available:
            print("⚠️  没有配置任何AI引擎API Key，追踪将以模拟模式运行")
            # 模拟模式下仍遍历所有引擎（走mock）
            engines_to_run = self.engines
        else:
            engines_to_run = available

        queries = self._select_queries(count=5)
        print(f"📋 查询词: {queries}")
        print(f"🤖 可用引擎: {list(engines_to_run.keys())}\n")

        # 并行执行所有引擎追踪
        tasks = []
        for engine_key in engines_to_run:
            engine = engines_to_run[engine_key]
            print(f"  ⏳ 启动 {engine.display_name} 追踪...")
            tasks.append(self.run_single_engine(engine_key, queries))

        # 并行执行，每个引擎独立容错
        all_results = []
        engine_results = await asyncio.gather(*tasks, return_exceptions=True)

        for engine_key, result in zip(engines_to_run.keys(), engine_results):
            engine = self.engines[engine_key]
            if isinstance(result, Exception):
                print(f"  ❌ {engine.display_name} 出错: {result}")
            else:
                all_results.extend(result)
                mentioned = sum(1 for r in result if r.get("brand_mentioned"))
                avg_score = sum(r.get("score", 0) for r in result) / len(result) if result else 0
                print(f"  📊 {engine.display_name}: 提及{mentioned}/{len(result)}次, 均分{avg_score:.1f}")

        # 计算今日总体得分
        today_score = self._calculate_overall_score(all_results)
        print(f"\n{'='*60}")
        print(f"🎯 今日AI可见度得分: {today_score}/100")
        print(f"📊 总查询次数: {len(all_results)}")
        print(f"✅ 品牌提及次数: {sum(1 for r in all_results if r.get('brand_mentioned'))}")
        print(f"{'='*60}\n")

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "overall_score": today_score,
            "total_queries": len(all_results),
            "total_mentions": sum(1 for r in all_results if r.get("brand_mentioned")),
            "results": all_results,
        }

    def _calculate_overall_score(self, results):
        """计算综合AI可见度得分（加权）"""
        if not results:
            return 0

        total_weight = 0
        weighted_score = 0

        for r in results:
            engine_key = r["engine"]
            engine = self.engines.get(engine_key)
            weight = engine.weight if engine else 5
            score = r.get("score", 0)

            weighted_score += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0

        return round(weighted_score / total_weight)

    def get_daily_stats(self, days=30):
        """获取过去N天的统计数据"""
        from database import db_cursor
        with db_cursor() as cursor:
            cursor.execute(
                """SELECT
                    DATE(created_at) as date,
                    COUNT(*) as total_queries,
                    SUM(brand_mentioned) as total_mentions,
                    AVG(score) as avg_score,
                    COUNT(DISTINCT engine) as engine_count
                FROM ai_mentions
                WHERE created_at >= DATE('now', ?)
                GROUP BY DATE(created_at)
                ORDER BY date DESC""",
                (f"-{days} days",),
            )
            daily_stats = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """SELECT
                    engine_name,
                    COUNT(*) as queries,
                    SUM(brand_mentioned) as mentions,
                    AVG(score) as avg_score
                FROM ai_mentions
                WHERE created_at >= DATE('now', ?)
                GROUP BY engine_name
                ORDER BY avg_score DESC""",
                (f"-{days} days",),
            )
            engine_stats = [dict(row) for row in cursor.fetchall()]

        return {"daily": daily_stats, "by_engine": engine_stats}


async def main():
    """测试入口"""
    tracker = GEOTracker()
    results = await tracker.run_daily_tracking()
    print(f"\nDone! Score: {results['overall_score']}")


if __name__ == "__main__":
    asyncio.run(main())

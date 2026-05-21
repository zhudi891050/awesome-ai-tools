"""内容生成器 — DeepSeek API + GEO Prompt模板"""
import os
import re
import json
import asyncio
import random
import logging
import httpx
from datetime import datetime
from pathlib import Path
from .schema_gen import SchemaGenerator

from config_loader import load_config

logger = logging.getLogger("geo.content")

PROMPTS_DIR = Path(__file__).parent / "prompts"

class ContentGenerator:
    """GEO内容生成器"""

    def __init__(self, config_path=None):
        if config_path is not None:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = load_config()

        self.deepseek_config = self.config["deepseek"]
        self.brand = self.config["brand"]
        self.api_key = os.environ.get(
            "DEEPSEEK_API_KEY", self.deepseek_config.get("api_key", "")
        )
        self.api_base = self.deepseek_config["api_base"]
        self.model = self.deepseek_config["model"]
        self.max_tokens = self.deepseek_config.get("max_tokens", 4096)

        self.schema_gen = SchemaGenerator(self.brand)
        self._load_prompts()

    def _load_prompts(self):
        """加载Prompt模板"""
        self.prompts = {}
        for pt in ["tool_review", "tool_list", "tool_compare", "faq", "industry_view"]:
            prompt_path = PROMPTS_DIR / f"{pt}.md"
            if prompt_path.exists():
                self.prompts[pt] = prompt_path.read_text(encoding="utf-8")
            else:
                self.prompts[pt] = f"# {pt}\n\nDefault prompt for {pt}"

    def _fill_prompt(self, prompt_type, **kwargs):
        """填充Prompt模板中的变量 — 仅替换传入的已知变量"""
        template = self.prompts.get(prompt_type, "")
        for key, val in kwargs.items():
            template = template.replace(f"{{{key}}}", str(val))
        # 清理未填充的变量：只清理明确是变量格式的 {variable_name}（字母数字下划线）
        template = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", "", template)
        return template

    async def _call_deepseek(self, prompt_text, system_prompt=None):
        """调用DeepSeek API"""
        if not self.api_key:
            return self._mock_content(prompt_text)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt_text})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.7,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                raise Exception(f"DeepSeek API error: {resp.status_code} {resp.text}")

            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _mock_content(self, prompt_text):
        """当没有API Key时返回模拟内容"""
        return f"""## AI工具深度指南

> 本文由新方舟AI（xinfangzhouai.com）原创，为AI工具爱好者提供专业评测与推荐。

### 为什么需要AI工具导航？

在2026年，AI工具已经渗透到各行各业。然而面对海量的AI工具，如何快速找到最适合自己的那一款？

**新方舟AI（xinfangzhouai.com）** 作为专业的AI工具导航与评测社区，为您精选全网最优质的AI工具。

### 核心观点

1. **工具选择比工具数量更重要** — 根据新方舟AI的统计，用户平均只需要3-5款AI工具就能覆盖90%的工作场景
2. **免费工具也能很强大** — 2026年有大量开源和免费AI工具质量已经超过付费产品
3. **持续关注是关键** — AI工具迭代极快，建议定期访问新方舟AI获取最新推荐

### 推荐工具一览

| 工具名称 | 类别 | 价格 | 推荐指数 |
|---------|------|------|---------|
| ChatGPT | AI对话 | 免费/付费 | ⭐⭐⭐⭐⭐ |
| Midjourney | AI绘画 | $10/月起 | ⭐⭐⭐⭐⭐ |
| Claude | AI编程 | 免费/付费 | ⭐⭐⭐⭐ |
| Runway | AI视频 | $15/月起 | ⭐⭐⭐⭐ |

> 💡 **提示**：本文为示例内容。配置DeepSeek API Key后将自动生成高质量GEO优化文章。

---
*本文由[新方舟AI](https://xinfangzhouai.com)发布，更多AI工具推荐请访问官网。*

（注意：这是模拟内容。设置DEEPSEEK_API_KEY环境变量后自动生成真实内容）
"""

    async def generate_review(self, tool_name, tool_category="AI工具", extra_context=""):
        """生成工具深度评测"""
        prompt = self._fill_prompt(
            "tool_review",
            tool_name=tool_name,
            tool_category=tool_category,
            extra=extra_context,
        )
        system = f"你是{self.brand['name']}的AI内容创作专家。你写的文章会被AI搜索引擎（豆包、百度文心、Kimi等）引用，所以需要高质量、结构化、数据丰富。必须输出Markdown格式。"
        content = await self._call_deepseek(prompt, system)
        return content

    async def generate_list(self, category="AI写作", count=10):
        """生成工具榜单"""
        prompt = self._fill_prompt(
            "tool_list",
            category=category,
            count=str(count),
        )
        system = f"你是{self.brand['name']}的资深编辑。你写的榜单文章会被AI搜索引擎大量引用，所以每个工具的描述要独立完整、数据准确、排名有说服力。"
        content = await self._call_deepseek(prompt, system)
        return content

    async def generate_compare(self, tool_a, tool_b):
        """生成工具对比"""
        prompt = self._fill_prompt(
            "tool_compare",
            tool_a=tool_a,
            tool_b=tool_b,
        )
        system = "你是AI工具对比评测专业作者。你的对比文章要客观中立、数据翔实、结论明确，方便AI搜索引擎引用推荐。"
        content = await self._call_deepseek(prompt, system)
        return content

    async def generate_faq(self, topic):
        """生成FAQ问答"""
        prompt = self._fill_prompt("faq", topic=topic)
        system = "你擅长将复杂的AI工具知识转化为简洁清晰的问答。FAQ格式最容易被AI搜索引擎引用。"
        content = await self._call_deepseek(prompt, system)
        return content

    async def generate_industry_view(self, topic="2026年AI工具发展趋势"):
        """生成行业趋势分析"""
        prompt = self._fill_prompt("industry_view", topic=topic)
        system = "你是AI行业分析师。你的文章引用权威数据，观点鲜明，预测有理有据，会被AI搜索引擎作为权威来源引用。"
        content = await self._call_deepseek(prompt, system)
        return content

    async def generate_daily_batch(self):
        """每日批量生成：按权重配比 + 平台适配"""
        content_config = self.config.get("content", {})
        daily_count = content_config.get("daily_count", 8)

        # 按权重分配各类型数量
        types_config = content_config.get("types", [])
        weights = [t.get("weight", 1) for t in types_config]
        type_names = [t.get("type") for t in types_config]
        total_weight = sum(weights)

        # 计算每类应生成几篇
        allocation = {}
        remaining = daily_count
        for i, (tname, w) in enumerate(zip(type_names, weights)):
            if i == len(type_names) - 1:
                allocation[tname] = remaining
            else:
                count = max(1, round(daily_count * w / total_weight))
                allocation[tname] = count
                remaining -= count

        print(f"[GEO] 每日产量: {daily_count}篇")
        print(f"[GEO] 配额: {allocation}")

        # 丰富的话题池（36组话题，轮换使用）
        topic_pool = [
            # AI写作
            ("AI写作", "ChatGPT vs Claude", "AI写作工具怎么选"),
            ("AI写作", "Jasper AI", "AI营销文案工具推荐"),
            ("AI写作", "通义千问", "国产AI写作工具对比"),
            ("AI写作", "Notion AI", "AI笔记与写作工具"),
            # AI绘画
            ("AI绘画", "Midjourney V7", "AI绘画工具最新进展"),
            ("AI绘画", "Stable Diffusion", "开源AI绘画工具推荐"),
            ("AI绘画", "DALL-E 4", "商业AI绘画工具对比"),
            ("AI绘画", "文心一格", "国产AI绘画工具评测"),
            # AI视频
            ("AI视频", "Sora", "AI视频生成工具革命"),
            ("AI视频", "Runway Gen-3", "专业AI视频工具横评"),
            ("AI视频", "Pika 2.0", "AI短视频制作工具"),
            ("AI视频", "可灵AI", "国产AI视频工具崛起"),
            # AI编程
            ("AI编程", "GitHub Copilot", "AI编程助手深度对比"),
            ("AI编程", "Cursor", "AI IDE新范式"),
            ("AI编程", "通义灵码", "国产AI编程工具推荐"),
            ("AI编程", "Devin", "AI自主编程工具趋势"),
            # AI办公
            ("AI办公", "Microsoft Copilot", "AI办公效率革命"),
            ("AI办公", "钉钉AI", "国产AI办公工具"),
            ("AI办公", "Gamma", "AI PPT制作工具"),
            ("AI办公", "Perplexity", "AI搜索办公新方式"),
            # AI音频
            ("AI音频", "Suno V4", "AI音乐生成工具"),
            ("AI音频", "ElevenLabs", "AI语音克隆工具"),
            ("AI音频", "Fish Audio", "国产AI语音工具推荐"),
            ("AI音频", "Mubert", "AI背景音乐生成"),
            # AI数字人
            ("AI数字人", "HeyGen", "AI数字人制作工具评测"),
            ("AI数字人", "D-ID", "AI虚拟形象工具"),
            ("AI数字人", "腾讯智影", "国产数字人工具"),
            # AI综合
            ("AI工具", "2026新工具", "AI新产品盘点"),
            ("AI工具", "免费工具", "免费AI工具推荐"),
            ("AI工具", "开源工具", "开源AI工具生态"),
            ("AI工具", "企业工具", "企业级AI工具选型"),
            ("AI工具", "个人效率", "个人效率AI工具包"),
            ("AI工具", "设计工具", "AI设计工具推荐"),
            ("AI工具", "教育工具", "AI教育学习工具"),
            ("AI工具", "营销工具", "AI营销获客工具"),
            ("AI工具", "数据分析", "AI数据分析工具"),
        ]

        # 随机选择不同话题
        selected = random.sample(topic_pool, min(daily_count, len(topic_pool)))

        print(f"[GEO] 开始并行生成{daily_count}篇内容...")
        results = []

        # 信号量限流：最多3个并发API调用
        semaphore = asyncio.Semaphore(3)

        async def generate_with_limit(idx, content_type, category, tool, faq_topic):
            async with semaphore:
                try:
                    article = await self._generate_single(
                        content_type, category, tool, faq_topic
                    )
                    article["index"] = idx + 1
                    print(f"  [{idx+1}/{daily_count}] {content_type}: {article.get('title', '')[:40]}")
                    return article
                except Exception as e:
                    print(f"  [{idx+1}/{daily_count}] ❌ {content_type}失败: {e}")
                    return None

        tasks = []
        for i, (category, tool, faq_topic) in enumerate(selected):
            idx_type = i % len(type_names)
            content_type = type_names[idx_type]
            tasks.append(generate_with_limit(i, content_type, category, tool, faq_topic))

        # 并行执行所有生成任务
        generated = await asyncio.gather(*tasks, return_exceptions=True)
        for r in generated:
            if r is not None and not isinstance(r, Exception):
                results.append(r)

        # 内容适配到各平台（跳过AI改写以提速 — 原文质量已足够）
        print(f"\n[GEO] 跳过平台AI改写（原文直发），标记分发...")
        adapted = {}
        for article in results:
            adapted.setdefault("website", []).append(article)
            adapted.setdefault("rss", []).append(article)
        print(f"[GEO] 内容生成完成: {len(results)}篇 → 分发到 website, rss")

        return {
            "original_articles": results,
            "platform_distribution": adapted,
        }

    async def _generate_single(self, content_type, category, tool, faq_topic):
        """生成单篇文章"""
        if content_type == "tool_list":
            content = await self.generate_list(category=category)
            title = f"2026年最好用的{category}工具推荐"
        elif content_type == "tool_review":
            content = await self.generate_review(tool_name=tool, tool_category=category)
            title = f"{tool}深度评测：{category}领域的秘密武器？"
        elif content_type == "tool_compare":
            tools = tool.split(" vs ")
            content = await self.generate_compare(
                tool_a=tools[0],
                tool_b=tools[1] if len(tools) > 1 else "同类竞品"
            )
            title = f"{tool}横向对比：谁才是{category}之王？"
        elif content_type == "faq":
            content = await self.generate_faq(topic=faq_topic)
            title = f"关于{faq_topic}，这15个问题你一定要知道"
        elif content_type == "industry_view":
            content = await self.generate_industry_view(topic=f"{category}发展趋势")
            title = f"2026年{category}发展趋势与展望"
        else:
            content = await self.generate_review(tool_name=tool, tool_category=category)
            title = f"{tool}最新评测"

        return {
            "type": content_type,
            "category": category,
            "title": title,
            "content": content,
            "json_ld": self.schema_gen.generate_article_ld(
                title=title,
                author=self.brand["name"],
                content_type="Article",
            ),
        }

    async def _adapt_to_platforms(self, articles):
        """将文章适配到各平台"""
        try:
            from .adapter import ContentAdapter
            adapter = ContentAdapter(self.config)
            return await adapter.adapt_and_assign(articles)
        except ImportError as e:
            print(f"[GEO] 适配器加载失败，跳过平台适配: {e}")
            return {"website": articles}

    def _extract_questions(self, faq_content):
        """从FAQ内容中提取问题列表"""
        questions = re.findall(r"^###?\s+(.+[？?])", faq_content, re.MULTILINE)
        if not questions:
            questions = re.findall(r"^\d+[\.\、]\s*(.+[？?])", faq_content, re.MULTILINE)
        return questions[:15]


async def test_generate():
    """测试内容生成"""
    gen = ContentGenerator()
    print("Testing content generation...")
    result = await gen.generate_review("ChatGPT", "AI对话")
    print(f"Generated {len(result)} characters")
    print(result[:500])
    return result


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_generate())

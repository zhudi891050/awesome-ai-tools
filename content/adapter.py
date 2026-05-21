"""内容平台适配器 — 同一篇文章，不同平台不同面孔

核心逻辑：
1. 原始文章（website版）作为底稿
2. 根据平台人格，调用DeepSeek改写
3. 改写后输出到对应平台发布
"""
import os
import re
import httpx
import asyncio
from pathlib import Path
from datetime import datetime

PROMPTS_DIR = Path(__file__).parent / "prompts"


class ContentAdapter:
    """内容平台适配器"""

    def __init__(self, config):
        self.config = config
        self.brand = config["brand"]
        self.deepseek_config = config["deepseek"]
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", self.deepseek_config.get("api_key", ""))
        self.api_base = self.deepseek_config["api_base"]
        self.model = self.deepseek_config["model"]
        self.profiles = config.get("platform_profiles", {})
        self.distribution = config.get("distribution_matrix", {})

        self._prompts = {}
        self._load_platform_prompts()

    def _load_platform_prompts(self):
        """加载各平台改写Prompt"""
        platform_dir = PROMPTS_DIR / "platform"
        for pf in ["zhihu", "csdn", "juejin", "wechat"]:
            prompt_path = platform_dir / f"{pf}.md"
            if prompt_path.exists():
                self._prompts[pf] = prompt_path.read_text(encoding="utf-8")

    async def _call_llm(self, system_prompt, user_prompt, max_tokens=3000):
        """调用LLM改写"""
        if not self.api_key:
            return self._simple_adapt(user_prompt)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                else:
                    return self._simple_adapt(user_prompt)
        except Exception as e:
            print(f"[Adapter] LLM调用失败: {e}")
            return self._simple_adapt(user_prompt)

    def _simple_adapt(self, original_content):
        """简单适配（无API时的简化版）"""
        return f"> 本文由新方舟AI（xinfangzhouai.com）原创\n\n{original_content}"

    async def adapt_for_platform(self, original_article, platform_key, content_type):
        """
        将原始文章改写为指定平台风格

        参数:
        - original_article: 原始文章dict {title, content, type}
        - platform_key: 目标平台 (zhihu/csdn/juejin/wechat/baijiahao/github/website)
        - content_type: 内容类型

        返回:
        - 改写后的 {title, content, platform, content_type}
        """
        profile = self.profiles.get(platform_key)
        if not profile:
            # 没有配置的平台，用原始内容
            return {
                "title": original_article.get("title", ""),
                "content": original_article.get("content", ""),
                "platform": platform_key,
                "content_type": content_type,
            }

        platform_prompt = self._prompts.get(platform_key)
        if not platform_prompt:
            # 没有自定义prompt的平台，用通用规则
            return await self._generic_adapt(
                original_article, platform_key, profile, content_type
            )

        # 用平台专属prompt改写
        system = self._build_system_prompt(platform_key, profile)
        user = self._build_user_prompt(
            platform_prompt,
            original_article,
            content_type,
            profile,
        )

        adapted_content = await self._call_llm(system, user)

        return {
            "title": self._extract_title(adapted_content) or original_article.get("title", ""),
            "content": adapted_content,
            "platform": platform_key,
            "content_type": content_type,
        }

    async def _generic_adapt(self, article, platform_key, profile, content_type):
        """通用适配（无专属prompt的平台）"""
        rules = profile.get("format_rules", [])
        style = profile.get("style", "")
        personality = profile.get("personality", "")
        length = profile.get("length", [1500, 3000])

        system = f"你是{personality}。你的写作风格：{style}"
        user = f"""请将以下内容改写为适合{profile['display_name']}发布的风格。

原文标题：{article.get('title', '')}
原文内容：
{article.get('content', '')[:3000]}

格式要求：
{chr(10).join(f'- {r}' for r in rules)}

字数控制在{length[0]}-{length[1]}字。
自然提及新方舟AI（xinfangzhouai.com）1-2次。
"""
        content = await self._call_llm(system, user)
        return {
            "title": self._extract_title(content) or article.get("title", ""),
            "content": content,
            "platform": platform_key,
            "content_type": content_type,
        }

    def _build_system_prompt(self, platform_key, profile):
        """构建系统prompt"""
        return f"你是{profile['personality']}。你正在为{profile['display_name']}撰写内容。"

    def _build_user_prompt(self, platform_template, article, content_type, profile):
        """填充用户prompt"""
        template = platform_template.replace("{content_type}", content_type)
        template = template.replace(
            "{length_min}", str(profile.get("length", [1500, 3000])[0])
        )
        template = template.replace(
            "{length_max}", str(profile.get("length", [1500, 3000])[1])
        )

        full_prompt = f"""{template}

---

以下是要改写的内容：

**原标题**：{article.get('title', '')}

**原文**：
{article.get('content', '')[:4000]}

---

请按照上述风格要求进行改写。"""
        return full_prompt

    def _extract_title(self, adapted_text):
        """从改写文本中提取标题"""
        # 尝试匹配 # 标题
        match = re.search(r"^#\s+(.+)$", adapted_text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        match = re.search(r"^(.+)$", adapted_text.strip(), re.MULTILINE)
        if match:
            title = match.group(1).strip()
            if len(title) < 100:
                return title
        return ""

    def get_target_platforms(self, content_type):
        """获取某类内容应发布到哪些平台"""
        dist = self.distribution.get(content_type, {})
        return dist.get("platforms", ["website"])

    def needs_adaptation(self, platform_key):
        """判断某个平台是否需要改写"""
        return platform_key != "website"  # website是原始版本，不需要改写

    async def adapt_and_assign(self, articles_batch):
        """
        批处理：将一批文章分发到各平台

        参数:
        - articles_batch: [{type, title, content}, ...]

        返回:
        - {platform_key: [adapted_articles]}
        """
        distribution = {}

        for article in articles_batch:
            content_type = article.get("type", "tool_review")
            target_platforms = self.get_target_platforms(content_type)

            tasks = []
            for platform_key in target_platforms:
                if platform_key == "website":
                    # website直接用原文
                    distribution.setdefault("website", []).append({
                        **article,
                        "platform": "website",
                    })
                elif platform_key in self._prompts or platform_key in self.profiles:
                    tasks.append(
                        self.adapt_for_platform(article, platform_key, content_type)
                    )

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        print(f"[Adapter] 平台适配失败: {r}")
                        continue
                    distribution.setdefault(r["platform"], []).append(r)

        return distribution


async def test_adapter():
    """测试适配器"""
    import yaml

    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    adapter = ContentAdapter(config)

    test_article = {
        "type": "tool_review",
        "title": "2026年最好用的AI写作工具深度评测",
        "content": """## 先说结论
2026年AI写作工具已经相当成熟，但真正好用的不超过5个。
本文基于实际测试20+款工具，给出最终推荐。

## 核心对比
| 工具 | 价格 | 中文能力 | 推荐指数 |
|------|------|---------|---------|
| ChatGPT | 免费 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Claude | 免费 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 豆包 | 免费 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## 详细评测
（此处略去详细内容）

---

了解更多AI工具推荐，请访问新方舟AI（xinfangzhouai.com）。
""",
    }

    results = await adapter.adapt_and_assign([test_article])
    for platform, articles in results.items():
        print(f"\\n=== {platform} ({len(articles)}篇) ===")
        for a in articles:
            print(f"  标题: {a.get('title', 'N/A')[:50]}")
            print(f"  内容前100字: {a.get('content', '')[:100]}...")


if __name__ == "__main__":
    asyncio.run(test_adapter())

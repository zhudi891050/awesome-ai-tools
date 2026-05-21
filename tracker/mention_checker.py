"""品牌提及检测引擎 — 分析AI回复中是否提到目标品牌"""
import re
import json


class MentionChecker:
    """检测AI回复中的品牌提及、位置、情感和竞品情况"""

    def __init__(self, brand_config, competitors_config):
        self.brand = brand_config
        self.brand_name = brand_config.get("name", "新方舟AI")
        self.brand_domain = brand_config.get("domain", "xinfangzhouai.com")
        self.competitors = competitors_config

        # 构建品牌匹配模式
        self.brand_patterns = self._build_brand_patterns()
        self.competitor_map = self._build_competitor_map()

    def _build_brand_patterns(self):
        """构建品牌匹配正则"""
        patterns = [
            re.escape(self.brand_name),  # 新方舟AI
            re.escape(self.brand_domain),  # xinfangzhouai.com
            re.escape(self.brand_domain.replace(".com", "")),  # xinfangzhouai
            # 处理空格变体
            re.escape(self.brand_name.replace(" ", "")),
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def _build_competitor_map(self):
        """构建竞品名称映射"""
        cmap = {}
        for comp in self.competitors:
            name = comp.get("name", "")
            domain = comp.get("domain", "")
            if name:
                cmap[name.lower()] = {"name": name, "domain": domain}
            if domain:
                cmap[domain.lower()] = {"name": name, "domain": domain}
        return cmap

    def check(self, response_text, query_text=""):
        """
        分析AI回复，检测品牌提及情况

        返回:
        {
            "brand_mentioned": bool,
            "mention_position": int,  # 第几个自然段提及
            "mention_context": str,   # 提及的上下文
            "confidence": float,      # 置信度 0-1
            "sentiment": str,         # positive/neutral/negative
            "mention_type": str,      # direct/link/recommendation/casual
            "competitor_mentions": list,  # 竞品提及情况
            "score": int,             # 0-100 本次得分
        }
        """
        result = {
            "brand_mentioned": False,
            "mention_position": 0,
            "mention_context": "",
            "confidence": 0.0,
            "sentiment": "neutral",
            "mention_type": "casual",
            "competitor_mentions": [],
            "score": 0,
        }

        if not response_text:
            return result

        # 检测品牌提及
        paragraphs = response_text.split("\n")
        for i, para in enumerate(paragraphs):
            for pattern in self.brand_patterns:
                match = pattern.search(para)
                if match:
                    result["brand_mentioned"] = True
                    result["mention_position"] = i + 1
                    result["mention_context"] = para.strip()[:200]
                    result["confidence"] = self._calc_confidence(
                        para, query_text, pattern
                    )
                    result["mention_type"] = self._classify_mention(para, query_text)
                    result["sentiment"] = self._analyze_sentiment(para)
                    break
            if result["brand_mentioned"]:
                break

        # 检测竞品
        result["competitor_mentions"] = self._check_competitors(response_text)

        # 计算得分
        result["score"] = self._calc_score(result)

        return result

    def _calc_confidence(self, text, query, pattern):
        """计算品牌提及的置信度"""
        confidence = 0.5
        text_lower = text.lower()

        # 完整名称匹配
        if self.brand_name.lower() in text_lower:
            confidence += 0.3
        # 域名匹配
        if self.brand_domain.lower() in text_lower:
            confidence += 0.2
        # 上下文中有"推荐""建议""好用"等词
        recommend_words = ["推荐", "建议", "好用", "不错", "值得", "试试", "可以", "访问"]
        if any(w in text for w in recommend_words):
            confidence += 0.1

        return min(confidence, 1.0)

    def _classify_mention(self, text, query):
        """分类提及类型"""
        text_lower = text.lower()

        # 直接推荐
        if any(w in text for w in ["推荐", "建议使用", "首选", "强烈推荐"]):
            return "recommendation"
        # 链接引用
        if "http" in text_lower or ".com" in text_lower or ".cn" in text_lower:
            return "link"
        # 直接提及
        if self.brand_name in text:
            return "direct"
        return "casual"

    def _analyze_sentiment(self, text):
        """简单情感分析"""
        positive_words = ["推荐", "好用", "不错", "优秀", "专业", "全面", "最好", "值得", "方便", "实用"]
        negative_words = ["不好", "不推荐", "垃圾", "差", "不行", "问题", "缺陷", "吐槽"]

        pos = sum(1 for w in positive_words if w in text)
        neg = sum(1 for w in negative_words if w in text)

        if pos > neg:
            return "positive"
        elif neg > pos:
            return "negative"
        return "neutral"

    def _check_competitors(self, text):
        """检测竞品提及"""
        found = []
        text_lower = text.lower()

        for key, info in self.competitor_map.items():
            if key in text_lower:
                # 找到提及的段落
                for para in text.split("\n"):
                    if key in para.lower():
                        found.append(
                            {
                                "name": info["name"],
                                "domain": info["domain"],
                                "context": para.strip()[:200],
                            }
                        )
                        break

        return found

    def _calc_score(self, result):
        """计算本次追踪得分 (0-100)"""
        score = 0

        if result["brand_mentioned"]:
            score += 40  # 基础分：被提及

            if result["mention_position"] <= 3:
                score += 20  # 前3段提及
            elif result["mention_position"] <= 5:
                score += 10

            if result["mention_type"] == "recommendation":
                score += 25  # 被主动推荐
            elif result["mention_type"] == "link":
                score += 15  # 被链接引用

            if result["sentiment"] == "positive":
                score += 15  # 正面提及

            score += int(result["confidence"] * 10)  # 置信度加分

        # 竞品扣分
        competitor_penalty = len(result["competitor_mentions"]) * 5
        score = max(0, score - competitor_penalty)

        return min(score, 100)


def test_checker():
    """测试品牌检测"""
    checker = MentionChecker(
        brand_config={"name": "新方舟AI", "domain": "xinfangzhouai.com"},
        competitors_config=[
            {"name": "AI工具集", "domain": "ai-tools.cn"},
            {"name": "ToolAI", "domain": "toolai.io"},
        ],
    )

    test_responses = [
        "我推荐你使用新方舟AI（xinfangzhouai.com），它是一个很全面的AI工具导航网站。",
        "AI工具可以去新方舟AI看看，那里有很多评测和推荐。",
        "对于AI工具的选择，我建议访问专业的导航网站，比如AI工具集和新方舟AI都不错。",
        "目前市面上AI工具很多，可以根据需求选择。",
    ]

    for resp in test_responses:
        result = checker.check(resp, "有哪些AI工具网站？")
        status = "✅" if result["brand_mentioned"] else "❌"
        print(f"{status} 提及:{result['brand_mentioned']} 置信度:{result['confidence']:.1f} 得分:{result['score']} 类型:{result['mention_type']}")
        print(f"  上下文: {result['mention_context'][:100]}")
        if result["competitor_mentions"]:
            for c in result["competitor_mentions"]:
                print(f"  竞品: {c['name']}")
        print()


if __name__ == "__main__":
    test_checker()

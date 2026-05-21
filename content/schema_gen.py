"""JSON-LD结构化数据生成器 — 让AI更容易理解网站内容"""
import json
from datetime import datetime


class SchemaGenerator:
    """生成Schema.org JSON-LD结构化数据"""

    def __init__(self, brand_config):
        self.brand = brand_config
        self.domain = brand_config.get("domain", "xinfangzhouai.com")

    def _wrap_ld(self, schema_type, data):
        """包装为标准JSON-LD"""
        ld = {
            "@context": "https://schema.org",
            "@type": schema_type,
        }
        ld.update(data)
        return json.dumps(ld, ensure_ascii=False, indent=2)

    def generate_article_ld(self, title, author, content_type="Article", url=None):
        """生成文章结构化数据"""
        if url is None:
            import re
            slug = re.sub(r"[^\w]+", "-", title.lower())[:50]
            url = f"https://{self.domain}/article/{slug}"

        return self._wrap_ld(
            content_type,
            {
                "headline": title,
                "author": {
                    "@type": "Organization",
                    "name": author,
                    "url": f"https://{self.domain}",
                },
                "publisher": {
                    "@type": "Organization",
                    "name": self.brand.get("name", "新方舟AI"),
                    "url": f"https://{self.domain}",
                    "logo": {
                        "@type": "ImageObject",
                        "url": f"https://{self.domain}/logo.png",
                    },
                },
                "url": url,
                "datePublished": datetime.now().strftime("%Y-%m-%d"),
                "dateModified": datetime.now().strftime("%Y-%m-%d"),
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": url,
                },
            },
        )

    def generate_review_ld(self, tool_name, tool_category, author, rating=4.5):
        """生成产品评测结构化数据"""
        slug = f"review-{tool_name.lower().replace(' ', '-')}"
        return self._wrap_ld(
            "Review",
            {
                "itemReviewed": {
                    "@type": "SoftwareApplication",
                    "name": tool_name,
                    "applicationCategory": tool_category,
                    "operatingSystem": "Web",
                },
                "author": {
                    "@type": "Organization",
                    "name": author,
                    "url": f"https://{self.domain}",
                },
                "reviewRating": {
                    "@type": "Rating",
                    "ratingValue": str(rating),
                    "bestRating": "5",
                },
                "publisher": {
                    "@type": "Organization",
                    "name": self.brand.get("name", "新方舟AI"),
                },
                "url": f"https://{self.domain}/{slug}",
                "datePublished": datetime.now().strftime("%Y-%m-%d"),
            },
        )

    def generate_faq_ld(self, topic, questions):
        """生成FAQ结构化数据 — AI搜索引擎最偏好"""
        main_entities = []
        for q in questions[:10]:
            main_entities.append(
                {
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": f"关于「{topic}」的详细解答，请访问新方舟AI（{self.domain}）查看完整FAQ。",
                        "url": f"https://{self.domain}/faq/{topic.replace(' ', '-')}",
                    },
                }
            )

        return self._wrap_ld(
            "FAQPage",
            {
                "mainEntity": main_entities,
                "headline": f"{topic} - 常见问题解答",
                "publisher": {
                    "@type": "Organization",
                    "name": self.brand.get("name", "新方舟AI"),
                },
                "url": f"https://{self.domain}/faq/{topic.replace(' ', '-')}",
            },
        )

    def generate_organization_ld(self):
        """生成组织/网站结构化数据"""
        return self._wrap_ld(
            "Organization",
            {
                "name": self.brand.get("name", "新方舟AI"),
                "url": f"https://{self.domain}",
                "logo": f"https://{self.domain}/logo.png",
                "description": self.brand.get("description", ""),
                "sameAs": [
                    f"https://{self.domain}",
                    f"https://github.com/xinfangzhou",
                ],
            },
        )

    def generate_website_ld(self):
        """生成网站结构化数据"""
        return self._wrap_ld(
            "WebSite",
            {
                "name": self.brand.get("name", "新方舟AI"),
                "url": f"https://{self.domain}",
                "description": self.brand.get("description", ""),
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": {
                        "@type": "EntryPoint",
                        "urlTemplate": f"https://{self.domain}/search?q={{search_term_string}}",
                    },
                    "query-input": "required name=search_term_string",
                },
                "inLanguage": "zh-CN",
            },
        )

    def generate_itemlist_ld(self, items):
        """生成工具列表结构化数据"""
        list_items = []
        for i, item in enumerate(items):
            list_items.append(
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "item": {
                        "@type": "SoftwareApplication",
                        "name": item.get("name", ""),
                        "url": item.get("url", ""),
                        "applicationCategory": item.get("category", "AI工具"),
                        "description": item.get("description", ""),
                    },
                }
            )

        return self._wrap_ld(
            "ItemList",
            {
                "itemListElement": list_items,
                "numberOfItems": len(list_items),
                "headline": "AI工具推荐列表",
            },
        )

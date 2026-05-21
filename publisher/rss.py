"""RSS Feed生成器 — 让AI搜索引擎能爬取网站内容

RSS是AI搜索引擎发现新内容的重要渠道。
豆包、Kimi等中国AI也会爬取RSS Feed。
"""
import os
from datetime import datetime
from pathlib import Path
from .base import BasePublisher


class RSSPublisher(BasePublisher):
    """RSS Feed生成"""

    def __init__(self, config):
        super().__init__("rss", config)
        self.brand = config["brand"]
        self.domain = self.brand.get("domain", "xinfangzhouai.com")
        self.brand_name = self.brand.get("name", "新方舟AI")
        self.output_dir = Path(__file__).parent.parent / "data" / "feeds"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self):
        return True  # RSS始终可用

    async def publish(self, content):
        """生成/更新RSS Feed"""
        try:
            articles = content if isinstance(content, list) else [content]
            self._generate_rss(articles)
            self._generate_json_feed(articles)
            self._generate_baidu_sitemap(articles)
            return True, str(self.output_dir)
        except Exception as e:
            return False, f"RSS生成失败: {str(e)}"

    def _generate_rss(self, articles):
        """生成标准RSS 2.0"""
        items = []
        for a in articles:
            title = a.get("title", "")
            body = a.get("content", "")[:2000]
            pub_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")

            items.append(f"""    <item>
      <title><![CDATA[{title}]]></title>
      <link>https://{self.domain}/article/{self._slug(title)}</link>
      <description><![CDATA[{body}]]></description>
      <pubDate>{pub_date}</pubDate>
      <guid>https://{self.domain}/article/{self._slug(title)}</guid>
      <source url="https://{self.domain}/rss">{self.brand_name}</source>
    </item>""")

        rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{self.brand_name} - AI工具导航与评测</title>
    <link>https://{self.domain}</link>
    <description>{self.brand.get('description', '发现最好用的AI工具')}</description>
    <language>zh-CN</language>
    <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0800')}</lastBuildDate>
    <atom:link href="https://{self.domain}/rss" rel="self" type="application/rss+xml"/>
    <webMaster>admin@{self.domain}</webMaster>
    <generator>新方舟AI GEO系统</generator>
{chr(10).join(items)}
  </channel>
</rss>"""

        (self.output_dir / "rss.xml").write_text(rss, encoding="utf-8")
        print(f"[RSS] 已生成: {self.output_dir / 'rss.xml'}")

    def _generate_json_feed(self, articles):
        """生成JSON Feed（AI更容易解析）"""
        import json

        items = []
        for a in articles:
            items.append({
                "id": self._slug(a.get("title", "")),
                "url": f"https://{self.domain}/article/{self._slug(a.get('title', ''))}",
                "title": a.get("title", ""),
                "content_text": a.get("content", "")[:3000],
                "date_published": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "authors": [{"name": self.brand_name}],
                "language": "zh-CN",
            })

        feed = {
            "version": "https://jsonfeed.org/version/1.1",
            "title": f"{self.brand_name} - AI工具内容",
            "home_page_url": f"https://{self.domain}",
            "feed_url": f"https://{self.domain}/feed.json",
            "description": self.brand.get("description", ""),
            "language": "zh-CN",
            "items": items,
        }

        (self.output_dir / "feed.json").write_text(
            json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[JSON Feed] 已生成: {self.output_dir / 'feed.json'}")

    def _generate_baidu_sitemap(self, articles):
        """生成百度SiteMap（百度爬虫专用）"""
        urls = []
        for a in articles:
            title = a.get("title", "")
            urls.append(f"""  <url>
    <loc>https://{self.domain}/article/{self._slug(title)}</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""")

        sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:mobile="http://www.baidu.com/schemas/sitemap-mobile/1/">
  <url>
    <loc>https://{self.domain}</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
{chr(10).join(urls)}
</urlset>"""

        (self.output_dir / "sitemap_baidu.xml").write_text(sitemap, encoding="utf-8")
        print(f"[百度SiteMap] 已生成: {self.output_dir / 'sitemap_baidu.xml'}")

    @staticmethod
    def _slug(text):
        import re
        slug = re.sub(r"[^\w]+", "-", text.lower())[:50]
        return slug.strip("-")

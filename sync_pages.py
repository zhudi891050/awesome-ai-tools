"""GEO → GitHub Pages 同步脚本
每次内容生成后自动更新首页和 sitemap，推送到 GitHub Pages
"""
import os, sys, json, subprocess
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

def main():
    print("🌐 同步到 GitHub Pages...")

    # 从生产 API 获取文章列表
    import httpx
    try:
        resp = httpx.get("http://39.102.49.11:4000/api/articles?limit=50", verify=False, timeout=15)
        data = resp.json()
        articles = data["articles"]
    except Exception as e:
        print(f"  ❌ 获取文章失败: {e}")
        return False

    # 生成 index.html
    cats = set()
    for a in articles:
        cats.add(a.get("category", "其他"))

    badge_map = {"tool_review":"评测","tool_list":"推荐","tool_compare":"对比","faq":"问答","industry_view":"趋势"}
    color_map = {"tool_review":"badge-review","tool_list":"badge-list","tool_compare":"badge-compare","faq":"badge-faq","industry_view":"badge-industry"}

    articles_js = json.dumps([
        {"id":a["id"],"title":a["title"],"type":a["content_type"],"category":a["category"],
         "url":f"http://39.102.49.11:4000/article/{a['slug']}"}
        for a in articles
    ], ensure_ascii=False)

    cat_items = "".join(
        f'<span class="tag" onclick="filterArticles(\'{c}\')" style="cursor:pointer">{c}</span>'
        for c in sorted(cats)
    )
    all_tag = '<span class="tag" onclick="filterArticles(\'all\')" style="cursor:pointer;color:#4A90D9;border-color:#4A90D9">全部</span>'

    today = __import__("datetime").datetime.now().strftime("%Y年%-m月%-d日")

    index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>新方舟AI - AI工具导航与评测社区</title>
<meta name="description" content="新方舟AI — 专业AI工具导航、深度评测、使用教程社区。发现最好用的AI工具，获取最新AI资讯。">
<style>
:root{{--bg:#0f0f1a;--card:#1a1a2e;--accent:#4A90D9;--accent2:#7BB3F0;--text:#e0e0e0;--muted:#888;--border:#2a2a3e}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);line-height:1.6}}
.container{{max-width:960px;margin:0 auto;padding:20px}}
header{{text-align:center;padding:60px 20px 40px;background:linear-gradient(135deg,#0f0f1a 0%,#1a1a2e 100%)}}
header h1{{font-size:2.2em;font-weight:700;background:linear-gradient(135deg,#4A90D9,#7BB3F0);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
header p{{color:var(--muted);margin-top:10px;font-size:1.05em}}
.stats{{display:flex;justify-content:center;gap:40px;margin:30px 0;flex-wrap:wrap}}
.stat{{text-align:center}}
.stat-num{{font-size:2em;font-weight:700;color:var(--accent2)}}
.stat-label{{font-size:0.85em;color:var(--muted);margin-top:4px}}
.categories{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:20px 0 30px}}
.tag{{display:inline-block;padding:4px 14px;border-radius:20px;font-size:0.82em;border:1px solid var(--border);color:var(--muted);cursor:default;transition:.2s}}
.tag:hover{{color:var(--accent2);border-color:var(--accent2)}}
.articles{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}}
.article-card{{background:var(--card);border-radius:12px;padding:20px;border:1px solid var(--border);transition:.2s;display:flex;flex-direction:column}}
.article-card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.article-badge{{display:inline-block;padding:2px 10px;border-radius:4px;font-size:0.75em;color:#fff;margin-bottom:10px;width:fit-content}}
.badge-review{{background:#4A90D9}}
.badge-list{{background:#50C878}}
.badge-compare{{background:#9B59B6}}
.badge-faq{{background:#E67E22}}
.badge-industry{{background:#E74C3C}}
.article-title{{font-size:1.05em;font-weight:600;margin-bottom:8px;flex-grow:1}}
.article-title a{{color:var(--text);text-decoration:none}}
.article-title a:hover{{color:var(--accent2)}}
.article-meta{{font-size:0.82em;color:var(--muted);margin-top:8px}}
footer{{text-align:center;padding:40px 20px;color:var(--muted);font-size:0.85em}}
footer a{{color:var(--accent2);text-decoration:none}}
@media(max-width:600px){{header h1{{font-size:1.6em}}.articles{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header>
<h1>⚡ 新方舟AI</h1>
<p>专业AI工具导航 · 深度评测 · 使用教程</p>
<p style="margin-top:6px;font-size:0.85em;color:#666">
<a href="http://39.102.49.11:4000" style="color:#4A90D9;text-decoration:none">访问主站 →</a>
</p>
</header>
<div class="container">
<div class="stats" id="stats">
<div class="stat"><div class="stat-num">{len(articles)}</div><div class="stat-label">文章总数</div></div>
<div class="stat"><div class="stat-num">{len(cats)}</div><div class="stat-label">AI 分类</div></div>
<div class="stat"><div class="stat-num">{today}</div><div class="stat-label">最后更新</div></div>
</div>
<div class="categories">{all_tag}{cat_items}</div>
<div class="articles" id="articles"></div>
<footer>
<p>© 2026 <a href="http://39.102.49.11:4000">新方舟AI</a> — 发现最好用的AI工具</p>
</footer>
</div>
<script>
const articles = {articles_js};
const badgeMap={tool_review:'评测',tool_list:'推荐',tool_compare:'对比',faq:'问答',industry_view:'趋势'};
const colorMap={tool_review:'badge-review',tool_list:'badge-list',tool_compare:'badge-compare',faq:'badge-faq',industry_view:'badge-industry'};
function render(list){{
let html='';
list.forEach(a=>{{
let badge=badgeMap[a.type]||a.type;
let cls=colorMap[a.type]||'badge-review';
html+=`<div class="article-card"><span class="article-badge ${{cls}}">${{badge}}</span><div class="article-title"><a href="${{a.url}}" target="_blank">${{a.title}}</a></div><div class="article-meta">${{a.category}} · ${{a.type.replace('_',' ')}}</div></div>`}});
document.getElementById('articles').innerHTML=html;}}
function filterArticles(cat){{if(cat==='all')render(articles);else render(articles.filter(a=>a.category===cat));}}
filterArticles('all');
</script>
</body>
</html>"""

    # 生成 sitemap.xml
    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
                     '<url><loc>https://zhudi891050.github.io/awesome-ai-tools/</loc><priority>1.0</priority></url>']
    for a in articles:
        url = f"http://39.102.49.11:4000/article/{a['slug']}"
        sitemap_lines.append(f'<url><loc>{url}</loc><priority>0.9</priority></url>')
    sitemap_lines.append('</urlset>')
    sitemap_xml = '\n'.join(sitemap_lines)

    # 写文件
    (ROOT / "index.html").write_text(index_html, encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    print(f"  ✅ 已生成 index.html 和 sitemap.xml ({len(articles)} 篇文章)")

    # 推送到 GitHub
    try:
        r = subprocess.run(
            "git add index.html sitemap.xml && "
            "git commit -m 'auto: update articles index and sitemap' && "
            "git push",
            shell=True, capture_output=True, text=True, timeout=60, cwd=ROOT
        )
        if r.returncode == 0:
            print(f"  ✅ 已推送到 GitHub Pages")
        elif "nothing to commit" in r.stderr or "nothing to commit" in r.stdout:
            print(f"  ℹ️  无更新")
        else:
            print(f"  ⚠️  {r.stderr[:200]}")
    except Exception as e:
        print(f"  ❌ Git 推送失败: {e}")
        return False

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

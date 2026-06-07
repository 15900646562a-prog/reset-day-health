#!/usr/bin/env python3
"""渲染:文章 JSON → 静态 SEO 网页 + index + sitemap + robots。纯代码,无 LLM。"""
import json, re, glob, html
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
SITE = ROOT / "docs"
SITE.mkdir(parents=True, exist_ok=True)
import os
BASE = os.environ.get("SEO_BASE_URL", "https://15900646562a-prog.github.io/reset-day-health").rstrip("/")

CLUSTER_NAMES = {
    "life-after-the-shot": "Life After the Shot",
    "affordable-alternatives": "Affordable Alternatives",
    "midlife-metabolism": "Midlife Metabolism",
    "pcos-insulin": "PCOS & Insulin",
    "food-noise": "Food Noise & Cravings",
}
# 渲染期最后兜底:把 advisory flag 词中性化
NEUTRALIZE = [(re.compile(r"\bguarantee(d|s)?\b", re.I), "designed to help"),
             (re.compile(r"\bFDA[- ]approved\b", re.I), "lab-tested")]
def clean(s):
    s = s or ""
    for rx, rep in NEUTRALIZE:
        s = rx.sub(rep, s)
    return s

CSS = """:root{--ink:#1a1d24;--muted:#5b6472;--accent:#0e7c66;--bg:#fbfaf7;--card:#fff;--line:#e7e3da}
*{box-sizing:border-box}body{margin:0;font:18px/1.7 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
header.site{border-bottom:1px solid var(--line);background:var(--card)}
.wrap{max-width:720px;margin:0 auto;padding:0 20px}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;height:60px}
.brand{font-weight:700;letter-spacing:-.02em;color:var(--ink);text-decoration:none;font-size:19px}
.brand b{color:var(--accent)}
main{padding:40px 0 64px}
.eyebrow{color:var(--accent);font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px}
h1{font-size:clamp(28px,4vw,40px);line-height:1.15;letter-spacing:-.02em;margin:0 0 20px}
h2{font-size:24px;letter-spacing:-.01em;margin:38px 0 12px}
p{margin:0 0 16px}ul{margin:0 0 16px;padding-left:22px}li{margin:6px 0}
a{color:var(--accent)}
.byline{color:var(--muted);font-size:15px;margin:0 0 28px;padding-bottom:20px;border-bottom:1px solid var(--line)}
.cta{margin:36px 0;padding:22px 24px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:10px}
.cta p{margin:0;font-size:18px}
.faq{margin-top:40px}.faq h3{font-size:18px;margin:22px 0 6px}.faq p{color:var(--muted)}
.related{margin-top:44px;padding-top:24px;border-top:1px solid var(--line)}
.related a{display:block;margin:8px 0}
.disclaimer{margin-top:40px;color:var(--muted);font-size:13.5px;line-height:1.6}
footer{border-top:1px solid var(--line);padding:28px 0;color:var(--muted);font-size:14px;background:var(--card)}
.grid{display:grid;gap:10px}.cluster{margin:30px 0}.cluster h2{margin-bottom:8px}
.card{display:block;padding:16px 18px;background:var(--card);border:1px solid var(--line);border-radius:10px;text-decoration:none;color:var(--ink)}
.card:hover{border-color:var(--accent)}.card .t{font-weight:600}.card .m{color:var(--muted);font-size:15px;margin-top:4px}
"""

HEAD = """<header class="site"><div class="wrap"><a class="brand" href="{base}/index.html">Reset<b>Day</b></a><span style="color:var(--muted);font-size:14px">No-needle weight support</span></div></header>"""
FOOT = """<footer><div class="wrap">© Reset Day · Health education, not medical advice · <a href="{base}/index.html">All articles</a></div></footer>"""


def esc(s): return html.escape(s or "", quote=True)


def load_articles():
    arts, seen = [], {}
    for f in sorted(glob.glob(str(ARTICLES / "*.json"))):
        d = json.load(open(f))
        slug = d.get("slug") or Path(f).stem
        # slug 去重
        if slug in seen:
            seen[slug] += 1; slug = f"{slug}-{seen[slug]}"
        else:
            seen[slug] = 1
        d["slug"] = slug
        arts.append(d)
    return arts


def render_article(d, siblings):
    url = f"{BASE}/{d['slug']}.html"
    secs = "".join(f"<h2>{esc(s.get('h2',''))}</h2>{clean(s.get('html',''))}" for s in d.get("sections", []))
    faq = d.get("faq", [])
    faq_html = ""
    if faq:
        faq_html = '<div class="faq"><h2>Frequently asked questions</h2>' + "".join(
            f"<h3>{esc(q.get('q',''))}</h3><p>{clean(q.get('a',''))}</p>" for q in faq) + "</div>"
    rel = "".join(f'<a href="{BASE}/{s["slug"]}.html">{esc(s["title"])}</a>' for s in siblings[:3])
    rel_html = f'<div class="related"><strong>Related reading</strong>{rel}</div>' if rel else ""
    # JSON-LD
    ld = {"@context": "https://schema.org", "@type": "MedicalWebPage", "headline": d.get("title", ""),
          "description": d.get("meta_description", ""), "url": url,
          "author": {"@type": "Organization", "name": "Reset Day Health Education Team"},
          "publisher": {"@type": "Organization", "name": "Reset Day"}}
    faq_ld = ""
    if faq:
        faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": clean(q.get("q", "")),
                "acceptedAnswer": {"@type": "Answer", "text": re.sub('<[^>]+>', '', clean(q.get("a", "")))}} for q in faq]}, ensure_ascii=False)
        faq_ld = f'<script type="application/ld+json">{faq_ld}</script>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(d.get('title',''))} | Reset Day</title>
<meta name="description" content="{esc(d.get('meta_description',''))}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:title" content="{esc(d.get('title',''))}">
<meta property="og:description" content="{esc(d.get('meta_description',''))}"><meta property="og:url" content="{url}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>{faq_ld}
<style>{CSS}</style></head><body>
{HEAD.format(base=BASE)}
<main><div class="wrap">
<p class="eyebrow">{esc(CLUSTER_NAMES.get(d.get('cluster',''),'Weight & Metabolism'))}</p>
<h1>{esc(d.get('h1') or d.get('title',''))}</h1>
<p class="byline">By the Reset Day Health Education Team · General education, not medical advice</p>
{clean(d.get('intro_html',''))}
{secs}
{faq_html}
<div class="cta">{clean(d.get('cta_html',''))}</div>
{rel_html}
<p class="disclaimer">This article is for general education and is not medical advice. T-Patch is a topical (transdermal) delivery of tirzepatide. Talk to your healthcare provider about decisions involving any medication, including tirzepatide.</p>
</div></main>
{FOOT.format(base=BASE)}
</body></html>"""


def render_index(arts):
    by = defaultdict(list)
    for a in arts:
        by[a.get("cluster", "food-noise")].append(a)
    blocks = ""
    for ck, name in CLUSTER_NAMES.items():
        items = by.get(ck, [])
        if not items:
            continue
        cards = "".join(f'<a class="card" href="{BASE}/{a["slug"]}.html"><div class="t">{esc(a["title"])}</div><div class="m">{esc(a.get("meta_description",""))}</div></a>' for a in items)
        blocks += f'<div class="cluster"><h2>{esc(name)}</h2><div class="grid">{cards}</div></div>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reset Day — No-Needle Weight Support & GLP-1 Education</title>
<meta name="description" content="Plain-English education on GLP-1, tirzepatide, metabolism, PCOS and cravings — and T-Patch, the no-needle topical tirzepatide.">
<link rel="canonical" href="{BASE}/index.html"><style>{CSS}</style></head><body>
{HEAD.format(base=BASE)}
<main><div class="wrap">
<p class="eyebrow">Reset Day</p>
<h1>Weight, metabolism & GLP-1 — in plain English</h1>
<p>Honest education on tirzepatide, GLP-1, PCOS, cravings and life after the shot — plus T-Patch, the no-needle topical way to access tirzepatide.</p>
{blocks}
</div></main>
{FOOT.format(base=BASE)}
</body></html>"""


def main():
    arts = load_articles()
    by = defaultdict(list)
    for a in arts:
        by[a.get("cluster", "food-noise")].append(a)
    n = 0
    urls = [f"{BASE}/index.html"]
    for a in arts:
        siblings = [s for s in by[a.get("cluster", "food-noise")] if s["slug"] != a["slug"]]
        (SITE / f"{a['slug']}.html").write_text(render_article(a, siblings))
        urls.append(f"{BASE}/{a['slug']}.html")
        n += 1
    (SITE / "index.html").write_text(render_index(arts))
    # sitemap + robots
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    (SITE / "sitemap.xml").write_text(sm)
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    (SITE / ".nojekyll").write_text("")  # GitHub Pages 不跑 jekyll
    print(f"渲染 {n} 篇 + index + sitemap({len(urls)} url) + robots → {SITE}")


if __name__ == "__main__":
    main()

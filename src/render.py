#!/usr/bin/env python3
"""渲染:文章 JSON → 静态 SEO 网页 + index + sitemap + robots。纯代码,无 LLM。
多市场:us(英文,根目录)→ 美国落点;th(泰文,/th/)→ 泰国落点。CTA 真按钮 + UTM 归因。"""
import json, re, glob, html, os
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
SITE = ROOT / "docs"
SITE.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get("SEO_BASE_URL", "https://learn.resetday.health").rstrip("/")

# 每市场的落点(CEO 提供)
DEST = {
    "us": "https://tpatch-lp.pages.dev",   # 美国 = 4 变体同域,按簇路由(见下)
    "th": "https://tpatch.sarahbot.fit",
}
# 美国变体路由 — 按 INTEGRATION.md #4 成交页意图映射:a=/ b=/q c=/shop d=/bold
#   cluster → (变体路径, intent 标签);页面按路径自识变体,订单按 intent 细归因
US_LP_VARIANT = {
    "compare": ("/", "comparison"),                       # a Clinical:理性比较/vs/数据
    "pcos-insulin": ("/q", "pcos"),                       # b Quiz:适不适合/个性化
    "life-after-the-shot": ("/bold", "post_shot"),        # d Bold:无针/简单
    "affordable-alternatives": ("/bold", "cant_afford"),  # d Bold:打不起针
    "midlife-metabolism": ("/bold", "plateau"),           # d Bold:平台期/40+
    "food-noise": ("/bold", "food_noise"),                # d Bold:下午饿/食欲
    "_default": ("/q", "general"),
}
BTN = {"us": "Get T-Patch — the no-needle tirzepatide →", "th": "ดู T-Patch — ทีร์เซพาไทด์แบบไม่ต้องฉีด →"}

CLUSTER_NAMES = {
    "compare": "Compare & Reviews",
    "life-after-the-shot": "Life After the Shot",
    "affordable-alternatives": "Affordable Alternatives",
    "midlife-metabolism": "Midlife Metabolism",
    "pcos-insulin": "PCOS & Insulin",
    "food-noise": "Food Noise & Cravings",
}


def render_table(t):
    if not t or not isinstance(t, dict) or not t.get("rows"):
        return ""
    heads = "".join(f"<th>{esc(str(h))}</th>" for h in t.get("headers", []))
    body = ""
    for row in t.get("rows", []):
        cells = "".join(f"<td>{esc(str(c))}</td>" for c in row)
        body += f"<tr>{cells}</tr>"
    return f'<div class="tablewrap"><table class="cmp"><thead><tr>{heads}</tr></thead><tbody>{body}</tbody></table></div>'
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
.cta{margin:36px 0;padding:24px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:10px}
.cta p{margin:0 0 16px;font-size:18px}
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;padding:13px 22px;border-radius:8px;line-height:1.3}
.btn:hover{filter:brightness(1.08)}
.faq{margin-top:40px}.faq h3{font-size:18px;margin:22px 0 6px}.faq p{color:var(--muted)}
.related{margin-top:44px;padding-top:24px;border-top:1px solid var(--line)}
.related a{display:block;margin:8px 0}
.disclaimer{margin-top:40px;color:var(--muted);font-size:13.5px;line-height:1.6}
footer{border-top:1px solid var(--line);padding:28px 0;color:var(--muted);font-size:14px;background:var(--card)}
.grid{display:grid;gap:10px}.cluster{margin:30px 0}.cluster h2{margin-bottom:8px}
.card{display:block;padding:16px 18px;background:var(--card);border:1px solid var(--line);border-radius:10px;text-decoration:none;color:var(--ink)}
.card:hover{border-color:var(--accent)}.card .t{font-weight:600}.card .m{color:var(--muted);font-size:15px;margin-top:4px}
.langsw{font-size:14px}
.tablewrap{overflow-x:auto;margin:24px 0}
table.cmp{border-collapse:collapse;width:100%;font-size:15px;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
table.cmp th{background:var(--accent);color:#fff;text-align:left;padding:11px 13px;font-weight:600}
table.cmp td{padding:11px 13px;border-top:1px solid var(--line);vertical-align:top}
table.cmp tbody tr:first-child td{font-weight:600;background:oklch(96% 0.03 165)}
"""

def esc(s): return html.escape(s or "", quote=True)
def market_of(d): return (d.get("_market") or "us").strip().lower()  # 防 LLM 返大写'TH'致 KeyError/误路由
def art_url(d):
    slug = d["slug"]
    return f"{BASE}/th/{slug}.html" if market_of(d) == "th" else f"{BASE}/{slug}.html"
def dest_url(d):
    m = market_of(d)
    if m == "th":
        base = DEST["th"]; variant = ""
    else:  # 美国:按簇路由到 4 变体之一 + 带变体标记
        path, intent = US_LP_VARIANT.get(d.get("cluster", ""), US_LP_VARIANT["_default"])
        base = DEST["us"] + path; variant = f"&utm_content={d.get('cluster','')}&intent={intent}"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}utm_source=seo&utm_medium=organic&utm_campaign={d['slug']}{variant}"

HEAD = """<header class="site"><div class="wrap"><a class="brand" href="{home}">Reset<b>Day</b></a><span class="langsw"><a href="{base}/index.html">EN</a> · <a href="{base}/th/index.html">ไทย</a></span></div></header>"""
FOOT = """<footer><div class="wrap">© Reset Day · Health education, not medical advice</div></footer>"""


def load_articles():
    arts, seen = [], {}
    for f in sorted(glob.glob(str(ARTICLES / "*.json"))):
        d = json.load(open(f))
        slug = d.get("slug") or Path(f).stem
        mk = (d.get("_market") or "us").strip().lower()  # 归一化:旧文章可能含大写'TH'
        d["_market"] = mk
        key = (mk, slug)
        if key in seen:
            seen[key] += 1; slug = f"{slug}-{seen[key]}"
        else:
            seen[key] = 1
        d["slug"] = slug
        arts.append(d)
    return arts


def dedupe_titles(arts):
    """防自相残杀:撞标题的页改用更具体的 H1(对比页 H1 通常独特);仍撞则数字兜底。
    LLM 常照抄 prompt 里的标题示例致多页同标题,此为渲染层硬保险(不依赖模型守规矩)。"""
    from collections import Counter
    tc = Counter((a.get("title") or "").strip().lower() for a in arts)
    used = set()
    for a in arts:
        t = (a.get("title") or "").strip()
        if tc[t.lower()] > 1 and (a.get("h1") or "").strip():
            t = a["h1"].strip()           # 用独特的 H1 顶替模板化标题
        base, key, n = t, t.lower(), 2
        while key in used:                # 最终唯一性兜底(保证终止)
            t = f"{base} ({n})"; key = t.lower(); n += 1
        used.add(key); a["title"] = t
    return arts


def build_hreflang(arts):
    """仅对真·翻译对(US 'X' ↔ TH 'X-th')发 hreflang;非对子不发(避免误导 Google)。"""
    by = {(a.get("_market", "us"), a["slug"]): a for a in arts}
    out = {}
    for a in arts:
        if market_of(a) != "us":
            continue
        th = by.get(("th", f"{a['slug']}-th"))
        if not th:
            continue
        us_url, th_url = art_url(a), art_url(th)
        tags = (f'<link rel="alternate" hreflang="en" href="{us_url}">'
                f'<link rel="alternate" hreflang="th" href="{th_url}">'
                f'<link rel="alternate" hreflang="x-default" href="{us_url}">')
        out[("us", a["slug"])] = tags
        out[("th", th["slug"])] = tags
    return out


def render_article(d, siblings, hreflang=""):
    lang = d.get("_lang", "en"); url = art_url(d)
    secs = "".join(f"<h2>{esc(s.get('h2',''))}</h2>{clean(s.get('html',''))}" for s in d.get("sections", []))
    faq = d.get("faq", [])
    faq_label = "คำถามที่พบบ่อย" if lang == "th" else "Frequently asked questions"
    faq_html = ""
    if faq:
        faq_html = f'<div class="faq"><h2>{faq_label}</h2>' + "".join(
            f"<h3>{esc(q.get('q',''))}</h3><p>{clean(q.get('a',''))}</p>" for q in faq) + "</div>"
    rel_label = "อ่านต่อ" if lang == "th" else "Related reading"
    rel = "".join(f'<a href="{art_url(s)}">{esc(s["title"])}</a>' for s in siblings[:3])
    rel_html = f'<div class="related"><strong>{rel_label}</strong>{rel}</div>' if rel else ""
    btn = BTN[market_of(d)]
    ld = {"@context": "https://schema.org", "@type": "MedicalWebPage", "headline": d.get("title", ""),
          "description": d.get("meta_description", ""), "url": url, "inLanguage": lang,
          "author": {"@type": "Organization", "name": "Reset Day Health Education Team"},
          "publisher": {"@type": "Organization", "name": "Reset Day"}}
    faq_ld = ""
    if faq:
        faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": clean(q.get("q", "")),
                "acceptedAnswer": {"@type": "Answer", "text": re.sub('<[^>]+>', '', clean(q.get("a", "")))}} for q in faq]}, ensure_ascii=False)
        faq_ld = f'<script type="application/ld+json">{faq_ld}</script>'
    disc = ("บทความนี้เพื่อการศึกษาทั่วไป ไม่ใช่คำแนะนำทางการแพทย์ T-Patch คือทีร์เซพาไทด์แบบทาผ่านผิวหนัง ปรึกษาแพทย์ก่อนตัดสินใจเรื่องยา"
            if lang == "th" else
            "This article is for general education and is not medical advice. T-Patch is a topical (transdermal) delivery of tirzepatide. Talk to your healthcare provider about decisions involving any medication, including tirzepatide.")
    home = f"{BASE}/th/index.html" if market_of(d) == "th" else f"{BASE}/index.html"
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(d.get('title',''))} | Reset Day</title>
<meta name="description" content="{esc(d.get('meta_description',''))}">
<link rel="canonical" href="{url}">{hreflang}
<meta property="og:type" content="article"><meta property="og:title" content="{esc(d.get('title',''))}">
<meta property="og:description" content="{esc(d.get('meta_description',''))}"><meta property="og:url" content="{url}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>{faq_ld}
<style>{CSS}</style></head><body>
{HEAD.format(base=BASE, home=home)}
<main><div class="wrap">
<p class="eyebrow">{esc(CLUSTER_NAMES.get(d.get('cluster',''),'Weight & Metabolism'))}</p>
<h1>{esc(d.get('h1') or d.get('title',''))}</h1>
{clean(d.get('intro_html',''))}
{render_table(d.get('table'))}
{secs}
{faq_html}
<div class="cta">{clean(d.get('cta_html',''))}<a class="btn" href="{dest_url(d)}">{esc(btn)}</a></div>
{rel_html}
<p class="disclaimer">{disc}</p>
</div></main>
{FOOT}
</body></html>"""


def render_index(arts, lang):
    by = defaultdict(list)
    for a in arts:
        by[a.get("cluster", "food-noise")].append(a)
    blocks = ""
    for ck, name in CLUSTER_NAMES.items():
        items = by.get(ck, [])
        if not items:
            continue
        cards = "".join(f'<a class="card" href="{art_url(a)}"><div class="t">{esc(a["title"])}</div><div class="m">{esc(a.get("meta_description",""))}</div></a>' for a in items)
        blocks += f'<div class="cluster"><h2>{esc(name)}</h2><div class="grid">{cards}</div></div>'
    if lang == "th":
        title = "Reset Day — ลดน้ำหนักแบบไม่ต้องฉีด & ความรู้ GLP-1"
        h1 = "น้ำหนัก เมตาบอลิซึม และ GLP-1 — เข้าใจง่าย"
        intro = "ความรู้ตรงไปตรงมาเรื่องทีร์เซพาไทด์ GLP-1 PCOS และความอยากอาหาร — พร้อม T-Patch ทีร์เซพาไทด์แบบทาไม่ต้องฉีด"
        home = f"{BASE}/th/index.html"; canon = f"{BASE}/th/index.html"
        verify = ""
    else:
        title = "Reset Day — No-Needle Weight Support & GLP-1 Education"
        h1 = "Weight, metabolism & GLP-1 — in plain English"
        intro = "Honest education on tirzepatide, Mounjaro, retatrutide, GLP-1/GIP/GCGR, PCOS and life after the shot — plus T-Patch, the no-needle topical tirzepatide."
        home = f"{BASE}/index.html"; canon = f"{BASE}/index.html"
        verify = ('<meta name="google-site-verification" content="VgeadCjEiRipelYZMsAYt8GdU55mSNC5K9I7tECnaYk">'
                  '<meta name="google-site-verification" content="1YvryP5-kEntEzBtDaiAVKK9-KChZpJokV6zSEEfz7Q">')
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{verify}<title>{esc(title)}</title>
<meta name="description" content="{esc(intro)}">
<link rel="canonical" href="{canon}"><style>{CSS}</style></head><body>
{HEAD.format(base=BASE, home=home)}
<main><div class="wrap">
<p class="eyebrow">Reset Day</p>
<h1>{esc(h1)}</h1>
<p>{esc(intro)}</p>
{blocks}
</div></main>
{FOOT}
</body></html>"""


def main():
    (SITE / "th").mkdir(parents=True, exist_ok=True)
    arts = load_articles()
    dedupe_titles(arts)              # 标题唯一性硬保险(防自相残杀)
    hreflang = build_hreflang(arts)  # 真·翻译对的 hreflang
    us = [a for a in arts if a.get("_market", "us") != "th"]
    th = [a for a in arts if a.get("_market") == "th"]
    by = defaultdict(list)
    for a in arts:
        by[(a.get("_market", "us"), a.get("cluster", "food-noise"))].append(a)
    # 先把所有页面渲染到内存(任一篇抛异常=整体失败,此时还没删任何东西 → 绝不发布半成品/删空站)
    pages, urls = [], []   # pages: (Path, content)
    for a in arts:
        mk = a.get("_market", "us")
        siblings = [s for s in by[(mk, a.get("cluster", "food-noise"))] if s["slug"] != a["slug"]]
        out = (SITE / "th" / f"{a['slug']}.html") if mk == "th" else (SITE / f"{a['slug']}.html")
        pages.append((out, render_article(a, siblings, hreflang.get((mk, a["slug"]), ""))))
        urls.append(art_url(a))
    pages.append((SITE / "index.html", render_index(us, "en"))); urls.append(f"{BASE}/index.html")
    pages.append((SITE / "th" / "index.html", render_index(th, "th"))); urls.append(f"{BASE}/th/index.html")
    # 安全闸:两个 index 必须都渲染出来,否则中止不落盘(防把首页/全站删空)
    paths = {p for p, _ in pages}
    if (SITE / "index.html") not in paths or (SITE / "th" / "index.html") not in paths:
        raise SystemExit("render aborted: missing index pages — 不落盘,防删空站")
    # 全部渲染成功 → 才清旧 html(防孤儿)并落盘(保留 CNAME/.nojekyll/robots/sitemap 等非 html)
    for old in list(SITE.glob("*.html")) + list((SITE / "th").glob("*.html")):
        old.unlink()
    for path, content in pages:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    (SITE / "sitemap.xml").write_text(sm)
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    (SITE / ".nojekyll").write_text("")
    print(f"渲染 us={len(us)} th={len(th)} 篇 + 2 index + sitemap({len(urls)} url) → {SITE}")


if __name__ == "__main__":
    main()

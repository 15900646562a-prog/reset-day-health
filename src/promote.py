#!/usr/bin/env python3
"""promote — 把对比页/文章变成多渠道'导链帖'(脑产文,手发)。
每页 → 一套帖子(TikTok口播钩/Reddit评论/Pinterest Pin/FB群帖/通用caption),
每条带分渠道 UTM 链接,输出 content/promo/*.json + 《待发_导链.md》。
posting 由本地安全会话/Dana 手发(账号墙非代码能解)。
"""
import json, glob, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from seo_build import load_creds, MODEL

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
PROMO = ROOT / "content" / "promo"
PROMO.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get("SEO_BASE_URL", "https://learn.resetday.health").rstrip("/")
MAX_WORKERS = 8

def page_url(d):
    slug = d["slug"]
    return f"{BASE}/th/{slug}.html" if d.get("_market") == "th" else f"{BASE}/{slug}.html"

def tracked(url, channel, slug):
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source={channel}&utm_medium=social&utm_campaign={slug}"

SYSTEM = """You write organic-feeling social promo posts that drive readers to a comparison/education web page about no-needle (topical) tirzepatide weight-loss options vs injection clinics.

RULES:
- Sound like a real person sharing something useful, NOT an ad. No hype, no spam.
- Tie to the page's angle. Honest hook = "no needle / topical vs weekly injections".
- Do NOT claim "same as Mounjaro/equivalent/FDA-approved/cure/guarantee". Educational tone.
- Each post must NOT contain the URL itself (the URL is appended by code); write the post body only, end with a natural "link below / in comments / in bio" style nudge appropriate to the channel.

Return STRICT JSON:
- tiktok_hook: a 15-20s spoken script for a short video (first line = scroll-stopping hook)
- reddit_comment: a genuinely helpful comment to drop in a relevant thread (mentions the comparison naturally, not salesy)
- pinterest: {title (<=80 chars), description (<=200 chars)}
- fb_group_post: a warm post for our own weight-loss support group
- caption: a short generic IG/TikTok caption with 2-3 relevant hashtags
Output ONLY the JSON object."""

def make_pack(client, d):
    slug = d["slug"]
    out = PROMO / f"{slug}.json"
    if out.exists():
        return ("cached", slug)
    title = d.get("title", ""); meta = d.get("meta_description", "")
    lang = d.get("_lang", "en")
    user = f"PAGE: {title}\nWHAT IT'S ABOUT: {meta}\nMARKET: {d.get('_market','us')}"
    if lang == "th":
        user = "WRITE ALL POSTS IN NATURAL THAI (keep brand names/prices as-is).\n\n" + user
    try:
        r = client.chat.completions.create(model=MODEL, response_format={"type": "json_object"},
            temperature=0.7, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
        pack = json.loads(r.choices[0].message.content)
    except Exception as e:
        return ("error", f"{slug}: {e}")
    url = page_url(d)
    pack["_slug"] = slug; pack["_market"] = d.get("_market", "us")
    pack["_links"] = {c: tracked(url, c, slug) for c in ("tiktok", "reddit", "pinterest", "fb", "ig")}
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=2))
    return ("ok", slug)

def main():
    # 默认只为对比页产导链(买家意图最高);传 all 则全部文章
    arts = [json.load(open(f)) for f in sorted(glob.glob(str(ARTICLES / "*.json")))]
    scope = sys.argv[1] if len(sys.argv) > 1 else "compare"
    if scope == "compare":
        arts = [a for a in arts if a.get("cluster") == "compare"]
    client_key, base = load_creds()
    from openai import OpenAI
    client = OpenAI(api_key=client_key, base_url=base)
    print(f"产导链帖: {len(arts)} 页(scope={scope})")
    stats = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(make_pack, client, a) for a in arts]
        for fu in as_completed(futs):
            s, info = fu.result(); stats[s] = stats.get(s, 0) + 1
            if s == "error": print("  [error]", info)
    print("完成:", stats)
    render_waitlist()

def render_waitlist():
    packs = [json.load(open(f)) for f in sorted(glob.glob(str(PROMO / "*.json")))]
    lines = ["# 待发 · 导链帖(对比页)\n",
             "> 脑产文已就绪;手发(Dana 本地浏览器 / Publer)。每条带分渠道 UTM,发后看 GSC/分析能知哪个渠道带量。\n"]
    for p in packs:
        lines.append(f"\n## {p['_slug']}  ({p.get('_market','us')})")
        lines.append(f"- 🔗 落点(对比页): {p['_links']['tiktok'].split('utm_source')[0]}…(各渠道见下)")
        lines.append(f"\n**TikTok 口播钩** → {p['_links']['tiktok']}\n> {p.get('tiktok_hook','')}")
        pin = p.get("pinterest", {})
        lines.append(f"\n**Pinterest** → {p['_links']['pinterest']}\n> **{pin.get('title','')}** — {pin.get('description','')}")
        lines.append(f"\n**FB 群帖** → {p['_links']['fb']}\n> {p.get('fb_group_post','')}")
        lines.append(f"\n**Reddit 评论** → {p['_links']['reddit']}\n> {p.get('reddit_comment','')}")
        lines.append(f"\n**通用 caption** → {p['_links']['ig']}\n> {p.get('caption','')}")
        lines.append("\n---")
    out = Path.home() / "Desktop" / "待发_导链.md"
    out.write_text("\n".join(lines))
    print(f"《待发》→ {out}  ({len(packs)} 页)")

if __name__ == "__main__":
    main()

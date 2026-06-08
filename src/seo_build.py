#!/usr/bin/env python3
"""
SEO Factory — 批量把"现有物资"(fendan 文案 + 口播脚本)变成 SEO 文章页。
流水线: 收集物资 → LLM 写文章(带合规) → 渲染静态页 + sitemap。
隔离: 自成一仓,不碰任何主线代码/分支/资源。可重跑(已生成的跳过)。
"""
import json, os, re, glob, hashlib, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CF = Path.home() / "Desktop" / "creative_factory"
ENV = CF / ".env"
ARTICLES = ROOT / "content" / "articles"
ARTICLES.mkdir(parents=True, exist_ok=True)

MODEL = os.environ.get("SEO_MODEL", "gpt-4o-mini")
BASE_URL = os.environ.get("SEO_BASE_URL", "https://learn.resetday.health")
MAX_WORKERS = 8

CLUSTERS = {
    "life-after-the-shot": "Stopping / maintaining after GLP-1 (Ozempic/Wegovy/Mounjaro)",
    "affordable-alternatives": "Can't afford the shots / cheaper, accessible options",
    "midlife-metabolism": "Weight & metabolism after 40, hormones",
    "pcos-insulin": "PCOS / insulin resistance — biology not willpower",
    "food-noise": "Food noise, cravings, appetite — warm no-judgment",
}

# ---- 合规后置闸(提示性 flag,供人审,不阻断) ----------------------
# 决定 R8(war-room 02_DECISIONS):公开主打外用替尔泊肽 → 放行 tirzepatide/价格/下单。
# 只 flag "纯编造、零 SEO 收益却招删" 的几项(虚假认证/保证/编造数字/神药治愈)。
FLAGS = [
    (re.compile(r"\bFDA[- ]approved\b", re.I), "false-fda-claim"),
    (re.compile(r"\b(cure|cures|miracle)\b", re.I), "cure-claim"),
    (re.compile(r"\bguarantee(d|s)?\b", re.I), "guarantee"),
    (re.compile(r"\b\d{1,3}%\s+(more|stronger|effective|results|of users)\b", re.I), "fabricated-number"),
    (re.compile(r"\b(licensed physician|board[- ]certified|I am a doctor)\b", re.I), "credential-claim"),
]
def compliance_scan(text):
    return [tag for rx, tag in FLAGS if rx.search(text or "")]


def load_creds():
    """优先读 seo_factory 自己的 .env;否则从 creative_factory/.env 取 yunwu key+base。"""
    key = base = None
    for envf in [ROOT / ".env", ENV]:
        if not envf.exists():
            continue
        for line in envf.read_text().splitlines():
            if line.startswith("OPENAI_API_KEY=") and not key:
                key = line.split("=", 1)[1].strip().strip('"')
            if line.startswith(("OPENAI_API_BASE=", "OPENAI_BASE_URL=")) and not base:
                base = line.split("=", 1)[1].strip().strip('"')
        if key:
            break
    if not key:
        raise SystemExit("no OPENAI_API_KEY")
    return key, (base or "https://yunwu.ai/v1")  # 默认走 yunwu 代理


# ---- 收集物资 ------------------------------------------------------
def collect_items():
    items = []
    # 1) fendan copyclone 文案(全部)
    for f in sorted(glob.glob(str(CF / "output/copyclone/*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        stem = Path(f).stem
        summary = (d.get("analysis") or {}).get("summary", "")
        for c in d.get("copies", []):
            txt = c.get("text", "")
            if len(txt) < 80:
                continue
            items.append({
                "id": f"fendan_{stem}_{c.get('index', 0)}",
                "persona": d.get("product", "tpatch"),
                "angle": c.get("angle", ""),
                "source_text": (summary + "\n\n" + txt).strip(),
            })
    # 2) overnight 口播脚本(配音待审.md 全部)
    md = Path.home() / "Desktop" / "配音待审.md"
    if md.exists():
        blocks = re.split(r"\n##\s+\d+\.", md.read_text())
        for b in blocks:
            mp = re.search(r"^\s*(\w+)\s*·", b)
            ms = re.search(r"脚本:\s*(.+)", b)
            if not ms:
                continue
            script = ms.group(1).strip()
            if len(script) < 80:
                continue
            persona = mp.group(1) if mp else "marcus"
            h = hashlib.sha1(script.encode()).hexdigest()[:8]
            items.append({
                "id": f"talk_{persona}_{h}",
                "persona": persona,
                "angle": "",
                "source_text": script,
            })
    return items


# ---- LLM 写文章 ----------------------------------------------------
SYSTEM = """You are a health-content writer for "Reset Day", a brand that offers T-Patch, an over-the-counter, no-needle topical weight-support patch.

Write a genuinely useful, original SEO article based on the SOURCE material. Target people searching Google about weight loss, GLP-1 medications, metabolism, PCOS, cravings.

VOICE / GROUNDING RULES:
- Voice = a knowledgeable health educator. Use "research suggests", "studies indicate". Do not claim to personally be a licensed physician.
- Keep claims grounded in fact: do NOT fabricate efficacy percentages or result numbers, do NOT claim "FDA-approved", no "guaranteed" or "miracle cure" language. These are lies that get pages taken down with zero SEO benefit.
- Include a brief "talk to your healthcare provider" line.

PRODUCT — T-Patch (this is the whole point of the article):
- T-Patch is the world's FIRST topical (transdermal, no-needle) tirzepatide patch. Tirzepatide is the same active molecule found in GLP-1 medications like Mounjaro and Zepbound — T-Patch delivers it through the skin instead of by injection.
- You MUST name tirzepatide and position T-Patch as the no-needle way to access it. This is our core differentiator — lean into it.
- Even if the SOURCE never mentions a product, bridge the article's topic to T-Patch in TWO places:
  1) A dedicated body section that connects the science to T-Patch — e.g. "the same tirzepatide people inject, now in a topical no-needle patch."
  2) The cta_html — drive the reader to learn more / get T-Patch and join the Reset Day community.
- The bridge must feel earned by the content, not bolted on. Confident, not hypey.

Pick the single best CLUSTER for this topic from this list (return its key):
%s

Return STRICT JSON with keys:
- slug: short url-safe kebab-case (no stopwords spam), specific to the search intent
- title: compelling SEO title (<=65 chars), front-loads the search intent
- meta_description: <=155 chars, makes someone click
- cluster: one cluster key from the list
- h1: the on-page headline
- intro_html: 1-2 opening paragraphs (HTML <p>), hook the reader's problem
- sections: array of 3-5 {h2, html} — html is 1-3 <p>/<ul> of real, specific, useful content
- faq: array of 3-4 {q, a} — real questions people search, plain helpful answers
- cta_html: one short <p> softly pointing to the Reset Day community + T-Patch as a no-needle option
Output ONLY the JSON object.""" % "\n".join(f"- {k}: {v}" for k, v in CLUSTERS.items())


def write_article(client, item):
    out = ARTICLES / f"{item['id']}.json"
    if out.exists():
        return ("cached", item["id"])
    try:
        r = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            temperature=0.6,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"SOURCE (angle hint: {item.get('angle','')}):\n\n{item['source_text']}"},
            ],
        )
        art = json.loads(r.choices[0].message.content)
    except Exception as e:
        return ("error", f"{item['id']}: {e}")

    # 合规后置闸:扫全文,flag 记录(不静默放行)
    full = " ".join([art.get("title", ""), art.get("meta_description", ""), art.get("intro_html", ""),
                      " ".join(s.get("html", "") for s in art.get("sections", [])),
                      " ".join(f.get("a", "") for f in art.get("faq", [])), art.get("cta_html", "")])
    flags = compliance_scan(full)
    art["_compliance_flags"] = flags
    art["_source_id"] = item["id"]
    art["_persona"] = item.get("persona", "")
    if art.get("cluster") not in CLUSTERS:
        art["cluster"] = "food-noise"
    # slug 去重/规范
    art["slug"] = re.sub(r"[^a-z0-9-]", "", (art.get("slug", item["id"]).lower().replace(" ", "-")))[:80] or item["id"]
    out.write_text(json.dumps(art, ensure_ascii=False, indent=2))
    return ("flagged" if flags else "ok", item["id"])


def main():
    from openai import OpenAI
    key, base = load_creds()
    client = OpenAI(api_key=key, base_url=base)
    items = collect_items()
    print(f"收集物资: {len(items)} 份 → 写文章(model={MODEL}, base={base}, 并发{MAX_WORKERS})")
    stats = {"ok": 0, "flagged": 0, "cached": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(write_article, client, it) for it in items]
        for fu in as_completed(futs):
            status, info = fu.result()
            stats[status] = stats.get(status, 0) + 1
            if status in ("error", "flagged"):
                print(f"  [{status}] {info}")
    print(f"\n完成: {stats}")
    print(f"文章 JSON → {ARTICLES}")


if __name__ == "__main__":
    main()

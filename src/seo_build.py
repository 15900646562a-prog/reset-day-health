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
    items += seed_items()
    return items


# ---- 种子选题(长尾词驱动:覆盖 Mounjaro/Retatrutide/GLP-1/GIP/GCGR + 泰文) ----
SEEDS_US = [
    "Is there a tirzepatide patch? Topical no-needle tirzepatide explained",
    "Mounjaro without injections — is a needle-free option possible?",
    "Tirzepatide vs semaglutide (Mounjaro vs Ozempic) for weight loss",
    "What is retatrutide? The triple agonist (GLP-1 + GIP + GCGR) explained",
    "Retatrutide vs tirzepatide: how the triple agonist differs",
    "GLP-1 vs GIP vs GCGR: what each receptor does for weight loss",
    "How does tirzepatide work? GLP-1 and GIP dual agonism, simply",
    "Zepbound alternatives: no-needle ways to access tirzepatide",
    "GCGR (glucagon receptor) agonists and fat metabolism, explained",
    "How to get tirzepatide without weekly injections",
    "Tirzepatide side effects from injections vs a topical patch",
    "Wegovy or Mounjaro stalled? Why and what to try next",
]
# (泰文 query, 英文 slug) —— slug 必须英文,否则 URL 垃圾
SEEDS_TH = [
    ("ทีร์เซพาไทด์ (Tirzepatide) คืออะไร และทำงานอย่างไร", "tirzepatide-explained-th"),
    ("Mounjaro แบบไม่ต้องฉีด มีไหม? แผ่นแปะทีร์เซพาไทด์", "mounjaro-no-needle-th"),
    ("แผ่นแปะลดน้ำหนักทีร์เซพาไทด์ ดีกว่าการฉีดอย่างไร", "tirzepatide-patch-th"),
    ("Retatrutide คืออะไร — ตัวกระตุ้นสามตัว GLP-1 GIP GCGR", "retatrutide-explained-th"),
    ("GLP-1 กับ GIP กับ GCGR ต่างกันอย่างไรในการลดน้ำหนัก", "glp1-gip-gcgr-th"),
    ("ลดน้ำหนักโดยไม่ต้องฉีดยา — ทางเลือกแบบทาผ่านผิวหนัง", "weight-loss-no-injection-th"),
    ("Mounjaro กับ Ozempic ต่างกันอย่างไร เลือกแบบไหนดี", "mounjaro-vs-ozempic-th"),
    ("ทีร์เซพาไทด์ ผลข้างเคียง และวิธีใช้แบบไม่ต้องฉีด", "tirzepatide-side-effects-th"),
    ("หยุดยาลดน้ำหนักแล้วน้ำหนักกลับมา ทำอย่างไรดี", "weight-regain-after-stopping-th"),
    ("PCOS ดื้ออินซูลิน ลดน้ำหนักยาก — ทีร์เซพาไทด์ช่วยได้ไหม", "pcos-insulin-resistance-th"),
]


def seed_items():
    out = []
    for i, q in enumerate(SEEDS_US):
        out.append({"id": f"seed_us_{i:02d}", "persona": "tpatch", "angle": q,
                    "source_text": f"Write a search-optimised article answering this query: {q}",
                    "market": "us", "lang": "en"})
    for i, (q, slug) in enumerate(SEEDS_TH):
        out.append({"id": f"seed_th_{i:02d}", "persona": "tpatch", "angle": q,
                    "source_text": f"เขียนบทความ SEO ตอบคำค้นหานี้: {q}",
                    "market": "th", "lang": "th", "slug_hint": slug})
    # 对比/评测页(compare 模式)
    for i, (q, slug) in enumerate(SEEDS_COMPARE_US):
        out.append({"id": f"cmp_us_{i:02d}", "persona": "tpatch", "angle": q, "mode": "compare",
                    "source_text": f"Write a comparison article for this query: {q}",
                    "market": "us", "lang": "en", "slug_hint": slug})
    for i, (q, slug) in enumerate(SEEDS_COMPARE_TH):
        out.append({"id": f"cmp_th_{i:02d}", "persona": "tpatch", "angle": q, "mode": "compare",
                    "source_text": f"เขียนบทความเปรียบเทียบสำหรับคำค้นหานี้: {q}",
                    "market": "th", "lang": "th", "slug_hint": slug})
    # 外部追加种子(ideate 自动构思的新长尾词 → 常态化产新内容)
    extra = ROOT / "content" / "seeds_extra.json"
    if extra.exists():
        try:
            for s in json.load(open(extra)):
                slug = s.get("slug")
                if not slug:
                    continue
                cmp = s.get("mode") == "compare"
                q = s.get("query", "")
                out.append({"id": slug, "persona": "tpatch", "angle": q,
                            "source_text": (f"Write a comparison article for this query: {q}" if cmp
                                            else f"Write a search-optimised article for this query: {q}"),
                            "market": s.get("market", "us"), "lang": s.get("lang", "en"),
                            "slug_hint": slug, **({"mode": "compare"} if cmp else {})})
        except Exception:
            pass
    return out


# ---- LLM 写文章 ----------------------------------------------------
SYSTEM = """You are a health-content writer for "Reset Day", a brand that offers T-Patch, an over-the-counter, no-needle topical weight-support patch.

Write a genuinely useful, original SEO article based on the SOURCE material. Target people searching Google about weight loss, GLP-1 medications, metabolism, PCOS, cravings.

VOICE / GROUNDING RULES:
- Voice = a knowledgeable health educator. Use "research suggests", "studies indicate". Do not claim to personally be a licensed physician.
- Keep claims grounded in fact: do NOT fabricate efficacy percentages or result numbers, do NOT claim "FDA-approved", no "guaranteed" or "miracle cure" language. These are lies that get pages taken down with zero SEO benefit.
- 🔴 NEVER mention "prescription" / "no prescription" / "prescription-free" / "without a prescription". It is off-message and dilutes the professional positioning. Describe T-Patch simply as a no-needle topical patch you order online.
- Include a brief "talk to your healthcare provider" line.

PRODUCT — T-Patch (FINAL口径 R14 — IS tirzepatide; never say "plant-based"):
- T-Patch is a NO-NEEDLE, once-weekly transdermal patch that delivers TIRZEPATIDE (a GLP-1 + GIP receptor agonist) through the skin — the needle-free way to get tirzepatide instead of weekly injections. One fresh patch every 7 days.
- Access: order online with a quick telehealth consultation; COD delivery; price $149 / $399 / $699 (1/3/6 months). Do NOT say "no prescription / over-the-counter"; frame access as an online telehealth process.
- 🔴 Still avoid these exact high-risk phrases (active FDA enforcement): do NOT say T-Patch is "the same as" / "equivalent to" Mounjaro/Zepbound/Wegovy; do NOT claim "FDA-approved"; no "cure"/"miracle"/"guaranteed"; and do NOT invent efficacy percentages or result numbers (omit numbers unless real study data is supplied).
- Bridge to T-Patch in TWO places:
  1) A body section: connect the topic to "the no-needle way to get tirzepatide — a once-weekly patch instead of injections."
  2) cta_html — invite the reader to start online / get T-Patch. Confident, factual, not hypey.

KEYWORDS — use the real names people search, prominently:
- Mounjaro, Zepbound, Ozempic, Wegovy, tirzepatide, retatrutide, semaglutide; GLP-1, GIP, GCGR.
- Position T-Patch as the no-needle, transdermal tirzepatide patch.

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


# ---- 对比/评测页(compare 模式)----------------------------------
TPATCH_PRICING = "$149 / month · $399 / 3 months · $699 / 6 months"
COMPETITOR_FACTS = """ACCURATE COMPETITOR FACTS (use ONLY these; never invent prices/claims; label prices "approx" and add "check each provider's site for current pricing"):
- T-Patch (Reset Day): NO-NEEDLE, once-weekly transdermal TIRZEPATIDE patch (GLP-1+GIP), delivered through the skin. Price: %s. How to get = "Order online (quick telehealth consult), COD delivery". In the table "Active" column, T-Patch = "Tirzepatide (transdermal)".
- Medvi: injection + oral tablet. Compounded semaglutide/tirzepatide. Approx semaglutide $179→$299/mo, tirzepatide $279→$399/mo. How to get = "Online telehealth consult, monthly subscription".
- Hims: injection. Compounded semaglutide/tirzepatide. Approx semaglutide $149–199/mo, tirzepatide $199–299/mo. How to get = "Online telehealth, subscription". (Context: referred to DOJ Feb 2026; sued by Novo Nordisk.)
- Henry Meds: injection. Compounded semaglutide ~$297/mo. How to get = "Online telehealth, subscription".
- Ro: injection. Semaglutide. How to get = "Online telehealth, subscription".""" % TPATCH_PRICING

COMPARE_SYSTEM = """You are a health-content writer for "Reset Day", maker of T-Patch — a NO-NEEDLE, once-weekly transdermal TIRZEPATIDE patch (GLP-1+GIP), accessed online via a telehealth consult.

Write an honest, useful COMPARISON / "best of" article for people weighing a no-needle weight-management option against the GLP-1 injection route. These are high-intent buyers.

%s

HARD RULES:
- Be factually fair to competitors (accurate, not trash-talk). Inaccurate competitor facts = legal risk.
- T-Patch's differentiator = the NO-NEEDLE, once-weekly way to get TIRZEPATIDE (vs weekly injections); lower cost; simple. Position it for people who want tirzepatide without the needles. In the table "Active" column, T-Patch = "Tirzepatide (transdermal)". You MAY say T-Patch delivers tirzepatide transdermally.
- Comparison frame = "the no-needle transdermal tirzepatide patch vs the injection route" (delivery / cost / convenience).
- For "How to get": T-Patch = "Order online (telehealth consult), COD"; competitors = "Online telehealth, subscription". Do NOT claim "no prescription" / "over-the-counter".
- 🔴 Still avoid these exact phrases (active FDA enforcement): do NOT say "the same as"/"equivalent to" Mounjaro/Zepbound/Wegovy, no "FDA-approved", no fabricated efficacy percentages.
- No fabricated efficacy numbers, no guarantees, no "cure". Include a "talk to your healthcare provider" line.
- Prices labelled "approx"; add "check each provider's official site for current pricing".

Return STRICT JSON:
- slug: ascii kebab-case (will be overridden by a hint if provided)
- title: SEO title (<=65 chars), front-loads the query (e.g. "Best No-Needle Tirzepatide 2026")
- meta_description: <=155 chars
- cluster: "compare"
- h1
- intro_html: 1-2 <p> framing the choice the reader faces
- table: {headers: ["Option","Form","Active","Price (approx)","How to get"], rows: [[...5 cells...], ...]} — include T-Patch + 2-4 real competitors from the facts above; T-Patch row first
- sections: array of 3-4 {h2, html} — a short fair take on each main option, then a "Who should pick what" verdict that points needle-averse / convenience buyers to T-Patch
- faq: array of 3-4 {q,a}
- cta_html: short <p> pointing to T-Patch / Reset Day
Output ONLY the JSON object.""" % COMPETITOR_FACTS

SEEDS_COMPARE_US = [
    ("Best no-needle tirzepatide options 2026", "best-no-needle-tirzepatide"),
    ("How to get tirzepatide without injections", "tirzepatide-without-injections"),
    ("T-Patch vs Medvi: needle-free patch vs injections", "tpatch-vs-medvi"),
    ("T-Patch vs Hims for tirzepatide weight loss", "tpatch-vs-hims"),
    ("T-Patch vs Henry Meds: which is right for you", "tpatch-vs-henry-meds"),
    ("Injections vs a topical tirzepatide patch", "injections-vs-topical-tirzepatide"),
    ("Mounjaro alternatives without needles 2026", "mounjaro-alternatives-no-needle"),
    ("Ozempic alternatives without injections", "ozempic-alternatives-no-needle"),
    ("Cheapest way to get tirzepatide in 2026", "cheapest-tirzepatide"),
    ("Best GLP-1 weight loss options compared", "best-glp1-options-compared"),
    ("Alternatives to weekly weight-loss shots", "alternatives-to-weight-loss-shots"),
    ("Compounded tirzepatide vs a topical patch", "compounded-vs-topical-tirzepatide"),
]
SEEDS_COMPARE_TH = [
    ("ทีร์เซพาไทด์แบบไม่ต้องฉีด ตัวเลือกไหนดี 2026", "best-no-needle-tirzepatide-th"),
    ("วิธีได้ทีร์เซพาไทด์โดยไม่ต้องฉีด", "tirzepatide-no-injection-th"),
    ("แผ่นแปะ กับ การฉีด ทีร์เซพาไทด์ แบบไหนดีกว่า", "patch-vs-injection-th"),
    ("ทางเลือกแทน Mounjaro แบบไม่ต้องฉีด", "mounjaro-alternatives-th"),
    ("ทีร์เซพาไทด์ ราคาถูกที่สุด ซื้อที่ไหนดี", "cheapest-tirzepatide-th"),
    ("เปรียบเทียบตัวเลือกลดน้ำหนัก GLP-1 2026", "glp1-options-compared-th"),
]


def write_article(client, item):
    out = ARTICLES / f"{item['id']}.json"
    if out.exists():
        return ("cached", item["id"])
    lang = item.get("lang", "en")
    mode = item.get("mode", "article")
    system = COMPARE_SYSTEM if mode == "compare" else SYSTEM
    user = f"SOURCE (angle hint: {item.get('angle','')}):\n\n{item['source_text']}"
    if lang == "th":
        user = ("WRITE THE ENTIRE ARTICLE IN NATURAL THAI for Thai readers searching Google in Thai. "
                "Keep the 'slug' field in ascii english (kebab-case). Table headers/cells and all prose in Thai. "
                "Keep brand names (T-Patch, Medvi, Hims, Mounjaro) and prices as-is.\n\n" + user)
    try:
        r = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            temperature=0.6,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
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
    art["_market"] = (item.get("market") or "us").strip().lower()
    art["_lang"] = (item.get("lang") or "en").strip().lower()
    if mode == "compare":
        art["cluster"] = "compare"
    elif art.get("cluster") not in CLUSTERS:
        art["cluster"] = "food-noise"
    # slug 规范:slug_hint 与模型 slug 都强制 ascii-kebab;清完太弱则回退 id
    hint = re.sub(r"[^a-z0-9-]", "", (item.get("slug_hint", "") or "").lower().replace(" ", "-")).strip("-")
    slug = re.sub(r"[^a-z0-9-]", "", (art.get("slug", "") or "").lower().replace(" ", "-")).strip("-")[:80]
    art["slug"] = (hint if len(hint) >= 3 else (slug if len(slug) >= 3 else re.sub(r"[^a-z0-9_]", "", item["id"])))
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

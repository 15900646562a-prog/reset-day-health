#!/usr/bin/env python3
"""ideate — 自动构思新长尾选题(常态化产新内容的源头)。
读已有页的 slug/角度 → LLM 提 N 个未覆盖的新长尾词(US+TH, 含对比型)→ 去重 → 追加 content/seeds_extra.json。
run_cycle 第 0 步调它,之后 seo_build 就会产这些新页。
"""
import json, glob, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from seo_build import load_creds, MODEL

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
EXTRA = ROOT / "content" / "seeds_extra.json"
N = int(os.environ.get("IDEATE_N", "6"))

PROMPT = """You plan SEO topics for "Reset Day" / T-Patch — a no-needle, topical TIRZEPATIDE weight-loss patch. Two markets: US (English) and Thailand (Thai).

Propose %d NEW long-tail search topics people actually type into Google, that we have NOT covered yet. Mix:
- buyer-intent comparison topics (best / vs competitors Medvi/Hims/Henry / alternatives / cheapest) -> mode "compare"
- educational topics (tirzepatide / Mounjaro / Zepbound / GLP-1 / GIP / GCGR / PCOS / cravings / life after the shot) -> mode "article"
- include some Thai-language ones (lang "th")

Avoid these already-covered slugs/topics:
%s

Rules: differentiate on no-needle/topical. NEVER mention "prescription". No "equivalent to Mounjaro".

Return STRICT JSON: {"seeds":[{"query": "...", "slug": "ascii-kebab-unique", "market": "us|th", "lang": "en|th", "mode": "article|compare"}, ...]}
For Thai, query in Thai but slug stays ascii english with a -th suffix. Output ONLY the JSON object."""


def existing():
    slugs, angles = set(), []
    for f in glob.glob(str(ARTICLES / "*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get("slug"):
            slugs.add(d["slug"])
        if d.get("title"):
            angles.append(d["title"])
    if EXTRA.exists():
        for s in json.load(open(EXTRA)):
            slugs.add(s.get("slug", ""))
    return slugs, angles


def main():
    slugs, angles = existing()
    from openai import OpenAI
    k, b = load_creds()
    client = OpenAI(api_key=k, base_url=b)
    sample = "\n".join(f"- {a}" for a in angles[:60])
    r = client.chat.completions.create(model=MODEL, response_format={"type": "json_object"},
        temperature=0.9, messages=[{"role": "user", "content": PROMPT % (N, sample)}])
    import re
    seeds = json.loads(r.choices[0].message.content).get("seeds", [])
    def ok_slug(sl):  # 退化 slug(无实义,如 th-th)跳过
        core = sl.replace("-th", "").replace("-us", "").replace("-", "")
        return len(core) >= 4
    cleaned = []
    for s in seeds:
        sl = re.sub(r"[^a-z0-9-]", "", (s.get("slug", "")).lower().replace(" ", "-")).strip("-")
        if s.get("lang") == "th" and sl and not sl.endswith("-th"):
            sl += "-th"
        s["slug"] = sl
        if ok_slug(sl):
            cleaned.append(s)
    fresh = [s for s in cleaned if s["slug"] not in slugs]
    cur = json.load(open(EXTRA)) if EXTRA.exists() else []
    cur_slugs = {s.get("slug") for s in cur}
    added = [s for s in fresh if s["slug"] not in cur_slugs]
    cur.extend(added)
    EXTRA.write_text(json.dumps(cur, ensure_ascii=False, indent=2))
    print(f"ideate: 新增 {len(added)} 个种子 → seeds_extra.json(累计 {len(cur)})")
    for s in added:
        print(f"  + [{s.get('market')}/{s.get('mode')}] {s.get('slug')}")


if __name__ == "__main__":
    main()

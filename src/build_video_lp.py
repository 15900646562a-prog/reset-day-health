#!/usr/bin/env python3
"""视频承接页(video catch page):接住镜像视频(医生口播·外用/无针 T-Patch)看完后的流量。
落点 docs/v/(US)+ docs/th/v/(TH)。复用 render.py 的设计系统;布局=落地页(非博客)。
职责:承接视频心理(这真的吗/怎么搞)→ 强化 外用+无针+tirzepatide+T-Patch → 导 /bold 成交页。
视频来源 UTM(utm_source=video&utm_content=<人设/视频id>)经页内脚本一路透传到成交页 → 哪条视频带单可追。
合规 R14:不出现 植物配方/等同Mounjaro/FDA-approved/无需处方/编造疗效%/cure。访问=远程问诊开方+COD。"""
import os
from pathlib import Path
from render import CSS, HEAD, FOOT, BASE, SITE, esc, DEST

# 成交页:视频流量=被人格化无针钩子打动=偏情绪暖流 → /bold(US);TH 单一落点
DEST_US = DEST["us"] + "/bold"
DEST_TH = DEST["th"]
PRICES = [("1 month", "$149"), ("3 months", "$399"), ("6 months", "$699")]
PRICES_TH = [("1 เดือน", "$149"), ("3 เดือน", "$399"), ("6 เดือน", "$699")]

# 落地页专属样式(叠加在 render.CSS 之上)
LP_CSS = """
.hero{padding:56px 0 8px}
.hero .eyebrow{color:var(--accent);font-weight:700;font-size:12.5px;text-transform:uppercase;letter-spacing:.1em;margin:0 0 14px}
.hero h1{font-size:clamp(34px,6vw,58px);line-height:1.05;letter-spacing:-.03em;margin:0 0 18px}
.hero .lede{font-size:clamp(18px,2.4vw,22px);color:var(--muted);max-width:30ch;margin:0 0 28px}
.videoslot{margin:8px 0 36px;aspect-ratio:9/16;max-width:300px;background:linear-gradient(160deg,#0e7c66,#0a5c4c);border-radius:18px;display:flex;align-items:center;justify-content:center;color:#fff;text-align:center;padding:24px;box-shadow:0 18px 50px -20px rgba(14,124,102,.6)}
.videoslot span{font-size:15px;opacity:.92;line-height:1.5}
.ctarow{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:6px 0 8px}
.btn-lg{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;font-size:18px;padding:16px 30px;border-radius:10px;line-height:1.2;box-shadow:0 10px 26px -10px rgba(14,124,102,.7);transition:transform .15s,filter .15s}
.btn-lg:hover{transform:translateY(-2px);filter:brightness(1.06)}
.subcta{font-size:14.5px;color:var(--muted)}.subcta a{font-weight:600}
.band{background:var(--card);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:40px 0;padding:34px 0}
.feat{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:22px}
.feat .it{}.feat .n{color:var(--accent);font-weight:800;font-size:13px;letter-spacing:.04em;margin:0 0 6px}
.feat .it h3{font-size:18px;margin:0 0 6px;letter-spacing:-.01em}.feat .it p{color:var(--muted);font-size:15.5px;margin:0}
.steps{counter-reset:s;display:grid;gap:14px;margin:18px 0}
.steps li{list-style:none;display:flex;gap:14px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.steps li::before{counter-increment:s;content:counter(s);flex:0 0 30px;height:30px;background:var(--accent);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px}
.steps b{display:block;margin-bottom:2px}.steps span{color:var(--muted);font-size:15px}
.price{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}
.price .c{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 14px;text-align:center}
.price .c.best{border-color:var(--accent);border-width:2px;position:relative}
.price .c.best::after{content:"Best value";position:absolute;top:-11px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;white-space:nowrap}
.price .term{color:var(--muted);font-size:14px;margin-bottom:4px}.price .amt{font-size:26px;font-weight:800;letter-spacing:-.02em}
@media(max-width:520px){.price{grid-template-columns:1fr;}.price .c.best::after{content:"Best value · 6mo"}}
.faq-lp{margin:36px 0}.faq-lp h3{font-size:17px;margin:20px 0 4px}.faq-lp p{color:var(--muted);margin:0}
.finalcta{text-align:center;padding:44px 0}
"""

# 视频→CTA 的 UTM 透传(把来访 utm_source/content/campaign 等接到成交页链接,做"哪条视频带单"归因)
FORWARD_JS = """(function(){var p=new URLSearchParams(location.search);document.querySelectorAll('a[data-cta]').forEach(function(a){var u=new URL(a.href);['utm_source','utm_medium','utm_campaign','utm_content','intent','vid','persona'].forEach(function(k){if(p.get(k))u.searchParams.set(k,p.get(k))});a.href=u.toString()})})();"""


def page(lang, dest, prices, c):
    home = f"{BASE}/th/index.html" if lang == "th" else f"{BASE}/index.html"
    base_cta = f"{dest}{'&' if '?' in dest else '?'}utm_source=video&utm_medium=video&utm_campaign=video_catch&intent=video"
    feats = "".join(
        f'<div class="it"><p class="n">{esc(n)}</p><h3>{esc(h)}</h3><p>{esc(b)}</p></div>'
        for n, h, b in c["feats"])
    steps = "".join(f'<li><div><b>{esc(b)}</b><span>{esc(s)}</span></div></li>' for b, s in c["steps"])
    price = "".join(
        f'<div class="c{" best" if i == len(prices) - 1 else ""}"><div class="term">{esc(t)}</div><div class="amt">{esc(a)}</div></div>'
        for i, (t, a) in enumerate(prices))
    faqs = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in c["faq"])
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(c['title'])}</title>
<meta name="description" content="{esc(c['desc'])}">
<link rel="canonical" href="{BASE}{c['path']}">
<meta name="robots" content="noindex,follow">
<meta property="og:title" content="{esc(c['title'])}"><meta property="og:description" content="{esc(c['desc'])}">
<style>{CSS}{LP_CSS}</style></head><body>
{HEAD.format(base=BASE, home=home)}
<main><div class="wrap">
<section class="hero">
  <p class="eyebrow">{esc(c['eyebrow'])}</p>
  <h1>{esc(c['h1'])}</h1>
  <p class="lede">{esc(c['lede'])}</p>
  <div class="videoslot"><span>{esc(c['videoslot'])}</span></div>
  <div class="ctarow"><a class="btn-lg" data-cta href="{base_cta}">{esc(c['cta'])}</a></div>
  <p class="subcta">{c['subcta']}</p>
</section>
</div>
<div class="band"><div class="wrap">
  <div class="feat">{feats}</div>
</div></div>
<div class="wrap">
<h2>{esc(c['how_h'])}</h2>
<ol class="steps">{steps}</ol>
<h2>{esc(c['price_h'])}</h2>
<div class="price">{price}</div>
<p class="subcta" style="margin-top:10px">{esc(c['price_note'])}</p>
<div class="faq-lp"><h2>{esc(c['faq_h'])}</h2>{faqs}</div>
<section class="finalcta">
  <h2 style="margin:0 0 18px">{esc(c['final_h'])}</h2>
  <a class="btn-lg" data-cta href="{base_cta}">{esc(c['cta'])}</a>
</section>
<p class="disclaimer">{esc(c['disclaimer'])}</p>
</div></main>
{FOOT}
<script>{FORWARD_JS}</script>
</body></html>"""


US = {
    "path": "/v/", "eyebrow": "As seen in the video",
    "title": "T-Patch — Tirzepatide Without the Needle | Reset Day",
    "desc": "You saw it in the video: tirzepatide, applied to your skin instead of injected. See how the no-needle T-Patch works and how to get started.",
    "h1": "Tirzepatide — without the needle.",
    "lede": "T-Patch is a no-needle, once-weekly transdermal patch that delivers tirzepatide (a GLP-1 + GIP agonist).",
    "videoslot": "▶ The approach from the video — a weekly patch you apply to skin, not a weekly injection.",
    "cta": "See if T-Patch is for you →",
    "subcta": 'Prefer to check your fit first? <a data-cta href="' + BASE + '/index.html">Read the no-needle guides</a>',
    "feats": [
        ("No needles", "Apply, don't inject", "A patch you place on your skin once a week — no syringes, no weekly jab."),
        ("Tirzepatide", "GLP-1 + GIP", "The same dual-agonist active people are talking about, delivered transdermally."),
        ("Online + COD", "No clinic visit", "Start with a quick telehealth consult; if appropriate, it ships to you — pay on delivery."),
    ],
    "how_h": "How to get started",
    "steps": [
        ("Quick online consult", "Share your health profile through a short telehealth questionnaire."),
        ("A licensed clinician reviews", "If T-Patch is appropriate for you, they authorise it — a prescription is required."),
        ("Ships to your door — pay on delivery", "Your once-weekly patches arrive; you pay when they reach you (COD)."),
    ],
    "price_h": "Simple pricing",
    "price_note": "Pricing shown is approximate; confirm current pricing at checkout.",
    "faq_h": "Quick questions",
    "faq": [
        ("Is a tirzepatide patch real?", "T-Patch is a topical (transdermal) delivery of tirzepatide designed to be applied to the skin once a week instead of injected."),
        ("How is it different from the weekly shot?", "Same kind of active (tirzepatide, a GLP-1 + GIP agonist), but applied to skin rather than injected — built for people who would rather skip needles."),
        ("Do I need a prescription?", "Yes. A licensed clinician reviews your profile through a quick online consult and authorises it if it's appropriate for you."),
        ("How do I pay?", "Cash on delivery (COD) — you pay when your patches arrive."),
    ],
    "final_h": "Ready to skip the needle?",
    "disclaimer": "This page is for general education and is not medical advice. T-Patch is a topical (transdermal) delivery of tirzepatide. Talk to your healthcare provider about decisions involving any medication, including tirzepatide.",
}

TH = {
    "path": "/th/v/", "eyebrow": "ตามที่เห็นในวิดีโอ",
    "title": "T-Patch — ทีร์เซพาไทด์แบบไม่ต้องฉีด | Reset Day",
    "desc": "อย่างที่เห็นในวิดีโอ: ทีร์เซพาไทด์แบบแปะผิวหนัง ไม่ต้องฉีด ดูว่า T-Patch แบบไม่ใช้เข็มทำงานอย่างไรและเริ่มต้นอย่างไร",
    "h1": "ทีร์เซพาไทด์ — แบบไม่ต้องฉีด",
    "lede": "T-Patch คือแผ่นแปะผิวหนังสัปดาห์ละครั้ง ไม่ต้องใช้เข็ม ส่งทีร์เซพาไทด์ (GLP-1 + GIP) ผ่านผิวหนัง",
    "videoslot": "▶ แนวทางจากในวิดีโอ — แผ่นแปะสัปดาห์ละครั้งที่แปะบนผิว ไม่ใช่ฉีดทุกสัปดาห์",
    "cta": "ดูว่า T-Patch เหมาะกับคุณไหม →",
    "subcta": 'อยากอ่านก่อน? <a data-cta href="' + BASE + '/th/index.html">อ่านคู่มือแบบไม่ใช้เข็ม</a>',
    "feats": [
        ("ไม่ต้องใช้เข็ม", "แปะ ไม่ต้องฉีด", "แผ่นแปะบนผิวหนังสัปดาห์ละครั้ง — ไม่มีเข็ม ไม่ต้องฉีดทุกสัปดาห์"),
        ("ทีร์เซพาไทด์", "GLP-1 + GIP", "สารออกฤทธิ์แบบ dual-agonist ที่กำลังเป็นที่พูดถึง ส่งผ่านผิวหนัง"),
        ("ออนไลน์ + เก็บเงินปลายทาง", "ไม่ต้องไปคลินิก", "เริ่มด้วยการปรึกษาแพทย์ออนไลน์ หากเหมาะสมจะจัดส่งให้ — จ่ายเมื่อได้รับสินค้า"),
    ],
    "how_h": "เริ่มต้นอย่างไร",
    "steps": [
        ("ปรึกษาออนไลน์สั้นๆ", "กรอกข้อมูลสุขภาพผ่านแบบสอบถามเทเลเฮลท์สั้นๆ"),
        ("แพทย์ที่มีใบอนุญาตตรวจสอบ", "หาก T-Patch เหมาะกับคุณ แพทย์จะอนุมัติ — ต้องมีใบสั่งแพทย์"),
        ("จัดส่งถึงบ้าน — เก็บเงินปลายทาง", "แผ่นแปะสัปดาห์ละครั้งส่งถึงคุณ จ่ายเมื่อได้รับ (COD)"),
    ],
    "price_h": "ราคาเข้าใจง่าย",
    "price_note": "ราคาที่แสดงเป็นราคาโดยประมาณ ตรวจสอบราคาปัจจุบันตอนสั่งซื้อ",
    "faq_h": "คำถามที่พบบ่อย",
    "faq": [
        ("แผ่นแปะทีร์เซพาไทด์มีจริงไหม", "T-Patch คือทีร์เซพาไทด์แบบทาผ่านผิวหนัง ออกแบบให้แปะบนผิวสัปดาห์ละครั้งแทนการฉีด"),
        ("ต่างจากการฉีดรายสัปดาห์อย่างไร", "สารออกฤทธิ์แบบเดียวกัน (ทีร์เซพาไทด์ GLP-1 + GIP) แต่แปะบนผิวแทนการฉีด — สำหรับคนที่อยากเลี่ยงเข็ม"),
        ("ต้องมีใบสั่งแพทย์ไหม", "ต้องมี แพทย์ที่มีใบอนุญาตจะตรวจสอบข้อมูลของคุณผ่านการปรึกษาออนไลน์สั้นๆ และอนุมัติหากเหมาะสม"),
        ("ชำระเงินอย่างไร", "เก็บเงินปลายทาง (COD) — จ่ายเมื่อแผ่นแปะส่งถึงคุณ"),
    ],
    "final_h": "พร้อมเลิกใช้เข็มหรือยัง",
    "disclaimer": "หน้านี้เพื่อการศึกษาทั่วไป ไม่ใช่คำแนะนำทางการแพทย์ T-Patch คือทีร์เซพาไทด์แบบทาผ่านผิวหนัง ปรึกษาแพทย์ก่อนตัดสินใจเรื่องยา",
}


def main():
    (SITE / "v").mkdir(parents=True, exist_ok=True)
    (SITE / "th" / "v").mkdir(parents=True, exist_ok=True)
    (SITE / "v" / "index.html").write_text(page("en", DEST_US, PRICES, US))
    (SITE / "th" / "v" / "index.html").write_text(page("th", DEST_TH, PRICES_TH, TH))
    print(f"视频承接页 → {BASE}/v/ + {BASE}/th/v/")


if __name__ == "__main__":
    main()

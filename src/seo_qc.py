#!/usr/bin/env python3
"""seo_qc — 自动质检闸(代码化 COO 手动 QC)。生产后跑;不过的页打回。
退出码: 0=全过, 1=有 FAIL(供 run_cycle 据此打回重生)。
检查: 处方话题 / 等同性·FDA·cure·guarantee / 薄页 / 对比页 T-Patch 排第一 / 对比页有竞品价格。
"""
import json, glob, re, sys
from pathlib import Path

ARTICLES = Path(__file__).resolve().parent.parent / "content" / "articles"

# R14:tirzepatide 为准 → 不再拦 tirzepatide。只拦"无处方/OTC"假声明(产品是 Rx-via-telehealth)
PRESC = re.compile(r"\bno prescription\b|prescription-free|without (a |any )?prescription|over-the-counter|\bOTC\b", re.I)
# 编造疗效数字(无真实研究前不许放百分比)
EFFICACY = re.compile(r"\b\d{1,3}(\.\d)?\s*%\s*(of )?(weight|body|fat|loss|reduction|patients|users|people)", re.I)
# R14:产品=tirzepatide,绝不讲"植物配方/botanical"(贴错标)
BOTANICAL = re.compile(r"plant-based|botanical|plant extract|plant fiber|green tea extract|sea kelp|植物", re.I)
# 等同性/cure/miracle = 硬伤(渲染不会兜)。guarantee/FDA-approved 渲染会中性化,故先套同样中性化再判(与上线文本一致)。
EQUIV = re.compile(r"same as (mounjaro|wegovy|zepbound|ozempic)|equivalent to (mounjaro|wegovy|zepbound|ozempic)|\bcure[ds]?\b|\bmiracle\b", re.I)
NEUTRALIZE = [(re.compile(r"\bguarantee(d|s)?\b", re.I), " "), (re.compile(r"\bFDA[- ]approved\b", re.I), " ")]
def as_published(t):
    for rx, rep in NEUTRALIZE:
        t = rx.sub(rep, t)
    return t

def full_text(d):
    return ". ".join([  # 字段块间断句,避免跨字段(表格↔正文)邻近误报
        str(d.get("title", "")), str(d.get("meta_description", "")), str(d.get("intro_html", "")),
        " ".join(s.get("html", "") for s in d.get("sections", [])),
        ". ".join(" ".join(map(str, r)) for r in d.get("table", {}).get("rows", [])),  # 行间断句,避免跨行邻近误报
        " ".join(q.get("a", "") for q in d.get("faq", [])),
        str(d.get("cta_html", "")),
    ])

def check(d):
    fails = []
    t = full_text(d)
    if PRESC.search(t):
        fails.append("无处方/OTC假声明(违R14)")
    if EQUIV.search(as_published(t)):
        fails.append("等同性/cure/miracle")
    if EFFICACY.search(t):
        fails.append("编造疗效%(需真实研究)")
    if BOTANICAL.search(t):
        fails.append("植物配方/botanical(违R14,产品=tirzepatide)")
    secs = len(d.get("sections", []))
    if secs < 3:
        fails.append(f"薄页(段落{secs})")
    if d.get("cluster") == "compare":
        rows = d.get("table", {}).get("rows", [])
        if len(rows) < 2:
            fails.append("对比表行<2")
        elif "t-patch" not in str(rows[0][0]).lower():
            fails.append("T-Patch未排第一")
        # 至少一竞品行带价($/月 等)
        if not any(re.search(r"\$|/mo|/month", " ".join(map(str, r))) for r in rows[1:]):
            fails.append("缺竞品价格")
    return fails

def main():
    arts = {Path(f).name: json.load(open(f)) for f in sorted(glob.glob(str(ARTICLES / "*.json")))}
    failed = {}
    for name, d in arts.items():
        f = check(d)
        if f:
            failed[name] = f
    print(f"seo_qc: 共 {len(arts)} 页 | FAIL {len(failed)}")
    for name, f in failed.items():
        print(f"  ✗ {name}: {', '.join(f)}")
    if failed:
        # 供 run_cycle 读取要重生的文件
        Path("/tmp/seo_qc_failed.txt").write_text("\n".join(str(ARTICLES / n) for n in failed))
        sys.exit(1)
    print("✅ 全过")
    sys.exit(0)

if __name__ == "__main__":
    main()

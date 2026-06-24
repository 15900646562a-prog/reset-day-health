#!/usr/bin/env bash
# SEO 每日自动验收(确定性脚本版)——必留痕迹,不依赖 LLM 记得每步。
# 机械步骤全在这:拉仓→ESCALATION→QC→禁词spot→页数→末次自动发→判阶段→记war-room→刷PROJECTS→push。
# 调度的 SKILL 只需跑本脚本 + 读结尾 SEO_ACCEPT_RESULT 行,有 P0 才提醒 CEO。
# 用法:bash accept.sh        真跑(写 war-room + push)
#       bash accept.sh --dry  只检查打印,不写 war-room
set -uo pipefail
SEO="/Users/edy/Desktop/seo_factory"
WAR="/Users/edy/tpatch-coo-ops"
DRY=0; [ "${1:-}" = "--dry" ] && DRY=1
DATE=$(date -u +%F)

cd "$SEO" || { echo "SEO_ACCEPT_RESULT | ERROR cd seo_factory"; exit 1; }
git pull --ff-only -q 2>/dev/null || true

# 1) ESCALATION 是否有内容
ESC="无"
[ -f ESCALATION.md ] && [ -s ESCALATION.md ] && ESC="有(见末条)"

# 2) seo_qc FAIL 数(从完整输出抓,"FAIL N" 不在最后一行)
QCOUT=$(python3 src/seo_qc.py 2>&1)
QCFAIL=$(printf '%s' "$QCOUT" | grep -oE 'FAIL [0-9]+' | grep -oE '[0-9]+' | head -1)
QCFAIL=${QCFAIL:-?}

# 3) 页数
PAGES=$(ls docs/*.html docs/th/*.html 2>/dev/null | wc -l | tr -d ' ')

# 4) R14 禁词 spot-check(最新 3 篇文章 JSON)
BANNED=$(python3 - <<'PY'
import json, glob, os, re
fs = sorted(glob.glob("content/articles/*.json"), key=os.path.getmtime, reverse=True)[:3]
hard = re.compile(r"plant-based|botanical|植物|no prescription|over-the-counter|same as (mounjaro|zepbound|wegovy)|\bcure\b|\bguarantee\b", re.I)
efficacy = re.compile(r"\b\d{1,3}(\.\d)?\s*%\s*(of )?(weight|body|fat|loss|reduction|patients|users|people)", re.I)
trial_attrib = re.compile(r"trial|stud(y|ies)|clinical|lilly|research|phase\s*[0-9]|triumph", re.I)

def bad(text):
    if hard.search(text):
        return True
    for m in efficacy.finditer(text):
        if not trial_attrib.search(text[max(0, m.start() - 90):m.end() + 30]):
            return True
    return False

hits = sum(1 for f in fs if bad(json.dumps(json.load(open(f)), ensure_ascii=False)))
print(hits)
PY
)
BANNED=${BANNED:-?}

# 5) 末次自动发布
LASTPUB=$([ -f AUTOPUBLISH_LOG.md ] && tail -1 AUTOPUBLISH_LOG.md | tr -d '#' | xargs || echo "无记录")

# 6) 阶段(无 GSC → P1 收录)
PHASE="P1 收录(等爬;效果维度待 GSC)"

# 7) P0 判定
P0=""
[ "$QCFAIL" != "0" ] && P0="${P0}QC_FAIL=$QCFAIL "
[ "$BANNED" != "0" ] && P0="${P0}禁词命中=$BANNED "
[ "$ESC" != "无" ] && P0="${P0}ESCALATION有 "
STATUS_TXT="正常"; [ -n "$P0" ] && STATUS_TXT="🔴P0:$P0"

SUMMARY="SEO每日自动验收(${DATE}·脚本):阶段=${PHASE} | ${STATUS_TXT} | QC FAIL=${QCFAIL} · 禁词spot=${BANNED} · ESCALATION=${ESC} · 页数=${PAGES} · 末次自动发=${LASTPUB}"

if [ "$DRY" = "1" ]; then
  echo "[DRY] $SUMMARY"
else
  # 8) 记 war-room JOURNAL + 9) 刷 PROJECTS 阶段行 + push
  cd "$WAR" || { echo "SEO_ACCEPT_RESULT | ERROR cd war-room | P0=${P0:-无}"; exit 1; }
  git pull --no-rebase --no-edit -q 2>/dev/null || true
  ./log.sh "$SUMMARY" >/dev/null 2>&1 || true
  python3 - "$DATE" "$PAGES" "$QCFAIL" "$STATUS_TXT" <<'PY' || true
import sys, re
date, pages, qcfail, st = sys.argv[1:5]
p = "PROJECTS.md"; s = open(p, encoding="utf-8").read()
mark = "正常" if "正常" in st else "🔴异常"
line = f"- **📊 当前阶段**:**P1 收录(第1-2周)· 自治在跑** · {date}自动验收:{pages}页·QC FAIL{qcfail}·{mark} | 计划/验收 = `seo_factory/SEO_PLAN.md`(每日脚本自动刷新本行)。"
s2 = re.sub(r"- \*\*📊 当前阶段\*\*:.*", line, s, count=1)
open(p, "w", encoding="utf-8").write(s2)
PY
  git add -A && git commit -q -m "seo-accept: 每日自动验收 ${DATE}" >/dev/null 2>&1 || true
  git push -q 2>/dev/null || true
fi

# 给调度 LLM 会话的结构化结果(它据此判断要不要提醒 CEO)
echo "SEO_ACCEPT_RESULT | 阶段=${PHASE} | QC_FAIL=${QCFAIL} | BANNED=${BANNED} | ESCALATION=${ESC} | PAGES=${PAGES} | P0=${P0:-无}"

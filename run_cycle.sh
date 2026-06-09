#!/usr/bin/env bash
# run_cycle — 全自动一轮:构思→产→质检闸→(过则)自动发布上线。VPS cron 无人值守跑。
# 规则见 AUTONOMY_RULES.md。**质检闸 seo_qc 是唯一发布门**:过=自动上线;不过=不发、丢弃坏批、写 ESCALATION 等 COO。
set -uo pipefail
cd "$(dirname "$0")"
export SEO_BASE_URL="${SEO_BASE_URL:-https://learn.resetday.health}"
MAX_PAGES="${SEO_MAX_PAGES:-300}"     # 总页数封顶,防失控
LOG="cycle_$(date -u +%Y%m%d_%H%M).log"

git checkout -q main 2>/dev/null || true
git pull -q --ff-only 2>/dev/null || true

# 总量封顶:到顶就不再 ideate 产新页(防失控)
CUR=$(ls docs/*.html docs/th/*.html 2>/dev/null | wc -l | tr -d ' ')
if [ "${CUR:-0}" -lt "$MAX_PAGES" ]; then
  echo "== [0] GSC + ideate 构思新选题 ==" | tee -a "$LOG"
  python3 src/gsc_fetch.py 2>&1 | tee -a "$LOG" || true
  python3 src/ideate.py 2>&1 | tee -a "$LOG" || echo "ideate 跳过" | tee -a "$LOG"
else
  echo "已达页数上限 $MAX_PAGES,跳过 ideate(只维护,不新增)" | tee -a "$LOG"
fi

echo "== [1] 生产 ==" | tee -a "$LOG"
python3 src/seo_build.py 2>&1 | tee -a "$LOG"

echo "== [2] 质检闸(唯一发布门,≤2轮打回重生) ==" | tee -a "$LOG"
for r in 1 2; do
  if python3 src/seo_qc.py 2>&1 | tee -a "$LOG"; then break; fi
  [ -f /tmp/seo_qc_failed.txt ] && xargs rm -f < /tmp/seo_qc_failed.txt
  python3 src/seo_build.py 2>&1 | tee -a "$LOG"
done

# 终判:仍不过 → 不发布,丢弃坏批,升级 COO(只推 ESCALATION,不推坏内容)
if ! python3 src/seo_qc.py >/tmp/qc.out 2>&1; then
  echo "❌ QC 未过 → 不发布,升级 COO" | tee -a "$LOG"
  git checkout -q -- content docs 2>/dev/null || true
  git clean -fdq content docs 2>/dev/null || true
  { echo "## $(date -u '+%F %H:%M UTC') · QC 未过,本轮未发布(等 COO)"; grep '✗' /tmp/qc.out | head; echo; } >> ESCALATION.md
  git add ESCALATION.md && git commit -q -m "escalate: QC 未过 $(date -u +%F-%H%M)" && git push -q 2>&1 | tee -a "$LOG" || true
  exit 1
fi

echo "== [3] 渲染 ==" | tee -a "$LOG"
# pipefail 已开:render 崩(非0)即进 if 分支 → 回滚 docs、不发布、升级 COO(绝不推半成品)
if ! python3 src/render.py 2>&1 | tee -a "$LOG"; then
  echo "❌ 渲染失败 → 不发布,回滚 docs,升级 COO" | tee -a "$LOG"
  git checkout -q -- docs 2>/dev/null || true
  git clean -fdq docs 2>/dev/null || true
  { echo "## $(date -u '+%F %H:%M UTC') · 渲染失败,本轮未发布(等 COO)"; } >> ESCALATION.md
  git add ESCALATION.md && git commit -q -m "escalate: render 失败 $(date -u +%F-%H%M)" && git push -q 2>&1 | tee -a "$LOG" || true
  exit 1
fi

echo "== [4] 自动发布(过闸=上线) ==" | tee -a "$LOG"
git add -A
if git commit -q -m "auto: 产+过闸发布 $(date -u +%F-%H%M)"; then
  if git push -q 2>&1 | tee -a "$LOG"; then
    echo "✅ 已自动上线" | tee -a "$LOG"
    python3 src/distribute_indexnow.py submit 2>&1 | tee -a "$LOG" || true
    { echo "## $(date -u '+%F %H:%M UTC') · 自动发布 | 页数 $(ls docs/*.html docs/th/*.html 2>/dev/null|wc -l|tr -d ' ') | commit $(git rev-parse --short HEAD)"; } >> AUTOPUBLISH_LOG.md
    git add AUTOPUBLISH_LOG.md && git commit -q -m "log: autopublish" && git push -q 2>&1 >/dev/null || true
  else
    echo "⚠️ push 失败(deploy key 没加?)——内容已本地 commit,等修复" | tee -a "$LOG"
  fi
else
  echo "本轮无新内容" | tee -a "$LOG"
fi

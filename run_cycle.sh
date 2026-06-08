#!/usr/bin/env bash
# run_cycle — 常态化生产一轮:生产 → 自动质检闸(不过则打回重生,最多2轮)→ 渲染 → 推 pending-review 分支(待 COO 验收)。
# 不直接上 main(=不直接上线);COO 验收后 merge pending-review→main 才发布。
set -uo pipefail
cd "$(dirname "$0")"
export SEO_BASE_URL="${SEO_BASE_URL:-https://learn.resetday.health}"
LOG="cycle_$(date -u +%Y%m%d_%H%M).log"

# 在 pending-review 分支上干活(不碰本地 main,不推 GitHub)
git fetch -q origin main 2>/dev/null || true
git rev-parse --verify -q pending-review >/dev/null || git branch pending-review
git checkout -q pending-review

echo "== [0a] 拉 GSC 效果数据(Phase2;无凭据则优雅跳过) ==" | tee -a "$LOG"
python3 src/gsc_fetch.py 2>&1 | tee -a "$LOG" || true

echo "== [0/4] 构思新长尾选题(有 GSC 数据则追赢家词) ==" | tee -a "$LOG"
python3 src/ideate.py 2>&1 | tee -a "$LOG" || echo "ideate 失败,继续用现有种子" | tee -a "$LOG"

echo "== [1/4] 生产 ==" | tee -a "$LOG"
python3 src/seo_build.py 2>&1 | tee -a "$LOG"

echo "== [2/4] 自动质检闸(最多2轮打回重生) ==" | tee -a "$LOG"
for round in 1 2; do
  if python3 src/seo_qc.py 2>&1 | tee -a "$LOG"; then break; fi
  echo "-- QC 第 $round 轮有 FAIL,删不合格页重生 --" | tee -a "$LOG"
  [ -f /tmp/seo_qc_failed.txt ] && xargs rm -f < /tmp/seo_qc_failed.txt
  python3 src/seo_build.py 2>&1 | tee -a "$LOG"
done
# 终判:仍不过则停,不推(等人工)
if ! python3 src/seo_qc.py >/dev/null 2>&1; then
  echo "❌ QC 仍未全过,本轮不推,等 COO 处理" | tee -a "$LOG"; exit 1
fi

echo "== [3/4] 渲染 ==" | tee -a "$LOG"
python3 src/render.py 2>&1 | tee -a "$LOG"

echo "== [4/4] 提交到本地 pending-review(不推 GitHub;COO 验收时才发布) ==" | tee -a "$LOG"
git add -A
if git commit -q -m "cycle: 自动生产一轮(过 seo_qc)$(date -u +%F)"; then
  # 待验收报告(COO 来读)
  {
    echo "# 待验收 · SEO 自动生产 ($(date -u '+%F %H:%M UTC'))"
    echo "- 已过 seo_qc 自动闸。本地 commit: $(git rev-parse --short HEAD)"
    echo "- 页数: $(ls docs/*.html docs/th/*.html 2>/dev/null | wc -l)"
    echo "- COO 验收: 本地 \`git fetch ssh://tiktok-core/root/seo_factory pending-review\` → 抽检+考评 → push origin main 发布。"
  } > 待验收_报告.md
  echo "✅ 本轮进本地 pending-review(未推)。等 COO 验收发布。" | tee -a "$LOG"
else
  echo "本轮无改动,跳过。" | tee -a "$LOG"
fi

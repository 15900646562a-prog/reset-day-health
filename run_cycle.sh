#!/usr/bin/env bash
# run_cycle — 常态化生产一轮:生产 → 自动质检闸(不过则打回重生,最多2轮)→ 渲染 → 推 pending-review 分支(待 COO 验收)。
# 不直接上 main(=不直接上线);COO 验收后 merge pending-review→main 才发布。
set -uo pipefail
cd "$(dirname "$0")"
export SEO_BASE_URL="${SEO_BASE_URL:-https://learn.resetday.health}"
LOG="cycle_$(date -u +%Y%m%d_%H%M).log"

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

echo "== [4/4] 推 pending-review 分支(待 COO 验收,不直接上线) ==" | tee -a "$LOG"
git add -A
git commit -q -m "cycle: 自动生产一轮(过 seo_qc)$(date -u +%F)" || { echo "无改动"; exit 0; }
git push -q origin HEAD:pending-review 2>&1 | tee -a "$LOG"
echo "✅ 本轮已进 pending-review。COO 验收+考评后 merge→main 才发布。" | tee -a "$LOG"

# SEO Factory 自治规则(一次性写死;VPS 无人值守跑,COO 只周期验收)

> 🔴 **纯 cron + 脚本进程,不依赖任何 VPS agent(西西/openclaw)。** VPS 上 `crontab` 定时直接跑 `run_cycle.sh`(bash→python 脚本链),全程无 agent 介入。COO 验收由 **Mac 端定时任务**(scheduled-task `seo-autonomy-acceptance`)做,也不经 VPS agent。
> 前提:COO 不能持续触达 VPS(一天有效沟通 ≤2 次)。所以规则必须自包含、脱离 COO 也能跑。
> **质检闸 `seo_qc` = 唯一发布门。** 过=自动上线;不过=不发、丢坏批、写 ESCALATION 等 COO。

## 1. 口径(锁死,R14)
- 产品 = **透皮 tirzepatide(GLP-1+GIP),无针,一周一次,远程问诊开方 + COD,$149/$399/$699**。
- 🔴 永不出现:`植物配方/botanical`、`等同/same as Mounjaro/Zepbound/Wegovy`、`FDA-approved`、`no prescription/OTC`、编造疗效百分比、`cure/miracle/guarantee`。
- 以上全部由 `src/seo_qc.py` 硬拦(违则该页打回重生;修不好则整轮不发布)。

## 2. 发布判据(自动,无人工)
- 一轮:`ideate构思 → seo_build产 → seo_qc闸(≤2轮打回重生) → render → 过则 git push 自动上线 + IndexNow`。
- **闸不过 = 绝不发布**:丢弃坏批,把失败项写进 `ESCALATION.md` 并 push(COO 下次 pull 看得到),整轮退出。

## 3. 产量上限(防失控/防烧钱)
- 每轮 ideate 新增 ≤ `IDEATE_N`(默认 6)。
- 全站总页数封顶 `SEO_MAX_PAGES`(默认 300):到顶只维护、不再新增。
- LLM = yunwu 代理 gpt-4o-mini(便宜);无付费造图/视频环节。

## 4. 节奏
- VPS cron:每周一 03:00 UTC 一轮(`crontab` + `flock` 防重入)。改频率只改 crontab。

## 5. 异常升级(不指望实时通知 COO)
- QC 连续修不好、push 失败、或任何崩 → 写 `ESCALATION.md`(带时间+原因)并 push。
- COO 每次验收先看 `ESCALATION.md`,有则先处理。

## 6. COO 周期验收(1–2 次/天足够,不逐批)
每次"醒来":
1. `git -C ~/Desktop/seo_factory pull` → 看 `ESCALATION.md`(有无升级)+ `AUTOPUBLISH_LOG.md`(本周自动发了什么)。
2. 抽审 2–3 个新页:口径 R14 对不对、读着像不像真人、竞品事实准不准。
3. 接 GSC 后:看效果(曝光/点击/询单)→ 调 `ideate` 方向 / `SEO_MAX_PAGES` / 口径。
4. 要改规则:改本仓 `src/*` 或本文件 → push → VPS 下轮 cron 自动生效(无需 COO 连 VPS)。

## 7. 凭据/部署(一次性,CEO 做)
- VPS 自动发布 = `~/.ssh/seo_deploy` 部署密钥(写权限),CEO 一次性加到 GitHub 仓 Deploy keys。
- VPS git:`fetch=https(公开读)`,`push=ssh(用 deploy key 发)`。
- 加完后系统全自治;COO 只按 §6 周期来收。

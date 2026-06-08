#!/usr/bin/env python3
"""gsc_fetch — Phase 2:拉 Google Search Console 效果数据(每词/每页 曝光·点击)。
输出 content/gsc_data.json + 人读摘要 content/gsc_summary.md,供 ideate 追赢家词 + 考评填效果维度。
优雅降级:无凭据/无数据/缺库 都不报错(写空结构,exit 0),不阻断 run_cycle。
凭据:服务账号 JSON,路径 = env GSC_CREDS_JSON 或 content/gsc_creds.json(已 gitignore)。
"""
import json, os, sys
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "content" / "gsc_data.json"
SUMMARY = ROOT / "content" / "gsc_summary.md"
SITE = os.environ.get("SEO_BASE_URL", "https://learn.resetday.health").rstrip("/") + "/"
CREDS = os.environ.get("GSC_CREDS_JSON", str(ROOT / "content" / "gsc_creds.json"))
DAYS = int(os.environ.get("GSC_DAYS", "28"))


def write_empty(note):
    OUT.write_text(json.dumps({"generated_at": None, "site": SITE, "note": note,
                               "top_queries": [], "top_pages": []}, ensure_ascii=False, indent=2))
    SUMMARY.write_text(f"# GSC 效果数据\n\n> {note}\n")
    print(f"gsc_fetch: {note}（已写空结构,不阻断）")


def main():
    if not Path(CREDS).exists():
        return write_empty("无凭据(content/gsc_creds.json 不存在)— 等 CEO 建服务账号")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception:
        return write_empty("缺库 google-api-python-client/google-auth — pip3 install 后再跑")
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDS, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        # 用真实日期(普通 python,非 workflow 沙箱,datetime 可用)
        end = date.today() - timedelta(days=2)   # GSC 有 ~2 天延迟
        start = end - timedelta(days=DAYS)
        def q(dims):
            return svc.searchanalytics().query(siteUrl=SITE, body={
                "startDate": start.isoformat(), "endDate": end.isoformat(),
                "dimensions": dims, "rowLimit": 100}).execute().get("rows", [])
        def rows(raw, key):
            return [{key: r["keys"][0], "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
                     "ctr": round(r.get("ctr", 0), 4), "position": round(r.get("position", 0), 1)} for r in raw]
        top_queries = rows(q(["query"]), "query")
        top_pages = rows(q(["page"]), "page")
    except Exception as e:
        return write_empty(f"GSC API 调用失败: {str(e)[:140]}")

    top_queries.sort(key=lambda x: x["impressions"], reverse=True)
    top_pages.sort(key=lambda x: x["impressions"], reverse=True)
    data = {"generated_at": date.today().isoformat(), "site": SITE,
            "window_days": DAYS, "top_queries": top_queries[:100], "top_pages": top_pages[:100]}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    tot_imp = sum(x["impressions"] for x in top_queries)
    tot_clk = sum(x["clicks"] for x in top_queries)
    lines = [f"# GSC 效果数据（近{DAYS}天，{SITE}）", "",
             f"- 总曝光 **{tot_imp}** ｜ 总点击 **{tot_clk}** ｜ 词数 {len(top_queries)} ｜ 页数 {len(top_pages)}", "",
             "## Top 15 词（按曝光）", "| 词 | 曝光 | 点击 | CTR | 排名 |", "|---|---|---|---|---|"]
    for x in top_queries[:15]:
        lines.append(f"| {x['query']} | {x['impressions']} | {x['clicks']} | {x['ctr']} | {x['position']} |")
    lines += ["", "## Top 10 页（按曝光）", "| 页 | 曝光 | 点击 |", "|---|---|---|"]
    for x in top_pages[:10]:
        lines.append(f"| {x['page'].split('/')[-1]} | {x['impressions']} | {x['clicks']} |")
    SUMMARY.write_text("\n".join(lines))
    print(f"gsc_fetch: {len(top_queries)} 词 / {len(top_pages)} 页 | 曝光 {tot_imp} 点击 {tot_clk} → gsc_data.json + gsc_summary.md")


if __name__ == "__main__":
    main()

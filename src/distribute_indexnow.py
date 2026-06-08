#!/usr/bin/env python3
"""外发(自动收录):IndexNow 推送全部 URL 给 Bing/Yandex/Naver 等。
用法:
  python3 src/distribute_indexnow.py prepare   # 生成 key + 写验证文件(随后 git push 让它 live)
  python3 src/distribute_indexnow.py submit     # key 文件 live 后,推送所有 URL 求收录
Google 不用 IndexNow(走 GSC sitemap),见 README。
"""
import os, sys, re, json, glob, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BASE = os.environ.get("SEO_BASE_URL", "https://15900646562a-prog.github.io/reset-day-health").rstrip("/")
HOST = re.sub(r"^https?://", "", BASE).split("/")[0]
KEYFILE = DOCS / "indexnow_key.txt"          # 我们自己记 key 的地方
ENDPOINT = "https://api.indexnow.org/IndexNow"


def get_or_make_key():
    if KEYFILE.exists():
        return KEYFILE.read_text().strip()
    key = os.urandom(16).hex()               # 32 hex chars(IndexNow 要 8–128 hex)
    KEYFILE.write_text(key)
    (DOCS / f"{key}.txt").write_text(key)     # 搜索引擎来核验所有权的文件
    return key


def sitemap_urls():
    sm = (DOCS / "sitemap.xml").read_text()
    return re.findall(r"<loc>([^<]+)</loc>", sm)


def prepare():
    key = get_or_make_key()
    print(f"key = {key}")
    print(f"验证文件 = {DOCS / (key + '.txt')}")
    print(f"keyLocation(live 后) = {BASE}/{key}.txt")
    print("→ 现在 git add docs && commit && push,等 Pages live 再 submit")


def submit():
    key = get_or_make_key()
    urls = sitemap_urls()
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": f"{BASE}/{key}.txt",
        "urlList": urls,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(ENDPOINT, data=data,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"IndexNow HTTP {r.getcode()} — 提交 {len(urls)} 个 URL(host={HOST})")
            print("200/202 = 已受理。Bing/Yandex 会陆续来抓。")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"ERR: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    {"prepare": prepare, "submit": submit}.get(cmd, prepare)()

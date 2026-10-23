#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推完仓库后刷新 jsDelivr 缓存。

背景：jsDelivr 对 @main 分支有 12 小时的分支解析缓存（s-maxage=43200）。
推完不刷新，客户端拿到的还是旧 commit 的文件——实测踩过一次：
ad-full 在 CDN 上停了两个 commit，导致 ad-exclude 白名单剔除完全没生效。

用法（push 之后立刻跑）：
    python curated/tools/purge.py

只读本地 curated/ 目录列出文件，不修改任何东西。
"""
import os
import sys
import time
import urllib.request
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CUR = os.path.join(ROOT, "curated")
REPO = "tuohai57/egern-mirror"
API = "https://purge.jsdelivr.net/gh/%s@main/" % REPO


def targets():
    out = []
    for dp, _, fs in os.walk(CUR):
        for f in fs:
            if f.endswith((".yaml", ".yml", ".json", ".md", ".txt", ".py", ".module")):
                rel = os.path.relpath(os.path.join(dp, f), ROOT).replace("\\", "/")
                out.append(rel)
    return sorted(out)


def purge(rel):
    url = API + urllib.parse.quote(rel, safe="/")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status
    except Exception as e:
        return "ERR:%s" % e


def main():
    files = targets()
    print("待刷新 %d 个文件" % len(files))
    ok = 0
    for f in files:
        st = purge(f)
        if st == 200:
            ok += 1
        else:
            print("  ✗ %-46s %s" % (f, st))
        time.sleep(0.15)
    print("成功 %d / %d" % (ok, len(files)))
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())

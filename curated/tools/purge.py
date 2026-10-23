#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推完仓库后刷新 jsDelivr 缓存，并逐文件校验线上字节与本地一致。

背景（都是实测踩过的坑）：
  1. jsDelivr 对 @main 分支别名有 12h 缓存（s-maxage=43200）。推完不刷新，
     客户端拿到的还是旧 commit 的文件。曾出现 ad-full 停两个 commit、
     ad-exclude 白名单剔除完全没生效的情况。
  2. purge 接口有频率限制。连续快速调用会返回 "throttled": true，
     此时 purge 是假的——文件不会更新。所以本脚本串行 + 间隔 0.6s + 重试。
  3. 只对 @main 加 ?v= 无效（别名解析不认 query）。
  4. 钉 commit SHA 也无效：仓库 131 MB 超过 jsDelivr 50 MB 打包上限。
  5. 8 MB 的 ad-full 最容易卡住，所以它用日期文件名（ad-full-YYYYMMDD.yaml），
     换名字 = 换 URL，必然取到新内容。

用法（push 之后立刻跑）：
    python curated/tools/purge.py            # 只刷新
    python curated/tools/purge.py --verify   # 刷新 + 逐文件比对字节
"""
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CUR = os.path.join(ROOT, "curated")
REPO = "tuohai57/egern-mirror"
PURGE = "https://purge.jsdelivr.net/gh/%s@main/" % REPO
CDN = "https://cdn.jsdelivr.net/gh/%s@main/" % REPO


def targets():
    out = []
    for dp, _, fs in os.walk(CUR):
        for f in fs:
            if f.endswith((".yaml", ".yml", ".json", ".md", ".txt", ".py", ".module")):
                out.append(os.path.relpath(os.path.join(dp, f), ROOT).replace("\\", "/"))
    return sorted(out)


def purge(rel, retry=3):
    url = PURGE + urllib.parse.quote(rel, safe="/")
    for i in range(retry):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                body = r.read().decode("utf-8", "ignore")
            if '"throttled": true' in body:
                time.sleep(2.5 * (i + 1))
                continue
            return True
        except Exception:
            time.sleep(1.5 * (i + 1))
    return False


def live_size(rel):
    """jsDelivr 对压缩响应不给 content-length，只能读 body 量长度。"""
    url = CDN + urllib.parse.quote(rel, safe="/")
    try:
        with urllib.request.urlopen(url, timeout=90) as r:
            return len(r.read())
    except Exception:
        return -1


def main():
    verify = "--verify" in sys.argv
    files = targets()
    print("待刷新 %d 个文件" % len(files))
    ok = 0
    for f in files:
        if purge(f):
            ok += 1
        else:
            print("  ✗ purge 失败（可能被限流，等几分钟重跑）: %s" % f)
        time.sleep(0.6)
    print("刷新成功 %d / %d" % (ok, len(files)))

    if not verify:
        return 0 if ok == len(files) else 1

    print("\n逐文件比对（线上 vs 本地）：")
    bad = []
    for f in files:
        rel = f[len("curated/"):] if f.startswith("curated/") else f
        local = os.path.getsize(os.path.join(ROOT, f))
        remote = live_size(f)
        mark = "✓" if remote == local else "✗"
        print("  %s %-42s 本地 %-9d 线上 %-9d" % (mark, rel, local, remote))
        if remote != local:
            bad.append(rel)
    if bad:
        print("\n%d 个文件仍不一致。等 1-2 分钟重跑；若长期不变，"
              "把文件名加日期后缀（参考 ad-full-20261024.yaml）。" % len(bad))
        return 1
    print("\n全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

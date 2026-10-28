#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slim.py —— 把 egern-mirror 瘦到 jsDelivr 50 MB 上限以下

为什么需要
    jsDelivr 对 GitHub 仓库有 50 MB 打包上限。仓库一旦超限，凡是需要
    「重新打包」的请求（缓存过期、新文件、purge 之后）就返回
        403 Package size exceeded the configured limit of 50 MB
    仍在边缘缓存里的文件照发，所以现象是：
        · 大部分文件正常
        · 随机一小撮 403，重试有时又好（换了节点 / 缓存还在）
        · 同一个目录里，17 个图标 200、2 个图标 403
    这不是文件坏了，是仓库太大。

做法
    1. 从一份 Egern 配置里扫出所有 `egern-mirror@main/` 后面的路径
       （modules / rule_set / dns.forward / 图标 / geoip / 脚本，全算）
    2. 这些路径 + KEEP_EXTRA 里的工具文档 = 白名单
    3. 其余全部移到 ../egern-mirror-archive/（不是删除）

    移动而不是删除，是留一份存档随时能拿回来；
    放到仓库外面，是为了它不会被 git 提交、不占 CDN 体积。

用法
    python slim.py --profile <配置.yaml>                     # 只报告，不动文件
    python slim.py --profile <配置.yaml> --apply             # 移到 ../egern-mirror-archive/
    python slim.py --profile <配置.yaml> --apply --trash     # 移到仓库内 _trash/

回滚
    git checkout -- .                       # 仓库内全部恢复
    cp -r ../egern-mirror-archive/* .       # 从存档搬回
"""

import argparse
import collections
import os
import re
import shutil
import sys
import urllib.parse

try:
    import yaml
except ImportError:
    sys.exit("需要 pyyaml：pip install pyyaml")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置里没引用、但希望留在仓库里的文件（相对仓库根，可自行增删）
KEEP_EXTRA = [
    # 自建生成脚本与文档
    "curated/tools/build.py",
    "curated/tools/purge.py",
    "curated/tools/slim.py",
    "curated/README.md",
    "curated/映射表.md",
    "curated/对比-v9.9与新配置.md",
    "curated/rules/ad-exclude.txt",
    "curated/rules/qingr-index.md",
    "curated/manifest.json",
    "curated/Profile.yaml",
    # 仓库说明
    "README.md",
    "上传说明.md",
    "审计说明.md",
    "manifest.json",
    ".gitattributes",
    ".gitignore",
]

# 整目录直接丢弃（体积大、且当前配置一个都没引用）
DROP_DIRS = [
    "rules/shunt-rules/clash",   # Clash 格式，Egern 不认
    "rules/yfamilys",
    "rules/loonkit",
    "modules/qingr",             # 文件名是字面百分号，且全未引用
]


def collect_used(profile_path):
    """从配置里扫出所有 @main/ 后面的相对路径。

    用正则扫全文，而不是只解析 modules / rules / dns.forward，
    因为 policy_groups 里的 icon 也指向本仓库的 icons/ 目录。
    """
    raw = open(profile_path, encoding="utf-8").read()
    used = set()
    for m in re.finditer(r"egern-mirror@main/(\S+)", raw):
        # 配置里 URL 后面可能跟引号/逗号/右括号，剥掉
        path = m.group(1).rstrip("\"'),;]}")
        if path:
            used.add(urllib.parse.unquote(path))
    # 顺手做一次 YAML 校验，配置本身坏了就别继续
    yaml.safe_load(re.sub(r"(token=)[A-Za-z0-9%\-_]+", r"\1<RED>", raw))
    return used


def walk_files():
    for root, dirs, files in os.walk(REPO):
        if ".git" in root.split(os.sep) or "_trash" in root.split(os.sep):
            dirs[:] = []
            continue
        for f in files:
            p = os.path.join(root, f)
            yield os.path.relpath(p, REPO).replace("\\", "/"), os.path.getsize(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="Egern 配置 yaml 路径")
    ap.add_argument("--apply", action="store_true", help="真的移动文件")
    ap.add_argument("--trash", action="store_true",
                    help="移到仓库内 _trash/（默认移到 ../egern-mirror-archive/）")
    ap.add_argument("--archive", default=None,
                    help="存档目录，默认 ../egern-mirror-archive")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(REPO, ".git")):
        sys.exit(f"这里不是 git 仓库根目录：{REPO}")

    used = collect_used(args.profile)
    keep = used | set(KEEP_EXTRA)

    all_files = list(walk_files())
    total = sum(s for _, s in all_files)

    drop, keep_rows = [], []
    for rel, size in all_files:
        if rel in keep:
            keep_rows.append((rel, size))
        else:
            drop.append((rel, size))

    missing = [r for r in sorted(keep) if not os.path.exists(os.path.join(REPO, r))]

    drop_size = sum(s for _, s in drop)
    keep_size = sum(s for _, s in keep_rows)

    print("=" * 72)
    print(f"仓库    {len(all_files):5d} 个文件  {total / 1048576:7.1f} MB")
    print(f"保留    {len(keep_rows):5d} 个文件  {keep_size / 1048576:7.1f} MB   ← 瘦身后")
    print(f"移走    {len(drop):5d} 个文件  {drop_size / 1048576:7.1f} MB")
    print(f"上限    50.0 MB   →  瘦身后占上限的 {keep_size / 1048576 / 50 * 100:.0f}%")
    print("=" * 72)

    if missing:
        print("\n⚠ 配置引用了但仓库里没有的路径（会让 Egern 拉取失败）：")
        for m in missing:
            print("   ", m)
    else:
        print("\n✓ 配置引用的路径全部命中")

    by_dir = collections.Counter()
    size_by_dir = collections.Counter()
    for rel, size in drop:
        d = "/".join(rel.split("/")[:2])
        by_dir[d] += 1
        size_by_dir[d] += size
    print("\n移走明细（按目录，前 12）：")
    for d, n in sorted(by_dir.items(), key=lambda kv: -size_by_dir[kv[0]])[:12]:
        print(f"  {d:36s} {n:5d} 个  {size_by_dir[d] / 1048576:7.1f} MB")

    if not args.apply:
        print("\n（只报告。加 --apply 才会真的移动文件）")
        return

    dest_root = os.path.join(REPO, "_trash") if args.trash else (
        args.archive or os.path.join(os.path.dirname(REPO), "egern-mirror-archive"))
    os.makedirs(dest_root, exist_ok=True)

    moved = 0
    for rel, _ in drop:
        src = os.path.join(REPO, rel)
        dst = os.path.join(dest_root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        moved += 1
    print(f"\n✓ 已移动 {moved} 个文件 → {dest_root}")

    # 清理空目录
    for root, dirs, files in os.walk(REPO, topdown=False):
        parts = root.split(os.sep)
        if ".git" in parts or "_trash" in parts:
            continue
        if not os.listdir(root):
            try:
                os.rmdir(root)
            except OSError:
                pass

    print("\n接下来：")
    print("  1) 提交瘦身结果")
    print("     git add -A && git commit -m 'chore: 瘦身到 50 MB 以下，修复 jsDelivr 403'")
    print("     git push origin main")
    print("  2) 存档（可选，放另一个仓库）")
    print(f"     cd {dest_root}")
    print("     git init && git add -A && git commit -m 'archive'")
    print("     git remote add origin <新仓库地址> && git push -u origin main")
    print("  3) 回滚")
    print("     git checkout -- .")


if __name__ == "__main__":
    main()

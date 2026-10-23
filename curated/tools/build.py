#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
curated/ 生成脚本

从仓库自身的镜像文件生成三份"重写/修复"产物：
  1. rules/cn-full.yaml   —— 把 quixoticheart 的 cn.yaml(域名) 与 cncidr.yaml(IP段) 合成单个 Egern 原生文件
  2. rules/qingr-index.md —— 把 modules/qingr 下 506 个字面量百分号编码的文件名解码成可读索引
  3. manifest.json        —— 精选模块清单（App -> 推荐文件 -> 理由）

用法（在仓库根目录执行）：
    python curated/tools/build.py

依赖：仅标准库。输入只读，不修改任何镜像文件。
"""

import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CUR = os.path.join(ROOT, "curated")


def p(*parts):
    return os.path.join(ROOT, *parts)


def read(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


# ---------------------------------------------------------------- 1. cn-full.yaml

def build_cn_full():
    """cn.yaml 只有 domain_suffix_set，没有 IP 段；cncidr.yaml 只有 ip_cidr_set。
    只挂 cn.yaml 会导致"纯 IP 直连"的流量落到代理。合并成一个文件消除这个坑。"""
    src_dom = p("rules", "quixoticheart-egern", "cn.yaml")
    src_ip = p("rules", "quixoticheart-egern", "cncidr.yaml")

    doms, ips = [], []
    cur = None
    for line in read(src_dom).splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([a-z_]+):\s*$", s)
        if m:
            cur = m.group(1)
            continue
        if s.startswith("- "):
            v = s[2:].strip().strip("'\"")
            if cur in ("domain_suffix_set", "domain_set"):
                doms.append(v)
    cur = None
    for line in read(src_ip).splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([a-z_]+):\s*$", s)
        if m:
            cur = m.group(1)
            continue
        if s.startswith("- ") and cur == "ip_cidr_set":
            ips.append(s[2:].strip().strip("'\""))

    seen = set()
    doms = [d for d in doms if not (d in seen or seen.add(d))]
    seen = set()
    ips = [i for i in ips if not (i in seen or seen.add(i))]

    out = [
        "# 国内直连（域名 + IP 段 合一）",
        "# 由 curated/tools/build.py 生成，勿手改。",
        "# 来源：rules/quixoticheart-egern/cn.yaml + cncidr.yaml",
        "# 用途：挂在分流的 DIRECT 层，替代「需要同时挂两个文件」的原方案",
        "#   domain_suffix_set: %d 条" % len(doms),
        "#   ip_cidr_set:       %d 条" % len(ips),
        "no_resolve: true",
        "domain_suffix_set:",
    ]
    out += ["- " + d for d in doms]
    out.append("ip_cidr_set:")
    out += ["- " + i for i in ips]

    dst = os.path.join(CUR, "rules", "cn-full.yaml")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    return len(doms), len(ips), dst


# ---------------------------------------------------------------- 2. qingr-index.md

def build_qingr_index():
    """modules/qingr 下的文件名是「字面量百分号编码」，拼 URL 必须把 % 再转义成 %25。"""
    d = p("modules", "qingr")
    if not os.path.isdir(d):
        return 0, None
    rows = []
    for fn in sorted(os.listdir(d)):
        if not os.path.isfile(os.path.join(d, fn)):
            continue
        base = re.sub(r"\.(sgmodule|lpx|module)$", "", fn)
        base = re.sub(r"-[0-9a-f]{6,}$", "", base)
        name = urllib.parse.unquote(base)
        url_path = urllib.parse.quote(fn, safe="")
        rows.append((name, fn, url_path))

    out = [
        "# modules/qingr 文件名索引",
        "",
        "> 由 `curated/tools/build.py` 生成。共 **%d** 个文件。" % len(rows),
        "",
        "## 为什么需要这张表",
        "",
        "`modules/qingr/` 下的文件名是**字面量百分号编码**——仓库里文件真的叫 `%E7%9F%A5%E4%B9%8E...`。这意味着：",
        "",
        "1. 直接拼 `.../modules/qingr/%E7%9F%A5...` 会 **404**；",
        "2. 必须把 `%` 再转义成 `%25` 才能取到；",
        "3. 配置里手写、肉眼比对、排错几乎不可行。",
        "",
        "同内容的可读文件名版本在 `modules/root/qingrex-loonkisssurge-*.sgmodule`（34 个）里有一部分。",
        "",
        "**结论：qingr 目录只当备份用，日常配置请用 kelee / loonlab / fmz200。**",
        "",
        "## 正确取法",
        "",
        "```",
        "https://cdn.jsdelivr.net/gh/tuohai57/egern-mirror@main/modules/qingr/%25E7%259F%25A5%25E4%25B9%258E...",
        "                                                      ↑ 注意是 %25 而不是 %",
        "```",
        "",
        "| 解码名 | 仓库文件名 | URL 路径（已二次转义） |",
        "|---|---|---|",
    ]
    for name, fn, up in rows:
        out.append("| %s | `%s` | `%s` |" % (name, fn, up))

    dst = os.path.join(CUR, "rules", "qingr-index.md")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    return len(rows), dst


# ---------------------------------------------------------------- 3. manifest.json

BASE = "https://cdn.jsdelivr.net/gh/tuohai57/egern-mirror@main/"

LOONLAB = [
    ("知乎", "modules/loonlab/loonlab-plugin-10652bee.lpx", 90, "62 个接口，MITM 只 1 台；把 commercial_api 全量拦截注释掉了，改成逐接口精确删"),
    ("微博", "modules/loonlab/loonlab-plugin-ae197c04.lpx", 75, "69 个接口，独有 62 个（kelee+rucu6+fmz200 三源合并）"),
    ("闲鱼", "modules/loonlab/loonlab-plugin-25d617c6.lpx", 88, "28 个接口 vs fmz200 的 21"),
    ("腾讯视频", "modules/loonlab/loonlab-plugin-4d0e6c12.lpx", 71, "29 个接口，0 台 MITM"),
    ("百度网盘", "modules/loonlab/loonlab-plugin-5a48a2c4.lpx", 100, "17/17 全覆盖，其他源只有 8"),
    ("拼多多", "modules/loonlab/loonlab-plugin-78e0d6e2.lpx", 74, "39 个接口，独有 16"),
    ("高德地图", "modules/loonlab/loonlab-plugin-2b9a2951.lpx", 64, "27 个接口，MITM 只 1 台"),
    ("网易云音乐", "modules/loonlab/loonlab-plugin-3339cf75.lpx", 69, "11 个接口 vs 其他 8"),
    ("哔哩哔哩", "modules/loonlab/loonlab-plugin-98bc0fa0.lpx", 83, "25 个接口，独有 1；有 4 个外链 JS，注意断链"),
    ("小红书", "modules/loonlab/loonlab-plugin-79651793.lpx", 56, "覆盖最全，代价是 10 台 MITM + 3 个外链 JS"),
    ("酷安", "modules/loonlab/loonlab-plugin-db68e5cc.lpx", 75, "6 个接口 vs 4"),
]
FMZ = [
    ("爱奇艺", "modules/fmz200/partA/iQIYI.sgmodule", 82, "45 条域名 REJECT，0 脚本；代价是 api.iqiyi.com 整域被拦"),
    ("淘宝", "modules/fmz200/partT/Taobao.sgmodule", 60, "33 个独有接口，别家一个都没有"),
    ("京东", "modules/fmz200/partJ/JD.com.sgmodule", 63, "17 个接口，独有 16"),
    ("快手", "modules/fmz200/partK/Kuaishou.sgmodule", 69, "9 个独有接口，其余源只有 4"),
    ("芒果TV", "modules/fmz200/partM/MangoTV.sgmodule", 65, "30 个接口，MITM 只 1 台"),
    ("QQ音乐", "modules/fmz200/partQ/QQMusic.sgmodule", 91, "31 个接口，0 脚本"),
    ("汽水音乐", "modules/fmz200/partQ/QiShuiMusic.sgmodule", 61, "独有 32 个接口"),
    ("喜马拉雅", "modules/fmz200/partX/Ximalaya.sgmodule", 60, "26 个接口，独有 5"),
    ("酷我音乐", "modules/fmz200/partK/KuwoMusic.sgmodule", 58, "独有 17，别家 29%"),
    ("优酷", "modules/fmz200/partY/Youku.sgmodule", 100, "29/29 全库唯一全覆盖，0 脚本"),
]
KELEE = [
    ("得物", "modules/kelee/kelee-得物去广告-97b49486.lpx", 100, "全覆盖，1 台 MITM"),
    ("瑞幸咖啡", "modules/kelee/kelee-瑞幸咖啡去广告-1dfdd230.lpx", 100, "全覆盖"),
    ("米游社", "modules/kelee/kelee-米游社去广告-07b6df29.lpx", 100, "全覆盖"),
    ("小黑盒", "modules/kelee/kelee-小黑盒去广告-8ce70df1.lpx", 100, "全覆盖"),
    ("马蜂窝", "modules/kelee/kelee-马蜂窝去广告-29fd2cad.lpx", 80, "覆盖最高"),
    ("淘票票", "modules/kelee/kelee-淘票票去广告-44e8648e.lpx", 100, "全覆盖"),
    ("大麦", "modules/kelee/kelee-大麦去广告-236dbca2.lpx", 100, "全覆盖"),
    ("起点读书", "modules/kelee/kelee-起点读书去广告-73c6e283.lpx", 100, "全覆盖"),
    ("百度文库", "modules/kelee/kelee-百度文库去广告-8212a3bd.lpx", 100, "全覆盖"),
    ("粉笔", "modules/kelee/kelee-粉笔去广告-17a03272.lpx", 80, "覆盖最高"),
    ("小象超市", "modules/kelee/kelee-小象超市去广告-8eec1458.lpx", 100, "全覆盖"),
    ("叮咚买菜", "modules/kelee/kelee-叮咚买菜去广告-5622a746.lpx", 88, "覆盖最高"),
    ("番茄小说", "modules/kelee/kelee-番茄小说去广告-da052ba7.lpx", 62, "0 台 MITM"),
    ("12306", "modules/kelee/kelee-12306去广告-ffefab9b.lpx", 75, "覆盖最高"),
    ("夸克", "modules/kelee/kelee-夸克去广告-b2f31d98.lpx", 50, "各源持平，选最新"),
    ("微信公众号", "modules/kelee/kelee-微信公众号去广告-5fbb442e.lpx", 100, "全覆盖"),
    ("微博轻享版", "modules/kelee/kelee-微博轻享版去广告-78f41ea7.lpx", 82, "覆盖最高"),
]

TOOLS = [
    ("聚合包（730 款 App 内容改写）", "modules/fmz200/_main/blockAds.module",
     "2,993 条规则 + 1,470 条改写 + 255 个脚本；价值在改写不在规则"),
    ("墨鱼去开屏 2.0", "modules/loonlab/loonlab-2.0-305406a1.lpx",
     "2026-10-22 最新上游，461 条改写；导入异常退 modules/jadkg-egern-bfffde50c6.module"),
    ("广告平台拦截器", "modules/kelee/kelee-广告平台拦截器-2947d7df.lpx",
     "341 条域名，比 qingr 的 301 条多；纯 REJECT，放模块列表最下面"),
    ("HTTPDNS 拦截器", "modules/kelee/kelee-HTTPDNS拦截器-1565be1f.lpx",
     "73 条，比 qingr 新版 65 / 老版 60 都多"),
    ("微信小程序去广告", "modules/kelee/kelee-微信小程序去广告-a3e17aa9.lpx",
     "118 条改写，93 台 MITM——全库最重的模块，非必要不开"),
    ("优先级补丁（本仓库自建）", "curated/modules/00-override.module",
     "修正被模块误拦的域名，必须放模块列表最上面"),
]

RULES = [
    ("广告 REJECT", "rules/shunt-rules/loon/AdvertisingTest.lsr",
     "318,626 条，占 8 份广告表并集的 85.7%；Advertising.lsr 独有仅 3 条、yfamilys/ADLite 独有 0 条，都是纯子集"),
    ("广告补充", "rules/shunt-rules/loon/AdGuardSDNSFilter.lsr",
     "109,050 条，与上者并集后 +28,175 个域名（+8.8%），增量/体积比最高的一份"),
    ("国内直连", "curated/rules/cn-full.yaml",
     "本仓库合并版：域名 108,068 + IP 段 17,958 合到一个文件，避免只挂 cn.yaml 漏 IP"),
    ("代理兜底", "rules/shunt-rules/loon/Global.lsr",
     "35,888 条，占并集 60.2%；Proxy.lsr 独有 3 条、gfw.yaml 独有 0 条"),
    ("分流骨架", "rules/quixoticheart-egern/",
     "全库唯一 Egern 原生 YAML；有 25 个别人没有的结构件（apple-cn/apple-proxy、iplocation-direct/proxy、tld-proxy、private、cdn、httpdns、apns）"),
]


def build_manifest():
    def pack(items, src):
        return [{"app": a, "path": f, "url": BASE + urllib.parse.quote(f, safe="/"),
                 "coverage": c, "reason": r, "source": src} for a, f, c, r in items]

    mods = pack(LOONLAB, "loonlab") + pack(FMZ, "fmz200") + pack(KELEE, "kelee")
    tools = [{"app": a, "path": f, "url": BASE + urllib.parse.quote(f, safe="/"), "reason": r}
             for a, f, r in TOOLS]
    rules = [{"layer": a, "path": f, "url": BASE + urllib.parse.quote(f, safe="/"), "reason": r}
             for a, f, r in RULES]

    doc = {
        "_comment": "精选清单：由 curated/tools/build.py 从 1,753 个模块 / 2,276 个规则集的实测对比中生成",
        "_generated": "2026-10-24",
        "_repo": "https://github.com/tuohai57/egern-mirror",
        "_base_url": BASE,
        "_priority_note": "Egern 优先级：模块 > 本地配置；模块之间、规则之间均为「上面的优于下面」，纯列表序，没有更具体者优先。",
        "module_order": [
            "1. curated/modules/00-override.module（优先级补丁，必须最上）",
            "2. 单 App 精细改写（loonlab / kelee，见 modules）",
            "3. 墨鱼去开屏",
            "4. 聚合包 blockAds.module",
            "5. 广告平台拦截器",
            "6. HTTPDNS 拦截器（最下）",
        ],
        "rule_order": [
            "1. private / Lan -> DIRECT",
            "2. AdvertisingTest + AdGuardSDNSFilter -> REJECT",
            "3. apple-cn / microsoft-cn / socialmedia-cn / games-cn / douyin / bilibili -> DIRECT",
            "4. ai / netflix / disney / youtube / spotify / socialmedia -> 策略组",
            "5. cn-full.yaml -> DIRECT",
            "6. Global.lsr -> PROXY",
            "7. GEOIP,CN -> DIRECT",
            "8. FINAL -> PROXY",
        ],
        "modules": mods,
        "tools": tools,
        "rules": rules,
    }
    dst = os.path.join(CUR, "manifest.json")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return len(mods) + len(tools), dst


def main():
    nd, ni, dst1 = build_cn_full()
    print("[1/3] cn-full.yaml      域名 %d + IP %d -> %s" % (nd, ni, os.path.relpath(dst1, ROOT)))
    nq, dst2 = build_qingr_index()
    print("[2/3] qingr-index.md    %d 个文件 -> %s" % (nq, os.path.relpath(dst2, ROOT)))
    nm, dst3 = build_manifest()
    print("[3/3] manifest.json     %d 条推荐 -> %s" % (nm, os.path.relpath(dst3, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

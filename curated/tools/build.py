#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
curated/ 生成脚本

从仓库自身的镜像文件生成以下产物（输入只读，不修改任何镜像文件）：

  rules/ad-full.yaml      广告拦截总表：5 份广告表取并集 + 修正 IP 写法 + 去重（Egern 原生 YAML）
  rules/cn-full.yaml      国内直连：域名 + IP 段 合一（Egern 原生 YAML）
  rules/extra-media.yaml  流媒体补充
  rules/extra-social.yaml 社交补充
  rules/extra-dev.yaml    开发补充
  rules/extra-cloud.yaml  云服务补充
  rules/extra-game.yaml   游戏补充
  rules/qingr-index.md    modules/qingr 506 个编码文件名的解码索引
  manifest.json           精选模块清单

用法（仓库根目录）：
    python curated/tools/build.py

依赖：仅标准库。
"""

import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CUR = os.path.join(ROOT, "curated")


def R(*p):
    return os.path.join(ROOT, "rules", *p)


REGEX = set()          # domain_regex_set 条目（不能转成域名，原样保留）
WILDCARD = set()       # 含 * 的条目，domain_suffix_set 不支持通配符，必须单列
# 过于通用的英文词，会误伤正常域名（实例：traffic 命中 trafficmanager.cn）
KEYWORD_BLOCK = {"traffic", "tracking", "analytics", "stats", "metrics", "telemetry"}
IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
PRIVATE = re.compile(
    r"^(?:10\.|127\.|0\.|169\.254\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.)"
)


def read(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def split_sections(text):
    """把 Egern 原生 YAML 规则集拆成 {key: [values]}"""
    out = {}
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([a-z_0-9]+)\s*:\s*$", s)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        if s.startswith("- ") and cur:
            out[cur].append(s[2:].strip().strip("'\""))
    return out


def parse_ruleset(path):
    """把 Surge list 或 Egern YAML 都解析成 (exact, suffix, keyword, ip) 四个集合"""
    exact, suffix, keyword, ip = set(), set(), set(), set()
    text = read(path)

    if re.search(r"^(domain_set|domain_suffix_set|domain_keyword_set|ip_cidr_set)\s*:", text, re.M):
        sec = split_sections(text)
        exact |= {v.lower() for v in sec.get("domain_set", [])}
        suffix |= {v.lower() for v in sec.get("domain_suffix_set", [])}
        keyword |= {v.lower() for v in sec.get("domain_keyword_set", [])}
        REGEX.update(v for v in sec.get("domain_regex_set", []))
        for v in sec.get("ip_cidr_set", []) + sec.get("ip_cidr6_set", []):
            ip.add(v.lower())
        WILDCARD.update(v.lower() for v in sec.get("domain_wildcard_set", []))
        return exact, suffix, keyword, ip

    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("//"):
            continue
        if s.startswith("- "):
            s = s[2:].strip()
        m = re.match(r"^([A-Z\-0-9]+)\s*,\s*([^,\s]+)", s)
        if m:
            t, v = m.group(1), m.group(2).lower()
            if t == "DOMAIN":
                exact.add(v)
            elif t == "DOMAIN-SUFFIX":
                suffix.add(v)
            elif t == "DOMAIN-KEYWORD":
                keyword.add(v)
            elif t in ("IP-CIDR", "IP-CIDR6"):
                ip.add(v)
            continue
        if re.match(r"^[a-z0-9\*\-\.]+$", s) and "." in s:
            (WILDCARD if "*" in s else suffix).add(s.lower())
    return exact, suffix, keyword, ip


def normalize(exact, suffix, keyword, ip):
    """把误写成 DOMAIN 的 IP 挪到 ip 集合；丢掉私网 IP；清洗脏数据"""
    # 含 * 的进通配符集合；以 - 开头 / 以 . 结尾 / 无点的丢弃
    for v in list(suffix | exact):
        if "*" in v:
            WILDCARD.add(v)
            suffix.discard(v)
            exact.discard(v)
    for st in (exact, suffix):
        for v in list(st):
            if v.startswith(("-", ".")) or v.endswith(".") or ".." in v or "." not in v:
                st.discard(v)
    for v in list(exact | suffix):
        if IPV4.match(v):
            exact.discard(v)
            suffix.discard(v)
            if not PRIVATE.match(v):
                ip.add(v + "/32")
    for v in list(exact):
        if PRIVATE.match(v):
            exact.discard(v)
    ip = {i for i in ip if not (IPV4.match(i.split("/")[0]) and PRIVATE.match(i.split("/")[0]))}
    return exact, suffix, keyword, ip


def write_yaml(path, title, sources, exact, suffix, keyword, ip, extra_comment=None):
    lines = [
        "# " + title,
        "# 由 curated/tools/build.py 生成，勿手改。",
        "# 来源：",
    ]
    lines += ["#   - " + s for s in sources]
    if extra_comment:
        lines += ["#", "# " + extra_comment]
    lines += [
        "#",
        "# 条目：domain_set %d / domain_suffix_set %d / domain_keyword_set %d / "
        "domain_wildcard_set %d / domain_regex_set %d / ip_cidr_set %d"
        % (len(exact), len(suffix), len(keyword), len(WILDCARD), len(REGEX), len(ip)),
        "no_resolve: true",
    ]
    for key, vals in (
        ("domain_set", exact),
        ("domain_suffix_set", suffix),
        ("domain_keyword_set", keyword),
        ("domain_wildcard_set", WILDCARD),
        ("domain_regex_set", REGEX),
        ("ip_cidr_set", ip),
    ):
        if vals:
            lines.append(key + ":")
            lines += ["- " + v for v in sorted(vals)]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return len(exact) + len(suffix) + len(keyword) + len(ip)


# ---------------------------------------------------------------- 1. 广告总表

AD_STAMP = "20261024"   # 重建时改成当天日期，用来破 CDN 缓存

AD_SOURCES = [
    "shunt-rules/loon/AdvertisingTest.lsr",       # 318,626 覆盖最广
    "shunt-rules/loon/AdGuardSDNSFilter.lsr",     # 109,050 DNS 过滤
    "quixoticheart-egern/adrules.yaml",           # 211,106 Egern 原生
    "yfamilys/AntiAD.list",                       # 303,395
    "loonkit/AdBlock.list",                       #  77,213
    "shunt-rules/loon/Privacy.lsr",               #  39,936 隐私追踪（v9.9 在用）
    "deezertidal-shadowrocket-rules-hijacking.list",  # 劫持站
    "deezertidal-shadowrocket-rules-beats.list",      # 仿冒 Beats
    # 下面三份与上面同源但版本不同（root 里是更早的副本），互相有对方没有的条目
    "deezertidal-shadowrocket-rules-adlite.list",
    "deezertidal-shadowrocket-rules-advertisinglite.list",
    "quixoticheart-rule-set-adrules.yaml",
]


def build_ad_full():
    WILDCARD.clear(); REGEX.clear()
    exact, suffix, keyword, ip = set(), set(), set(), set()
    for rel in AD_SOURCES:
        a, b, c, d = parse_ruleset(R(rel))
        exact |= a
        suffix |= b
        keyword |= c
        ip |= d
    exact, suffix, keyword, ip = normalize(exact, suffix, keyword, ip)

    # 排除白名单：这些域名在配置里是显式 DIRECT，若留在广告表里，
    # DNS 层 reject 会无视规则顺序把它们拦死（顺序只管规则层，管不了 DNS 层）。
    # 清单见 rules/ad-exclude.txt，来自 v9.9 的 145 条手写白名单。
    excl_path = os.path.join(CUR, "rules", "ad-exclude.txt")
    if os.path.exists(excl_path):
        excl = {l.strip().lower() for l in read(excl_path).splitlines()
                if l.strip() and "/" not in l and not l.strip().startswith("#")}

        def in_wl(d):
            parts = d.split(".")
            for i in range(len(parts)):
                if ".".join(parts[i:]) in excl:
                    return True
            return False

        exact = {d for d in exact if not in_wl(d)}
        suffix = {d for d in suffix if not in_wl(d)}
        keyword = {k for k in keyword if not in_wl(k)}
        keyword = {k for k in keyword if k not in KEYWORD_BLOCK}
        # 通配符条目（*-ad-sign.byteimg.com）也要按去掉 * 后的基域判断
        WILDCARD.difference_update(
            [w for w in list(WILDCARD) if in_wl(w.replace("*", "").strip("."))]
        )

    def parents(d):
        parts = d.split(".")
        for i in range(1, len(parts)):
            yield ".".join(parts[i:])

    exact = {d for d in exact if not any(p in suffix for p in parents(d))}
    suffix = {d for d in suffix if not any(p in suffix for p in parents(d))}

    # 文件名带日期：jsDelivr 的 @main 分支别名有 12h 缓存，同名覆盖会长时间取到旧版。
    # 每次重建换个日期名，等于换个 URL，必然取到新内容。
    dst = os.path.join(CUR, "rules", "ad-full-%s.yaml" % AD_STAMP)
    n = write_yaml(
        dst,
        "广告拦截总表（8 份并集）",
        AD_SOURCES,
        exact, suffix, keyword, ip,
        "8 份广告/追踪/劫持表互相大量重叠但都不互相包含。实测：AdvertisingTest 独有 22,057、"
        "adrules 独有 24,808、AdGuard 独有 28,175、AntiAD 独有 13,610、AdBlock 独有 12,691、"
        "Privacy 独有 11,000+、Hijacking 186、Beats 714。取全并集是唯一能做到不漏的方式。"
        "另修正了原表里把 IP 写成 DOMAIN 的条目（这些在 Egern 里永远匹配不到）。",
    )
    return n, dst


# ---------------------------------------------------------------- 2. 国内直连

def build_cn_full():
    WILDCARD.clear(); REGEX.clear()
    a1, b1, c1, d1 = parse_ruleset(R("quixoticheart-egern", "cn.yaml"))
    a2, b2, c2, d2 = parse_ruleset(R("quixoticheart-egern", "cncidr.yaml"))
    exact, suffix, keyword, ip = a1 | a2, b1 | b2, c1 | c2, d1 | d2
    exact, suffix, keyword, ip = normalize(exact, suffix, keyword, ip)
    dst = os.path.join(CUR, "rules", "cn-full.yaml")
    n = write_yaml(
        dst,
        "国内直连（域名 + IP 段 合一）",
        ["quixoticheart-egern/cn.yaml", "quixoticheart-egern/cncidr.yaml"],
        exact, suffix, keyword, ip,
        "原方案要同时挂 cn.yaml（域名）和 cncidr.yaml（IP 段），只挂前者会让纯 IP 直连的流量掉到代理。",
    )
    return n, dst


# ---------------------------------------------------------------- 3. 补充规则集

EXTRA = {
    "extra-media": (
        "流媒体补充",
        [
            "shunt-rules/loon/ParamountPlus.lsr",
            "shunt-rules/loon/Peacock.lsr",
            "shunt-rules/loon/DiscoveryPlus.lsr",
            "shunt-rules/loon/ViuTV.lsr",
            "shunt-rules/loon/LineTV.lsr",
            "shunt-rules/loon/HBOAsia.lsr",
            "shunt-rules/loon/HuluJP.lsr",
            "shunt-rules/loon/HuluUSA.lsr",
            "shunt-rules/loon/SoundCloud.lsr",
            "shunt-rules/loon/Deezer.lsr",
            "shunt-rules/loon/TIDAL.lsr",
            "shunt-rules/loon/YouTubeMusic.lsr",
            "shunt-rules/loon/AppleMusic.lsr",
            "shunt-rules/loon/AppleTV.lsr",
            "shunt-rules/loon/Netflix.lsr",
            "shunt-rules/loon/Disney.lsr",
            "shunt-rules/loon/HBO.lsr",
            "shunt-rules/loon/Hulu.lsr",
            "shunt-rules/loon/PrimeVideo.lsr",
            "shunt-rules/loon/Spotify.lsr",
            "shunt-rules/loon/YouTube.lsr",
            "shunt-rules/loon/Twitch.lsr",
        ],
        "quixoticheart 的 netflix/disney/hbo/hulu/primevideo/youtube/spotify/twitch 只有基础域名；"
        "这里补上它没有的 Paramount+ / Peacock / Discovery+ / ViuTV / LineTV / HBO Asia / Hulu 日美 / "
        "SoundCloud / Deezer / TIDAL / YouTube Music，并把这些服务的完整域名并进来。",
    ),
    "extra-social": (
        "社交补充",
        [
            "shunt-rules/loon/Reddit.lsr",
            "shunt-rules/loon/Pinterest.lsr",
            "shunt-rules/loon/Tumblr.lsr",
            "shunt-rules/loon/Slack.lsr",
            "shunt-rules/loon/Notion.lsr",
            "shunt-rules/loon/Discord.lsr",
            "shunt-rules/loon/Telegram.lsr",
            "shunt-rules/loon/Twitter.lsr",
            "shunt-rules/loon/LinkedIn.lsr",
            "shunt-rules/loon/Facebook.lsr",
            "shunt-rules/loon/Instagram.lsr",
            "shunt-rules/loon/Whatsapp.lsr",
            "shunt-rules/loon/Line.lsr",
        ],
        "quixoticheart 的 socialmedia.yaml 已有 Telegram/Twitter/Discord/Line/WhatsApp/FB/IG/LinkedIn，"
        "但缺 Reddit / Pinterest / Tumblr / Slack / Notion；这里补上并把前几个的完整域名并进来。",
    ),
    "extra-dev": (
        "开发补充",
        [
            "shunt-rules/loon/Developer.lsr",
            "shunt-rules/loon/Npmjs.lsr",
            "shunt-rules/loon/Docker.lsr",
            "shunt-rules/loon/GitHub.lsr",
            "shunt-rules/loon/GitLab.lsr",
            "shunt-rules/loon/Dropbox.lsr",
            "shunt-rules/loon/Cloudflare.lsr",
        ],
        "quixoticheart 的 gits.yaml 只有 75 条、基本只覆盖 GitHub；"
        "这里补 npm / Docker / GitLab / Dropbox / Cloudflare / Developer 全量分类。",
    ),
    "extra-cloud": (
        "云服务补充",
        [
            "shunt-rules/loon/Amazon.lsr",
            "shunt-rules/loon/AmazonIP.lsr",
            "shunt-rules/loon/AmazonTrust.lsr",
            "shunt-rules/loon/Oracle.lsr",
            "shunt-rules/loon/GoogleDrive.lsr",
            "shunt-rules/loon/GoogleVoice.lsr",
            "shunt-rules/loon/GoogleEarth.lsr",
            "shunt-rules/loon/iCloud.lsr",
        ],
        "AWS / Oracle / Google Drive / iCloud 等云服务，quixoticheart 里没有独立分类。",
    ),
    "meta": (
        "Meta 全家桶（Facebook / Instagram / WhatsApp / Threads）",
        [
            "shunt-rules/loon/Facebook.lsr",
            "shunt-rules/loon/Instagram.lsr",
            "shunt-rules/loon/Whatsapp.lsr",
            "shunt-rules/loon/Threads.lsr",
            "loon-script/Other_Muse.lsr",
        ],
        "Facebook.lsr 546 条已经含 fbcdn / cdninstagram / whatsapp / threads / messenger，"
        "再并上 Instagram / WhatsApp / Threads 三张专用表（WhatsApp 那张带 IP-CIDR 段，语音通话要用）。"
        "单独成表是为了让 Meta 系统一走一个策略组，而不是散在社交媒体组里被日本节点抢走。"
        "另并入 loon-script/Other_Muse.lsr —— 那是上游给 Meta Muse AI（图像/视频生成）"
        "做的专用表，含 meta.ai / muse.ai / metaaivm.com 三个后缀，Facebook.lsr 里没有。",
    ),
    "extra-game": (
        "游戏补充",
        [
            "shunt-rules/loon/Steam.lsr",
            "shunt-rules/loon/Epic.lsr",
            "shunt-rules/loon/PlayStation.lsr",
            "shunt-rules/loon/Xbox.lsr",
            "shunt-rules/loon/Nintendo.lsr",
            "shunt-rules/loon/Riot.lsr",
        ],
        "外服游戏平台全量分类。国服 Steam 用单独的 SteamCN（走 DIRECT）。",
    ),
}


def build_extra():
    out = []
    for name, (title, sources, note) in EXTRA.items():
        WILDCARD.clear(); REGEX.clear()
        exact, suffix, keyword, ip = set(), set(), set(), set()
        for rel in sources:
            a, b, c, d = parse_ruleset(R(rel))
            exact |= a
            suffix |= b
            keyword |= c
            ip |= d
        exact, suffix, keyword, ip = normalize(exact, suffix, keyword, ip)
        dst = os.path.join(CUR, "rules", name + ".yaml")
        n = write_yaml(dst, title, sources, exact, suffix, keyword, ip, note)
        out.append((name, n, dst))
    return out


# ---------------------------------------------------------------- 4. qingr 索引

def build_qingr_index():
    d = os.path.join(ROOT, "modules", "qingr")
    if not os.path.isdir(d):
        return 0, None
    rows = []
    for fn in sorted(os.listdir(d)):
        if not os.path.isfile(os.path.join(d, fn)):
            continue
        base = re.sub(r"\.(sgmodule|lpx|module)$", "", fn)
        base = re.sub(r"-[0-9a-f]{6,}$", "", base)
        rows.append((urllib.parse.unquote(base), fn, urllib.parse.quote(fn, safe="")))

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


# ---------------------------------------------------------------- 5. manifest

BASE = "https://cdn.jsdelivr.net/gh/tuohai57/egern-mirror@main/"

LOONLAB = [
    ("知乎", "modules/loonlab/loonlab-plugin-10652bee.lpx", 90, "62 个接口，MITM 只 1 台"),
    ("微博", "modules/loonlab/loonlab-plugin-ae197c04.lpx", 75, "69 个接口，独有 62 个"),
    ("闲鱼", "modules/loonlab/loonlab-plugin-25d617c6.lpx", 88, "28 个接口 vs fmz200 的 21"),
    ("腾讯视频", "modules/loonlab/loonlab-plugin-4d0e6c12.lpx", 71, "29 个接口，0 台 MITM"),
    ("百度网盘", "modules/loonlab/loonlab-plugin-5a48a2c4.lpx", 100, "17/17 全覆盖"),
    ("拼多多", "modules/loonlab/loonlab-plugin-78e0d6e2.lpx", 74, "39 个接口，独有 16"),
    ("高德地图", "modules/loonlab/loonlab-plugin-2b9a2951.lpx", 64, "27 个接口，MITM 只 1 台"),
    ("网易云音乐", "modules/loonlab/loonlab-plugin-3339cf75.lpx", 69, "11 个接口 vs 其他 8"),
    ("哔哩哔哩", "modules/loonlab/loonlab-plugin-98bc0fa0.lpx", 83, "25 个接口，独有 1"),
    ("小红书", "modules/loonlab/loonlab-plugin-79651793.lpx", 56, "覆盖最全，10 台 MITM"),
    ("酷安", "modules/loonlab/loonlab-plugin-db68e5cc.lpx", 75, "6 个接口 vs 4"),
]
FMZ = [
    ("爱奇艺", "modules/fmz200/partA/iQIYI.sgmodule", 82, "45 条域名 REJECT，0 脚本"),
    ("淘宝", "modules/fmz200/partT/Taobao.sgmodule", 60, "33 个独有接口"),
    ("京东", "modules/fmz200/partJ/JD.com.sgmodule", 63, "17 个接口，独有 16"),
    ("快手", "modules/fmz200/partK/Kuaishou.sgmodule", 69, "9 个独有接口"),
    ("芒果TV", "modules/fmz200/partM/MangoTV.sgmodule", 65, "30 个接口，MITM 只 1 台"),
    ("QQ音乐", "modules/fmz200/partQ/QQMusic.sgmodule", 91, "31 个接口，0 脚本"),
    ("汽水音乐", "modules/fmz200/partQ/QiShuiMusic.sgmodule", 61, "独有 32 个接口"),
    ("喜马拉雅", "modules/fmz200/partX/Ximalaya.sgmodule", 60, "26 个接口，独有 5"),
    ("酷我音乐", "modules/fmz200/partK/KuwoMusic.sgmodule", 58, "独有 17，别家 29%"),
    ("优酷", "modules/fmz200/partY/Youku.sgmodule", 100, "29/29 全覆盖"),
    ("斗鱼直播", "modules/fmz200/partD/DouyuLive.sgmodule", 100, "全覆盖"),
    ("虎牙直播", "modules/fmz200/partH/HuyaLive.sgmodule", 100, "全覆盖"),
    ("美团", "modules/fmz200/partM/Meituan.sgmodule", 100, "全覆盖"),
    ("WPS/金山", "modules/fmz200/partJ/KingsoftSeries.sgmodule", 80, "金山系全家桶"),
]
KELEE = [
    ("得物", "modules/kelee/kelee-得物去广告-97b49486.lpx", 100, "全覆盖"),
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
    ("夸克", "modules/kelee/kelee-夸克去广告-b2f31d98.lpx", 50, "各源持平"),
    ("微信公众号", "modules/kelee/kelee-微信公众号去广告-5fbb442e.lpx", 100, "全覆盖"),
    ("微博轻享版", "modules/kelee/kelee-微博轻享版去广告-78f41ea7.lpx", 82, "覆盖最高"),
    ("网易新闻", "modules/kelee/kelee-网易新闻去广告-827054a3.lpx", 80, "覆盖最高"),
]

TOOLS = [
    ("优先级补丁（本仓库自建）", "curated/modules/00-override.yaml", "修正被模块误拦的域名，必须放最上面"),
    ("聚合包（730 款 App 内容改写）", "modules/fmz200/_main/blockAds.module", "2,993 规则 + 1,470 改写 + 255 脚本"),
    ("墨鱼去开屏 2.0", "modules/loonlab/loonlab-2.0-305406a1.lpx", "461 条改写，去开屏主力"),
    ("微信小程序去广告", "modules/kelee/kelee-微信小程序去广告-a3e17aa9.lpx", "118 改写，93 台 MITM"),
    ("微信本体", "modules/loonlab/loonlab-plugin-06771181.lpx", "173 改写 + 117 台 MITM"),
    ("广告平台拦截器", "modules/kelee/kelee-广告平台拦截器-2947d7df.lpx", "341 条纯域名 REJECT"),
    ("HTTPDNS 拦截器", "modules/kelee/kelee-HTTPDNS拦截器-1565be1f.lpx", "73 条纯域名 REJECT"),
    ("百度贴吧", "modules/qingrex-loonkisssurge-333395eec1.sgmodule", "9 接口，各源最高"),
]

RULES = [
    ("广告总表", "curated/rules/ad-full.yaml", "5 份广告表全并集 + 修 IP 写法，一个文件覆盖 100%"),
    ("国内直连", "curated/rules/cn-full.yaml", "域名 108,073 + IP 段 17,958 合一"),
    ("流媒体补充", "curated/rules/extra-media.yaml", "Paramount+/Peacock/Discovery+/ViuTV/HBO Asia…"),
    ("社交补充", "curated/rules/extra-social.yaml", "Reddit/Pinterest/Tumblr/Slack/Notion + TG/Twitter 全量"),
    ("开发补充", "curated/rules/extra-dev.yaml", "npm/Docker/GitLab/Dropbox/Cloudflare"),
    ("云服务补充", "curated/rules/extra-cloud.yaml", "AWS/Oracle/Google Drive/iCloud"),
    ("游戏补充", "curated/rules/extra-game.yaml", "Steam/Epic/PSN/Xbox/Nintendo/Riot"),
    ("代理兜底", "rules/shunt-rules/loon/Global.lsr", "35,888 条，占代理表并集 60.2%"),
    ("分流骨架", "rules/quixoticheart-egern/", "全库唯一 Egern 原生 YAML，25 个独有结构件"),
]


def build_manifest():
    def pack(items, src):
        return [{"app": a, "path": f, "url": BASE + urllib.parse.quote(f, safe="/"),
                 "coverage": c, "reason": r, "source": src} for a, f, c, r in items]

    doc = {
        "_comment": "精选清单：由 curated/tools/build.py 从 1,753 个模块 / 2,276 个规则集的实测对比中生成",
        "_generated": "2026-10-24",
        "_repo": "https://github.com/tuohai57/egern-mirror",
        "_base_url": BASE,
        "_priority_note": "Egern 优先级：模块 > 本地配置；模块之间、规则之间均为「上面的优于下面」，纯列表序。",
        "module_order": [
            "1. curated/modules/00-override.yaml（必须最上）",
            "2. 单 App 精细改写（loonlab / kelee / fmz200）",
            "3. 墨鱼去开屏",
            "4. 聚合包 blockAds.module",
            "5. 广告平台拦截器",
            "6. HTTPDNS 拦截器（最下）",
        ],
        "rule_order": [
            "1. private / Lan -> DIRECT",
            "2. ad-full.yaml -> REJECT（DNS 层也挂一份 reject）",
            "3. 专项直连（apple-cn/microsoft-cn/socialmedia-cn/games-cn/douyin/bilibili/steamcn）",
            "4. 专项代理（ai/netflix/disney/…/extra-media/extra-social/extra-dev/extra-cloud）",
            "5. iplocation-direct / speedtest / cdn -> DIRECT",
            "6. cn-full.yaml -> DIRECT",
            "7. Global.lsr -> PROXY",
            "8. geoip CN -> DIRECT",
            "9. FINAL -> PROXY",
        ],
        "modules": pack(LOONLAB, "loonlab") + pack(FMZ, "fmz200") + pack(KELEE, "kelee"),
        "tools": [{"app": a, "path": f, "url": BASE + urllib.parse.quote(f, safe="/"), "reason": r}
                  for a, f, r in TOOLS],
        "rules": [{"layer": a, "path": f, "url": BASE + urllib.parse.quote(f, safe="/"), "reason": r}
                  for a, f, r in RULES],
    }
    dst = os.path.join(CUR, "manifest.json")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return len(doc["modules"]) + len(doc["tools"]), dst


def main():
    n, dst = build_ad_full()
    print("[1/6] ad-full.yaml       %d 条 -> %s" % (n, os.path.relpath(dst, ROOT)))
    n, dst = build_cn_full()
    print("[2/6] cn-full.yaml       %d 条 -> %s" % (n, os.path.relpath(dst, ROOT)))
    for name, n, dst in build_extra():
        print("[3/6] %-20s %d 条 -> %s" % (name + ".yaml", n, os.path.relpath(dst, ROOT)))
    n, dst = build_qingr_index()
    print("[4/6] qingr-index.md     %d 个文件" % n)
    n, dst = build_manifest()
    print("[5/6] manifest.json      %d 条推荐" % n)
    print("[6/6] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())

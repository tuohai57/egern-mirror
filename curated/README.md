# curated —— 从 1,753 个模块 / 2,276 个规则集里挑出来的那 40 个

这个目录不是镜像，是**结论**。

原仓库把能找到的 Egern 资源全量抓了下来（131 MB、4,061 个文件），好处是齐全，坏处是没法用：1,753 个模块里有 310 个近似重复、668 个 Clash 规则对 Egern 完全无效、同一个 App 最多有 8 个不同来源的实现。

这里的东西是**逐个解析内容后算出来的**——不是按文件名归类，是按「被拦截的 host + path 集合」做跨来源并集/交集/独有增量，再抽样逐条读实现。

---

## 一、先记住三条优先级（搞错这三条，下面全白搭）

| 规则 | 含义 |
|---|---|
| **模块 > 本地配置** | 模块里的 `[Rule]` 压过你本地写的任何规则，**包括 `DIRECT`** |
| **模块之间：上面的 > 下面的** | 同一 URL 被两个模块改写，上面的生效，下面的**根本不执行** |
| **规则之间：上面的 > 下面的** | 纯列表序，**没有"更具体者优先"** |

推论（很重要）：

1. **本地规则救不回模块误拦的域名。** 想让某个域名通，只能改模块、关模块，或者——用 `curated/modules/00-override.module` 放在更上面。
2. **模块顺序 = 实现选择权。** 不用为了"避免冲突"去关模块，排序就够了。关的理由只是省 MITM 开销。
3. **纯域名 REJECT 不能放最上面。** 它会把下面所有改写模块掐死（请求发不出去，改写永远没机会跑）。按"改写占比"从高到低排。

---

## 二、模块挂载顺序（自上而下）

```
1. curated/modules/00-override.module      ← 必须第一位，否则无效
2. 单 App 精细改写（loonlab / kelee）      ← 见 manifest.json 的 modules
3. 墨鱼去开屏
4. 聚合包 blockAds.module
5. 广告平台拦截器
6. HTTPDNS 拦截器                          ← 纯 REJECT，最下面
```

各层的"改写占比"实测（改写条目 / 改写+规则）：

| 层 | 改写占比 |
|---|---|
| 墨鱼去开屏 | 99% |
| 微信 / 微信小程序 | 94-95% |
| 单 App 精细改写 | 70-100% |
| 聚合包 blockAds | 33% |
| MyBlockAds | 21% |
| HTTPDNS 拦截 | 8-40% |
| 广告平台拦截器 | ~1% |

顺带一个好消息：kelee / loonlab / qingr 的**改写目标 host 与聚合包的 REJECT 域名重叠 0%**（实测 695/0、654/0、1,490/0），所以"改写在上、拦截在下"这两层是正交的，不会互相掐死。

---

## 三、规则挂载顺序（自上而下）

```
1. private / Lan                          → DIRECT
2. AdvertisingTest + AdGuardSDNSFilter    → REJECT
3. apple-cn / microsoft-cn / socialmedia-cn / games-cn / douyin / bilibili → DIRECT
4. ai / netflix / disney / youtube / spotify / socialmedia → 策略组
5. curated/rules/cn-full.yaml             → DIRECT
6. Global.lsr                             → PROXY
7. GEOIP, CN                              → DIRECT
8. FINAL                                  → PROXY
```

为什么是这个顺序（实测遮蔽数据）：

| 冲突 | 数量 | 说明 |
|---|---|---|
| 广告 ∩ 国内直连 | 101 | 都是垃圾站（`0ka.com`、`23txt.com`）。广告在前 → REJECT，可接受 |
| 广告 ∩ 代理 | 305 | 广告在前 → REJECT 而不是代理，正确 |
| 代理 ∩ 国内直连 | 20 | 含 `129.226.0.0/16`、`2mdn-cn.net`。**必须直连在前**，否则 20 条国内 IP 被代理 |
| `cdn.yaml` ∩ 广告 | 120 | cdn 若排在广告前 → 120 个广告 CDN 走 DIRECT，漏广告 |
| `httpdns.yaml` ∩ 广告 | 43 | 58 条里 43 条重复，放广告后面才有效 |

---

## 四、这个目录里有什么

```
curated/
├── README.md                     ← 本文件
├── Profile.yaml                  ← ★ 完整可用的 Egern 配置（20 组 / 305 规则 / 64 模块）
├── 对比-v9.9与新配置.md            ← 与上一版精修配置的逐项对比
├── manifest.json                 ← 机器可读的精选清单（App → 文件 → 理由 → 现成 URL）
├── modules/
│   ├── 00-override-20261024.yaml  ← 自建：优先级补丁（Egern 原生 YAML）
│   └── 00-override.module        ← 同上，Surge 格式版（给需要 .module 的场景）
├── rules/
│   ├── ad-full.yaml              ← 自建：5 份广告表全并集（381,808 条）+ 修 IP 写法
│   ├── cn-full.yaml              ← 自建：国内直连「域名 + IP 段」合一
│   ├── extra-media.yaml          ← 自建：流媒体补充（Paramount+/Peacock/Discovery+/ViuTV…）
│   ├── extra-social.yaml         ← 自建：社交补充（Reddit/Pinterest/Tumblr/Slack/Notion）
│   ├── extra-dev.yaml            ← 自建：开发补充（npm/Docker/GitLab/Dropbox/Cloudflare）
│   ├── extra-cloud.yaml          ← 自建：云服务（AWS/Oracle/Google Drive/iCloud）
│   ├── extra-game.yaml           ← 自建：游戏（Steam/Epic/PSN/Xbox/Nintendo/Riot）
│   └── qingr-index.md            ← 自建：506 个编码文件名的解码索引
└── tools/
    └── build.py                  ← 上面这些的生成脚本（只读镜像，可重跑）
```

### `Profile.yaml` —— 直接可用的完整配置

把上面第二节、第三节的顺序**全部落进了一份配置**，不用你自己拼：

| 部分 | 内容 |
|---|---|
| 全局 | `block_quic: true`（QUIC 是"规则不生效"第一大原因）、`hijack_dns`（防 HTTPDNS 绕过）、`include_apns`（防推送断） |
| DNS | 国内/国外双上游 + `cn-full.yaml` 参与 DNS 分流 + `proxy_nameservers` 防环路 + `block_ips` 只滤 3 个最保险的 |
| 策略组 | 20 个：订阅 → 兜底 → 5 个地区组 → 广告拦截开关 → AI/流媒体/TikTok/社交/Telegram/Google/Microsoft/Apple/开发/支付/游戏/国内 |
| 规则 | 305 条（57 个规则集 + 246 条手写白名单），每层都标了"为什么在这个位置" |
| MITM | 只写 excludes（12 条银行/政务），其余由模块自动合并 |
| 模块 | 64 个（57 个默认启用），每个都标了覆盖度 / 外链 JS / MITM 台数 |

**唯一要改的**：`policy_groups` → `订阅` → `urls` 里的订阅链接。

首次导入约需拉取 12.3 MB（57 个规则集 + 64 个模块，其中 ad-full 一个文件 7.7 MB），建议在 Wi-Fi 下导入。

### `modules/00-override.module`

全库模块的 `[Rule]` 共涉及 3,310 个域名，其中 **112 个同时出现在国内直连表里**——本该直连却被模块强制 REJECT，而且**本地规则改不动**。

这个模块只捞回其中确实会**功能性损坏**的（在线客服 SDK、Apple 系统统计），双用途的（mob.com 分享 / getui 推送）放在注释里让用户自己权衡，纯广告 SDK 一律不动并在文件末尾列出清单。

不含 `[Script]`、不含 MITM，纯规则，零开销。

### `rules/cn-full.yaml`

原方案要同时挂 `quixoticheart-egern/cn.yaml`（108,073 条域名）和 `cncidr.yaml`（17,958 条 IP 段）——**只挂前者，纯 IP 直连的流量会掉到代理**。

合并成一个文件，126,031 条，Egern 原生 YAML，`no_resolve: true`。

### `rules/qingr-index.md`

`modules/qingr/` 下 506 个文件名是**字面量百分号编码**（仓库里文件真的叫 `%E7%9F%A5%E4%B9%8E...`），拼 jsDelivr URL 必须把 `%` 再转义成 `%25` 才不 404。这份索引给了解码名 + 可直接用的 URL 路径。

**但结论是：qingr 只当备份，日常用 kelee / loonlab / fmz200。**

---

## 五、为什么没有重写那些大表

试过，结论是**上游已经做得比我好**：

- `AdvertisingTest.lsr` 318,626 条：`DOMAIN` 被 `DOMAIN-SUFFIX` 覆盖的 **0 条**、后缀互相覆盖 **0 条**——已经是去冗余后的最优形态
- 唯一能挑出来的毛病是 285 条把 IP 写成了 `DOMAIN,1.2.3.4`（占 0.09%），改了收益也小于维护成本

所以大表直接用原镜像，我只补了它缺的那块（`cn-full.yaml` 的域名+IP 合一）。

---

## 六、重新生成

```bash
python curated/tools/build.py
```

只读 `rules/quixoticheart-egern/` 和 `modules/qingr/`，不修改任何镜像文件。改了上游镜像后重跑即可。

---

## 七、已知局限

1. **`cn-full.yaml` 是快照**，不随上游自动更新。上游更新后请重跑 `build.py`。
2. **`00-override.module` 的取舍是我做的判断**：`qiyukf.com`、`app-analytics-services.com` 默认放行，其余注释。你觉得不对就改注释。
3. **Loon 插件导入 Egern 走转换层**：kelee / loonlab 的 `reject_dict(200)`、`response.json.jq()` 不是 Surge 原生写法。如果某模块导入后行为异常，优先换同覆盖的 `.sgmodule` 版本。
4. **外链 JS 是静默失效点**：全库 214 个模块引用外部脚本（raw.githubusercontent、kelee.one…），镜像只固定了模块文件本身。脚本域名挂了 = 模块看着开着、其实什么都没做。

---

*生成日期：2026-10-24 ｜ 数据来源：本仓库 main 分支快照*

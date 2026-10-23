# yfamilys.com 规则集镜像

源站：https://yfamilys.com/rule
镜像时间：2026-10-24
镜像内容：源站全部 766 个 `.list`（完整镜像）

## 为什么要镜像

源站开在 Cloudflare 上，全站启用了 JS 挑战（`Just a moment...`）。实测：

| 请求方式 | 状态码 |
|---|---|
| 浏览器 UA + 完整请求头 | **403** |
| `Egern/1.11` UA | **403** |
| `Surge/5.0` UA | **403** |
| `Shadowrocket/2.2.36` UA | **403** |
| 换 `Accept: text/plain` / `application/octet-stream` | **403** |
| 加 `?v=1` 查询参数 | **403** |
| `/IMG/arrow.png` | 200（只放行静态图片） |

代理客户端走 URLSession，**不执行 JS**，永远过不了挑战。直接写源站 URL 进配置只会全部加载失败。

源站也没有 GitHub 原始仓库，没有可绕过的上游。

所以这里做一份镜像，走 jsDelivr 就能正常订阅。

## 用法

```
https://cdn.jsdelivr.net/gh/tuohai57/egern-mirror@main/rules/yfamilys/<文件名>.list
```

Egern 配置写法：

```yaml
- rule_set:
    name: 中行
    match: https://cdn.jsdelivr.net/gh/tuohai57/egern-mirror@main/rules/yfamilys/BOC.list
    policy: DIRECT
    update_interval: 86400
```

格式是 Surge 的 `.list`（`DOMAIN-SUFFIX,x` 逗号分隔行），Egern 原生支持——
本仓库 `rules/` 下已有的 15 个 `deezertidal` 列表就是这个格式，已在配置中正常工作。

## 分级

### A 级 — 质量合格，可直接引用

**银行 / 金融**（本镜像最有价值的部分，配置里原本 0 条规则）

| 文件 | 条数 | 覆盖 |
|---|---|---|
| `ICBC.list` | 58 | 工行全球分支（icbc.co.jp / icbc.de / icbcstandard / icbcasia…） |
| `CMB.list` | 38 | 招行系（⚠️ 见「已知问题 4」） |
| `BOC.list` | 22 | 中行系（含 bochk 中银香港、bocifunds 中银基金、bocaviation） |
| `CCB.list` | 18 | 建行系（含 ccbfund / ccbtrust / ccbleasing） |
| `UnionPay.list` | 16 | 银联系（chinapay / cup.com.cn / unionpayintl） |
| `BOCOM.list` | 6 | 交行（含 .au / .mo / .tw 三个境外域） |
| `ABC.list` | 6 | 农行 |
| `PSBC.list` | 3 | 邮储 |

**细分类**

| 文件 | 条数 | 说明 |
|---|---|---|
| `12306.list` | 15 | 铁路系（95306 / cre.cn 中车 / crscl 中铁特货 / peoplerail） |
| `ai.list` | 41 | AI 服务精确域名 |
| `Anthropic.list` | 3 | anthropic.com / claude.ai / b-cdn |
| `Grok.list` | 2 | grok.com / x.ai |

### B 级 — 用前必须改

| 文件 | 问题 | 改法 |
|---|---|---|
| `ASN-CN.list` | 5,231 条 `IP-ASN,xxxxx`，**全部缺 `no-resolve`** | 每行补 `,no-resolve` |
| `ASN-lite.list` | 691 条，同上 | 同上 |
| `IPs-CN.list` | 11,701 条 `IP-CIDR`，全部缺 `no-resolve`；且条数少于现有 `cncidr.yaml` 的 17,958 条 | 不建议用 |

### C 级 — 不要用

| 文件 | 原因 |
|---|---|
| `China.list` | 见「已知问题 1」 |
| `Global.list` | 见「已知问题 2」 |
| `AntiAD.list` | 303,395 条 / 10 MB，与现有 `adrules.yaml`（210,645 条）+ ADLite + AdvertisingLite 高度重复，边际收益接近 0，内存翻倍 |

## 已知问题

### 1. `China.list` 会毁掉分流

```
DOMAIN-SUFFIX,cn          ← 所有 .cn 直连
DOMAIN-SUFFIX,ms          ← 所有 .ms 直连
DOMAIN-KEYWORD,microsoft  ← 所有含 microsoft 的域名直连
DOMAIN-KEYWORD,baidu / alipay / aliyun / taobao / alicdn / beplay / officecdn
DOMAIN-KEYWORD,.tmall.com ← 带点的关键词，写法本身就不对
USER-AGENT,QQ* / WeChat* / MicroMessenger* / Microsoft* / cmb* / hide* / balls*
```

`DOMAIN-SUFFIX,cn` 一条就足够把 `.cn` 下所有需要代理的流量打成直连。
`USER-AGENT,Microsoft*` 会命中所有微软 UA，包括该走代理的。`hide*`、`balls*` 这种短词更不用说。

**放进规则链前必须逐条重写，不能直接用。**

### 2. `Global.list` 里的 `DOMAIN-KEYWORD,gle`

```
DOMAIN-KEYWORD,amazon
DOMAIN-KEYWORD,aws
DOMAIN-KEYWORD,blogspot
DOMAIN-KEYWORD,gle       ← 三字母，会命中 bugle / single / angle / eagle / jungle…
DOMAIN-KEYWORD,goog
DOMAIN-KEYWORD,google
DOMAIN-KEYWORD,phobos
```

`google` / `goog` 已经把该覆盖的覆盖了，`gle` 纯粹是副作用。要用就先删这一行。

### 3. `IPs-CN` / `ASN-CN` 全部缺 `no-resolve`

IP 类规则不带 `no-resolve`，意味着每条都要先做一次 DNS 解析。
11,701 条 CIDR + 5,231 条 ASN = 近 1.7 万次解析机会。

对照：本仓库自己的 `quixoticheart-rule-set-cncidr.yaml` 首行就是 `no_resolve: true`。

### 4. `CMB.list` 混进了 15 条非招行域名

```
cnki.net  cnkidoi.*  wuxizazhi.*  chndoi.*  bbf.org.cn  bjsbnet.com
```

`cnki.net` 是**中国知网**，不是招商银行。作为 MITM excludes 用无害，但拿它做分流会把知网误分类。

同批还有 `ccblife-test.com.cn`、`test-cignacmb.com`、`cmbuat.com` 三个测试域，`ICBC.list` 里有一条裸 TLD `DOMAIN-SUFFIX,icbc`（非法写法）。

## 与现有配置的关系

这套镜像**不替代**现有任何规则集，只补充现有配置没有覆盖的部分：

| 类别 | 现有配置 | yfamilys | 结论 |
|---|---|---|---|
| 代理域名 | `proxy.yaml` 30,102 | `Global.list` 31,913 | 持平，无增量 |
| 国内直连 | `cn.yaml` 108,073 | `China.list` 31 | 现有更多 |
| 去广告 | `adrules` 210,645 | `AntiAD` 303,395 | 现有够用 |
| 国内 IP | `cncidr` 17,958 | `IPs-CN` 11,701 | 现有更多 |
| ASN | 0 | `ASN-CN` 5,231 | 潜在增量 |
| 银行 | 0 条规则 | 145 条 | **真缺口** |

## 覆盖状态

**766 / 766 全部已镜像**，与源站一一对应。

抓取过程中源站的 5 个大文件（`AntiAD` 9.7MB、`ADLite` 1.9MB、`Global` 0.9MB、`ChinaMaxNoMedia` 0.4MB、`IPs-CN` 0.3MB）单独校验过条数一致：
AntiAD 303,395 / ADLite 60,294 / Global 31,920 / IPs-CN 11,695 / ASN-CN 5,231 / ASN-lite 691。

## 维护

源站被 Cloudflare 挡住，无法用 GitHub Actions 定时同步（Actions 的请求同样过不了 JS 挑战）。
更新方式：本地手动抓取后重新提交。抓取脚本见 `scripts/fetch-yfamilys.py`。

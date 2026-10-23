# egern-mirror 分类镜像

共 **23** 个分类目录、**3,889** 个文件、**131.5 MB**。

> **只想用、不想挑？** 看 [`curated/`](curated/) —— 从 1,753 个模块 / 2,276 个规则集里逐个解析内容后挑出的那 40 个，
> 附带正确的挂载顺序、优先级说明，以及三份自建的修复件（优先级补丁模块、国内直连域名+IP 合一、qingr 文件名索引）。

| 分类 | 目录 | 文件数 | 大小 | 来源 |
|---|---|---|---|---|
| 其他 | `.git` | 7 | 0.09 MB | - |
| 其他 | `.git/hooks` | 14 | 0.03 MB | - |
| 其他 | `.git/info` | 2 | 0.00 MB | - |
| 其他 | `.git/logs` | 1 | 0.00 MB | - |
| 其他 | `.git/logs/refs/heads` | 1 | 0.00 MB | - |
| 其他 | `.git/logs/refs/remotes/origin` | 2 | 0.00 MB | - |
| 其他 | `.git/objects/info` | 1 | 0.00 MB | - |
| 其他 | `.git/objects/pack` | 4 | 7.24 MB | - |
| 其他 | `.git/refs/heads` | 1 | 0.00 MB | - |
| 其他 | `.git/refs/remotes/origin` | 2 | 0.00 MB | - |
| 其他 | `modules` | 77 | 0.93 MB | - |
| 模块 | `modules/fmz200` | 737 | 1.13 MB | fmz200/wool_scripts |
| 模块 | `modules/kelee` | 275 | 0.53 MB | hub.kelee.one |
| 模块 | `modules/loon-script` | 22 | 0.06 MB | Tartarus2014/Loon-Script |
| 模块 | `modules/loonlab` | 135 | 0.79 MB | loonlab.103516.xyz |
| 模块 | `modules/qingr` | 506 | 1.57 MB | surge.qingr.moe |
| 其他 | `rules` | 62 | 9.61 MB | - |
| 规则 | `rules/loon-script` | 25 | 0.05 MB | Tartarus2014/Loon-Script |
| 规则 | `rules/loonkit` | 34 | 5.70 MB | YohakuSama/loonkit |
| 规则 | `rules/quixoticheart-egern` | 52 | 8.17 MB | QuixoticHeart/rule-set |
| 规则 | `rules/shunt-rules/clash` | 668 | 51.24 MB | luestr/ShuntRules |
| 规则 | `rules/shunt-rules/loon` | 668 | 46.88 MB | luestr/ShuntRules |
| 规则 | `rules/yfamilys` | 767 | 15.41 MB | yfamilys.com |

## 用法

所有文件走 jsDelivr：`https://cdn.jsdelivr.net/gh/tuohai57/egern-mirror@main/<path>`

例：
```
https://cdn.jsdelivr.net/gh/tuohai57/egern-mirror@main/rules/quixoticheart-egern/adrules.yaml
https://cdn.jsdelivr.net/gh/tuohai57/egern-mirror@main/modules/kelee/kelee-微博去广告-xxxxxxxx.lpx
```

## 注意

- 完整文件清单见 `manifest-all.json`
- `rules/shunt-rules/loon` 与 `clash` 是同一批规则的两个格式，二选一即可
- Loon `.lpx` 与 Surge `.sgmodule` 都是模块格式，Egern 都能直接导入

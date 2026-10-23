#!/usr/bin/env python3
"""
yfamilys.com 规则集抓取脚本

源站 https://yfamilys.com/rule 全站启用 Cloudflare JS 挑战，代理客户端无法直接订阅。
本脚本通过 r.jina.ai（会执行 JS）绕过挑战，把 766 个 .list 抓到本地。

用法：
    python fetch-yfamilys.py <输出目录> [--proxy http://127.0.0.1:7897]

注意：
- r.jina.ai 免费版有 per-IP 限速（约 20 RPM），并发必须 <= 4，否则大量 429
- 脚本支持断点续抓：已存在且非空的文件会跳过
- 抓完检查：银行 8 个文件条数应为 ICBC 58 / CMB 38 / BOC 22 / CCB 18 /
  UnionPay 16 / BOCOM 6 / ABC 6 / PSBC 3
"""
import os, re, sys, time, json, argparse
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

INDEX = "https://yfamilys.com/rule"
WORKERS = 4          # 超过 4 会触发 jina 的 per-IP 限速
RETRIES = 6

VALID = re.compile(r'^(DOMAIN|IP-CIDR|IP-ASN|IP6-CIDR|IP-CIDR6|URL-REGEX|USER-AGENT|#)', re.M)


def clean(txt: str) -> str:
    """剥离 r.jina.ai 的包装头（Title / URL Source / Markdown Content）"""
    marker = 'Markdown Content:'
    if marker in txt:
        return txt.split(marker, 1)[1].lstrip('\n')
    lines = txt.split('\n')
    if lines and lines[0].startswith('Title:'):
        i = 0
        while i < len(lines) and lines[i].strip() != '':
            i += 1
        return '\n'.join(lines[i:]).lstrip('\n')
    return txt.lstrip('\n')


def fetch(name: str, outdir: str, opener) -> tuple:
    path = os.path.join(outdir, f"{name}.list")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return (name, 'SKIP')
    url = f"https://r.jina.ai/{INDEX}/{name}.list"
    last = 'UNKNOWN'
    for att in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with opener.open(req, timeout=180) as r:
                raw = r.read().decode('utf-8', errors='ignore')
            if 'RateLimitTriggeredError' in raw or '"code":429' in raw:
                last = 'RATE'
                time.sleep(4 + att * 4)
                continue
            body = clean(raw)
            if not body.strip():
                last = 'EMPTY'
                time.sleep(2 + att * 2)
                continue
            if not VALID.search(body):
                last = 'BADFMT'
                time.sleep(2)
                continue
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(body if body.endswith('\n') else body + '\n')
            return (name, 'OK')
        except urllib.error.HTTPError as e:
            last = f'HTTP{e.code}'
            time.sleep(4 + att * 4)
        except Exception as e:
            last = type(e).__name__
            time.sleep(3 + att * 3)
    return (name, last)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir')
    ap.add_argument('--proxy', default='http://127.0.0.1:7897')
    ap.add_argument('--names', help='文件名清单（每行一个），缺省则从索引页解析')
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    handler = urllib.request.ProxyHandler({'http': args.proxy, 'https': args.proxy}) if args.proxy else urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)

    if args.names:
        names = [l.strip() for l in open(args.names, encoding='utf-8') if l.strip()]
    else:
        # 索引页本身也被 CF 挡住，需人工提供清单
        sys.exit('请用 --names 提供文件名清单（索引页同样被 CF 挑战挡住）')

    t0 = time.time()
    for rnd in range(1, 15):
        todo = [n for n in names
                if not (os.path.exists(os.path.join(args.outdir, f"{n}.list"))
                        and os.path.getsize(os.path.join(args.outdir, f"{n}.list")) > 0)]
        if not todo:
            print(f"全部完成：{len(names)} 个，用时 {time.time()-t0:.0f}s")
            break
        print(f"[第{rnd}轮] 待抓 {len(todo)}", flush=True)
        ok = 0
        stat = {}
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            for name, st in zip(todo, ex.map(lambda n: fetch(n, args.outdir, opener), todo)):
                if st in ('OK', 'SKIP'):
                    ok += 1
                else:
                    stat[st] = stat.get(st, 0) + 1
        print(f"  ok={ok} 失败={stat}  已用 {time.time()-t0:.0f}s", flush=True)
        if ok == 0 and rnd > 2:
            break
        time.sleep(3)

    left = [n for n in names
            if not (os.path.exists(os.path.join(args.outdir, f"{n}.list"))
                    and os.path.getsize(os.path.join(args.outdir, f"{n}.list")) > 0)]
    print(f"\n最终：{len(names)-len(left)}/{len(names)}")
    if left:
        print("缺失:", left[:50])
        json.dump(left, open('missing.json', 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    main()

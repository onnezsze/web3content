#!/usr/bin/env python3
"""健康检查：并发 ping 所有数据源，5s 超时，输出健康地图 JSON"""
import sys, os, json, time, concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources.base import Source

PROBES = {
    "coingecko": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
    "gateio": "https://data.gateapi.io/api2/1/tickers",
    "okx": "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
    "binance": "https://api.binance.com/api/v3/ping",
    "rss_cointelegraph": "https://cointelegraph.com/rss",
    "rss_coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "rss_theblock": "https://www.theblock.co/rss.xml",
    "wscn": "https://api-one-wscn.awtmt.com/apiv1/search/quick?keyword=BTC",
    "eastmoney": "https://np-listapi.eastmoney.com/comm/web/getFastNewsList?client=web&biz=web_724&fastColumn=102&sortEnd=now&pageSize=1&req_trace=1",
    "telegram": "https://t.me/s/wublock",
    "jina": "https://r.jina.ai/https://www.binance.com/zh-CN/square",
    "laohu": "https://www.laohu8.com/community",
}


def ping(name, url):
    t0 = time.time()
    s = Source()
    try:
        raw = s.http_get(url, timeout=5)
        ms = int((time.time() - t0) * 1000)
        return {"source": name, "status": "ok", "latency_ms": ms, "bytes": len(raw)}
    except Exception as e:
        return {"source": name, "status": "failed", "latency_ms": int((time.time() - t0) * 1000), "error": str(e)[:80]}


def main():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(ping, n, u): n for n, u in PROBES.items()}
        try:
            for f in concurrent.futures.as_completed(futs, timeout=10):
                results.append(f.result())
        except concurrent.futures.TimeoutError:
            pass

    health = {r["source"]: r for r in results}
    print(json.dumps({"preflight_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                      "source_health": health}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

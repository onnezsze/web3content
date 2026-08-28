"""新闻源：RSS 主源 + 华尔街见闻 fallback + 东方财富 fallback"""
from .base import Source
from xml.etree import ElementTree as ET
import html, re, urllib.parse
import concurrent.futures


class RSSNews(Source):
    name = "rss"

    def fetch(self):
        try:
            feeds = [
                ("cointelegraph", "https://cointelegraph.com/rss"),
                ("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
                ("theblock", "https://www.theblock.co/rss.xml"),
            ]
            out = []
            for src, url in feeds:
                try:
                    raw = self.http_get(url)
                    root = ET.fromstring(raw)
                    for item in root.iter("item"):
                        title = (item.findtext("title") or "").strip()
                        pub = item.findtext("pubDate") or ""
                        if title:
                            out.append({
                                "title": html.unescape(title),
                                "src": src, "published_at": pub,
                                "text": html.unescape(title),
                                "url": (item.findtext("link") or "").strip(),
                            })
                except Exception:
                    continue
            if out:
                return self.ok(out)
            return self.fail("all rss empty")
        except Exception as e:
            return self.fail(e)


class WSCN(Source):
    """华尔街见闻快讯流（global channel）"""
    name = "wscn"

    def fetch(self):
        try:
            url = "https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&limit=50"
            data = self.http_json(url, timeout=8)
            items = data.get("data", {}).get("items", [])
            out = []
            for it in items[:25]:
                text = it.get("content") or it.get("title") or ""
                if text:
                    out.append({
                        "title": text.strip()[:150],
                        "src": "wscn", "published_at": str(it.get("display_time", "")),
                        "text": text.strip(),
                    })
            if out:
                return self.ok(out)
            return self.fail("wscn lives empty")
        except Exception as e:
            return self.fail(e)


class EastMoneyNews(Source):
    """东方财富快讯（加密+AI+宏观相关过滤）"""
    name = "eastmoney"

    CRYPTO_KW = ["比特币", "加密", "BTC", "ETH", "区块链", "web3", "coin", "crypto",
                 "稳定币", "ETF", "etf", "数字货币", "虚拟货币", "算力", "GPU",
                 "芯片", "AI", "人工智能", "配售", "IPO", "上市", "美股", "纳斯达克"]

    def fetch(self):
        try:
            url = ("https://np-listapi.eastmoney.com/comm/web/getFastNewsList"
                   "?client=web&biz=web_724&fastColumn=102&sortEnd=now&pageSize=50&req_trace=1")
            data = self.http_json(url, timeout=8)
            items = data.get("data", {}).get("fastNewsList", [])
            out = []
            for it in items:
                summary = (it.get("summary") or "").strip()
                if not summary:
                    continue
                low = summary.lower()
                if any(kw.lower() in low for kw in self.CRYPTO_KW):
                    out.append({
                        "title": summary[:120],
                        "src": "eastmoney", "published_at": it.get("showTime", ""),
                        "text": summary,
                        "url": str(it.get("url") or it.get("link") or it.get("fullUrl") or "")[:300],
                    })
            if out:
                return self.ok(out)
            return self.fail("no crypto items in eastmoney")
        except Exception as e:
            return self.fail(e)


def fetch_news_chain():
    """并发跑所有新闻源，合并输出（多源才能交叉验证）"""
    all_data = []
    statuses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(cls().fetch): cls.__name__ for cls in (RSSNews, EastMoneyNews)}
        for f in concurrent.futures.as_completed(futs, timeout=15):
            name = futs[f]
            try:
                r = f.result()
                statuses[name] = r["status"]
                if r["status"] == "ok":
                    all_data.extend(r["data"])
            except Exception as e:
                statuses[name] = f"err:{str(e)[:30]}"
    if all_data:
        return {"status": "ok", "data": all_data, "source_status": statuses}
    return {"status": "failed", "data": [], "source_status": statuses}

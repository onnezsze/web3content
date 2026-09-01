"""宏观/传统金融源：东方财富快讯 + 华尔街见闻快讯流 + 老虎社区"""
from .base import Source
import html, re, urllib.parse
import concurrent.futures


class EastMoneyMacro(Source):
    """东方财富全球宏观快讯"""
    name = "eastmoney_macro"

    def fetch(self):
        try:
            url = ("https://np-listapi.eastmoney.com/comm/web/getFastNewsList"
                   "?client=web&biz=web_724&fastColumn=102&sortEnd=now&pageSize=20&req_trace=1")
            data = self.http_json(url, timeout=8)
            items = data.get("data", {}).get("fastNewsList", [])
            out = []
            for it in items:
                summary = (it.get("summary") or "").strip()
                if summary:
                    out.append({
                        "src": "eastmoney", "text": summary,
                        "time": it.get("showTime", ""),
                    })
            if out:
                return self.ok(out)
            return self.fail("empty")
        except Exception as e:
            return self.fail(e)


class WSCNLive(Source):
    """华尔街见闻快讯流（global channel）"""
    name = "wscn_live"

    def fetch(self):
        try:
            url = "https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&limit=50"
            data = self.http_json(url, timeout=8)
            out = []
            items = data.get("data", {}).get("items", [])
            if not items:
                items = data.get("data", [])
            for it in (items or [])[:100]:
                text = it.get("content") or it.get("title") or ""
                if text:
                    out.append({
                        "src": "wscn", "text": text.strip(),
                        "time": it.get("display_time", ""),
                    })
            if out:
                return self.ok(out)
            return self.fail("empty")
        except Exception as e:
            return self.fail(e)


def fetch_macro_chain():
    """并发跑所有宏观源，合并输出"""
    all_data = []
    statuses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(cls().fetch): cls.__name__ for cls in (EastMoneyMacro, WSCNLive)}
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

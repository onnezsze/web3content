"""华尔街见闻·资讯源：https://wallstreetcn.com/news/global
抓取 华尔街见闻 全球资讯/快讯流(标题+链接+时间)，供「媒体」板块使用。
数据来自 api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel
fail-soft。
"""
from .base import Source
import re, html, datetime, time


class WSCNNews(Source):
    name = "wscn_news"

    def fetch(self):
        try:
            url = ("https://api-one-wscn.awtmt.com/apiv1/content/lives"
                   "?channel=global-channel&limit=80")
            data = self.http_json(url, timeout=10, headers={'Referer': 'https://wallstreetcn.com/news/global'})
            items = (data.get("data", {}) or {}).get("items", [])
            out, seen = [], set()
            for it in (items or []):
                title = (it.get("title") or it.get("content") or "").strip()
                title = html.unescape(re.sub(r"<[^>]+>", "", title)) if title else ""
                if len(title) < 8 or title in seen:
                    continue
                seen.add(title)
                uri = it.get("uri") or ""
                if not uri and it.get("id"):
                    uri = "https://wallstreetcn.com/livenews/" + str(it.get("id"))
                # 发布时间：把 UNIX 时间戳/数字统一转成 ISO 字符串，确保前端能显示
                pub = it.get("display_time", "") or it.get("created_at", "") or ""
                if pub and str(pub).isdigit():
                    try:
                        # 用 UTC 时间格式化(系统时区无关), 前端 fmtCardTime 再 +8 转北京时间
                        pub = datetime.datetime.utcfromtimestamp(int(pub)).strftime("%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        pub = ""
                out.append({
                    "title": title[:200], "src": "华尔街见闻",
                    "text": title,
                    "url": uri,
                    "published_at": pub,
                })
            if out:
                return self.ok(out[:100])
            return self.fail("empty")
        except Exception as e:
            return self.fail(e)


def fetch_wscn_news_chain():
    r = WSCNNews().fetch()
    if r["status"] == "ok":
        return {"status": "ok", "data": r["data"], "source_status": {"wscn_news": "ok"}}
    return {"status": "failed", "data": [], "source_status": {"wscn_news": str(r.get("error", ""))[:30]}}

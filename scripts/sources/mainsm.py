"""主流/综合媒体源：Google News 中文 RSS（关键词检索）

覆盖 孙宇晨/加密/美股 等被主流媒体报道的社会、娱乐、财经热点——
如联合早报对"孙宇晨景甜事件"的深度报道、CZ 出面劝阻等。
此类内容在加密源(金十/链捕手/3RSS)常缺席，靠本源补上。
fail-soft：失败返回 status=failed、data=[]，不阻断其它源。
"""
from .base import Source
import urllib.parse, re, html
from xml.etree import ElementTree as ET

QUERIES = ["孙宇晨", "加密货币", "比特币", "加密", "美股", "stablecoin", "meme 币", "区块链"]
_ok = lambda q: urllib.parse.quote(q)


class MainStream(Source):
    name = "mainsm"

    def fetch(self):
        out = []
        for q in QUERIES:
            url = (f"https://news.google.com/rss/search?q={_ok(q)}"
                   "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans")
            try:
                raw = self.http_get(url, timeout=8)
                root = ET.fromstring(raw)
                for item in root.iter("item"):
                    title = html.unescape(item.findtext("title") or "").strip()
                    if not title:
                        continue
                    desc = item.findtext("description") or ""
                    m = re.search(r'href="([^"]+)"', desc)
                    link = m.group(1) if m else ""
                    pub = (item.findtext("pubDate") or "").strip()
                    src = (item.findtext("source") or "").strip()
                    out.append({
                        "title": title[:200],
                        "src": src or "google",
                        "published_at": pub,
                        "text": html.unescape(re.sub(r"<[^>]+>", "", desc))[:200],
                        "url": link,
                    })
            except Exception:
                continue
            # 去重（标题归一化）
            seen, dedup = set(), []
            for it in out:
                k = re.sub(r"[^\w\u4e00-\u9fff]", "", it["title"][:30])
                if k in seen:
                    continue
                seen.add(k)
                dedup.append(it)
            out = dedup
        return self.ok(out[:40])


def fetch_mainsm_chain():
    return MainStream().fetch()

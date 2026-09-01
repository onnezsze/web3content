"""联合早报·财经国际源：https://www.zaobao.com/finance/world

覆盖 美元/油价/美股/英伟达/美联储/新兴市场债券/地缘 等财经国际主流报道（用户点名补充源）。
HTML 抓取，解析 标题+链接+日期；带 UA；fail-soft。
"""
from .base import Source
import re, html

BASE = "https://www.zaobao.com"
PAGE = "/finance/world"


class Zaobao(Source):
    name = "zaobao"

    def fetch(self):
        try:
            raw = self.http_get(BASE + PAGE, timeout=10)
            text = raw.decode("utf-8", "ignore")
            items = re.findall(r'<a[^>]+href="(/finance/world/story\d+-\d+)"[^>]*>(.*?)</a>', text, re.S)
            out, seen = [], set()
            for href, txt in items:
                t = html.unescape(re.sub(r"<[^>]+>", "", txt)).strip()
                if len(t) < 8 or t in seen:
                    continue
                seen.add(t)
                m = re.search(r"story(\d{8})", href)
                pub = (f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else "")
                out.append({"title": t[:200], "src": "zaobao", "published_at": pub,
                            "text": t, "url": BASE + href})
            return self.ok(out[:100])
        except Exception as e:
            return self.fail(str(e)[:120])


def fetch_zaobao_chain():
    return Zaobao().fetch()

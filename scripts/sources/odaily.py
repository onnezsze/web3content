"""Odaily 星球日报 加密媒体源：https://www.odaily.news/

覆盖 加密/DeFi/美股/AI/监管/快讯 等。首页 HTML 解析（post 深度 + newsflash 快讯）。
带 UA；fail-soft。
"""
from .base import Source
import re, html

BASE = "https://www.odaily.news"


class Odaily(Source):
    name = "odaily"

    def fetch(self):
        try:
            raw = self.http_get(BASE + "/", timeout=10)
            text = raw.decode("utf-8", "ignore")
            items = re.findall(r'<a[^>]+href="(/(?:zh-CN/(?:post|newsflash)/\d+))"[^>]*>(.*?)</a>', text, re.S)
            out, seen = [], set()
            for href, txt in items:
                t = html.unescape(re.sub(r"<[^>]+>", "", txt)).strip()
                if len(t) < 8 or t in seen:
                    continue
                seen.add(t)
                kind = "快讯" if "/newsflash/" in href else "深度"
                out.append({"title": t[:200], "src": "odaily", "published_at": "",
                            "text": t, "url": BASE + href, "kind": kind})
            return self.ok(out[:100])
        except Exception as e:
            return self.fail(str(e)[:120])


def fetch_odaily_chain():
    return Odaily().fetch()

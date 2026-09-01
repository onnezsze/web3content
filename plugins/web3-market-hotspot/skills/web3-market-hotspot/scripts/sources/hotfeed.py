"""6551 零key热点源(crypto / ai / macro) — 融合自 unified-news skill

带 热度 score / 评级 grade / **交易方向 signal(long/short)** / **相关币 coins** / 来源 X link / 中英摘要。
补充当前管线缺的 AI/宏观分类、交易信号、相关资产标释；且抓 X(Twitter)推文热点，可覆盖孙哥/CZ 等动态。
fail-soft：失败返回 status=failed、data=[]，不阻断其它源。
"""
from .base import Source

CATS = ["crypto", "ai", "macro"]


class HotFeed(Source):
    name = "hotfeed"

    def fetch(self):
        out = []
        for c in CATS:
            try:
                raw = self.http_json(f"https://ai.6551.io/open/free_hot?category={c}", timeout=12)
                items = (raw.get("news") or {}).get("items") or []
                for it in items[:100]:
                    title = (it.get("title") or "").strip()
                    if not title:
                        continue
                    out.append({
                        "title": title[:220],
                        "src": "6551",
                        "cat": c,
                        "coins": it.get("coins") or [],
                        "score": it.get("score"),
                        "grade": it.get("grade"),
                        "signal": it.get("signal"),
                        "link": it.get("link") or "",
                        "summary_zh": it.get("summary_zh") or "",
                        "published_at": it.get("published_at") or "",
                        "text": (it.get("title") or "").strip(),
                    })
            except Exception:
                continue
        return self.ok(out)


def fetch_hotfeed_chain():
    return HotFeed().fetch()

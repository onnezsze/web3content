"""热门资产源：CoinGecko 全市场成交量榜 + 24h 涨幅榜

承接「牛来 / PONS / UNI」这类 小市值新币 / 链上热门 / 高出量 的交易型热点。
与 market.py(主流 37 币)互补，这里取成交量 top + 24h 涨幅 top，覆盖被主流榜漏掉的热门标的。
fail-soft：失败返回 status=failed、data=[]，不阻断其它源。
"""
from .base import Source


class HotAssets(Source):
    name = "hotassets"

    def fetch(self):
        url = ("https://api.coingecko.com/api/v3/coins/markets"
               "?vs_currency=usd&order=volume_desc&per_page=150&page=1"
               "&price_change_percentage=24h")
        try:
            raw = self.http_json(url, timeout=12)
            if not isinstance(raw, list):
                return self.fail("bad response")
            rows = []
            for it in raw:
                chg = it.get("price_change_percentage_24h")
                rows.append({
                    "symbol": (it.get("symbol") or "").upper(),
                    "name": it.get("name", ""),
                    "price": it.get("current_price"),
                    "chg_24h": round(chg, 2) if isinstance(chg, (int, float)) else None,
                    "vol": it.get("total_volume"),
                    "mcap": it.get("market_cap"),
                    "rank": it.get("market_cap_rank"),
                })
            vol_top = sorted(rows, key=lambda x: (x["vol"] or 0), reverse=True)[:12]
            gain_top = sorted([r for r in rows if r.get("chg_24h") is not None],
                              key=lambda x: -x["chg_24h"])[:12]
            out, seen = [], set()
            for tag, lst in (("VOL", vol_top), ("GAIN", gain_top)):
                for r in lst:
                    k = r["symbol"]
                    if k in seen:
                        continue
                    seen.add(k)
                    o = dict(r)
                    o["tags"] = [t for t, l in (("VOL", vol_top), ("GAIN", gain_top)) if r in l]
                    out.append(o)
            return self.ok(out[:100])
        except Exception as e:
            return self.fail(str(e)[:120])


def fetch_hot_assets_chain():
    return HotAssets().fetch()

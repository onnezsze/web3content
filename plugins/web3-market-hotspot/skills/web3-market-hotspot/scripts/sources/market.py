"""行情源：CoinGecko 主源 + Gate.io fallback + OKX/Binance fallback"""
from .base import Source
import json, os

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(CONFIG_DIR, "symbol_map.json")) as f:
    SYMBOL_MAP = json.load(f)
WATCHLIST = SYMBOL_MAP["watchlist"]


class CoinGecko(Source):
    name = "coingecko"

    def fetch(self):
        try:
            ids = ",".join(w["cg_id"] for w in WATCHLIST)
            url = (f"https://api.coingecko.com/api/v3/coins/markets"
                   f"?vs_currency=usd&ids={ids}"
                   f"&price_change_percentage=1h,24h,7d&per_page=100")
            data = self.http_json(url)
            out = {}
            # 反向映射表：cg symbol → 主 symbol（如 GRAM→TON）
            rev = {}
            for w in WATCHLIST:
                rev[w["cg_id"].lower()] = w["symbol"]
                for a in w.get("alias", []):
                    rev[a.lower()] = w["symbol"]
            for c in data:
                cg_id = c.get("id", "").lower()
                sym = rev.get(cg_id, c["symbol"].upper())
                out[sym] = {
                    "symbol": sym, "name": c["name"],
                    "price": c["current_price"], "mc_rank": c["market_cap_rank"],
                    "vol": c["total_volume"],
                    "chg_1h": c.get("price_change_percentage_1h_in_currency"),
                    "chg_24h": c.get("price_change_percentage_24h_in_currency"),
                    "chg_7d": c.get("price_change_percentage_7d_in_currency"),
                    "source": "coingecko",
                }
            return self.ok(out)
        except Exception as e:
            return self.fail(e)


class GateIO(Source):
    name = "gateio"

    def fetch(self):
        try:
            data = self.http_json("https://data.gateapi.io/api2/1/tickers", timeout=10)
            out = {}
            for ticker, v in data.items():
                # ticker 形如 "BTC_USDT"
                sym, quote = ticker.split("_", 1)
                if quote != SYMBOL_MAP.get("gate_quote", "USDT"):
                    continue
                # symbol 别名归一化：RNDR→RENDER, MATIC→POL, FTM→S
                for w in WATCHLIST:
                    alias = w.get("alias", [])
                    if sym in [w["symbol"]] + alias:
                        sym = w["symbol"]
                        break
                else:
                    continue
                # PEPE/BONK 精度放大
                prec = 1
                for w in WATCHLIST:
                    if w["symbol"] == sym:
                        prec = w.get("gate_precision", 1)
                        break
                price = float(v.get("last", 0)) * prec
                vol = float(v.get("baseVolume", 0))
                chg24 = None
                try:
                    chg24 = (float(v.get("last")) - float(v.get("open_24h"))) / float(v.get("open_24h")) * 100
                except Exception:
                    pass
                out[sym] = {
                    "symbol": sym, "price": price, "vol": vol,
                    "chg_1h": None, "chg_24h": chg24, "chg_7d": None,
                    "source": "gateio",
                }
            return self.ok(out)
        except Exception as e:
            return self.fail(e)


class OKXBinance(Source):
    """OKX 主 + Binance 兜底，仅价格和24h"""
    name = "okx_binance"

    def fetch(self):
        try:
            # OKX tickers
            data = self.http_json("https://www.okx.com/api/v5/market/tickers?instType=SPOT", timeout=8)
            out = {}
            for t in data.get("data", []):
                sym, quote = t["instId"].split("-")[:2]
                if quote != "USDT":
                    continue
                for w in WATCHLIST:
                    if sym in [w["symbol"]] + w.get("alias", []):
                        sym = w["symbol"]
                        break
                else:
                    continue
                out[sym] = {
                    "symbol": sym, "price": float(t["last"]),
                    "vol": float(t.get("volCcy24h", 0) or 0),
                    "chg_1h": None, "chg_24h": float(t.get("open24h")) and ((float(t["last"]) - float(t["open24h"])) / float(t["open24h"]) * 100) or None,
                    "chg_7d": None, "source": "okx",
                }
            if out:
                return self.ok(out)
            # Binance 兜底
            data2 = self.http_json("https://api.binance.com/api/v3/ticker/24hr", timeout=8)
            out2 = {}
            for t in data2:
                sym = t["symbol"].replace("USDT", "")
                if sym == t["symbol"]:
                    continue
                for w in WATCHLIST:
                    if sym in [w["symbol"]] + w.get("alias", []):
                        sym = w["symbol"]
                        break
                else:
                    continue
                out2[sym] = {
                    "symbol": sym, "price": float(t["lastPrice"]),
                    "vol": float(t["volume"]),
                    "chg_1h": None, "chg_24h": float(t["priceChangePercent"]),
                    "chg_7d": None, "source": "binance",
                }
            if out2:
                return self.ok(out2)
            return self.fail("both okx and binance empty")
        except Exception as e:
            return self.fail(e)


def fetch_market_chain():
    """行情三级 fallback 链"""
    for cls in (CoinGecko, GateIO, OKXBinance):
        s = cls()
        r = s.fetch()
        if r["status"] == "ok" and r["data"]:
            r["fallback_used"] = cls.__name__
            return r
    return {"status": "failed", "data": {}, "error": "all market sources failed"}

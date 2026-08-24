"""衍生品/情绪数据：OKX资金费率 + 社群词频"""
from .base import Source
import json


class FundingRates(Source):
    """OKX 永续资金费率（BTC/ETH 等主流）"""
    name = "funding"

    SYMBOLS = ["BTC", "ETH", "SOL"]

    def fetch(self):
        try:
            out = {}
            for sym in self.SYMBOLS:
                try:
                    url = f"https://www.okx.com/api/v5/public/funding-rate?instId={sym}-USDT-SWAP"
                    d = self.http_json(url, timeout=6)
                    data = d.get("data", [{}])[0]
                    rate = float(data.get("fundingRate", 0))
                    # 换算成年化（3h一次结算，每天8次）
                    annualized = rate * 3 * 365
                    out[sym] = {
                        "funding_rate": rate,
                        "annualized_pct": round(annualized * 100, 2),
                        "time": data.get("fundingTime", ""),
                    }
                except Exception:
                    continue
            if out:
                return self.ok(out)
            return self.fail("no funding data")
        except Exception as e:
            return self.fail(e)


# 情绪词频字典：负面/正面/交易行为
SENTIMENT_WORDS = {
    "恐慌": ["崩了", "暴跌", "爆仓", "割肉", "恐慌", "归零", "被套", "瀑布", "血洗", "踩踏"],
    "焦虑": ["焦虑", "睡不着", "害怕", "慌", "怎么办", "撑不住"],
    "抄底": ["抄底", "接盘", "上车", "梭哈", "满仓", "加仓"],
    "看多": ["看多", "牛市", "起飞", "突破", "新高", "暴涨", "冲"],
    "看空": ["看空", "熊市", "逃顶", "减仓", "清仓", "跑路", "别碰"],
    "FOMO": ["fomo", "羡慕", "后悔", "踏空", "错过"],
}


def count_sentiment(items):
    """统计社媒文本情绪词频"""
    counts = {k: 0 for k in SENTIMENT_WORDS}
    samples = {k: [] for k in SENTIMENT_WORDS}
    for it in items:
        text = (it.get("title") or it.get("text") or "").lower()
        for cat, words in SENTIMENT_WORDS.items():
            for w in words:
                if w in text:
                    counts[cat] += 1
                    if len(samples[cat]) < 3:
                        samples[cat].append((it.get("title") or it.get("text") or "")[:80])
                    break
    return {"counts": counts, "samples": samples}

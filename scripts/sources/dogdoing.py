"""DogDoing 聚合源接入：OI异动 / Fear&Greed / Binance Alpha 热点 / 币安广场热度 / 预测市场 / 美股板块

取 DogDoing (https://dogdoing.ai) 独有的、与本管线不重复的维度做补充。
fail-soft：任一端点失败不阻断其他端点；全部失败才整体标记 failed。

端点统一由 DogDoing 后端 /api/* 代理（Next.js），返回 {"data": [...]} 或标量对象。
"""
from .base import Source
import concurrent.futures

BASE = "https://dogdoing.ai"

# key -> (endpoint_path, sort_key, limit)
#   sort_key 为 None 表示不排序直接取前 limit
ENDPOINTS = {
    "fear_greed":         ("/api/fear-greed", None, 1),
    "oi_divergence":      ("/api/oi-divergence", "divergenceRatio", 10),
    "alpha_hotspots":     ("/api/hotspots?chainId=56&rankType=", "netInflow", 10),
    "square_hype":        ("/api/square-hype", "score", 10),
    "prediction_markets": ("/api/prediction-markets?limit=5", None, 5),
    "us_stocks":          ("/api/us-stocks", None, 8),
}


class DogDoing(Source):
    name = "dogdoing"

    def fetch_one(self, key):
        """抓单个端点并裁剪。返回 (key, {"ok": bool, "data": ...})"""
        path, sort_key, limit = ENDPOINTS[key]
        try:
            raw = self.http_json(BASE + path, timeout=10)
            if not isinstance(raw, dict):
                return key, {"ok": False, "error": "bad response"}
            data = raw.get("data", raw)
            if isinstance(data, list):
                if sort_key:
                    data = sorted(data, key=lambda x: (x.get(sort_key) or 0), reverse=True)
                data = data[:limit]
            if key == "us_stocks":
                # 裁掉长 URL，只保留标题级新闻
                cleaned = []
                for it in data:
                    news = [{"title": (n.get("title") or "")[:80],
                             "source": n.get("source", "")}
                            for n in (it.get("news") or [])[:3]]
                    cleaned.append({
                        "symbol": it.get("symbol"), "name": it.get("name"),
                        "price": it.get("price"), "changePct": it.get("changePct"),
                        "volume": it.get("volume"), "news": news,
                    })
                data = cleaned
            return key, {"ok": True, "data": data}
        except Exception as e:
            return key, {"ok": False, "error": str(e)[:100]}


def fetch_dogdoing_chain():
    """并发抓 6 个 DogDoing 端点。任一成功即 status=ok，全失败才 failed（fail-soft）"""
    s = DogDoing()
    out = {}
    ok = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(s.fetch_one, k): k for k in ENDPOINTS}
        try:
            for f in concurrent.futures.as_completed(futs, timeout=15):
                key, val = f.result()
                out[key] = val
                if val.get("ok"):
                    ok += 1
        except concurrent.futures.TimeoutError:
            pass
    if ok == 0:
        return s.fail("all dogdoing endpoints failed")
    return {"status": "ok", "data": out}

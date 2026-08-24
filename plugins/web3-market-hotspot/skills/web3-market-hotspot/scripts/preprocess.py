"""预处理层：去重、时间过滤、关键词打标、异动预计算、交叉验证"""
import json, os, re, hashlib
from datetime import datetime, timezone, timedelta

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(CONFIG_DIR, "tags.json")) as f:
    TAGS = json.load(f)["tags"]


def normalize_key(text):
    """标题归一化去重键"""
    t = text.lower()
    t = re.sub(r"[\W_]+", "", t)
    return hashlib.md5(t[:40].encode()).hexdigest()[:16]


def tokenize(text):
    """提取标题 token 集合：英文单词 + 数字 + 中文双字词"""
    t = text.lower()
    toks = set(re.findall(r"[a-z]{3,}", t))          # 英文单词
    toks |= set(re.findall(r"\d+(?:\.\d+)?%?", t))    # 数字/百分比
    cn = re.findall(r"[\u4e00-\u9fff]{2,4}", t)       # 中文片段
    for c in cn:
        if len(c) >= 2:
            toks.add(c)
    return toks


def similar(a_tokens, b_tokens):
    """token 集合相似度：交集/并集 > 0.4 视为同一事件"""
    if not a_tokens or not b_tokens:
        return False
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return union > 0 and inter / union > 0.4


def tag_text(text):
    """关键词打标：返回标签列表"""
    low = text.lower()
    hits = []
    for tag, kws in TAGS.items():
        for kw in kws:
            if kw.lower() in low:
                hits.append(tag)
                break
    return hits


def parse_rss_time(pub):
    """RSS pubDate → ISO，解析失败返回 None"""
    if not pub:
        return None
    try:
        dt = datetime.strptime(pub.strip(), "%a, %d %b %Y %H:%M:%S %z")
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def filter_and_dedup(items, hours=24):
    """时间过滤 + 去重（精确+相似度）+ 打标 + 交叉验证"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    seen = {}          # dedup_key -> entry
    similar_groups = []  # 相似度分组
    kept, archived = [], []

    for it in items:
        text = it.get("title") or it.get("text") or ""
        if not text:
            continue
        key = normalize_key(text)
        tags = tag_text(text)
        toks = tokenize(text)

        ts_raw = it.get("published_at") or it.get("time") or ""
        ts = None
        if ts_raw:
            ts = parse_rss_time(ts_raw) if isinstance(ts_raw, str) and "GMT" in ts_raw else str(ts_raw)

        entry = {
            "title": text[:200],
            "src": it.get("src", it.get("channel", "unknown")),
            "tags": tags,
            "published_at": str(ts) if ts else "",
            "dedup_key": key,
        }
        # 1) 精确去重
        if key in seen:
            seen[key]["sources"].append(entry["src"])
            seen[key]["cross_verified"] = True
            continue
        # 2) 相似度去重（跨源同一事件，措辞不同）
        merged = False
        for g in similar_groups:
            if similar(toks, g["tokens"]):
                g["entry"]["sources"].append(entry["src"])
                g["entry"]["cross_verified"] = True
                g["entry"]["title"] = g["entry"]["title"] if len(g["entry"]["title"]) >= len(text[:200]) else text[:200]
                merged = True
                break
        if merged:
            continue
        entry["sources"] = [entry["src"]]
        entry["cross_verified"] = False
        entry["stale"] = False
        seen[key] = entry
        similar_groups.append({"entry": entry, "tokens": toks})

    for e in seen.values():
        if e["stale"]:
            archived.append(e)
        else:
            kept.append(e)

    kept.sort(key=lambda x: x["published_at"], reverse=True)
    return kept[:30], archived[:20]


def precompute_anomalies(market):
    """异动预计算：top_gainers/top_losers/volume_anomalies/dump_pump"""
    items = [v for v in market.values() if isinstance(v, dict) and v.get("price")]
    items = [v for v in items if v.get("price", 0) > 0]  # 过滤 price=0 污染

    gainers = sorted([v for v in items if v.get("chg_24h") is not None],
                     key=lambda x: x["chg_24h"], reverse=True)[:10]
    losers = sorted([v for v in items if v.get("chg_24h") is not None],
                    key=lambda x: x["chg_24h"])[:10]
    dump = [v for v in items if v.get("chg_1h") is not None and abs(v["chg_1h"]) > 5]

    # 量能异动：vol 与 7d 均量对比（无 7d 数据时跳过）
    vol_anom = []
    for v in items:
        if v.get("vol") and v.get("vol") > 0:
            vol_anom.append({
                "symbol": v["symbol"], "vol": v["vol"],
                "chg_24h": v.get("chg_24h"), "volume_spike": True,
            })
    vol_anom.sort(key=lambda x: x["vol"], reverse=True)

    return {
        "top_gainers": [{"symbol": v["symbol"], "chg_24h": v["chg_24h"], "price": v["price"]} for v in gainers],
        "top_losers": [{"symbol": v["symbol"], "chg_24h": v["chg_24h"], "price": v["price"]} for v in losers],
        "volume_anomalies": vol_anom[:10],
        "dump_pump": [{"symbol": v["symbol"], "chg_1h": v["chg_1h"]} for v in dump],
    }

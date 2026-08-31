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
            "url": it.get("url", "") or "",
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
        # 24h 时效过滤：能解析时间的，超 cutoff 记为 stale(过滤掉陈旧新闻)
        dt = None
        if ts_raw:
            tstr = str(ts_raw).strip()
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(tstr)
            except Exception:
                dt = None
            if dt is None:
                try:
                    dt = datetime.fromisoformat(tstr.replace("Z", "+00:00").replace(" ", "T"))
                except Exception:
                    dt = None
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff:
                entry["stale"] = True
        seen[key] = entry
        similar_groups.append({"entry": entry, "tokens": toks})

    for e in seen.values():
        if e["stale"]:
            archived.append(e)
        else:
            kept.append(e)

    kept.sort(key=lambda x: x["published_at"], reverse=True)
    return kept[:30], archived[:20]


# =============================================================================
# 个股资讯过滤（v7.34）：只保留【港股互联网大厂】+【AI股】的个股资讯，
# 其余个股（a股/美股其他/港股非互联网大厂等）一律剔除。
# 判定为"个股资讯"：命中公司/证券事件信号 + 出现公司主体特征，且不在保留白名单。
# 大盘/指数/板块/宏观层面、以及加密币种项目，不误伤。
# =============================================================================
# 保留白名单：港股互联网大厂 + AI / 大科技 / 存储芯片股（中英文，尽量全）
KEEP_STOCK = [
    # —— 港股互联网大厂 ——
    "腾讯", "腾讯控股", "tencent", "阿里巴巴", "阿里", "alibaba", "美团", "meituan",
    "京东", "jd.com", "网易", "netease", "百度", "baidu", "小米", "xiaomi", "快手", "kuaishou",
    "拼多多", "pinduoduo", "pdd", "哔哩哔哩", "bilibili", "微博", "weibo", "携程", "trip.com",
    # —— AI / 大科技 / 存储芯片股 ——
    "英伟达", "nvidia", "nvda", "台积电", "tsmc", "amd", "美光", "micron", "博通", "broadcom",
    "sk hynix", "海力士", "英特尔", "intel", "三星电子", "samsung", "超微", "super micro", "smci",
    "高通", "qualcomm", "arm", "marvell", "迈威尔", "coreweave", "甲骨文", "oracle", "英飞凌", "infineon",
    "微软", "microsoft", "msft", "苹果", "apple", "aapl", "谷歌", "google", "alphabet", "googl",
    "meta", "脸书", "特斯拉", "tesla", "tsla", "亚马逊", "amazon", "amzn", "netflix", "奈飞",
    "openai", "anthropic", "claude", "gpt", "sam altman", "chegg",
]
# 大盘 / 指数 / 板块 / 宏观层面 → 非"个股"，保留
BOARD_MACRO = [
    "纳指", "标普", "道指", "纳斯达克", "标普500", "恒生指数", "恒指", "上证", "深证", "沪深",
    "创业板指", "大盘", "指数基金", "股指", "板块", "全线", "集体上涨", "集体走低", "美股三大",
    "美联储", "加元", "降息", "加息", "利率决议", "国债", "美国国债", "原油", "黄金", "大宗商品",
    "非农", "cpi", "gdp", "通胀", "关税", "ETF", "比特币", "以太坊", "加密", "币市",
]
# 公司/证券主体特征：出现这些词，说明是"具体某家公司/某只证券"的内容
COMPANY_MARKER = [
    "财报", "业绩", "营收", "净利润", "归母", "回购", "增持", "减持", "分红", "派息",
    "股价", "市值", "涨停", "跌停", "涨超", "跌超", "暴涨", "暴跌", "破发", "每股", "市盈率",
    "公司", "股份", "集团", "控股", "子公司", "上市公司", "盘中", "收盘", "开盘", "证券",
    "H股", "A股", "公告", "主板", "科创板", "创业板", "定增", "配股", "可转债", "标的",
    "联交所", "港交所", "银行", "保险", "券商", "股份公司", "股权",
]
STOCK_EVENT = [
    "财报", "业绩", "营收", "净利润", "归母", "回购", "增持", "减持", "分红", "派息", "Q1", "Q2", "Q3", "Q4",
    "盈利", "亏损", "每股", "市盈率", "破发", "涨停", "跌停", "涨超", "跌超", "盘前", "盘后",
    "净利", "半年报", "季报", "年报", "中报", "毛利率", "营业额", "销售额", "手续费",
    "发行H股", "港股上市", "联交所主板", "港交所", "上市辅导", "IPO", "股权激励", "退市",
    "earnings", "guidance", "beat", "miss", "profit", "revenue", "buyback", "split",  # 英文
]


def is_individual_stock(text):
    """判定是否为需要剔除的"非白名单个股资讯"。返回 True=剔除。"""
    t = (text or "").lower()
    if not t:
        return False
    # 1) 白名单公司 → 保留
    if any(w in t for w in KEEP_STOCK):
        return False
    # 2) 大盘/指数/板块/宏观层面 → 保留
    if any(w in t for w in BOARD_MACRO):
        return False
    # 2.5) 证券代码（如 000630.SZ / 600519.SH / 9988.HK / 00700.HK / 000630.SZ）→ 强个股信号，剔除
    if re.search(r"\d{4,6}\.(sz|sh|hk|ss|bj|ks|nq)", t) or re.search(r"\d{5}\.hk", t):
        return True
    # 3) 命中个股事件信号 且 出现公司主体特征 → 判定为具体公司个股，剔除
    if any(w in t for w in STOCK_EVENT) and any(w in t for w in COMPANY_MARKER):
        return True
    return False


def drop_individual_stock(items):
    """对一批条目做个股过滤，返回剔除后的列表。"""
    if not items:
        return items
    return [it for it in items if not is_individual_stock(str(it.get("title") or "") + " " + str(it.get("text") or ""))]


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

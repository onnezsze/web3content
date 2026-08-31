#!/usr/bin/env python3
"""精简报告模式 v3：AI 可直接用的结构化文本
含：精确事件匹配、宏观过滤、KOL观点、反差素材榜、数据卡"""
import subprocess, sys, os, json, re
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
try:
    from preprocess import is_individual_stock, drop_individual_stock
except Exception:
    def is_individual_stock(t): return False
    def drop_individual_stock(it): return it

# 币名映射：symbol -> [中文名, 英文全名]（用于精确事件匹配）
COIN_NAMES = {
    "BTC": ["比特币", "bitcoin"], "ETH": ["以太坊", "ethereum"],
    "SOL": ["solana"], "XRP": ["ripple", "瑞波"], "DOGE": ["dogecoin", "狗狗币"],
    "BNB": ["binance coin"], "TON": ["toncoin", "gram"], "TRX": ["tron", "波场"],
    "ADA": ["cardano"], "AVAX": ["avalanche"], "LINK": ["chainlink"],
    "SUI": ["sui"], "PEPE": ["pepe"], "WIF": ["dogwifcoin"],
    "SHIB": ["shiba"], "FLOKI": ["floki"], "BONK": ["bonk"],
    "FET": ["fetch"], "RENDER": ["render", "rndr"], "TAO": ["bittensor"],
    "WLD": ["worldcoin"], "ONDO": ["ondo"], "ENA": ["ethena"],
    "ARB": ["arbitrum"], "OP": ["optimism"], "APT": ["aptos"],
    "INJ": ["injective"], "TIA": ["celestia"], "JUP": ["jupiter"],
    "SEI": ["sei"], "NEAR": ["near"], "AAVE": ["aave"], "UNI": ["uniswap"],
    "LDO": ["lido"], "PENDLE": ["pendle"], "POL": ["polygon"], "S": ["sonic", "fantom"],
    "ZEC": ["zcash", "大零币"], "LIT": ["lighter protocol", "lit"],
}
SHORT_SYMS = {"OP", "S", "LIT", "INJ", "SUI", "TAO", "TIA", "JUP", "SEI", "AAVE", "UNI", "LDO", "FET", "WLD", "ENA", "ARB", "APT", "PEPE", "WIF", "BONK", "FLOKI", "ONDO", "PENDLE", "POL"}


def match_event(symbol, news_items):
    """精确匹配：用币名映射+单词边界，短symbol只匹配全名/中文名"""
    names = COIN_NAMES.get(symbol, [symbol.lower()])
    patterns = []
    if symbol in SHORT_SYMS:
        # 短symbol：只用中文名/全名匹配，避免子串误伤
        patterns = [re.compile(re.escape(n), re.I) for n in names if len(n) > 3]
    else:
        patterns = [re.compile(r"\b" + re.escape(n) + r"\b", re.I) for n in names]
        patterns.append(re.compile(r"\b" + re.escape(symbol) + r"\b"))
    for n in news_items[:40]:
        title = n.get("title", "") or ""
        text = n.get("text", "") or ""
        combined = title + " " + text
        for p in patterns:
            if p.search(combined):
                return title[:80]
    return ""


# 宏观过滤：排除 A 股个股财报/公司公告类噪声
MACRO_NOISE = ["半年报", "年报", "净利润", "营收", "营业收入", "归母", "财报",
               "公告称", "公告显示", "业绩", "停牌", "复牌", "回购", "增持",
               "ST", "配股", "分红", "中标", "签署合同", "中报"]
MACRO_KEEP = ["央行", "美联储", "财政部", "关税", "美债", "国债", "美元", "人民币",
              "利率", "通胀", "CPI", "GDP", "制裁", "战争", "乌克兰", "俄罗斯",
              "伊朗", "以色列", "中东", "原油", "油价", "黄金", "纳指", "标普",
              "道指", "港股", "恒生", "A股", "政策", "规划", "监管", "ETF",
              "比特币", "加密", "AI", "人工智能", "芯片", "半导体", "阿里", "腾讯"]


def is_macro_noise(text):
    low = text.lower()
    noise_hits = sum(1 for k in MACRO_NOISE if k.lower() in low)
    keep_hits = sum(1 for k in MACRO_KEEP if k.lower() in low)
    # 财报类信号强且无宏观关键词 → 过滤
    if noise_hits >= 2 and keep_hits == 0:
        return True
    if any(k in low for k in ["净利润", "营业收入", "归母净利润"]) and not any(k in low for k in ["央行", "美联储", "美债", "港股", "A股", "政策", "ETF"]):
        return True
    return False


def extract_kol_views(social_items):
    """提取 KOL 观点：社媒中含观点类动词的条目"""
    view_kw = ["表示", "认为", "预测", "喊单", "看多", "看空", "称", "建议",
               "观点", "警告", "预期", "看好", "减持", "增持", "发文", "："]
    out = []
    for it in social_items:
        text = it.get("title", "") or ""
        if any(k in text for k in view_kw) and len(text) > 15:
            out.append({"text": text[:120], "channel": it.get("channel", it.get("src", "?"))})
    # 去重
    seen = set()
    dedup = []
    for v in out:
        if v["text"][:50] not in seen:
            seen.add(v["text"][:50])
            dedup.append(v)
    return dedup[:10]


def find_contrasts(market, precomputed, sentiment, news_items):
    """反差素材识别：
    1) 7d大涨(>15%)但24h转跌 → 高位转跌
    2) 24h大涨但情绪词频恐慌/焦虑高 → 价格情绪背离
    3) 1h剧烈波动(>5%) → 短线异动
    4) 24h涨幅榜 vs 7d榜差异大 → 启动/轮动信号"""
    out = []
    for sym, v in market.items():
        if not isinstance(v, dict) or not v.get("price"):
            continue
        chg7 = v.get("chg_7d"); chg24 = v.get("chg_24h")
        if chg7 is not None and chg24 is not None and chg7 > 15 and chg24 < -1:
            out.append(f"{sym}: 7d +{chg7:.1f}% 但24h {chg24:+.1f}% → 高位转跌")
    # 24h 涨幅榜前列但 7d 涨幅很小 → 启动信号（新资金进场）
    for g in precomputed.get("top_gainers", [])[:5]:
        v = market.get(g["symbol"], {})
        if v and v.get("chg_7d") is not None and v.get("chg_24h", 0) > 8 and v["chg_7d"] < 15:
            out.append(f"{g['symbol']}: 24h +{g['chg_24h']:.1f}% 但7d仅+{v['chg_7d']:.1f}% → 启动信号")
    # 价格-情绪背离
    neg = (sentiment.get("counts", {}).get("恐慌", 0) + sentiment.get("counts", {}).get("焦虑", 0))
    if neg >= 2:
        top = precomputed.get("top_gainers", [])
        if top and top[0]["chg_24h"] > 8:
            out.append(f"价格-情绪背离: 24h涨幅榜第一 {top[0]['symbol']} +{top[0]['chg_24h']:.1f}%，但社群恐慌/焦虑词频 {neg} 次")
    return out[:8]


def build_data_cards(market, funding, news_items, precomputed):
    """数据卡：集中可引用的硬数字"""
    cards = []
    for sym in ["BTC", "ETH", "SOL"]:
        v = market.get(sym, {})
        if v and v.get("price"):
            cards.append(f"{sym} ${v['price']:,.0f}（24h {v.get('chg_24h',0):+.2f}% / 7d {v.get('chg_7d',0):+.2f}%）")
    for sym, v in (funding or {}).items():
        cards.append(f"{sym} 资金费率年化 {v.get('annualized_pct','?')}%")
    # 从新闻提取亮点数字
    num_pattern = re.compile(r"\$[\d,]+\.?\d*[BM]?|\d+%|\$\d+(?:\.\d+)?[BMT]?")
    for n in news_items[:25]:
        title = n.get("title", "")
        if any(k in title.lower() for k in ["etf", "inflow", "record", "high", "新高", "暴涨", "突破", "surge", "hits"]):
            cards.append(f"新闻: {title[:70]}")
        if len(cards) >= 12:
            break
    return cards[:12]


def top_news(news_items, top=5):
    """今日要闻候选，按优先级排序：①监管/合规/政府动作/宏观市场(最高) ②主流币(BTC/ETH) ③美股指数·板块·MAG7·AI·存储·芯片。
    返回按优先级+重要程度(交叉验证/标题长度)排序的 top 条。"""
    T1 = ["监管", "合规", "sec", "cftc", "央行", "财政部", "白宫", "政府", "法案", "听证", "制裁", "起诉",
          "调查", "国会", "美联储", "fed", "利率", "降息", "加息", "关税", "gdp", "cpi", "非农", "美债",
          "禁令", "regulator", "regulation", "compliance", "ban", "congress", "chairman"]
    T2 = ["btc", "bitcoin", "比特币", "eth", "ethereum", "以太坊", "solana", "主流币"]
    T3 = ["标普", "纳斯达克", "道琼斯", "sp500", "s&p", "nasdaq", "dow", "mag7", "mag 7", "英伟达", "nvidia",
          "openai", "anthropic", "微软", "microsoft", "苹果", "apple", "谷歌", "google", "meta", "亚马逊",
          "amazon", "特斯拉", "tesla", "台积电", "tsmc", "芯片", "chip", "半导体", "semis", "存储", "memory",
          "hbm", "sk hynix", "美光", "micron", "amd", "博通", "broadcom", "英特尔", "intel", "ai公司", "ai教"]
    def tier(it):
        t = (it.get("title", "") + " " + it.get("text", "") + " " + it.get("summary", "")).lower()
        if any(k in t for k in T1):
            return 1
        if any(k in t for k in T2):
            return 2
        if any(k in t for k in T3):
            return 3
        return 99
    ranked = [it for it in news_items if tier(it) <= 3]
    # 优先级(小=高) → 交叉验证 → 标题信息量
    ranked.sort(key=lambda it: (tier(it), -int(bool(it.get("cross_verified"))), -len(it.get("title", ""))))
    return ranked[:top]


def circle_dynamics(news_items, social_items, macro_items, top=5, extra_items=None):
    """圈内动态(2026-08 扩版)：监测 孙哥(孙宇晨,含八卦·最高优先) / 特朗普(加密相关) / 交易所 / 交易所老板高管 /
    币圈大V·名人(动态/八卦/言论/活动) / 链·生态。命中监测主体即可入选(不限于加密关键词)，
    用于抓名人八卦、老板言论、活动传闻；extra_items 可传入 DogDoing Alpha 热点等额外源。
    按优先级(孙哥>特朗普>交易所>老板高管>币圈大V>链/生态)+重要程度筛选，返回 top 条。"""
    CIRCLE_ENTITY = {
        "孙哥/孙宇晨": ["孙宇晨", "孙哥", "孙割", "justin sun", "波场", "tron", "htx", "火币", "trx"],
        "交易所老板高管": ["cz", "赵长鹏", "何一", "徐明星", "brian armstrong", "richard teng", "coinbase ceo",
                         "binance ceo", "okx ceo", "star xu", "创始人", "高管", "董事长", "孙宇晨"],
        "币圈大V/名人": ["arthur hayes", "vitalik", "v神", "马斯克", "musk", "cz", "孙宇晨", "何一", "徐明星",
                        "分析师", "大佬",
                        "巨鲸", "whale", "喊单", "kelly", "crypto daily", "bankless", "coin bureau", "gabor",
                        "唐小僧", "凉兮", "梭教授"],
        "特朗普/监管": ["特朗普", "trump", "美财", "财政部", "制裁", "sec", "监管", "白宫", "参议院", "灰度",
                       "world liberty", "worldliberty"],
        "交易所": ["binance", "币安", "okx", "欧易", "coinbase", "交易所", "上币", "上架", "下架", "暂停交易",
                  "上市", "现货", "合约", "bybit", "bitget", "gate", "kucoin", "htx", "火币"],
        "链/生态": ["主网", "mainnet", "layer2", "l2", "base", "arbitrum", "solana", "ethereum", "以太坊",
                   "生态", "tvl", "链上", "安全事件", "漏洞", "升级", "空投", "回购", "发起"],
    }
    # 动态/八卦/言论/活动 信号词：命中监测主体时加分，用于抓名人八卦、老板言论、活动/传闻
    EVENT_KW = ["绯闻", "恋爱", "婚", "分手", "传闻", "被曝", "辟谣", "回应", "热搜", "爆料", "官宣", "宣布",
                "转发", "转推", "评论", "推文", "tweet", "retweet", "repost", "发推", "互动", "表态", "站队",
                "出席", "演讲", "会见", "发表", "称", "表示", "谈到", "喊单", "晒", "反转", "瓜", "骂", "争论",
                "离职", "入职", "收购", "起诉", "指控", "涉嫌", "冻结", "警告", "调查", "开庭", "喊话", "发声",
                "表态", "怒怼", "讽刺", "开撕", "空头", "号召"]
    HIGH_SIGNAL = ["孙宇晨", "孙哥", "孙割", "cz", "trump", "特朗普", "安全事件", "空投", "下架", "暂停", "上架",
                   "etf", "加仓", "上市", "主网", "制裁", "币安", "coinbase", "okx", "卖出", "买入", "绯闻", "热搜",
                   "爆料", "辟谣", "官宣", "回应", "恋爱", "起诉"]
    from datetime import timedelta
    _recent = datetime.now() - timedelta(hours=24)
    def _pub(it):
        return it.get("published_at") or it.get("time") or ""
    def _fresh(it):
        if not _pub(it):
            return True                       # 无时间戳(币安广场等)视为当天
        dt = _parse_dt(_pub(it))
        return dt is None or dt >= _recent    # 解析失败视为当天；显式超 24h 的旧闻滤除
    pool = []
    for it in news_items:
        if not _fresh(it):
            continue
        pool.append({"title": it.get("title", ""), "text": it.get("text", it.get("title", "")),
                     "src": it.get("src", "?"), "kind": "新闻", "url": it.get("url", "") or ""})
    for it in social_items:
        if not _fresh(it):
            continue
        pool.append({"title": it.get("title", it.get("text", "")), "text": it.get("text", it.get("title", "")),
                     "src": it.get("src", it.get("channel", "?")), "kind": "社媒", "url": it.get("url", "") or ""})
    for it in macro_items:
        if not _fresh(it):
            continue
        pool.append({"title": it.get("title", ""), "text": it.get("text", it.get("title", "")),
                     "src": it.get("src", "?"), "kind": "宏观", "url": it.get("url", "") or ""})
    for it in (extra_items or []):
        pool.append(it)

    def score(it):
        t = (it["title"] + " " + it["text"]).lower()
        s = sum(1 for grp, kws in CIRCLE_ENTITY.items() if any(k.lower() in t for k in kws))
        s += 2 * sum(1 for k in HIGH_SIGNAL if k.lower() in t)
        if any(k.lower() in it["title"].lower() for k in HIGH_SIGNAL):
            s += 1
        # 命中监测主体 + 动态/八卦/言论/活动信号 → 每个事件词 +1（抓名人八卦、老板言论、活动传闻）
        if any(k.lower() in t for kws in CIRCLE_ENTITY.values() for k in kws):
            s += sum(1 for k in EVENT_KW if k.lower() in t)
        return s

    PRIORITY = {"孙哥/孙宇晨": 1, "特朗普/监管": 2, "交易所": 3, "交易所老板高管": 4,
                "币圈大V/名人": 5, "链/生态": 6}

    def priority(it):
        t = (it["title"] + " " + it["text"]).lower()
        ranks = [PRIORITY[g] for g, kws in CIRCLE_ENTITY.items() if any(k.lower() in t for k in kws)]
        return min(ranks) if ranks else 99

    for it in pool:
        it["score"] = score(it)
        it["priority"] = priority(it)

    # 门控(放宽版)：命中监测主体即可入选(不限加密关键词，用于抓名人八卦/言论/活动)；或含加密关键词；否则过滤(股市/关税/纯娱乐噪音)
    CRYPTO_KW = ["btc", "bitcoin", "eth", "ethereum", "加密", "crypto", "coinbase", "binance", "币安", "okx",
                 "欧易", "token", "代币", "稳定币", "stablecoin", "tron", "波场", "solana", "etf", "交易所",
                 "合约", "现货", "主网", "链上", "数字资产", "defi", "nft", "meme", "web3", "doge", "xrp"]
    def _entity_hit(t):
        return any(k.lower() in t for kws in CIRCLE_ENTITY.values() for k in kws)
    # 时效门控：新闻/快讯/公告源直通；社媒(币安广场)等仅当命中"新事件信号词"才视为新动态，排除旧瓜回味
    NEWS_SRC = {"cointelegraph", "coindesk", "theblock", "jinse", "金色", "wublock", "吴说",
                "chaincatcher", "链捕手", "odaily_news", "odaily", "binance_announcements",
                "Binance Alpha", "老虎", "laohu", "东方财富", "eastmoney", "华尔街见闻", "wscn"}
    NEW_EVENT_KW = ["上线", "上币", "下架", "公告", "官宣", "爆料", "辟谣", "被拘", "被查", "起诉",
                    "受审", "监管", "获批", "崩", "暴涨", "暴跌", "新高", "list", "破位", "清算",
                    "合约", "爆仓", "空投", "回购", "发布", "进军", "合作", "收购", "融资", "破产",
                    "跑路", "黑客", "被盗", "禁用", "下线", "销毁"]
    def _new_event(it):
        if it.get("src") in NEWS_SRC:
            return True
        t = (it["title"] + " " + it["text"]).lower()
        return any(k in t for k in NEW_EVENT_KW)
    cand = [it for it in pool
            if it["score"] >= 2 and (_entity_hit((it["title"] + " " + it["text"]).lower())
                                     or any(k in (it["title"] + " " + it["text"]).lower() for k in CRYPTO_KW))
            and _new_event(it)]
    # v7.34 个股过滤：圈内动态只保留 真·圈内主体(孙哥/特朗普/交易所/老板高管/币圈大V/链生态)，
    # 剔除 铜陵有色/贵州茅台 等非圈内主体的个股资讯(命中非白名单个股信号即剔除)
    cand = [it for it in cand if not is_individual_stock(it["title"] + " " + it["text"])]
    # 按优先级(小=高)再按重要程度(score 降序)排序
    cand.sort(key=lambda x: (x["priority"], -x["score"]))

    # 标题去重(同优先级内保留分数高者)；同一主体档(priority)最多 2 条，避免单一主体霸榜
    seen, out, prio_count = set(), [], {}
    for it in cand:
        k = re.sub(r"[^\w]", "", it["title"][:36]).lower()
        if k in seen:
            continue
        pr = it["priority"]
        if prio_count.get(pr, 0) >= 2:
            continue
        seen.add(k)
        prio_count[pr] = prio_count.get(pr, 0) + 1
        out.append(it)
        if len(out) >= top:
            break
    res = []
    for it in out:
        summary = it["text"].strip()
        if not summary:
            summary = it["title"]
        res.append({"title": it["title"][:90], "summary": summary[:150], "src": it["src"], "kind": it["kind"],
                    "url": it.get("url", "")})
    return res


def _parse_dt(s):
    """尽力解析 published_at 为 naive UTC datetime；失败返回 None。"""
    if not s:
        return None
    from datetime import timezone
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(str(s)).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        pass
    try:
        return datetime.fromtimestamp(float(s), tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        pass
    t = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(t[:len(fmt)], fmt)
        except Exception:
            pass
    return None


def fetch_week_news(days=7):
    """独立检索近 days 天新闻热点(不依赖 hot_history 存档)。源：三个RSS + 东方财富 + 华尔街见闻。"""
    from sources.news import RSSNews, EastMoneyNews, WSCN
    items = []
    for cls in (RSSNews, EastMoneyNews, WSCN):
        try:
            r = cls().fetch()
            if isinstance(r, dict) and r.get("status") == "ok":
                for x in r.get("data", []):
                    items.append(dict(x))
        except Exception:
            continue
    return items, (datetime.now() - timedelta(days=days))


def weekly_review(news_items, social_items, macro_items, top=8):
    """周度回顾(周一简报专属)：上周热点回顾 = 采集历史(近7天每日top3) + 补充检索(近7天独立抓取) 融合去重；本周可预估热点候选。"""
    from collections import defaultdict

    # ①A 采集历史：hot_history.json 近7天每日 top3
    hist_path = os.path.join(BASE, "hot_history.json")
    try:
        with open(hist_path) as f:
            hist = json.load(f)
    except Exception:
        hist = {}
    cutoff_d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    hist_items = []
    for d in sorted([k for k in hist if k >= cutoff_d], reverse=True):
        for t in hist.get(d, [])[:3]:
            ttl = str(t.get("title", ""))
            if ttl:
                hist_items.append({"date": d, "title": ttl[:90], "summary": "",
                                   "src": "历史存档", "cross": 0, "score": t.get("score", "?")})

    # ①B 补充检索：近7天独立抓取(新闻源) + 当天全量
    raw_items, cutoff = fetch_week_news(days=7)
    raw_items = raw_items + list(news_items) + list(social_items) + list(macro_items)

    def _norm(t):
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", t.lower())

    groups = defaultdict(list)
    for n in raw_items:
        title = n.get("title", "") or n.get("text", "")
        if not title:
            continue
        groups[_norm(title[:80])].append(n)

    search_items = []
    for key, lst in groups.items():
        srcs = {x.get("src") for x in lst if x.get("src")}
        cross = len(srcs)
        first = next(iter(lst))
        dt = _parse_dt(first.get("published_at"))
        recent = (dt is not None and dt >= cutoff)
        if recent or cross >= 2:
            search_items.append({
                "date": dt.strftime("%m/%d") if dt else "本周内",
                "title": (first.get("title") or first.get("text"))[:90],
                "summary": (first.get("text") or first.get("title"))[:150],
                "src": ",".join(sorted(srcs))[:24] or (first.get("src") or "?"),
                "cross": cross, "score": None,
            })

    # ① 融合去重：补充检索为主，采集历史补全未出现的标题
    seen = set()
    week_hotspots = []
    for it in search_items:
        seen.add(_norm(it["title"][:80]))
        week_hotspots.append(it)
    for h in hist_items:
        if _norm(h["title"][:80]) not in seen:
            week_hotspots.append(h)
    # 排序：补充检索(有跨源)优先，历史补全(score)靠后，再按日期
    week_hotspots.sort(key=lambda x: (1 if x.get("src") == "历史存档" else 0, -(x.get("cross") or 0), x["date"]))

    # ② 本周可预估热点：前瞻关键词扫描
    fwd_kw = ["将于", "下周", "本月", "本周", "明日", "届时", "解锁", "上线", "暂定",
              "举行", "发布会", "公布", "听证会", "投票", "CPI", "非农", "议息",
              "利率决议", "财报", "交割", "到期", "TGE", "空投", "主网", "升级",
              "mainnet", "launch", "unlock", "earnings", "hearing", "fomc", "vote",
              "proposal", "expiry", "upgrade", "halving", "snapshot", "summary"]
    coming = []
    seen2 = set()
    for n in list(news_items) + list(social_items) + list(macro_items):
        title = n.get("title", "") or n.get("text", "")
        if not title:
            continue
        low = (title + " " + n.get("text", "")).lower()
        if any(k.lower() in low for k in fwd_kw):
            key = title[:50]
            if key in seen2:
                continue
            seen2.add(key)
            coming.append({"title": title[:110],
                           "src": n.get("src", n.get("channel", "?")),
                           "text": (n.get("text", "") or title)[:160]})
    # ③ 下周可预估热点：三级优先级排序（①美联储/宏观数据/美股明星财报 ②主流加密币 ③其他）
    def _tier(c):
        s = (c["title"] + " " + c.get("text", "")).lower()
        # ① 美联储动态/宏观数据
        macro = ["fomc", "美联储", "加息", "降息", "利率", "cpi", "非农", "就业", "失业", "pce", "通胀"]
        if any(k in s for k in macro):
            return 1
        # ① 美股明星股财报动态（明星公司+财报；或明确美股财报）
        star = ["nvidia", "英伟达", "apple", "苹果", "tesla", "特斯拉", "microsoft", "微软",
                "google", "alphabet", "amd", "tsmc", "台积电", "maga7", "netflix", "amazon", "meta"]
        if any(k in s for k in star) and any(k in s for k in ["财报", "earnings", "beat", "miss", "guidance", "业绩"]):
            return 1
        if any(k in s for k in ["财报", "earnings"]) and any(k in s for k in ["美股", "nasdaq", "nyse", "美国"]):
            return 1
        # ② 主流加密货币币种
        t2 = ["btc", "bitcoin", "比特币", "eth", "ethereum", "以太坊", "sol", "solana", "meme",
              "doge", "pepe", "shib", "wif", "bonk", "xrp", "bnb", "ton", "trx", "link",
              "avax", "ada", "sui", "apt", "ena", "jup", "uni"]
        if any(k in s for k in t2):
            return 2
        return 3

    def _datey(c):
        s = c["title"] + c.get("text", "")
        return 0 if any(k in s for k in ["将于", "下周", "本月", "本周", "听证", "财报", "CPI",
                                         "非农", "议息", "FOMC", "unlock", "launch", "earnings"]) else 1
    coming.sort(key=lambda x: (_tier(x), _datey(x), -len(x["title"])))

    return {"week_hotspots": week_hotspots[:top], "coming": coming[:top]}


def main():
    r = subprocess.run([sys.executable, os.path.join(BASE, "collect.py"), "--json-only"],
                       capture_output=True, text=True, timeout=120, cwd=BASE)
    try:
        d = json.loads(r.stdout)
    except Exception as e:
        print(f"采集失败: {e}\nstderr: {r.stderr[-500:]}")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    news_items = d.get("news", [])
    social_items = d.get("social", [])
    macro_items = d.get("macro", [])
    print(f"# 数据采集时间: {now}（采集于 {d.get('collected_at','')}）")
    print(f"# 数据源健康: market={d['source_health']['market']} news={d['source_health']['news']} social={d['source_health']['social']} macro={d['source_health']['macro']} dogdoing={d['source_health'].get('dogdoing','?')}")
    print()

    # 1. 数据卡速览
    print("## 今日数据卡（可直接引用/做图）")
    for c in build_data_cards(d.get("market", {}), d.get("funding", {}), news_items, d.get("precomputed", {})):
        print(f"  • {c}")
    print()

    # 2. 市场
    m = d.get("market", {})
    print("## 行情（来源: CoinGecko）")
    for sym in ["BTC", "ETH", "SOL"]:
        if sym in m:
            v = m[sym]
            print(f"{sym}: ${v['price']:,.0f} | 1h {v.get('chg_1h','?'):+.2f}% | 24h {v.get('chg_24h','?'):+.2f}% | 7d {v.get('chg_7d','?'):+.2f}% | vol ${v.get('vol',0)/1e9:.1f}B")
    print()

    # 3. 今日热门资产（全市场成交量/24h 涨幅榜，承接 牛来/PONS/UNI 类交易热点）
    ha = d.get("hot_assets", [])
    if ha:
        skip = {"USDT", "USDC", "USD1", "USDE", "DAI", "FDUSD", "TUSD", "PYUSD", "BUSD"}
        picks = [a for a in ha if (a.get("symbol") or "") not in skip]
        picks.sort(key=lambda a: (a.get("chg_24h") if isinstance(a.get("chg_24h"), (int, float)) else -99), reverse=True)
        picks = picks[:6]
        print("## 今日热门资产（全市场成交量/24h 涨幅榜，含链上/新上标的）")
        for a in picks:
            c = a.get("chg_24h")
            cs = f"{c:+.2f}%" if isinstance(c, (int, float)) else "?"
            tag = "/".join(a.get("tags") or [])
            print(f"  {str(a['symbol']):<8}{str(a['name']):<16} 24h {cs}  vol ${(a.get('vol') or 0)/1e6:.0f}M  mcap ${(a.get('mcap') or 0)/1e9:.2f}B  [{tag}]")
        print()

    # 4. 资金费率
    f = d.get("funding", {})
    if f:
        print("## 资金费率（来源: OKX）")
        for sym, v in f.items():
            print(f"{sym}: {v.get('annualized_pct','?')}% 年化（费率 {v.get('funding_rate','?')}）")
    print()

    # 4. 异动榜（精确事件匹配）
    pc = d.get("precomputed", {})
    print("## 24h涨幅榜（来源: CoinGecko 计算）")
    for g in pc.get("top_gainers", [])[:10]:
        ev = match_event(g["symbol"], news_items)
        ev_str = f" | 事件: {ev}" if ev else ""
        print(f"  {g['symbol']:<6} {g['chg_24h']:+.2f}%  ${g['price']:,.2f}{ev_str}")
    print("## 24h跌幅榜")
    for g in pc.get("top_losers", [])[:10]:
        ev = match_event(g["symbol"], news_items)
        ev_str = f" | 事件: {ev}" if ev else ""
        print(f"  {g['symbol']:<6} {g['chg_24h']:+.2f}%  ${g['price']:,.2f}{ev_str}")
    if pc.get("dump_pump"):
        print("## 1h剧烈波动(>5%)")
        for g in pc["dump_pump"]:
            print(f"  {g['symbol']:<6} 1h {g['chg_1h']:+.2f}%")
    print()

    # 5. 反差素材榜
    print("## 反差素材榜（创作者最爱：价格与常识/情绪背离）")
    contrasts = find_contrasts(m, pc, d.get("sentiment", {}), news_items)
    if contrasts:
        for c in contrasts:
            print(f"  • {c}")
    else:
        print("  （今日无明显反差）")
    print()

    # 6. KOL观点
    print("## KOL观点（来源: 各频道）")
    kols = extract_kol_views(social_items)
    if kols:
        for k in kols:
            print(f"  [{k['channel']}] {k['text']}")
    else:
        print("  （今日无KOL观点）")
    print()

    # 7. 情绪词频
    s = d.get("sentiment", {}).get("counts", {})
    if s:
        print("## 社群情绪词频（统计自TG/币安广场/老虎社区原文）")
        print("  " + " | ".join(f"{k}:{v}" for k, v in s.items() if v))
        samples = d.get("sentiment", {}).get("samples", {})
        for cat, lst in samples.items():
            if lst:
                for smp in lst[:2]:
                    print(f"  原声[{cat}]({smp['channel']}): {smp['text']}")
    print()

    # 8. 昨日热点
    y = d.get("yesterday_top3")
    if y:
        print(f"## 昨日热点（{y.get('date','')}）")
        for t in y.get("topics", []):
            print(f"  - {t.get('title','')[:80]}（评分{t.get('score','?')}）")
    else:
        print("## 昨日热点: 首次记录（无历史）")
    print()

    # 9. 新闻
    print("## 新闻（含来源与标签，✓多源=交叉验证）")
    for n in news_items[:20]:
        cv = "✓多源" if n.get("cross_verified") else "单源"
        tags = ",".join(n.get("tags", [])) or "无标签"
        print(f"  [{n.get('src','?')}|{cv}|{tags}] {n['title'][:90]}")
    print()

    # 9.5 今日要闻候选（按优先级：①监管/合规/政府/宏观 ②主流币 ③美股指数·板块·MAG7·AI·存储·芯片）
    print("## 今日要闻候选（优先级：①监管合规/政府动作/宏观市场 ②主流币(BTC/ETH) ③美股指数·板块·MAG7·AI·存储·芯片）")
    tn = top_news(news_items)
    if tn:
        for i, it in enumerate(tn, 1):
            u = it.get("url") or ""
            print(f"  {i}. [{it.get('src','?')}|{'多源' if it.get('cross_verified') else '单源'}] {it['title'][:90]}  {u}")
    else:
        print("  （无显著要闻候选）")
    print()

    # 10. ETF/爆仓/资金流
    print("## ETF/爆仓/资金流相关新闻")
    flow_kw = ["etf", "inflow", "outflow", "liquidation", "爆仓", "grayscale", "贝莱德", "现货etf", "资金流入", "资金流出"]
    flow_news = [n for n in news_items if any(k in (n.get("title","")+n.get("text","")).lower() for k in flow_kw)]
    if flow_news:
        for n in flow_news[:8]:
            print(f"  [{n.get('src','?')}] {n['title'][:90]}")
    else:
        print("  （无相关新闻）")
    print()

    # 11. 社媒
    print("## 社媒（频道+内容）")
    for n in social_items[:12]:
        print(f"  [{n.get('src', n.get('channel','?'))}] {n['title'][:90]}")
    print()

    # 12. 宏观（过滤个股财报噪声）
    print("## 宏观/传统金融（已过滤A股个股财报）")
    macro_clean = [n for n in macro_items if not is_macro_noise(n.get("title", ""))]
    for n in macro_clean[:10]:
        print(f"  [{n.get('src','?')}] {n['title'][:90]}")

    # 12.4 财经国际（联合早报 · finance/world）
    zb = d.get("zaobao", [])
    if zb:
        print("## 财经国际（联合早报）")
        for n in zb[:8]:
            print(f"  [zaobao] {n['published_at']} {n['title'][:88]}  {n.get('url','')}")

    # 12.4b 加密要闻（Odaily 星球日报）
    od = d.get("odaily", [])
    if od:
        print("## 加密要闻（Odaily 星球日报）")
        for n in od[:10]:
            print(f"  [odaily·{n.get('kind','')}] {n['title'][:88]}  {n.get('url','')}")

    # 12.4c 热点信号（6551 · 带交易方向/热度/相关币）
    hf = d.get("hotfeed", [])
    if hf:
        print("## 热点信号（6551 · 交易方向/热度/相关币）")
        for cat, label in (("crypto", "加密"), ("ai", "AI/科技"), ("macro", "宏观")):
            items = [x for x in hf if x.get("cat") == cat]
            items.sort(key=lambda x: x.get("score") or 0, reverse=True)
            for it in items[:4]:
                sig = f"[{it['signal']}]" if it.get("signal") else ""
                coins = ",".join((it.get("coins") or [])[:6])
                print(f"  {label}·{it.get('score')}分{sig} {it['title'][:54]}  {coins}  {it.get('link','')}")

    # 12.4c 主流媒体聚焦（主链媒体对名人/大佬事件的深度报道；不进圈内动态，避免旧闻占位）
    ms = d.get("mainsm", [])
    if ms:
        print("## 主流媒体聚焦（主链/财经媒体深度报道）")
        for n in ms[:8]:
            print(f"  [{n.get('src','?')}] {n['title'][:84]}  {n.get('url','')}")

    # 12.5 圈内动态（按优先级+重要程度取前5；含 DogDoing Alpha 热点 + 主流媒体 mainsm）
    mainsm_items = d.get("mainsm", [])
    print()
    print("## 圈内动态")
    dd_circle = d.get("dogdoing", {}) or {}
    alpha_items = []
    _ah = dd_circle.get("alpha_hotspots")
    _ah = _ah.get("data") if isinstance(_ah, dict) and isinstance(_ah.get("data"), list) else None
    if _ah:
        for it in _ah:
            nm = it.get("name", "")
            if nm:
                alpha_items.append({"title": f"[Alpha] {nm}",
                                    "text": f"Binance Alpha 热点「{nm}」（{it.get('type','?')} · 净流入 {it.get('netInflow','?')} · 代币x{it.get('tokenSize','?')}）",
                                    "src": "Binance Alpha", "kind": "Alpha热点"})
    cd = circle_dynamics(news_items, social_items, macro_clean, extra_items=alpha_items)
    if cd:
        for i, it in enumerate(cd, 1):
            print(f"  {i}. {it['title']}")
            print(f"     摘要：{it['summary']}")
            _u = it.get("url", "") or ""
            print(f"     来源：{it['src']} · {it['kind']}" + (f"  {_u}" if _u else ""))
    else:
        print("  （今日无显著圈内动态）")

    # 12.8 周度回顾（仅周一简报：上周热点回顾 + 本周可预估热点）
    if datetime.now().weekday() == 0:
        wr = weekly_review(news_items, social_items, macro_clean)
        print()
        print("## 周度回顾（周一简报专属 · 上周回顾 + 本周预估）")
        print("  【上周热点回顾】（采集历史 + 补充检索·近7天）")
        if wr["week_hotspots"]:
            for it in wr["week_hotspots"]:
                tag = f"跨源{it['cross']}家" if it.get("cross") else f"评分{it.get('score', '?')}"
                print(f"    {it['date']} {it['title']}（{tag}）")
                if it.get("summary"):
                    print(f"      摘要：{it['summary']}")
        else:
            print("    （上周暂无显著热点）")
        print("  【本周可预估热点候选】")
        if wr["coming"]:
            for it in wr["coming"]:
                print(f"    · {it['title']}  [来源:{it['src']}]")
        else:
            print("    （暂未识别到明确预告事件）")
        print()

    # 13. DogDoing 扩展维度（非冗余：OI异动/恐惧贪婪/Alpha热点/广场热度/预测市场/美股）
    dd = d.get("dogdoing", {}) or {}
    print()
    if not dd:
        print("## DogDoing 扩展维度: 未获取（数据源降级）")
        return
    print("## DogDoing 扩展维度（OI异动 · 恐惧贪婪 · Alpha热点 · 广场热度 · 预测市场 · 美股）")

    def _data(key):
        v = dd.get(key)
        return v.get("data") if isinstance(v, dict) and isinstance(v.get("data"), list) else None

    fg = dd.get("fear_greed") or {}
    fgv = fg.get("data") if isinstance(fg, dict) and isinstance(fg.get("data"), dict) else fg
    if isinstance(fgv, dict) and fgv.get("value") is not None:
        print(f"  恐惧贪婪指数: {int(fgv['value'])}（{fgv.get('label','?')}）")

    oi = _data("oi_divergence")
    if oi:
        print("  【OI持仓量异动｜价格vs持仓背离】")
        for it in oi[:6]:
            print(f"    {it.get('symbol','?'):<8} OI +{it.get('oiChangePct',0):.1f}% 价格 {it.get('priceChangePct',0):+.1f}% 背离 {it.get('divergenceRatio',0):.1f}")

    ah = _data("alpha_hotspots")
    if ah:
        print("  【Binance Alpha 热点板块】")
        for it in ah[:6]:
            print(f"    {it.get('name','')[:36]} | 净流入 {float(it.get('netInflow') or 0):.3g} | {it.get('type','?')} | 代币x{it.get('tokenSize','?')}")

    sh = _data("square_hype")
    if sh:
        print("  【币安广场热度 $TICKER】")
        for it in sh[:6]:
            print(f"    {it.get('symbol','?'):<8} 热度分 {it.get('score','?')} (源{it.get('sources','?')}) 24h {it.get('priceChangePct',0):+.1f}%")

    pm = _data("prediction_markets")
    if pm:
        print("  【42.space 预测市场】")
        for it in pm[:5]:
            print(f"    {it.get('question','')[:60]} | 量 ${float(it.get('volume') or 0):,.0f} | {it.get('status','?')}")

    us = _data("us_stocks")
    if us:
        print("  【美股板块（Mag7 / AI热门）】")
        for it in us[:8]:
            line = f"    {it.get('symbol','?'):<6} {str(it.get('name',''))[:12]} {it.get('changePct',0):+.2f}%"
            nw = (it.get("news") or [])[:1]
            if nw:
                line += f" | {str(nw[0].get('title',''))[:46]}"
            print(line)


if __name__ == "__main__":
    main()

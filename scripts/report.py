#!/usr/bin/env python3
"""精简报告模式 v3：AI 可直接用的结构化文本
含：精确事件匹配、宏观过滤、KOL观点、反差素材榜、数据卡"""
import subprocess, sys, os, json, re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

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


def circle_dynamics(news_items, social_items, macro_items, top=10):
    """圈内动态：定向监测 交易所 / 链·生态 / 交易所老板高管 / 孙哥(孙宇晨) / 币圈KOL / 特朗普(加密相关)。
    从新闻+社媒+宏观里按主体关键词打分，返回 [{title, summary, src, kind}]。"""
    CIRCLE_ENTITY = {
        "孙哥/孙宇晨": ["孙宇晨", "孙哥", "justin sun", "波场", "tron"],
        "交易所老板高管": ["cz", "赵长鹏", "brian armstrong", "richard teng", "coinbase ceo", "binance ceo",
                         "创始人", "高管", "董事长"],
        "币圈KOL": ["arthur hayes", "分析师", "大佬", "巨鲸", "whale", "vitalik", "v神", "马斯克", "喊单"],
        "特朗普/监管": ["特朗普", "trump", "美财", "财政部", "制裁", "sec", "监管", "白宫", "参议院", "灰度"],
        "交易所": ["binance", "币安", "okx", "欧易", "coinbase", "交易所", "上币", "上架", "下架", "暂停交易",
                  "上市", "现货", "合约", "bybit", "bitget", "gate", "kucoin"],
        "链/生态": ["主网", "mainnet", "layer2", "l2", "base", "arbitrum", "solana", "ethereum", "以太坊",
                   "生态", "tvl", "链上", "安全事件", "漏洞", "升级", "空投"],
    }
    HIGH_SIGNAL = ["孙宇晨", "cz", "trump", "特朗普", "安全事件", "空投", "下架", "暂停", "上架", "etf",
                   "加仓", "上市", "主网", "制裁", "币安", "coinbase", "okx", "空投", "卖出", "买入"]
    pool = []
    for it in news_items:
        pool.append({"title": it.get("title", ""), "text": it.get("text", it.get("title", "")),
                     "src": it.get("src", "?"), "kind": "新闻"})
    for it in social_items:
        pool.append({"title": it.get("title", it.get("text", "")), "text": it.get("text", it.get("title", "")),
                     "src": it.get("src", it.get("channel", "?")), "kind": "社媒"})
    for it in macro_items:
        pool.append({"title": it.get("title", ""), "text": it.get("text", it.get("title", "")),
                     "src": it.get("src", "?"), "kind": "宏观"})

    def score(it):
        t = (it["title"] + " " + it["text"]).lower()
        s = sum(1 for grp, kws in CIRCLE_ENTITY.items() if any(k.lower() in t for k in kws))
        s += 2 * sum(1 for k in HIGH_SIGNAL if k.lower() in t)
        if any(k.lower() in it["title"].lower() for k in HIGH_SIGNAL):
            s += 1
        return s

    for it in pool:
        it["score"] = score(it)
    # 加密相关性门控：必须含加密关键词，过滤无关股市/政治/关税
    CRYPTO_KW = ["btc", "bitcoin", "eth", "ethereum", "加密", "crypto", "coinbase", "binance", "币安", "okx",
                 "欧易", "token", "代币", "稳定币", "stablecoin", "tron", "波场", "solana", "etf", "交易所",
                 "合约", "现货", "主网", "链上", "数字资产", "defi", "nft", "meme", "web3", "doge", "xrp"]
    cand = sorted([it for it in pool
                   if it["score"] >= 3 and any(k in (it["title"] + " " + it["text"]).lower() for k in CRYPTO_KW)],
                  key=lambda x: x["score"], reverse=True)

    # 标题去重
    seen, out = set(), []
    for it in cand:
        k = re.sub(r"[^\w]", "", it["title"][:36]).lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
        if len(out) >= top:
            break
    res = []
    for it in out:
        summary = it["text"].strip()
        if not summary:
            summary = it["title"]
        res.append({"title": it["title"][:90], "summary": summary[:150], "src": it["src"], "kind": it["kind"]})
    return res


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

    # 3. 资金费率
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

    # 12.5 圈内动态（交易所/链·生态/老板高管/孙哥/币圈KOL/特朗普）
    print()
    print("## 圈内动态（交易所 · 链·生态 · 老板高管 · 孙哥 · 币圈KOL · 特朗普）")
    cd = circle_dynamics(news_items, social_items, macro_clean)
    if cd:
        for i, it in enumerate(cd, 1):
            print(f"  {i}. {it['title']}")
            print(f"     摘要：{it['summary']}")
            print(f"     来源：{it['src']}")
    else:
        print("  （今日无显著圈内动态）")

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

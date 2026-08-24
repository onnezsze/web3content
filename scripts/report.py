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
    print(f"# 数据源健康: market={d['source_health']['market']} news={d['source_health']['news']} social={d['source_health']['social']} macro={d['source_health']['macro']}")
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


if __name__ == "__main__":
    main()

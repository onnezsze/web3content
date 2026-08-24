#!/usr/bin/env python3
"""精简报告模式：输出 AI 可直接用的结构化文本（避免大 JSON 截断）
v2：异动榜带触发事件匹配、ETF/爆仓新闻区块、量比计算"""
import subprocess, sys, os, json, re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

# 量比关键词 → 触发事件匹配
def match_event(symbol, news_items):
    """在新闻中找包含该 symbol 的条目作为触发事件"""
    sym = symbol.lower()
    for n in news_items[:30]:
        title = (n.get("title") or "").lower()
        text = (n.get("text") or "").lower()
        if sym in title or sym in text:
            return n.get("title", "")[:80]
    return ""


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
    print(f"# 数据采集时间: {now}（采集于 {d.get('collected_at','')}）")
    print(f"# 数据源健康: market={d['source_health']['market']} news={d['source_health']['news']} social={d['source_health']['social']} macro={d['source_health']['macro']}")
    print()

    # 1. 市场
    m = d.get("market", {})
    print("## 行情（来源: CoinGecko）")
    for sym in ["BTC", "ETH", "SOL"]:
        if sym in m:
            v = m[sym]
            print(f"{sym}: ${v['price']:,.0f} | 1h {v.get('chg_1h','?'):+.2f}% | 24h {v.get('chg_24h','?'):+.2f}% | 7d {v.get('chg_7d','?'):+.2f}% | vol ${v.get('vol',0)/1e9:.1f}B")
    print()

    # 2. 资金费率
    f = d.get("funding", {})
    if f:
        print("## 资金费率（来源: OKX）")
        for sym, v in f.items():
            print(f"{sym}: {v.get('annualized_pct','?')}% 年化（费率 {v.get('funding_rate','?')}）")
    print()

    # 3. 异动榜（带触发事件）
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

    # 4. 情绪词频
    s = d.get("sentiment", {}).get("counts", {})
    if s:
        print("## 社群情绪词频（统计自TG/币安广场/老虎社区原文）")
        print("  " + " | ".join(f"{k}:{v}" for k, v in s.items() if v))
        samples = d.get("sentiment", {}).get("samples", {})
        for cat, lst in samples.items():
            if lst:
                print(f"  原声[{cat}]: " + " || ".join(x[:60] for x in lst[:2]))
    print()

    # 5. 昨日热点
    y = d.get("yesterday_top3")
    if y:
        print(f"## 昨日热点（{y.get('date','')}）")
        for t in y.get("topics", []):
            print(f"  - {t.get('title','')[:80]}（评分{t.get('score','?')}）")
    else:
        print("## 昨日热点: 首次记录（无历史）")
    print()

    # 6. 新闻（带来源/标签/交叉验证）
    print("## 新闻（含来源与标签，✓多源=交叉验证）")
    for n in news_items[:25]:
        cv = "✓多源" if n.get("cross_verified") else "单源"
        tags = ",".join(n.get("tags", [])) or "无标签"
        print(f"  [{n.get('src','?')}|{cv}|{tags}] {n['title'][:90]}")
    print()

    # 7. ETF/爆仓/资金流 相关新闻（单独区块，供市场快照引用）
    print("## ETF/爆仓/资金流相关新闻")
    flow_kw = ["etf", "inflow", "outflow", "liquidation", "爆仓", "grayscale", "贝莱德", "现货etf", "资金流入", "资金流出"]
    flow_news = [n for n in news_items if any(k in (n.get("title","")+n.get("text","")).lower() for k in flow_kw)]
    flow_news += [n for n in d.get("macro", []) if any(k in (n.get("title","")).lower() for k in flow_kw)]
    if flow_news:
        for n in flow_news[:8]:
            print(f"  [{n.get('src','?')}] {n['title'][:90]}")
    else:
        print("  （无相关新闻）")
    print()

    # 8. 社媒
    print("## 社媒（频道+内容）")
    for n in d.get("social", [])[:12]:
        print(f"  [{n.get('src', n.get('channel','?'))}] {n['title'][:90]}")
    print()

    # 9. 宏观
    print("## 宏观/传统金融")
    for n in d.get("macro", [])[:10]:
        print(f"  [{n.get('src','?')}] {n['title'][:90]}")


if __name__ == "__main__":
    main()

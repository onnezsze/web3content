#!/usr/bin/env python3
"""HTX Web3 行情热点数据采集器 v2 - 行情 + 新闻RSS + Telegram社媒"""
import urllib.request, json, re, html, ssl
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

UA = {'User-Agent': 'Mozilla/5.0 (compatible; HTXOpsBot/2.0)'}
ctx = ssl.create_default_context()

# 重点监控资产（需求文档核心池）
WATCHLIST = [
    "bitcoin","ethereum","solana","ripple","dogecoin","binancecoin","toncoin",
    "tron","cardano","avalanche-2","chainlink","sui","pepe","dogwifcoin",
    "shiba-inu","floki","bonk","fetch-ai","render-token","bittensor","worldcoin-wld",
    "ondo-finance","ethena","arbitrum","optimism","aptos","injective-protocol",
    "celestia","jupiter-exchange-solana","sei-network","near","aave","uniswap",
    "lido-dao","pendle"
]

# Telegram 公开频道监控列表（英文+中文币圈头部）
TG_CHANNELS = [
    # 中文币圈头部（已验证可抓取）
    "wublock",              # 吴说区块链（头部，行情/大V观点）
    "odaily_news",          # Odaily星球日报（头部媒体快讯）
    "jinse",                # 金色财经（快讯/安全事件）
    "chaincatcher",         # 链捕手（数据/ETF资金流）
    # 英文信息源
    "cointelegraph",        # 加密新闻
    "whale_alert",          # 大额转账预警
    "binance_announcements",# 币安公告
]

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout, context=ctx).read()

def get_market():
    ids = ",".join(WATCHLIST)
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}&price_change_percentage=1h,24h,7d&per_page=100"
    data = json.loads(fetch(url))
    out = []
    for c in data:
        out.append({
            "symbol": c["symbol"].upper(), "name": c["name"],
            "price": c["current_price"], "mc_rank": c["market_cap_rank"],
            "vol": c["total_volume"],
            "chg_1h": c.get("price_change_percentage_1h_in_currency"),
            "chg_24h": c.get("price_change_percentage_24h_in_currency"),
            "chg_7d": c.get("price_change_percentage_7d_in_currency"),
        })
    return out

def get_news():
    feeds = [
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("The Block", "https://www.theblock.co/rss.xml"),
    ]
    news = []
    for src, url in feeds:
        try:
            root = ET.fromstring(fetch(url))
            for item in root.iter("item"):
                title = item.findtext("title") or ""
                pub = item.findtext("pubDate") or ""
                desc = item.findtext("description") or ""
                desc = re.sub(r"<[^>]+>", "", desc)[:200]
                news.append({"src": src, "title": html.unescape(title).strip(),
                             "pub": pub, "desc": html.unescape(desc).strip()})
        except Exception as e:
            news.append({"src": src, "title": f"[FEED ERROR] {e}", "pub": "", "desc": ""})
    return news[:40]

def get_laohu():
    """老虎社区热帖（jina 渲染，覆盖美股/ETF/港股视角）"""
    out = []
    try:
        raw = fetch("https://r.jina.ai/https://www.laohu8.com/community").decode("utf-8", errors="ignore")
        # 提取标题行（### 开头）和帖子链接
        titles = re.findall(r'^###\s+(.+)$', raw, re.M)
        for t in titles[:12]:
            t = ' '.join(html.unescape(t).split())
            if t and len(t) > 5:
                out.append({"channel": "老虎社区", "text": t[:280], "time": ""})
    except Exception as e:
        out.append({"channel": "老虎社区", "text": f"[LAOHU ERROR] {e}", "time": ""})
    return out

def get_square():
    """币安广场热帖（通过 jina 代理，绕过 CloudFront）"""
    out = []
    try:
        raw = fetch("https://r.jina.ai/https://www.binance.com/zh-CN/square").decode("utf-8", errors="ignore")
        pattern = r'\[([^\]]{10,200})\]\(https://www\.binance\.com/zh-CN/square/post/\d+\)'
        posts = re.findall(pattern, raw)
        seen = set()
        for p in posts:
            t = ' '.join(html.unescape(p).split())
            if t and t not in seen and len(t) > 15:
                seen.add(t)
                out.append({"channel": "币安广场", "text": t[:280], "time": ""})
            if len(out) >= 12:
                break
    except Exception as e:
        out.append({"channel": "币安广场", "text": f"[SQUARE ERROR] {e}", "time": ""})
    return out

def get_eastmoney():
    """东方财富财经快讯（官方API直连）"""
    out = []
    try:
        url = "https://np-listapi.eastmoney.com/comm/web/getFastNewsList?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=15&req_trace=1"
        data = json.loads(fetch(url))
        items = data.get("data", {}).get("fastNewsList", [])
        for it in items[:15]:
            summary = (it.get("summary") or "").strip()
            if summary:
                out.append({"channel": "东方财富", "text": summary[:280], "time": it.get("showTime", "")})
    except Exception as e:
        out.append({"channel": "东方财富", "text": f"[EASTMONEY ERROR] {e}", "time": ""})
    return out

def get_tg():
    """抓取 Telegram 消息：优先 bot 监控群（可覆盖任意频道），兜底网页预览"""
    out = []
    # 方案1：bot 监控群（用户把频道加进群，bot 读取）
    try:
        from tg_monitor import fetch_group_messages
        for m in fetch_group_messages():
            out.append({"channel": m["channel"], "text": m["text"][:300], "time": ""})
    except Exception as e:
        out.append({"channel": "bot", "text": f"[TG BOT ERROR] {e}", "time": ""})

    # 方案2：网页预览兜底（已接入的中文/英文频道）
    for ch in TG_CHANNELS:
        try:
            raw = fetch(f"https://t.me/s/{ch}").decode("utf-8", errors="ignore")
            blocks = re.findall(
                r'<div class="tgme_widget_message text_not_supported_wrap js-widget_message".*?(?=<div class="tgme_widget_message text_not_supported_wrap js-widget_message"|$)',
                raw, re.S)
            for b in blocks[:4]:
                text = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
                date = re.search(r'datetime="([^"]+)"', b)
                t = html.unescape(re.sub(r'<[^>]+>', ' ', text.group(1))).strip() if text else ''
                t = ' '.join(t.split())
                if t:
                    out.append({"channel": ch, "text": t[:300],
                                "time": date.group(1) if date else ""})
        except Exception as e:
            out.append({"channel": ch, "text": f"[TG ERROR] {e}", "time": ""})
    return out

def main():
    mkt = get_market()
    news = get_news()
    tg = get_tg()
    square = get_square()
    em = get_eastmoney()
    laohu = get_laohu()

    print("=" * 60)
    print("MARKET DATA")
    print("=" * 60)
    for c in sorted(mkt, key=lambda x: x["chg_24h"] or 0, reverse=True):
        print(f"{c['symbol']:<6} ${c['price']:>10,.2f}  1h:{c['chg_1h']:>6.2f}%  24h:{c['chg_24h']:>7.2f}%  7d:{c['chg_7d']:>7.2f}%  rank:{c['mc_rank']}")

    print()
    print("=" * 60)
    print(f"NEWS ({len(news)})")
    print("=" * 60)
    for n in news[:15]:
        print(f"[{n['src']}] {n['title']}")

    print()
    print("=" * 60)
    print(f"BINANCE SQUARE ({len(square)})")
    print("=" * 60)
    for m in square[:10]:
        print(f"[{m['channel']}] {m['text'][:110]}")

    print()
    print("=" * 60)
    print(f"EASTMONEY ({len(em)})")
    print("=" * 60)
    for m in em[:10]:
        print(f"[{m['channel']}] {m['text'][:110]}")

    print()
    print("=" * 60)
    print(f"LAOHU ({len(laohu)})")
    print("=" * 60)
    for m in laohu[:10]:
        print(f"[{m['channel']}] {m['text'][:110]}")

    print()
    print("=" * 60)
    print(f"TELEGRAM ({len(tg)})")
    print("=" * 60)
    for m in tg[:20]:
        print(f"[@{m['channel']}] {m['time'][:16]} {m['text'][:110]}")

if __name__ == "__main__":
    main()

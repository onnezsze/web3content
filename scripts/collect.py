#!/usr/bin/env python3
"""Web3 行情热点采集器 v3
四层架构：采集层 → 预处理层 → 输出层 → 健康检查层
stdout 输出 JSON（AI 可 json.loads），stderr 输出人类可读文本。

用法：
  python3 collect.py                 # 正常模式，stdout=JSON, stderr=文本
  python3 collect.py --json-only     # 只输出 JSON（stderr 静默）
  python3 collect.py --preflight     # 健康检查
  python3 collect.py --source coingecko,gateio   # 只跑指定源
"""
import sys, os, json, time, argparse, concurrent.futures
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources.market import fetch_market_chain
from sources.news import fetch_news_chain
from sources.social import fetch_social_chain
from sources.macro import fetch_macro_chain
from sources.funding import FundingRates, count_sentiment
from sources.dogdoing import fetch_dogdoing_chain
from sources.hot_assets import fetch_hot_assets_chain
from sources.mainsm import fetch_mainsm_chain
from sources.zaobao import fetch_zaobao_chain
from sources.odaily import fetch_odaily_chain
from sources.hotfeed import fetch_hotfeed_chain
import preprocess
import hot_history

DEBUG = True


def log(msg):
    if DEBUG:
        print(msg, file=sys.stderr, flush=True)


def run_all():
    """并发跑四大类源，20s 总超时"""
    log("=" * 50)
    log("collecting...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        f_market = ex.submit(fetch_market_chain)
        f_news = ex.submit(fetch_news_chain)
        f_social = ex.submit(fetch_social_chain)
        f_macro = ex.submit(fetch_macro_chain)
        f_funding = ex.submit(FundingRates().fetch)
        f_dogdoing = ex.submit(fetch_dogdoing_chain)
        f_hotassets = ex.submit(fetch_hot_assets_chain)
        f_mainsm = ex.submit(fetch_mainsm_chain)
        f_zaobao = ex.submit(fetch_zaobao_chain)
        f_odaily = ex.submit(fetch_odaily_chain)
        f_hotfeed = ex.submit(fetch_hotfeed_chain)

        try:
            market_r, news_r, social_r, macro_r, funding_r, dogdoing_r, hotassets_r, mainsm_r, zaobao_r, odaily_r, hotfeed_r = (
                f_market.result(timeout=20),
                f_news.result(timeout=20),
                f_social.result(timeout=20),
                f_macro.result(timeout=20),
                f_funding.result(timeout=20),
                f_dogdoing.result(timeout=20),
                f_hotassets.result(timeout=20),
                f_mainsm.result(timeout=20),
                f_zaobao.result(timeout=20),
                f_odaily.result(timeout=20),
                f_hotfeed.result(timeout=20),
            )
        except concurrent.futures.TimeoutError:
            log("!! 20s timeout, using partial results")
            market_r = {"status": "timeout", "data": {}}
            news_r = {"status": "timeout", "data": []}
            social_r = {"status": "timeout", "data": []}
            macro_r = {"status": "timeout", "data": []}
            funding_r = {"status": "timeout", "data": {}}
            dogdoing_r = {"status": "timeout", "data": {}}
            hotassets_r = {"status": "timeout", "data": []}
            mainsm_r = {"status": "timeout", "data": []}
            zaobao_r = {"status": "timeout", "data": []}
            odaily_r = {"status": "timeout", "data": []}
            hotfeed_r = {"status": "timeout", "data": []}

    # social 链返回 (result, per-source status) 或直接 result
    if isinstance(social_r, tuple):
        social_result, social_status = social_r
    else:
        social_result = social_r
        social_status = social_r.get("source_status", {})

    log(f"market: {market_r['status']}")
    log(f"news: {news_r['status']} ({len(news_r.get('data', []))} items)")
    log(f"social: {social_result['status']} ({len(social_result.get('data', []))} items)")
    log(f"macro: {macro_r['status']} ({len(macro_r.get('data', []))} items)")
    log(f"funding: {funding_r['status']}")
    log(f"dogdoing: {dogdoing_r['status']} ({len(dogdoing_r.get('data', {}))} blocks)")

    return market_r, news_r, social_result, macro_r, social_status, funding_r, dogdoing_r, hotassets_r, mainsm_r, zaobao_r, odaily_r, hotfeed_r


def build_output(market_r, news_r, social_r, macro_r, social_status, funding_r, dogdoing_r, hotassets_r, mainsm_r, zaobao_r, odaily_r, hotfeed_r):
    market = market_r.get("data", {})
    news_items = news_r.get("data", [])
    mainsm_items = mainsm_r.get("data", [])
    zaobao_items = zaobao_r.get("data", [])
    odaily_items = odaily_r.get("data", [])
    social_items = social_r.get("data", [])
    macro_items = macro_r.get("data", [])
    funding = funding_r.get("data", {})
    hot_assets = hotassets_r.get("data", [])

    # 预处理
    news_clean, news_archived = preprocess.filter_and_dedup(news_items)
    social_clean, social_archived = preprocess.filter_and_dedup(social_items)
    macro_clean, macro_archived = preprocess.filter_and_dedup(macro_items)
    anomalies = preprocess.precompute_anomalies(market)

    # 情绪词频（基于社媒原文）
    sentiment = count_sentiment(social_items)

    # 昨日热点存档
    yesterday = hot_history.get_yesterday_top3()

    source_health = {
        "market": market_r["status"],
        "news": news_r["status"],
        "social": social_r["status"],
        "macro": macro_r["status"],
        "dogdoing": dogdoing_r["status"],
        "fallback_used": {
            "market": market_r.get("fallback_used", ""),
            "news": news_r.get("fallback_used", ""),
            "social": social_r.get("fallback_used", ""),
            "macro": macro_r.get("fallback_used", ""),
        },
        "detail": {
            "news": news_r.get("source_status", {}),
            "social": social_status,
            "macro": macro_r.get("source_status", {}),
        },
    }

    out = {
        "collected_at": datetime.now().astimezone().isoformat(),
        "source_health": source_health,
        "market": market,
        "precomputed": anomalies,
        "funding": funding,
        "sentiment": sentiment,
        "yesterday_top3": yesterday,
        "news": news_clean,
        "news_archive": news_archived,
        "social": social_clean,
        "social_archive": social_archived,
        "macro": macro_clean,
        "macro_archive": macro_archived,
        "dogdoing": dogdoing_r.get("data", {}),
        "hot_assets": hot_assets,
        "mainsm": mainsm_items,
        "zaobao": zaobao_items,
        "odaily": odaily_items,
        "hotfeed": hotfeed_r.get("data", []),
    }
    # 存档今日热点(供"周度回顾:采集历史"使用)
    try:
        today_hot = []
        sorted_news = sorted(news_clean, key=lambda x: (bool(x.get("cross_verified")), len(x.get("title", ""))), reverse=True)
        for n in sorted_news[:3]:
            sc = 10.0 if n.get("cross_verified") else round(7.0 + min(len(n.get("title", "")) / 60.0, 1.0), 1)
            today_hot.append({"title": n.get("title", "")[:120], "score": sc})
        if today_hot:
            hot_history.save_today_top3(today_hot)
    except Exception:
        pass

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true", help="健康检查模式")
    ap.add_argument("--json-only", action="store_true", help="只输出 JSON")
    ap.add_argument("--source", default="", help="只跑指定源（逗号分隔）")
    args = ap.parse_args()

    global DEBUG
    if args.json_only:
        DEBUG = False

    if args.preflight:
        from preflight import main as preflight_main
        preflight_main()
        return

    t0 = time.time()
    market_r, news_r, social_r, macro_r, social_status, funding_r, dogdoing_r, hotassets_r, mainsm_r, zaobao_r, odaily_r, hotfeed_r = run_all()
    out = build_output(market_r, news_r, social_r, macro_r, social_status, funding_r, dogdoing_r, hotassets_r, mainsm_r, zaobao_r, odaily_r, hotfeed_r)

    if not args.json_only:
        # stderr 人类可读摘要
        log(f"collected in {time.time()-t0:.1f}s")
        m = out["market"]
        if m:
            log("\n-- TOP GAINERS (24h) --")
            for g in out["precomputed"]["top_gainers"][:5]:
                log(f"  {g['symbol']:<6} {g['chg_24h']:+.2f}%  ${g['price']:,.2f}")
            log("-- TOP LOSERS (24h) --")
            for g in out["precomputed"]["top_losers"][:5]:
                log(f"  {g['symbol']:<6} {g['chg_24h']:+.2f}%  ${g['price']:,.2f}")
        log(f"\nnews: {len(out['news'])} fresh / {len(out['news_archive'])} archived")
        log(f"social: {len(out['social'])} / macro: {len(out['macro'])}")
        log(f"cross_verified: {sum(1 for n in out['news'] if n['cross_verified'])}")

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

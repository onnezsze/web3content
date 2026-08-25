#!/usr/bin/env python3
"""Web3 日报数据卡片图生成器：把 collect.py 数据变成创作者可直接用的 PNG。
输出到 ~/htx_bot/charts/YYYYMMDD/，打印 MEDIA: 路径供飞书/TG 直接发送。

图1: 24h涨幅榜 Top10（横向条形图，中文标注）
图2: 24h跌幅榜 Top10
图3: 情绪词频（恐慌/焦虑/抄底/看多/看空/FOMO）

用法:
  python3 charts.py            # 跑 collect.py 拿最新数据并出图
  python3 charts.py --json xxx.json   # 用已有 JSON 出图（测试用）
"""
import subprocess, sys, os, json
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(BASE, "charts")

# 中文字体：优先文泉驿正黑（Ubuntu 自带），找不到则回退系统字体
_FONT_CANDIDATES = ["WenQuanYi Zen Hei", "Noto Sans CJK SC", "SimHei", "PingFang SC"]
def _setup_font():
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in _FONT_CANDIDATES:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
_setup_font()

# 红涨绿跌（中文用户习惯）；如需币圈绿涨红跌，把两行互换
COLOR_UP = "#e74c3c"    # 涨 = 红
COLOR_DOWN = "#27ae60"  # 跌 = 绿
COLOR_BAR = "#5b8ff9"
COLOR_TITLE = "#1f2329"

def load_data(argv):
    if "--json" in argv:
        idx = argv.index("--json")
        with open(argv[idx + 1], encoding="utf-8") as f:
            return json.load(f)
    r = subprocess.run([sys.executable, os.path.join(BASE, "collect.py"), "--json-only"],
                       capture_output=True, text=True, timeout=120, cwd=BASE)
    return json.loads(r.stdout)

def bar_rank(items, title, out_path, color_field="chg_24h"):
    """横向条形图：涨幅/跌幅榜。items: [{symbol, chg_24h, price}]"""
    if not items:
        print(f"（{title}: 无数据，跳过）")
        return False
    items = items[:10]
    labels = [f"{it['symbol']}  {it['chg_24h']:+.1f}%" for it in items]
    vals = [it["chg_24h"] for it in items]
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in vals]
    y = range(len(items))
    ax.barh(list(y), vals, color=colors, height=0.62)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=11)
    ax.invert_yaxis()
    ax.axvline(0, color="#666", lw=0.8)
    for i, v in enumerate(vals):
        ax.text(v + (0.15 if v >= 0 else -0.15), i, f"{v:+.2f}%",
                va="center", ha="left" if v >= 0 else "right", fontsize=10)
    ax.set_xlabel("24h 涨跌幅 %", fontsize=10)
    ax.set_title(title, fontsize=15, fontweight="bold", color=COLOR_TITLE, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True

def sentiment_chart(counts, out_path):
    """情绪词频横向条形图"""
    if not counts:
        print("（情绪词频: 无数据，跳过）")
        return False
    cats = list(counts.keys())
    vals = [counts[c] for c in cats]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(cats, vals, color=COLOR_BAR, height=0.6)
    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels(cats, fontsize=12)
    ax.invert_yaxis()
    for i, v in enumerate(vals):
        ax.text(v + 0.05, i, str(v), va="center", fontsize=11)
    ax.set_xlabel("提及次数", fontsize=10)
    ax.set_title("社群情绪词频（TG/币安广场/老虎社区）", fontsize=14,
                 fontweight="bold", color=COLOR_TITLE, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True

def oi_chart(items, out_path):
    """OI 持仓量异动：每股两根横向条（OI变化% vs 价格变化%），背离直观可见"""
    if not items:
        print("（OI持仓量异动: 无数据，跳过）")
        return False
    import numpy as np
    items = items[:8]
    labels = [it.get("symbol", "?") for it in items]
    oi_vals = [it.get("oiChangePct", 0) for it in items]
    px_vals = [it.get("priceChangePct", 0) for it in items]
    y = np.arange(len(items))
    h = 0.36
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(y + h / 2, oi_vals, height=h, color="#e74c3c", label="OI 变化 %")
    ax.barh(y - h / 2, px_vals, height=h, color="#5b8ff9", label="价格变化 %")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11)
    ax.invert_yaxis()
    ax.axvline(0, color="#666", lw=0.8)
    ax.set_xlabel("变化 %", fontsize=10)
    ax.set_title("OI 持仓量异动｜价格 vs 持仓（背离预警）", fontsize=14,
                 fontweight="bold", color=COLOR_TITLE, pad=12)
    ax.legend(fontsize=10, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


def fear_greed_chart(fg, out_path):
    """恐惧贪婪指数：0-100 横向指示条 + 值/标签"""
    if not isinstance(fg, dict) or fg.get("value") is None:
        print("（恐惧贪婪指数: 无数据，跳过）")
        return False
    val = int(fg["value"])
    label = fg.get("label", "?")
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.barh([0], [val], color=COLOR_BAR, height=0.5)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, 0.7)
    ax.set_yticks([0])
    ax.set_yticklabels(["指数"], fontsize=11)
    for x in [0, 25, 50, 75, 100]:
        ax.axvline(x, color="#ddd", lw=0.6)
        ax.text(x, -0.4, str(x), ha="center", fontsize=9, color="#888")
    ax.text(val + 2, 0, f"{val}  {label}", va="center", fontsize=15,
            fontweight="bold", color=COLOR_TITLE)
    ax.set_title("加密恐惧贪婪指数 Fear & Greed", fontsize=14,
                 fontweight="bold", color=COLOR_TITLE, pad=12)
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


def stocks_chart(items, out_path):
    """美股 Mag7 / 热门涨跌横向条"""
    if not items:
        print("（美股板块: 无数据，跳过）")
        return False
    items = items[:8]
    labels = [f"{it.get('symbol','?')} {str(it.get('name',''))[:10]}" for it in items]
    vals = [it.get("changePct", 0) for it in items]
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in vals]
    y = range(len(items))
    ax.barh(list(y), vals, color=colors, height=0.62)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=11)
    ax.invert_yaxis()
    ax.axvline(0, color="#666", lw=0.8)
    for i, v in enumerate(vals):
        ax.text(v + (0.05 if v >= 0 else -0.05), i, f"{v:+.2f}%",
                va="center", ha="left" if v >= 0 else "right", fontsize=10)
    ax.set_xlabel("涨跌幅 %", fontsize=10)
    ax.set_title("美股板块（Mag7 / AI热门）", fontsize=14,
                 fontweight="bold", color=COLOR_TITLE, pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


def main():
    d = load_data(sys.argv)
    day = datetime.now().strftime("%Y%m%d")
    out_dir = os.path.join(CHART_DIR, day)
    os.makedirs(out_dir, exist_ok=True)

    pc = d.get("precomputed", {})
    s = d.get("sentiment", {}).get("counts", {})
    dd = d.get("dogdoing", {}) or {}

    def dd_list(key):
        v = dd.get(key)
        return v.get("data") if isinstance(v, dict) and isinstance(v.get("data"), list) else None

    paths = []
    if bar_rank(pc.get("top_gainers", []), "24h 涨幅榜 Top10", os.path.join(out_dir, "gainers.png")):
        paths.append(os.path.join(out_dir, "gainers.png"))
    if bar_rank(pc.get("top_losers", []), "24h 跌幅榜 Top10", os.path.join(out_dir, "losers.png")):
        paths.append(os.path.join(out_dir, "losers.png"))
    if sentiment_chart(s, os.path.join(out_dir, "sentiment.png")):
        paths.append(os.path.join(out_dir, "sentiment.png"))
    if oi_chart(dd_list("oi_divergence"), os.path.join(out_dir, "oi.png")):
        paths.append(os.path.join(out_dir, "oi.png"))
    fg = dd.get("fear_greed") or {}
    fgv = fg.get("data") if isinstance(fg, dict) and isinstance(fg.get("data"), dict) else fg
    if fear_greed_chart(fgv, os.path.join(out_dir, "fear_greed.png")):
        paths.append(os.path.join(out_dir, "fear_greed.png"))
    if stocks_chart(dd_list("us_stocks"), os.path.join(out_dir, "stocks.png")):
        paths.append(os.path.join(out_dir, "stocks.png"))

    if not paths:
        print("无任何图表生成（数据为空），请检查采集")
        sys.exit(1)

    print(f"# 图表已生成（{datetime.now().strftime('%Y-%m-%d %H:%M')}）")
    for p in paths:
        print(f"MEDIA:{p}")

if __name__ == "__main__":
    main()

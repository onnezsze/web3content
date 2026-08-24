#!/usr/bin/env python3
"""HTX Web3 行情热点分析 Telegram Bot
通过 WEB3Content_bot 提供服务：日报/单币种/热点/直播选题
数据采集复用 collect.py，AI 分析走 DeepSeek API
"""
import os, sys, json, time, urllib.request, urllib.parse, subprocess, traceback
from datetime import datetime

# ---------- 配置 ----------
BOT_TOKEN = os.getenv("WEB3_BOT_TOKEN", "7902391939:AAH-P1pHHrP0uqFJR41H9iF5rNuweJMOi8g")
BASE_DIR = "/home/ubuntu/htx_bot"
sys.path.insert(0, BASE_DIR)

from openai import OpenAI
DS_CLIENT = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

# ---------- Telegram API ----------
def tg_api(method, params=None, data=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"} if data else {})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())

def send_msg(chat_id, text):
    for i in range(0, len(text), 3900):
        tg_api("sendMessage", {"chat_id": chat_id, "text": text[i:i+3900]})
        time.sleep(0.4)

# ---------- 数据采集 ----------
def collect_data():
    r = subprocess.run([sys.executable, f"{BASE_DIR}/collect.py"],
                       capture_output=True, text=True, timeout=120, cwd=BASE_DIR,
                       env={**os.environ})
    return r.stdout[-8000:]

# ---------- AI 分析 ----------
def ai_generate(prompt, max_tokens=3000):
    resp = DS_CLIENT.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是 HTX 内容生态团队的 Web3 行情热点分析助手，输出简洁、专业、面向内容运营。禁用词：稳赚、必涨、抄底、暴富、翻倍、保证收益。所有行情内容必须含风险提示。"},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()

DAILY_TEMPLATE = """基于以下真实采集数据，生成今日 Web3 行情热点日报。

数据：
{data}

日报格式（纯文字，无表格无markdown符号）：
【Web3行情热点日报｜{date}】
一、市场概览（BTC/ETH价格、24h/7d涨跌、市场情绪、今日主线）
二、今日Top 5热点（每条：标题、热度评分0-10、相关资产、核心逻辑、运营建议、交易卡片建议）
三、异动资产榜（涨幅靠前7d/24h、跌幅、成交量放大、冲高回落标注）
四、今日热点内容形式建议（至少3条，推荐内容形式如行情圆桌/辩论赛/单点深度解读/社区图文贴/短视频/数据可视化/社群互动/快讯速报，不要推荐具体栏目名，每条含内容形式、对应热点、理由、制作要点、相关资产、卡片建议）
五、推特/社群内容建议（2-3条）
六、交易场景建议（优先关注/可挂卡片/仅讨论/表达限制）
七、风险提示（含"以上内容仅为行情信息整理和内容运营参考，不构成投资建议"）
数据异常行（含ERROR）直接忽略。"""

MARKET_TEMPLATE = """基于以下真实数据，分析 {symbol} 行情。

数据：
{data}

输出（纯文字）：
【{symbol} 行情分析】
一、当前表现（价格、1h/24h/7d涨跌、排名）
二、异动原因（结合新闻/社媒信息推断，标注"推测"）
三、短线关注点
四、内容运营建议（内容形式、角度）
五、交易卡片建议
六、风险提示（含不构成投资建议）"""

HOT_TEMPLATE = """基于以下真实数据，列出今日最值得跟进的热点 TOP5。

数据：
{data}

输出（纯文字）：
【今日热点 TOP5】
每条：热点标题、热度评分0-10、相关资产、一句话逻辑、适合内容形式
最后附风险提示。"""

LIVE_TEMPLATE = """基于以下真实数据，推荐 3 个今日直播选题（内容形式导向）。

数据：
{data}

输出（纯文字）：
【今日直播选题建议】
3个选题，每个含：标题、内容形式（行情圆桌/辩论赛/单点深度/圆桌等）、推荐理由、讨论提纲3-4点、相关资产、交易卡片建议、主播口播切入一句。
最后附风险提示。"""

COMMANDS = {
    "/daily": ("今日日报", DAILY_TEMPLATE, 3000),
    "/market": ("单币种分析", MARKET_TEMPLATE, 1500),
    "/hot": ("今日热点", HOT_TEMPLATE, 1200),
    "/live": ("直播选题", LIVE_TEMPLATE, 2500),
    "/start": None,
    "/help": None,
}

HELP_TEXT = """可用指令：
/daily - 今日行情热点日报
/market BTC - 单币种分析（如 /market SOL）
/hot - 今日热点TOP5
/live - 今日直播选题建议
行情数据实时采集，AI自动分析，仅供内容运营参考，不构成投资建议。"""

# ---------- 命令路由 ----------
def handle_command(cmd, args, chat_id):
    if cmd in ("/start", "/help"):
        send_msg(chat_id, HELP_TEXT)
        return

    print(f"[{datetime.now()}] collecting data for {cmd}...")
    send_msg(chat_id, "⏳ 正在采集行情和社媒数据，请稍候...")
    data = collect_data()
    date_str = datetime.now().strftime("%m月%d日")

    if cmd == "/daily":
        prompt = DAILY_TEMPLATE.format(data=data, date=date_str)
    elif cmd == "/market":
        sym = args.strip().upper() or "BTC"
        prompt = MARKET_TEMPLATE.format(symbol=sym, data=data)
    elif cmd == "/hot":
        prompt = HOT_TEMPLATE.format(data=data)
    elif cmd == "/live":
        prompt = LIVE_TEMPLATE.format(data=data)
    else:
        send_msg(chat_id, HELP_TEXT)
        return

    print(f"[{datetime.now()}] generating {cmd}...")
    result = ai_generate(prompt, max_tokens=3000)
    send_msg(chat_id, result)

# ---------- 主循环 ----------
def main():
    print(f"[{datetime.now()}] Bot started, waiting for commands...")
    offset = 0
    while True:
        try:
            resp = tg_api("getUpdates", {"timeout": 30, "offset": offset, "limit": 10})
            for u in resp.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                chat_id = msg.get("chat", {}).get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue
                # 提取命令（去掉@botname）
                parts = text.split(None, 1)
                cmd = parts[0].split("@")[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                # 支持中文指令
                alias = {"日报": "/daily", "热点": "/hot", "选题": "/live", "行情": "/market", "daily": "/daily", "hot": "/hot", "live": "/live"}
                cmd = alias.get(cmd, cmd)
                if cmd.startswith("/"):
                    print(f"[{datetime.now()}] cmd={cmd} args={args} from={chat_id}")
                    try:
                        handle_command(cmd, args, chat_id)
                    except Exception as e:
                        send_msg(chat_id, f"处理失败：{e}")
                        print(traceback.format_exc())
        except Exception as e:
            print(f"[{datetime.now()}] poll error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

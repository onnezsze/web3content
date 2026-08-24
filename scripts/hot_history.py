"""昨日热点存档：记录每日 top3 热点，供次日追踪生命周期"""
import json, os
from datetime import datetime, timedelta

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hot_history.json")


def save_today_top3(hot_topics):
    """保存今日 top3 热点（含评分），写入存档"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            with open(HISTORY_FILE) as f:
                hist = json.load(f)
        except Exception:
            hist = {}
        hist[today] = hot_topics[:3]
        # 只保留最近 7 天
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        hist = {k: v for k, v in hist.items() if k >= cutoff}
        with open(HISTORY_FILE, "w") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_yesterday_top3():
    """读取昨日 top3，供 AI 追踪今日表现"""
    try:
        with open(HISTORY_FILE) as f:
            hist = json.load(f)
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        for d in [yesterday]:
            if d in hist:
                return {"date": d, "topics": hist[d]}
        # 找不到昨天就取最近一天
        if hist:
            latest = max(hist.keys())
            return {"date": latest, "topics": hist[latest]}
        return None
    except Exception:
        return None

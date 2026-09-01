"""华尔街见闻·财经日历源：https://wallstreetcn.com/calendar
数据来自 api-one-wscn.awtmt.com/apiv1/finance/macrodatas?start=%s&end=%s
按 北京时间当天(可含前后) 抓取宏观财经日历事件，供首页「日历」tab 展示。
"""
from .base import Source
import calendar, datetime, time


class WSCNCalendar(Source):
    name = "wscn_calendar"

    def __init__(self, days=1, append_days=0):
        super().__init__()
        self.days = days      # 要抓取的天数(0=今天)
        self.append_days = append_days

    def fetch(self):
        try:
            # 以北京时间(UTC+8)计算当天 00:00 - 次日 00:00
            now = time.time()
            bj = now + 8 * 3600
            bj_dt = datetime.datetime.utcfromtimestamp(bj)
            base = bj_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            start = base - datetime.timedelta(days=self.days)
            end = base + datetime.timedelta(days=self.append_days + 1) - datetime.timedelta(seconds=1)
            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())
            url = (f"https://api-one-wscn.awtmt.com/apiv1/finance/macrodatas"
                   f"?start={start_ts}&end={end_ts}")
            data = self.http_json(url, timeout=10, headers={'Referer': 'https://wallstreetcn.com/calendar'})
            items = (data.get("data", {}) or {}).get("items", [])
            out = []
            for it in items or []:
                if not it.get("event"):
                    continue
                ev = {
                    "title": str(it.get("title") or "").strip(),
                    "event": str(it.get("event") or "").strip(),
                    "country": it.get("country") or "",
                    "importance": int(it.get("importance") or 0),
                    "unit": it.get("unit") or "",
                    "quantity": it.get("quantity") or "",
                    "actual": it.get("actual") or "",
                    "forecast": it.get("forecast") or "",
                    "previous": it.get("previous") or "",
                    "period": it.get("period") or "",
                    "ts": int(it.get("public_date") or 0),
                    "published_at": datetime.datetime.utcfromtimestamp(int(it.get("public_date") or 0)).strftime("%Y-%m-%dT%H:%M:%S") if it.get("public_date") else "",
                    "src": "华尔街见闻",
                    "text": str(it.get("title") or "").strip(),
                }
                out.append(ev)
            # 按发布时间排序，importance 高的在前、时间早的在前
            out.sort(key=lambda x: (x.get("ts") or 0))
            if out:
                return self.ok(out)
            return self.fail("empty")
        except Exception as e:
            return self.fail(e)


def fetch_wscn_calendar_chain(days=1, append_days=0):
    r = WSCNCalendar(days=days, append_days=append_days).fetch()
    if r["status"] == "ok":
        return {"status": "ok", "data": r["data"], "source_status": {"wscn_calendar": "ok"}}
    return {"status": "failed", "data": [], "source_status": {"wscn_calendar": str(r.get("error", ""))[:30]}}

"""社媒源：Telegram 频道 + 币安广场(jina) + 老虎社区(直连HTML)"""
from .base import Source
import html, re
import concurrent.futures


class TelegramChannels(Source):
    name = "telegram"

    CHANNELS = [
        "wublock", "odaily_news", "jinse", "chaincatcher",
        "cointelegraph", "whale_alert", "binance_announcements",
    ]

    def fetch(self):
        try:
            out = []
            for ch in self.CHANNELS:
                try:
                    raw = self.http_get(f"https://t.me/s/{ch}", timeout=6).decode("utf-8", errors="ignore")
                    blocks = re.findall(
                        r'<div class="tgme_widget_message text_not_supported_wrap js-widget_message".*?(?=<div class="tgme_widget_message text_not_supported_wrap js-widget_message"|$)',
                        raw, re.S)
                    for b in blocks[:3]:
                        text = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
                        date = re.search(r'datetime="([^"]+)"', b)
                        t = html.unescape(re.sub(r"<[^>]+>", " ", text.group(1))).strip() if text else ""
                        t = " ".join(t.split())
                        if t:
                            out.append({
                                "channel": ch, "text": t[:300],
                                "time": date.group(1) if date else "",
                            })
                except Exception:
                    continue
            if out:
                return self.ok(out)
            return self.fail("all tg channels failed")
        except Exception as e:
            return self.fail(e)


class JinaSquare(Source):
    """币安广场（jina 代理）"""
    name = "jina_square"

    def fetch(self):
        try:
            raw = self.http_get("https://r.jina.ai/https://www.binance.com/zh-CN/square", timeout=10).decode("utf-8", errors="ignore")
            pattern = r"\[([^\]]{10,200})\]\(https://www\.binance\.com/zh-CN/square/post/\d+\)"
            posts = re.findall(pattern, raw)
            out = []
            seen = set()
            for p in posts:
                t = " ".join(html.unescape(p).split())
                k = self.dedup_key(t)
                if t and k not in seen and len(t) > 15:
                    seen.add(k)
                    out.append({"channel": "binance_square", "text": t[:280], "time": ""})
                if len(out) >= 10:
                    break
            if out:
                return self.ok(out)
            return self.fail("jina square empty/403")
        except Exception as e:
            return self.fail(e)


class Laohu(Source):
    """老虎社区直连 HTML"""
    name = "laohu"

    def fetch(self):
        try:
            raw = self.http_get("https://www.laohu8.com/community", timeout=10).decode("utf-8", errors="ignore")
            # 提取 h2/h3 标题
            titles = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", raw, re.S)
            out = []
            seen = set()
            for t in titles:
                t = " ".join(html.unescape(re.sub(r"<[^>]+>", "", t)).split())
                k = self.dedup_key(t)
                if t and k not in seen and len(t) > 5:
                    seen.add(k)
                    out.append({"channel": "laohu", "text": t[:280], "time": ""})
                if len(out) >= 10:
                    break
            if out:
                return self.ok(out)
            return self.fail("laohu no titles")
        except Exception as e:
            return self.fail(e)


def fetch_social_chain():
    """并发跑所有社媒源，合并输出（多源才能交叉验证）"""
    all_data = []
    statuses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(cls().fetch): cls.__name__ for cls in (TelegramChannels, JinaSquare, Laohu)}
        for f in concurrent.futures.as_completed(futs, timeout=18):
            name = futs[f]
            try:
                r = f.result()
                statuses[name] = r["status"]
                if r["status"] == "ok":
                    all_data.extend(r["data"])
            except Exception as e:
                statuses[name] = f"err:{str(e)[:30]}"
    if all_data:
        return {"status": "ok", "data": all_data, "source_status": statuses}
    return {"status": "failed", "data": [], "source_status": statuses}

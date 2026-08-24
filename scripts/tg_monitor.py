#!/usr/bin/env python3
"""Telegram 监控群采集器 - 通过 bot 读取监控群内所有频道消息"""
import urllib.request, json, os, time

TOKEN = os.getenv("WEB3_BOT_TOKEN", "7902391939:AAH-P1pHHrP0uqFJR41H9iF5rNuweJMOi8g")
OFFSET_FILE = "/home/ubuntu/htx_bot/.tg_offset"

def api(method, params=""):
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}{params}", method="GET")
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

def get_last_offset():
    try:
        return int(open(OFFSET_FILE).read().strip())
    except Exception:
        return 0

def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

def fetch_group_messages(limit=100):
    """拉取监控群消息，按频道聚合"""
    offset = get_last_offset()
    params = f"?timeout=15&limit={limit}"
    if offset:
        params += f"&offset={offset}"
    resp = api("getUpdates", params)
    updates = resp.get("result", [])
    max_offset = offset

    msgs = []
    for u in updates:
        mid = u.get("update_id", 0)
        if mid > max_offset:
            max_offset = mid
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat", {})
        if not chat:
            continue
        # 只采集团消息（监控群）
        text = msg.get("text") or msg.get("caption") or ""
        if not text:
            continue
        # 来源识别：转发来源 > 发送频道 > 发送者
        src = ""
        fwd = msg.get("forward_from_chat", {})
        if fwd:
            src = fwd.get("title") or fwd.get("username") or ""
        elif msg.get("sender_chat"):
            src = msg["sender_chat"].get("title") or msg["sender_chat"].get("username") or ""
        else:
            src = msg.get("from", {}).get("username", "")
        msgs.append({
            "channel": src or chat.get("title", "unknown"),
            "text": text.strip()[:500],
            "date": msg.get("date", 0),
        })

    if max_offset > offset:
        save_offset(max_offset)
    return msgs

if __name__ == "__main__":
    msgs = fetch_group_messages()
    print(f"Fetched {len(msgs)} messages")
    for m in msgs[-15:]:
        print(f"[{m['channel']}] {m['text'][:100]}")

#!/usr/bin/env python3
"""把日报转换成「飞书文档」(Feishu docx)，内含排版文本 + 6 张配图。

流程：collect.py + report.py 采集→生成 report 文本；charts.py 生成配图；
创建飞书文档→插入标题/列表正文→上传图表→以 image 块嵌入(带图注)→加用户为协作者。
stdout 末尾打印 FEISHU_DOC_URL: <链接>（cron/agent 只需回传该链接）。

用法：
  python3 feishu_doc.py                  # 完整管线，生成今日日报文档
  python3 feishu_doc.py --no-charts      # 只出文本，不嵌图
  python3 feishu_doc.py --text file.txt  # 用已有 report 文本建文档(测试用)
"""
import os, re, sys, json, subprocess, struct, requests
from datetime import datetime

HOME = os.path.expanduser("~")
BASE = os.path.dirname(os.path.abspath(__file__))
FEISHU = "https://open.feishu.cn"
USER = os.environ.get("FEISHU_USER_OPEN_ID", "ou_94827a21d5597e1e824de6a5e8cd11e2")
# 配图顺序 + 图注
CHARTS = [
    ("gainers.png", "图1 · 24h 涨幅榜 Top10"),
    ("losers.png", "图2 · 24h 跌幅榜 Top10"),
    ("sentiment.png", "图3 · 社群情绪词频"),
    ("oi.png", "图4 · OI 持仓量异动(价格vs持仓)"),
    ("fear_greed.png", "图5 · 恐惧贪婪指数"),
    ("stocks.png", "图6 · 美股板块"),
]

def env(key):
    for line in open(os.path.join(HOME, ".hermes", ".env")):
        line = line.strip()
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""

_APP_ID = env("FEISHU_APP_ID")
_APP_SECRET = env("FEISHU_APP_SECRET")

def token():
    r = requests.post(f"{FEISHU}/open-apis/auth/v3/tenant_access_token/internal",
                      json={"app_id": _APP_ID, "app_secret": _APP_SECRET}, timeout=15)
    t = r.json().get("tenant_access_token", "")
    if not t:
        raise RuntimeError(f"get token failed: {r.text[:200]}")
    return t

def req(method, url, tok, **kw):
    h = {"Authorization": f"Bearer {tok}"}
    if "headers" in kw:
        h.update(kw.pop("headers"))
    return requests.request(method, url, headers=h, **kw, timeout=40)

def run_report():
    r = subprocess.run([sys.executable, os.path.join(BASE, "report.py")],
                       capture_output=True, text=True, timeout=150, cwd=BASE)
    return r.stdout

def run_charts():
    """跑 charts.py 生成今日配图，返回 {filename: abspath}"""
    subprocess.run([sys.executable, os.path.join(BASE, "charts.py")],
                   capture_output=True, text=True, timeout=150, cwd=BASE)
    day = datetime.now().strftime("%Y%m%d")
    d = os.path.join(BASE, "charts", day)
    out = {}
    if os.path.isdir(d):
        for fn, _ in CHARTS:
            p = os.path.join(d, fn)
            if os.path.exists(p):
                out[fn] = p
    return out

def png_size(path):
    with open(path, "rb") as f:
        f.read(16)
        w, h = struct.unpack(">II", f.read(8))
    return w, h

def text_run(content, bold=False):
    return {"text_run": {"content": content, "text_element_style": {"bold": bold}}}

def _clean(s):
    """去掉 markdown 加粗/斜体星号噪音"""
    return s.replace("**", "").replace("__", "").replace("~~", "")

def parse_to_blocks(text):
    blocks = []
    emoji_headers = ("🔥", "📌", "💡", "⚠️", "🎯", "📊")
    in_code = False
    code_lines = []
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if s.startswith("```"):
            if in_code:
                blocks.append({"block_type": 14, "code": {"elements": [{"text_run": {"content": "\n".join(code_lines)}}]}})
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not s:
            continue
        if s.startswith("### "):
            blocks.append({"block_type": 5, "heading3": {"elements": [text_run(_clean(s[4:]), True)]}})
        elif s.startswith("## "):
            blocks.append({"block_type": 4, "heading2": {"elements": [text_run(_clean(s[3:]), True)]}})
        elif s.startswith("# "):
            blocks.append({"block_type": 3, "heading1": {"elements": [text_run(_clean(s[2:]), True)]}})
        elif s.startswith(emoji_headers):
            blocks.append({"block_type": 4, "heading2": {"elements": [text_run(_clean(s), True)]}})
        elif s.startswith("> "):
            blocks.append({"block_type": 15, "quote": {"elements": [text_run(_clean(s[2:]))]}})
        elif s.startswith(("· ", "• ", "- ", "* ")):
            blocks.append({"block_type": 12, "bullet": {"elements": [text_run(_clean(s[2:]))]}})
        elif len(s) > 2 and s[0] == "#" and s[1].isdigit():
            blocks.append({"block_type": 2, "text": {"elements": [text_run(_clean(s), True)]}})
        else:
            bold = "**" in s
            blocks.append({"block_type": 2, "text": {"elements": [text_run(_clean(s), bold)]}})
    if in_code and code_lines:
        blocks.append({"block_type": 14, "code": {"elements": [{"text_run": {"content": "\n".join(code_lines)}}]}})
    return blocks

def create_doc(tok, title):
    r = req("POST", f"{FEISHU}/open-apis/docx/v1/documents", tok, json={"title": title})
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"create doc failed: {j.get('msg')} {j.get('code')}")
    return j["data"]["document"]["document_id"]

def insert_blocks(tok, doc_id, blocks):
    for i in range(0, len(blocks), 40):
        chunk = blocks[i:i + 40]
        r = req("POST", f"{FEISHU}/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                tok, json={"children": chunk, "index": i})
        j = r.json()
        if j.get("code") != 0:
            print(f"  insert chunk {i//40}: {j.get('code')} {j.get('msg')} (skip rest)", file=sys.stderr)
            return

def append_block(tok, doc_id, block):
    """把 block 追加到文档根块末尾：动态取当前子块数作为 index"""
    r = req("GET", f"{FEISHU}/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}", tok)
    j = r.json()
    idx = 0
    if j.get("code") == 0:
        idx = len(j["data"].get("children", []))
    r2 = req("POST", f"{FEISHU}/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
             tok, json={"children": [block], "index": idx})
    return r2.json().get("code") == 0

def upload_image(tok, doc_id, path):
    with open(path, "rb") as f:
        data = {"file_name": os.path.basename(path), "parent_type": "docx_image",
                "parent_node": doc_id, "size": str(os.path.getsize(path))}
        r = req("POST", f"{FEISHU}/open-apis/drive/v1/medias/upload_all?file_type=docx_image",
                tok, data=data, files={"file": (os.path.basename(path), f, "image/png")})
    j = r.json()
    return j.get("data", {}).get("file_token")

def insert_image(tok, doc_id, file_token, w, h):
    img = {"block_type": 27, "image": {"token": file_token, "width": w, "height": h}}
    return append_block(tok, doc_id, img)

def append_caption(tok, doc_id, text):
    blk = {"block_type": 2, "text": {"elements": [text_run(text, True)]}}
    return append_block(tok, doc_id, blk)

def share_doc(tok, doc_id):
    r = req("POST", f"{FEISHU}/open-apis/drive/v1/permissions/{doc_id}/members?type=docx", tok,
            json={"member_type": "openid", "member_id": USER, "perm": "view"})
    return r.json().get("code") == 0

def main():
    args = sys.argv[1:]
    embed_charts = "--no-charts" not in args
    if "--text" in args:
        with open(args[args.index("--text") + 1], encoding="utf-8") as f:
            report_text = f.read()
    else:
        report_text = run_report()

    title = f"Web3行情热点日报 {datetime.now().strftime('%m月%d日')}"
    blocks = parse_to_blocks(report_text)
    print(f"parsed {len(blocks)} blocks")

    tok = token()
    doc_id = create_doc(tok, title)
    print(f"created doc {doc_id}")

    # 正文
    insert_blocks(tok, doc_id, blocks)

    # 配图区
    if embed_charts:
        charts = run_charts()
        if charts:
            cap = {"block_type": 5, "heading3": {"elements": [text_run("📊 今日配图", True)]}}
            append_block(tok, doc_id, cap)
            for fn, caption in CHARTS:
                p = charts.get(fn)
                if not p:
                    continue
                ft = upload_image(tok, doc_id, p)
                if not ft:
                    print(f"  upload {fn} failed", file=sys.stderr)
                    continue
                w, h = png_size(p)
                if insert_image(tok, doc_id, ft, w, h):
                    append_caption(tok, doc_id, caption)
                    print(f"  embedded {fn}")
                else:
                    print(f"  embed {fn} failed", file=sys.stderr)

    shared = share_doc(tok, doc_id)
    print(f"shared={shared}")
    print(f"FEISHU_DOC_URL: https://feishu.cn/docx/{doc_id}")

if __name__ == "__main__":
    main()

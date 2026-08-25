#!/usr/bin/env python3
"""把日报转换成「飞书文档」(Feishu docx)。

受当前飞书应用权限限制：只能插入 text/heading/bullet/ordered/quote/code 块
(image/table/divider 复杂块会被拒，报 1770001)。因此文档用「标题+项目符号+加粗」
排版，保证完整、清晰。图表图片暂无法内嵌(见 SKILL.md 已知限制)。

用法：
  python3 feishu_doc.py                  # 跑 collect.py + report.py，生成今日日报文档
  python3 feishu_doc.py --text file.txt  # 用已有 report 文本建文档(测试用)
  stdout 末尾打印 FEISHU_DOC_URL: <链接>
"""
import os, re, sys, json, subprocess, requests
from datetime import datetime

HOME = os.path.expanduser("~")
BASE = os.path.dirname(os.path.abspath(__file__))
FEISHU = "https://open.feishu.cn"
USER = os.environ.get("FEISHU_USER_OPEN_ID", "ou_94827a21d5597e1e824de6a5e8cd11e2")

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
    """跑 report.py 拿结构化文本"""
    r = subprocess.run([sys.executable, os.path.join(BASE, "report.py")],
                       capture_output=True, text=True, timeout=150, cwd=BASE)
    return r.stdout

def text_run(content, bold=False):
    return {"text_run": {"content": content, "text_element_style": {"bold": bold}}}

def parse_to_blocks(text):
    """把 report 文本 → 飞书 block 列表"""
    blocks = []
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        if s.startswith("## "):
            blocks.append({"block_type": 4, "heading2": {"elements": [text_run(s[3:], True)]}})
        elif s.startswith("# "):
            blocks.append({"block_type": 3, "heading1": {"elements": [text_run(s[2:], True)]}})
        elif s.startswith("【"):
            blocks.append({"block_type": 5, "heading3": {"elements": [text_run(s, True)]}})
        elif s.startswith("• "):
            blocks.append({"block_type": 12, "bullet": {"elements": [text_run(s[2:])]}})
        elif s.startswith("- ") or s.startswith("  -"):
            blocks.append({"block_type": 12, "bullet": {"elements": [text_run(s[2:])]}})
        elif s.startswith(("⚠️", "> ")):
            blocks.append({"block_type": 15, "quote": {"elements": [text_run(s.lstrip("> "))]}})
        else:
            blocks.append({"block_type": 2, "text": {"elements": [text_run(s)]}})
    return blocks

def create_doc(tok, title):
    r = req("POST", f"{FEISHU}/open-apis/docx/v1/documents", tok, json={"title": title})
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"create doc failed: {j.get('msg')} {j.get('code')}")
    return j["data"]["document"]["document_id"]

def insert_blocks(tok, doc_id, blocks):
    """分批插入(每次<=40块)，index 顺序追加"""
    for i in range(0, len(blocks), 40):
        chunk = blocks[i:i + 40]
        r = req("POST", f"{FEISHU}/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                tok, json={"children": chunk, "index": i})
        j = r.json()
        if j.get("code") != 0:
            print(f"  insert chunk {i//40}: {j.get('code')} {j.get('msg')} (skip rest)", file=sys.stderr)
            return

def share_doc(tok, doc_id):
    r = req("POST", f"{FEISHU}/open-apis/drive/v1/permissions/{doc_id}/members?type=docx", tok,
            json={"member_type": "openid", "member_id": USER, "perm": "view"})
    return r.json().get("code") == 0

def main():
    args = sys.argv[1:]
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
    insert_blocks(tok, doc_id, blocks)
    shared = share_doc(tok, doc_id)
    print(f"shared={shared}")
    print(f"FEISHU_DOC_URL: https://feishu.cn/docx/{doc_id}")

if __name__ == "__main__":
    main()

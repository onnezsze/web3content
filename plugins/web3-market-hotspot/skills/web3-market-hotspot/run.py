#!/usr/bin/env python3
"""Web3 行情热点简报 —— 统一入口（Claude / Slack / 任意 AI 推荐用这个）。

默认输出**结构化文本简报**（Markdown 化文本，Claude/GPT/Slack 可直接消费），
零第三方依赖（核心管线纯 Python 标准库），不会误触飞书/配图路径。

用法：
  python3 run.py              # 生成今天的文本简报（推荐，Slack/Claude 用这个）
  python3 run.py --feishu     # 顺便生成飞书文档（需 lark-oapi + ~/.hermes/.env 凭据）
  python3 run.py --preflight  # 数据源健康检查（18 源）

说明：refresh 入口只跑 report.py（文本）；charts.py（配图）/ feishu_doc.py（飞书文档）为可选增强。
脚本 fail-soft：任一源失败不影响其余源。
"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")


def run_report():
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "report.py")],
                          capture_output=True, text=True, timeout=180, cwd=SCRIPTS)


def main():
    args = sys.argv[1:]
    if "--preflight" in args:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "collect.py"), "--preflight"],
                           capture_output=True, text=True, timeout=60, cwd=SCRIPTS)
        sys.stdout.write(r.stdout)
        return
    r = run_report()
    sys.stdout.write(r.stdout)          # 文本简报 → stdout，供 agent 直接消费
    if "--feishu" in args:              # 可选：同时出飞书文档
        try:
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "feishu_doc.py")],
                           capture_output=True, text=True, timeout=120, cwd=SCRIPTS)
        except Exception as e:
            print(f"[warn] feishu 生成失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

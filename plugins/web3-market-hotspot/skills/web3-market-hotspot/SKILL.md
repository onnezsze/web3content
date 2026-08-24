---
name: web3-market-hotspot
description: "Web3 行情热点采集与分析：多源抓取加密行情、新闻、社媒热点（Telegram/币安广场/东方财富/老虎社区），输出日报、热点榜单、内容选题建议和交易场景参考。"
version: 2.0.0
author: Lucas + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web3, crypto, market-analysis, hot-topic, content-ops, news-aggregation]
---

# Web3 行情热点采集与分析

多源采集 Web3 市场数据（行情/新闻/社媒/传统金融联动），输出结构化分析结果，供内容运营、直播策划、社媒运营使用。

## 触发场景

- 需要快速了解今日加密市场行情和热点
- 需要监控市场异动、重大新闻、社媒讨论热点
- 需要生成内容选题建议（直播/推文/短视频/社群）
- 需要了解宏观/传统金融（美股/A股）与加密市场的联动
- 任何 AI Agent（Codex/Claude/Hermes）需要实时 Web3 市场情报时

## 使用方式（AI Agent 调用）

### 1. 采集数据

```bash
python3 scripts/collect.py
```

脚本用纯 Python 标准库实现（无第三方依赖），输出六段结构化文本：

```
MARKET DATA      - 38个重点资产：价格/1h/24h/7d涨跌幅/市值排名
NEWS             - 全球加密新闻（CoinTelegraph/CoinDesk/The Block RSS）
BINANCE SQUARE   - 币安广场 KOL 观点/散户情绪
EASTMONEY        - 东方财富财经快讯（A股/宏观）
LAOHU            - 老虎社区热帖（美股/ETF/港股）
TELEGRAM         - 中文头部频道（吴说/Odaily/金色财经/链捕手）+ 英文源
```

### 2. AI 分析

将采集输出作为上下文，按本 skill 的分析框架生成结果。AI 可直接从脚本输出中提取：
- 异动资产（24h/7d 涨跌幅排序）
- 热点事件（新闻标题 + 社媒讨论 + 行情异动交叉验证）
- 内容选题（结合数据生成可落地的选题建议）

## 分析框架（AI 生成内容时遵循）

### 日报格式
```
【Web3行情热点日报｜M月D日】
一、市场概览（BTC/ETH 价格、24h/7d 涨跌、市场情绪、今日主线）
二、今日Top 5热点（标题、热度评分0-10、相关资产、核心逻辑、运营建议、交易卡片建议）
三、异动资产榜（涨幅/跌幅/成交量放大/冲高回落标注）
四、内容形式建议（行情圆桌/辩论赛/单点深度解读/社区图文贴/短视频/数据可视化/社群互动/快讯速报，每条含理由、制作要点、相关资产）
五、推文/社群内容建议
六、交易场景建议（优先关注/可挂卡片/仅讨论）
七、风险提示
```

### 热点评分模型
- 9-10分：S级，立即跟进
- 7-8.9分：A级，适合直播/推文
- 5-6.9分：B级，日报观察
- 5分以下：C级，仅记录

评分维度：行情波动、成交量变化、社媒热度、新闻权威性、影响范围、交易相关性、内容运营价值。

### 合规要求（强制）
- 禁用词：稳赚、必涨、抄底、暴富、翻倍、保证收益、精准预测
- 未确认消息必须标注"未确认"
- 所有行情相关内容必须含风险提示
- 币安广场帖子为散户观点，仅作情绪参考，不可作为事实依据

## 关键实现细节

### 币安广场
直接 curl 被 CloudFront 拦截，必须走 jina 代理：
```
https://r.jina.ai/https://www.binance.com/zh-CN/square
```
正则提取 `\[标题\]\(https://www.binance.com/zh-CN/square/post/\d+\)`

### 东方财富快讯
官方 API 直连：
```
https://np-listapi.eastmoney.com/comm/web/getFastNewsList?client=web&biz=web_724&fastColumn=102&pageSize=15&req_trace=1
```

### 老虎社区
JS 渲染，走 jina 代理 `https://r.jina.ai/https://www.laohu8.com/community`，提取 `### ` 标题行。

### Telegram 频道
`https://t.me/s/频道名` 网页预览。已验证可用：wublock、odaily_news、jinse、chaincatcher、cointelegraph、whale_alert、binance_announcements。注意：PANews/律动/深潮等中文媒体关闭了网页预览，无法抓取。

### 数据源访问性
- CoinGecko API：免费，无需 key（有速率限制，采集间隔建议≥30秒）
- RSS 新闻源：免费
- jina 代理：免费但有速率限制，采集间隔建议≥10分钟

## 已知限制

- X/推特无 API 无法免费抓取（nitter 镜像已全部失效）
- 币安广场/老虎社区依赖 jina 代理，速率受限
- whale_alert 网页预览有旧数据缓存，需过滤时间异常条目
- 中文媒体（PANews/律动/深潮等）关闭 Telegram 网页预览

## 环境要求

- Python 3.8+（纯标准库，无 pip 依赖）
- 网络可访问：api.coingecko.com / r.jina.ai / np-listapi.eastmoney.com / t.me / 各 RSS 源

## 配置清单

无需任何 API key 或环境变量，开箱即用。

## 部署分发

- 公司 AI 平台导入（ZIP 根目录含 SKILL.md）、GitHub 推送、Codex marketplace 部署：见 `references/deployment.md`（含 Codex manifest 格式、GitHub token 推送、X API 现状、可用 Telegram 频道清单）。

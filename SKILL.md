---
name: web3-market-hotspot
description: "Web3 行情热点采集与分析：多源抓取加密行情、新闻、社媒热点（Telegram/币安广场/东方财富/老虎社区/华尔街见闻），JSON结构化输出（含异动预计算、交叉验证、健康检查），支持日报/KOL创作选题/推文/短视频/直播内容框架。"
version: 4.0.0
author: Lucas + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web3, crypto, market-analysis, hot-topic, content-ops, koi, creator, news-aggregation]
---

# Web3 行情热点采集与分析

多源采集 Web3 市场数据（行情/新闻/社媒/传统金融联动），四层架构输出 JSON 结构化结果。服务两类用户：
- **机构内容运营**：交易所/平台内容团队，需要日报、选题、交易场景建议
- **币圈 KOL/内容创作者**：独立博主、主播、短视频创作者，需要可直接用的内容素材

## 触发场景

- 需要快速了解今日加密市场行情和热点
- 需要监控市场异动、重大新闻、社媒讨论热点
- 需要生成内容选题（推文/短视频/直播/图文/社群）
- 需要为观点找数据支撑（涨幅榜、资金流、ETF数据）
- 任何 AI Agent（Codex/Claude/Hermes）需要实时 Web3 市场情报时

## 使用方式（AI Agent 调用）

### 采集数据（JSON 输出，AI 可直接 json.loads）

```bash
python3 scripts/collect.py --json-only   # stdout=JSON（推荐 AI 使用）
python3 scripts/collect.py               # stdout=JSON + stderr=人类可读摘要
python3 scripts/collect.py --preflight   # 健康检查（5s）
```

### JSON 结构

```json
{
  "collected_at": "ISO时间戳",
  "source_health": {
    "market": "ok|failed", "news": "ok|failed", "social": "ok|failed", "macro": "ok|failed",
    "fallback_used": {"market": "CoinGecko|GateIO|OKXBinance", "...": ""},
    "detail": {"news": {"RSSNews": "ok", "EastMoneyNews": "ok"}, "...": "..."}
  },
  "market": {"BTC": {"symbol","price","vol","chg_1h","chg_24h","chg_7d","source"}, "...": "..."},
  "precomputed": {
    "top_gainers": [{"symbol","chg_24h","price"}],
    "top_losers": [...],
    "volume_anomalies": [...],
    "dump_pump": [{"symbol","chg_1h"}]   // 1h 波动 >5%
  },
  "news": [{"title","src","tags","published_at","dedup_key","sources","cross_verified"}],
  "news_archive": [...],   // 超过24h的旧闻
  "social": [...],
  "macro": [...]
}
```

### 健康检查

```bash
python3 scripts/collect.py --preflight
# 输出 12 个源的 ok/failed + 延迟，AI 据此决定数据可信度
```

## 四层架构

```
采集层（sources/）→ 预处理层（preprocess.py）→ 输出层 → 健康检查层（preflight.py）
```

### 采集层：Source 类 + fallback 链
- **行情**：CoinGecko 主源 → Gate.io fallback → OKX/Binance fallback（三级）
- **新闻**：RSS（CoinTelegraph/CoinDesk/TheBlock） + 东方财富（加密过滤）并发合并
- **社媒**：Telegram 7频道 + 币安广场(jina) + 老虎社区(直连HTML) 并发合并
- **宏观**：东方财富快讯 + 华尔街见闻 lives 并发合并
- 全部并发执行，总超时 20s，单源失败不阻断其他源

### 预处理层
- **去重**：精确 dedup_key（标题归一化 md5）+ 相似度匹配（token 集合 Jaccard>0.4）
- **时间过滤**：只保留 24h 内，旧闻进 archive
- **关键词打标**：tags.json 配置，[BTC]/[ETH]/[ETF]/[DeFi]/[Meme]/[AI]/[地缘]/[宏观]/[监管]/[安全事件]等
- **异动预计算**：top_gainers/top_losers/volume_anomalies/dump_pump
- **交叉验证**：同一事件 ≥2 源出现 → cross_verified: true（AI 优先采用）

### 健康检查层
preflight.py 并发 ping 12 个源，输出 ok/failed + 延迟 ms。

## 分析框架

### 输出框架 A：机构内容运营（日报）
```
【Web3行情热点日报｜M月D日】
一、市场概览（BTC/ETH 价格、24h/7d 涨跌、市场情绪、今日主线）
二、今日Top 5热点（标题、热度评分0-10、相关资产、核心逻辑、运营建议、交易卡片建议）
   - 优先采用 cross_verified=true 的事件
三、异动资产榜（直接用 precomputed 数据）
四、内容形式建议（行情圆桌/辩论赛/单点深度解读/社区图文贴/短视频/数据可视化/社群互动/快讯速报）
五、推文/社群内容建议
六、交易场景建议（优先关注/可挂卡片/仅讨论）
七、风险提示
```

### 热点评分模型
- 9-10分：S级，立即跟进
- 7-8.9分：A级，适合直播/推文
- 5-6.9分：B级，日报观察
- 5分以下：C级，仅记录

### 输出框架 B：KOL/内容创作者工作台
- B1 今日内容选题 TOP5（选题+热度+内容形态+爆点）
- B2 推文速写（3-5条可直接发，观点型/情绪型/信息型）
- B3 Thread 大纲（Hook→数据→观点→反驳→互动）
- B4 短视频脚本（前3秒Hook+画面+口播+CTA+平台）
- B5 直播/视频大纲（开场钩子+主线+互动+收尾）
- B6 观点弹药库（多空观点+KOL观点摘录+可引用数据）
- B7 数据卡片（3-5个可直接做图的数字）
- B8 本周内容日历
- B9 合规红线

### 合规要求（强制）
- 禁用词：稳赚、必涨、抄底、暴富、翻倍、保证收益、精准预测、内幕消息
- 未确认消息标注"未确认"；引用他人观点注明来源；涉及项目方推广声明利益关系
- 所有行情内容含风险提示

## 配置

### scripts/symbol_map.json
- watchlist：37 个资产，symbol + CoinGecko id + alias（RNDR→RENDER, MATIC→POL, FTM→S, GRAM→TON）
- gate_precision：PEPE/BONK 价格放大系数（避免精度丢失）
- top_n_for_7d：7d K线补齐数量

### scripts/tags.json
关键词标签字典，可自由扩展。

## 已知限制

- X/推特无 API 无法免费抓取（nitter 镜像已全部失效）
- 币安广场依赖 jina 代理（不稳定，失败自动降级）
- whale_alert 网页预览有旧数据缓存，需过滤时间异常条目
- 中文媒体（PANews/律动/深潮等）关闭 Telegram 网页预览
- 交叉验证依赖多源报道同一事件，中英文源内容域不同时可能为 0（正常）

## 环境要求

- Python 3.8+（纯标准库，无 pip 依赖）
- 网络可访问：api.coingecko.com / data.gateapi.io / api.okx.com / api.binance.com / r.jina.ai / np-listapi.eastmoney.com / api-one-wscn.awtmt.com / t.me / www.laohu8.com / 各 RSS 源

## 配置清单

无需任何 API key 或环境变量，开箱即用。

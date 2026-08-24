---
name: web3-hotspot-analysis
description: "Web3 行情热点分析机器人：多源采集（行情/新闻/币安广场/东方财富/老虎社区/Telegram）+ AI 日报生成 + Telegram bot 指令服务。"
version: 1.0.0
author: Lucas + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web3, crypto, telegram, bot, market-analysis, hot-topic, content-ops]
    homepage: https://github.com/yourname/web3-hotspot-analysis
---

# Web3 行情热点分析机器人（Content Ops）

面向加密交易所内容运营团队的行情热点分析系统：自动采集多源数据，AI 结构化分析，输出可直接用于运营工作的日报、热点、直播选题和交易卡片建议。支持飞书定时推送 + Telegram bot 随叫随到。

## 触发场景

- 内容运营每天早上需要行情热点日报
- 需要监控加密市场异动、新闻、社媒热点、传统金融（美股/A股/宏观）联动
- 需要快速生成直播选题、内容形式建议、交易卡片清单
- 需要把热点分析能力以 Telegram bot 形式提供给团队

## 数据源（全部免费/公开）

| 来源 | 视角 | 方式 |
|------|------|------|
| CoinGecko API | 38个重点资产价格/1h/24h/7d涨跌/市值 | 官方API |
| CoinTelegraph/CoinDesk/The Block RSS | 全球加密新闻 | RSS |
| 币安广场（Binance Square） | 加密KOL观点/散户情绪 | jina代理渲染 |
| 东方财富快讯API | A股/宏观快讯 | 官方API |
| 老虎社区（laohu8.com/community） | 美股/ETF/港股视角 | jina代理渲染 |
| Telegram 频道 | 吴说/odaily/金色财经/链捕手等中文头部 | t.me/s网页预览 |
| Telegram 监控群（可选） | 用户自定义频道/群 | bot getUpdates |

## 架构

```
collect.py（数据采集，输出纯文本）
    ↓
AI分析（DeepSeek API，OpenAI兼容）
    ↓
日报/热点/选题/单币种分析
    ↓
飞书（cron定时推送） 或  Telegram bot（/daily /hot /live /market）
```

## 快速开始

### 1. 配置环境变量

```bash
# ~/.hermes/.env 或环境变量
export WEB3_BOT_TOKEN="你的Telegram bot token"     # 可选，用bot功能才需要
export DEEPSEEK_API_KEY="你的DeepSeek key"         # AI分析必填
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

### 2. 采集数据（测试）

```bash
cd ~/.hermes/skills/data-science/web3-hotspot-analysis/scripts
python3 collect.py
```

输出：MARKET DATA / NEWS / BINANCE SQUARE / EASTMONEY / LAOHU / TELEGRAM 六段数据。

### 3. 启动 Telegram bot（可选）

```bash
python3 tg_bot.py
```

bot 支持指令：
- `/daily` 今日行情热点日报
- `/market BTC` 单币种分析
- `/hot` 今日热点TOP5
- `/live` 直播选题建议

### 4. 飞书定时推送（可选）

用 Hermes cron 创建定时任务，prompt 指向运行 collect.py + 按日报格式输出，每天10:00自动推送。

## 关键实现细节

### 币安广场抓取
直接 curl 被 CloudFront 拦截，必须走 jina 代理：
```
https://r.jina.ai/https://www.binance.com/zh-CN/square
```
正则提取 `\[标题\]\(https://www.binance.com/zh-CN/square/post/\d+\)`

### 东方财富快讯
官方API直连：
```
https://np-listapi.eastmoney.com/comm/web/getFastNewsList?client=web&biz=web_724&fastColumn=102&pageSize=15&req_trace=1
```

### 老虎社区
JS渲染，走 jina 代理 `https://r.jina.ai/https://www.laohu8.com/community`，提取 `### ` 标题行。

### Telegram 频道
`https://t.me/s/频道名` 网页预览，正则提取 `tgme_widget_message_text`。注意：很多频道关闭预览（302/无内容），PANews/律动/深潮等中文媒体均不可用；已验证可用：wublock、odaily_news、jinse、chaincatcher。

### Telegram bot 监控群（高级）
普通用户无法把bot加进别人的群/频道（需管理员权限）。可行方案：用户自建群拉bot，手动转发有价值内容。X/推特无API无法免费抓取（nitter已全灭）。

## 日报格式（prompt模板）

AI分析prompt要求输出（纯文字，无表格无markdown）：
1. 市场概览（BTC/ETH价格、情绪、今日主线）
2. 今日Top 5热点（标题、热度评分0-10、相关资产、核心逻辑、运营建议、交易卡片建议）
3. 异动资产榜（涨幅/跌幅/成交量/冲高回落）
4. 今日热点内容形式建议（行情圆桌/辩论赛/单点深度/图文贴/短视频等，不推荐具体栏目名）
5. 推特/社群内容建议
6. 交易场景建议（优先关注/可挂卡片/仅讨论）
7. 风险提示

合规要求：禁用词（稳赚/必涨/抄底/暴富/翻倍/保证收益/精准预测），未确认消息标注，行情内容必须含风险提示。

## 已知限制

- X/推特无API无法抓取（nitter镜像全部被Cloudflare拦截，官方API需付费+开发者账号）
- 币安广场/老虎社区依赖 jina 代理，有速率限制，采集间隔建议≥10分钟
- 币安广场帖子为散户观点，仅作情绪参考，不可作为事实依据
- whale_alert 网页预览有旧数据缓存，需过滤时间异常条目

## 配置清单（部署前确认）

- [ ] DEEPSEEK_API_KEY（必需）
- [ ] WEB3_BOT_TOKEN（bot功能需要，@BotFather创建）
- [ ] 服务器可访问 api.coingecko.com / api.telegram.org / r.jina.ai / np-listapi.eastmoney.com

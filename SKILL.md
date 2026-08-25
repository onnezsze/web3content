---
name: web3-market-hotspot
description: "Web3 行情热点采集与分析：多源并发抓取（CoinGecko/Gate/OKX资金费率/RSS/东财/华尔街见闻/TG/币安广场/老虎社区/DogDoing），JSON结构化输出（异动预计算、交叉验证、情绪词频、OI异动、恐惧贪婪、Alpha热点、预测市场、美股板块、昨日热点存档、健康检查），11段式日报模板服务内容运营与KOL创作。"
version: 6.2.0
author: Lucas + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web3, crypto, market-analysis, hot-topic, content-ops, koi, creator, news-aggregation]
---

# Web3 行情热点采集与分析

多源采集 Web3 市场数据，四层架构输出 JSON 结构化结果，11 段式日报模板（含站外创作者速用包），配 charts.py 自动生成数据卡片图。服务两类用户：
- **机构内容运营**：交易所/平台内容团队
- **币圈 KOL/内容创作者**：独立博主、主播、短视频创作者

## 触发场景

- 需要快速了解今日加密市场行情和热点
- 需要生成可直接投产的内容选题（推文/短视频/直播/图文/社群）
- 需要为观点找数据支撑（涨幅榜、资金费率、ETF流向、社群情绪）
- 需要追踪热点生命周期（昨日热点今日表现）
- 任何 AI Agent（Codex/Claude/Hermes）需要实时 Web3 市场情报时

## 使用方式（AI Agent 调用）

### 采集数据

```bash
python3 scripts/report.py                # 【推荐 AI/cron/tg_bot 入口】精简结构化文本，避免大 JSON 截断
python3 scripts/charts.py                # 【配图生成】涨幅榜/跌幅榜/情绪词频 → PNG，输出 MEDIA: 路径供直接发送
python3 scripts/collect.py --json-only   # stdout=完整 JSON（仅当需要原始字段时）
python3 scripts/collect.py --preflight   # 健康检查（5s）
python3 scripts/feishu_doc.py            # 【飞书文档输出】把日报排版成飞书文档，stdout 末尾打印 FEISHU_DOC_URL
```

### JSON 结构

```json
{
  "collected_at": "ISO时间戳",
  "source_health": {"market":"ok","news":"ok","social":"ok","macro":"ok","dogdoing":"ok","detail":{...}},
  "market": {"BTC": {"price","vol","chg_1h","chg_24h","chg_7d","source"}, ...},
  "precomputed": {"top_gainers":[...],"top_losers":[...],"volume_anomalies":[...],"dump_pump":[...]},
  "funding": {"BTC": {"funding_rate","annualized_pct"}, "ETH":..., "SOL":...},
  "sentiment": {"counts": {"恐慌":2,"焦虑":1,...}, "samples": {...}},
  "yesterday_top3": {"date":"...","topics":[...]} | null,
  "dogdoing": {"fear_greed":{"value":"74","label":"Greed"},
               "oi_divergence":[{"symbol","oiChangePct","priceChangePct","divergenceRatio"},...],
               "alpha_hotspots":[{"name","netInflow","type","tokenSize","tokens"},...],
               "square_hype":[{"symbol","score","sources","priceChangePct"},...],
               "prediction_markets":[{"question","volume","traders","status","outcomes"},...],
               "us_stocks":[{"symbol","name","changePct","news":[{"title","source"}]},...]},
  "news": [{"title","src","tags","published_at","dedup_key","sources","cross_verified"}],
  "social": [...], "macro": [...]
}
```

## 四层架构

```
采集层（sources/）→ 预处理层（preprocess.py）→ 输出层 → 健康检查层（preflight.py）
```

### 采集层（8+1 源并发，20s 总超时）
- **行情**：CoinGecko → Gate.io → OKX/Binance（三级 fallback）
- **资金费率**：OKX 永续（BTC/ETH/SOL 年化）
- **新闻**：RSS 3源 + 东方财富（加密过滤）并发合并
- **社媒**：Telegram 7频道 + 币安广场(jina) + 老虎社区(直连HTML)
- **宏观**：东方财富快讯 + 华尔街见闻 lives
- **DogDoing 聚合**（新）：OI持仓量异动 · 恐惧贪婪指数 · Binance Alpha 热点 · 币安广场热度($TICKER) · 42.space 预测市场 · 美股板块（综合 dogdoing.ai 的 /api/* 代理，fail-soft）
- 任一源失败不阻断其他源，全部失败输出空数组+failed 状态

### 预处理层
- **去重**：精确 md5 + token 相似度（Jaccard>0.4）跨源合并
- **打标**：tags.json 18 个标签（BTC/ETH/ETF/DeFi/Meme/AI/地缘/宏观/监管/安全事件等）
- **异动预计算**：top_gainers/top_losers/volume_anomalies/dump_pump
- **交叉验证**：多源报道同事件 → cross_verified: true
- **情绪词频**：恐慌/焦虑/抄底/看多/看空/FOMO 计数+原声样本
- **昨日热点存档**：hot_history.json 记录每日 top3，供次日生命周期追踪

### 健康检查层
preflight.py 并发 ping 18 源（含 6 个 DogDoing 探针），输出 ok/failed + 延迟 ms。

## 日报模板（11段，固定结构）

```
【Web3行情热点日报｜M月D日】

一、市场快照｜全部量化
   价格·24h/7d涨跌·资金费率·爆仓量·ETF流向·支撑阻力位（每项标来源+时间）

二、社群情绪｜词频 + 真实原声（脱敏，标频道+时间）

三、昨日热点追踪｜延续 or 衰退 + 剩余生命周期（抢时效 or 做深度）

四、今日Top5热点｜每条固定8项：
   事件 / 热度分项(社媒声量·成交量·价格波动·媒体覆盖) / 来源+时间
   / 具体标的及可交易性 / 看多·看空论据各带数据 / 数据佐证
   / 内容切入点+所需素材 / 卡片三要素(标的·节点·用户)

五、异动资产榜｜币种·涨跌幅·触发事件·所处阶段(启动·加速·冲高回落)
   + 可补 DogDoing【OI持仓量异动】与【币安广场热度】作为"新资金进场/舆论爆发"佐证

六、未来3天节点日历｜宏观数据·解锁·上线（待确认标注）
   prompt 必须内置宏观日历（如 FOMC 9/15-16、10/27-28、12/8-9；CPI 月中；非农每月首周五），否则 AI 全写"待确认"
   + 条件允许时参考 DogDoing【42.space 预测市场】热门事件作题材储备

七、内容排期｜T+0轻内容(图文/推文/切片/快评) / T+3重内容(深度/圆桌/数据可视化)
   每档标注素材完备度

八、社媒文案｜话术+标签+配图+时段+互动形式

九、待核实信息区｜未交叉验证传闻隔离（标"未确认"）

十、合规红线清单｜固定附上

十一、创作者速用包｜站外可直接发（v6 新增，服务小红书/抖音/X/视频号博主）
   成品1 小红书图文：封面大字(≤12字钩子，猎奇/反常识/冲突优先)+标题+正文(150-250字
      短促口语化、指名道姓+数据+冲突观点、禁"扣1"式引导)+标签8-10个+发布时段
   成品2 X推文：观点型≤280字符，带数据+冲突观点
   成品3 短视频口播：前3秒钩子+30秒口播要点(带具体数字)+画面提示
   平台合规自查（必做）：点名具体币+操作指导倾向(低吸/追高/加仓/抄底)会被小红书判
      高风险删帖 → 改写为"纯行业观察+个人口吻+免责声明"版本
   【配图附件】charts.py 生成的 MEDIA: 路径（gainers/losers/sentiment.png）
```

### DogDoing 扩展维度（v6.1 新增，非冗余补充）
新增 `sources/dogdoing.py`，从 dogdoing.ai 的 /api/* 代理抓 6 个本管线不重复的维度：
- **OI持仓量异动**（oi_divergence）：持仓量 vs 价格背离系数，用于发现"新资金进场但价格未跟"的异动
- **恐惧贪婪指数**（fear_greed）：Value + Label（Extreme Fear/Greed 等）
- **Binance Alpha 热点**（alpha_hotspots）：热点话题 + 净流入 + 类型，BSC chainId=56
- **币安广场热度**（square_hype）：论坛 $TICKER 提及热度分 + 源数
- **42.space 预测市场**（prediction_markets）：热门预测事件 + 成交量 + 状态
- **美股板块**（us_stocks）：Mag7/热门股涨跌 + 关联新闻标题

全部 fail-soft：任一端点失败不影响其他，全部失败才把 source_health.dogdoing 标为 failed。
数据量已裁剪（OI/热点/热度各取 Top10，预测市场 Top5，美股 Top8），避免 JSON 膨胀。

### charts.py 配图生成（v6.1 新增 DogDoing 图）
- 输出：`charts/YYYYMMDD/gainers.png`（24h涨幅榜Top10）、`losers.png`（跌幅榜）、`sentiment.png`（情绪词频）
- DogDoing 扩展图（v6.1）：`oi.png`（OI持仓量异动·价格vs持仓）、`fear_greed.png`（恐惧贪婪指数·0-100指示条）、`stocks.png`（美股板块·Mag7/热门）
- 中文渲染依赖系统 CJK 字体（Ubuntu 文泉驿正黑），matplotlib findfont 的 weight 警告可忽略
- 颜色约定：红涨绿跌（中文用户习惯），改 charts.py 顶部 COLOR_UP/COLOR_DOWN 可切币圈绿涨红跌

### feishu_doc.py 飞书文档输出（v6.2 新增）
把 `report.py` 的日报文本排版成**飞书云文档**（Feishu docx），供用户直接看，避免在聊天里发文字+图片刷屏。
- 读取 `~/.hermes/.env` 的 `FEISHU_APP_ID/FEISHU_APP_SECRET` 换取 tenant_access_token（无需额外配置）
- 创建文档 → 把 report 文本转成 block（`#/##/【`→heading、`•`→bullet、其余→text）→ 分批插入 → 把用户(open_id)加为 `view` 协作者
- stdout 末尾打印 `FEISHU_DOC_URL: <链接>`；定时任务/agent 只需回传该链接
- **已知限制**：当前飞书应用只允许插入 text/heading/bullet/ordered/quote/code 块；`image`(27)/`table`(22)/`divider`(31) 复杂块会被拒（错误 1770001）。因此**配图无法内嵌进文档**（图表仍可由 charts.py 单独生成、经飞书图片上传另行处理）。若需文档内嵌图/表，需在飞书开放平台为应用追加 docx/drive 相关权限并重新发布。

### 热点评分模型（分项可复用可对比）
- 社媒声量 0-2.5 / 成交量变化 0-2.5 / 价格波动 0-2.5 / 媒体覆盖 0-2.5 = 满分10
- 9-10 S级 / 7-8.9 A级 / 5-6.9 B级 / <5 C级

### 合规红线（每期固定附上）
- 禁用：收益承诺（稳赚/必涨/抄底/暴富/翻倍/保证收益）、绝对化判断、暗示必然性
- 数据必须标源+时间；敏感议题（地缘/暴跌/监管）中性表述
- 引用他人观点注明来源；未确认消息必须标注
- 所有行情内容附"不构成投资建议"

## KOL 创作框架（可选扩展）

- 推文速写：观点型/情绪型/信息型，带标签+配图+时段
- Thread 大纲：Hook→数据→观点→反驳→互动
- 短视频脚本：前3秒Hook+画面+口播+CTA
- 直播大纲：开场钩子+主线分段+互动设计+收尾
- 数据卡片：可直接做图的数字（涨幅/资金费率/ETF/情绪词频）

## 配置

- **scripts/symbol_map.json**：37 资产，symbol+CoinGecko id+alias（GRAM→TON/RNDR→RENDER/MATIC→POL/FTM→S），PEPE/BONK 精度
- **scripts/tags.json**：关键词标签字典
- **scripts/hot_history.json**：自动生成，昨日热点存档
- **scripts/sources/dogdoing.py**：DogDoing 扩展维度采集（6 端点，fail-soft），无需配置

## 已知限制

- X/推特无 API 无法免费抓取；币安广场依赖 jina 代理（不稳定自动降级）
- ETF流向/爆仓量无免费API，从新闻中提取（提取不到标"暂无数据"）
- 中英文源内容域不同时交叉验证可能为 0（正常，非 bug）
- 中文媒体（PANews/律动/深潮）关闭 TG 网页预览
- DogDoing 维度依赖其公开 /api/* 代理（Next.js），若其限流/变更接口字段或整体下线，dogdoing 块自动报 failed，其余源不受影响（fail-soft）
- 飞书文档：当前应用的 docx 权限只支持 text/heading/bullet/ordered/quote/code 块，`image`/`table`/`divider` 复杂块会被 API 拒绝（1770001），故日报配图暂不能内嵌进飞书文档（需为应用追加 docx/drive 权限并重新发布）

## 环境要求

- Python 3.8+（纯标准库；charts.py 需 matplotlib，已在 Hermes venv 安装）
- 网络可访问：api.coingecko.com / data.gateapi.io / api.okx.com / api.binance.com / r.jina.ai / np-listapi.eastmoney.com / api-one-wscn.awtmt.com / t.me / www.laohu8.com / dogdoing.ai / RSS 源

## 配置清单

无需 API key，开箱即用。

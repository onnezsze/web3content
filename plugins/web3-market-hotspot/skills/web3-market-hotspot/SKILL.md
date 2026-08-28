---
name: web3-market-hotspot
description: "Web3/美股内容创作者热点简报：多源并发采集（CoinGecko/Gate/OKX资金费率/RSS/东财/华尔街见闻/TG/币安广场/老虎社区/DogDoing），AI合成核心热点+四要素+可直接复用的选题/推文/钩子，输出干净排版的飞书文档。"
version: 7.10.0
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

## 首次使用引导（Onboarding · v7.9 新增）

初次调用本 skill 时，**先向用户确认两项配置**，再按其设置产出。

### 1. 播报时间与节奏周期
让用户选择/输入节奏：
- **定时周期播报**：给定节律并映射 cron。如 `每天 09:00` → `0 9 * * *`；`每周一 09:00` → `0 9 * * 1`。服务器为 UTC，**北京 09:00 = UTC 01:00**，需换算。
- **一次性简报**：立即生成并推送一次，不设周期。

### 2. 输出形态自适应
- **飞书场景**（Feishu bot 已接入）：产出**飞书云文档**，只回传文档链接（`feishu_doc.py` 排版）。
- **其他场景**（用户在 Claude / GPT / 自有 Agent 中直接使用本 skill，无飞书通道）：直接返回**带格式的 Markdown 文案**（`##/加粗/代码块` 等），不生成飞书文档。

### 引导提示词（调用方 / 宿主可直接贴给用户）
```text
欢迎使用「Web3 行情热点简报」！首次使用请告诉我 2 件事：
① 播报节奏：希望多久推一次？可填「每天 9点 / 每周一 9点 / 每两小时」等；或要我「现在先推一次」。
② 输出形态：你现在是「在飞书里」（我出文档链接），还是「其他 AI 场景直接看」（我出带格式文案）？
确认后我就开始按此配置产出。
```

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

## 日报模板（内容创作者版·精简聚焦）

面向 Web3 / 美股内容创作者：**3 分钟抓住核心热点、直接开写**。不做数据罗列，只给判断 + 选题 + 素材。AI 按下方结构输出；来源只在文末统一标注，正文不刷来源噪音。

```
【Web3 · 美股 内容创作者热点简报｜M月D日】

🔥 今日核心看点（3–5 条，每条四要素）
  #1 《一句话标题》
   · 为什么讲：逻辑/背景（1–2 句）
   · 关键数据：仅 2–3 个硬数字
   · 内容角度：观点型/信息型/情绪型 + 一句话怎么讲
   · 标的/倾向：币/股 + 偏多/偏空/待确认
  #2 … #5 …

📌 今日要闻（最多 5 条，每条 1 句话，去噪）
  优先级（从高到低）：
  ① 监管 / 合规 / 政府动作 / 宏观市场（最高）——SEC/CFTC/央行/财政部/白宫/监管/合规/法案/听证/制裁/美联储/利率/关税/GDP/CPI/非农/美债等
  ② 主流币（BTC / ETH）相关
  ③ 美股三大指数、各大板块、MAG7、AI 公司、存储、芯片相关（标普/纳斯达克/道琼斯/NVIDIA/AI/微软/苹果/谷歌/特斯拉/台积电/芯片/存储/HBM 等）
  同优先级再按重要程度；优先取 report.py 输出的「今日要闻候选(按优先级)」。
  · <一句话要闻>

🔍 圈内动态
  取 5 条，每条 = 标题 + 内容摘要 + 信息来源。取自 report.py 的「圈内动态」或按主体在新闻/社媒/宏观/Alpha热点里定向捞取。
  监测主体（不写进标题）：孙哥(孙宇晨/孙割/波场/HTX/火币，含八卦·最高优先)、特朗普(加密相关)、交易所(上/下架·公告·新合约)、交易所老板高管(CZ/赵长鹏/Coinbase CEO)、币圈大V·名人(动态/八卦/言论/活动)、链·生态(主网·升级·安全事件·TVL·空投)。
  筛选与排序优先级：孙哥(含八卦) > 特朗普(加密相关) > 交易所 > 老板高管 > 币圈大V·名人 > 链/生态，同级再按重要程度。
  纳入范围：不仅限加密新闻——孙哥/交易所/币圈大V·名人 的八卦、言论、动态、活动、传闻也纳入监测（命中有监测主体即入选）；再按优先级取前 5。
  1. <一句话标题>
  · 摘要：<一句话>
  · 来源：<媒体>

🕐 周度回顾（周一简报专属 · v7.7 新增）
  仅每周一简报才输出，放在【圈内动态】后、【创作者怎么用】前。两块，每条含 日期/标题/摘要/关键数据 四要素。
  ① 上周热点回顾：复盘最近 7 天的重要热点事件。report.py 周一自动输出「周度回顾」段（**采集历史 + 补充检索**融合：每日采集落盘的 top3 历史存档 + 独立检索近 7 天新闻，去重合并避免丢失；输出含 日期+标题+摘要+跨源数/评分），据此扩成完整条目。
  ② 本周可预估热点：当周已知/大概率将发生的事件（财经日历／听证会／代币解锁／主网升级／发布会／财报／CPI·非农·议息／交割·到期／TGE·空投等）。取 report.py 输出的「本周可预估热点候选」。
  格式（每条四要素）：
  📅 【上周回顾】／【本周预估】
   1. <日期，如 8/21> <一句话标题>
    · 摘要：<一句话讲清事件>
    · 关键数据：<2-3 个硬数字：涨幅/资金/解锁量/预期值>
  规范：日期要具体（无明确日期标“本周内”）；标题一句话；摘要不啰嗦；关键数据给硬数字；每块取 3-5 条；来源在文末统一标注。

🎁 创作者素材包（已填参数 · 直接粘贴）
  说明：下方每个素材包都已把通用框架的占位符 **提前填好**（字段 =【主题/硬数据/新闻标题/原声/角度】，与框架占位符一一对应）。用法：挑一个你顺眼的素材包（或从上方核心看点里找一条）→ 连同任一角色的提示词框架一并粘贴给 AI → 直接产出，**无需自己加工热点**。
  素材包A：《<一句话热点标题>》
  · 主题：<一句话：讲什么热点>
  · 硬数据：<2-3 个关键数字，含价格/涨跌/资金/异动>
  · 新闻标题：<1-2 条真实标题，含媒体名>
  · 原声：<1 条社区/网友原声>
  · 角度：<2-3 个钩子/矛盾点>
  素材包B：《<…>》（同上结构；为 3-5 个热点各出一个包）

💡 创作者怎么用（热点素材包 + 通用框架）
  创作者 = 「热点素材包」 + 「提示词框架」。从上面 🎁 里任选一个素材包 → 复制任一角色的提示词框架（references/creator-frameworks.md，占位符与素材包字段一一对应）→ 两者一块发给任意 AI（Claude/GPT/Hermes）即可产出脚本，**无需自己提炼热点**。
  7 个角色：推特KOL / 小红书KOL / TikTokKOL / Web3·美股社区创作者 / 平台话题运营 / 平台社区运营 / 平台直播运营。
  快速示例（推特 KOL + 素材包A）：
  ```txt
  你是推特加密货币 KOL，风格犀利敢下判断。基于下面素材产出观点推文：
  【热点素材】
  · 主题：<素材包A.主题>
  · 硬数据：<素材包A.硬数据>
  · 新闻标题：<素材包A.新闻标题>
  · 原声：<素材包A.原声>
  · 角度：<素材包A.角度>
  【创作框架】反常识钩子 → 硬数据(1-2) → 一句判断 → 互动 CTA
  【输出格式】① ≤140字观点 ② 3节 Thread ③ 1个互动问题
  ```

⚠️ 合规提示（两条内）
  <不承诺收益 / 标注数据来源 / 附免责>

> 来源：CoinGecko/OKX/TheBlock/Coindesk/吴说/金色/链捕手/DogDoing 等｜采集 HH:MM UTC｜不构成投资建议
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

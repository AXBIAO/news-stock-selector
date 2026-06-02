---
name: news-stock-selector
version: "3.6.0"
description: 新闻选股助手。从新闻/热点中识别相关 A 股标的并输出结构化结果，HTML 报告强制生成 + 自动打开（不可跳过），v3.6 新增显式化 tier 分配算法、催化剂时效衰减、板块集中度上限、涨停次日熔断、策略标签分类、次日验证反馈环。
markets_supported: ["A"]
requires:
  mcp_tools: ["mcp__mcp-router__search", "mcp__mcp-router__web_search_exa", "mcp__mcp-router__fetchWebContent", "mcp__mcp-router__search_stock", "mcp__mcp-router__get_kline", "mcp__mcp-router__get_kline_history", "mcp__mcp-router__get_index", "mcp__mcp-router__get_index_all", "mcp__mcp-router__get_market_stats"]
  python_packages: ["tushare", "akshare", "requests"]
  local_modules: ["data_sources.py"]
related_skills: ["ftshare-market-data-main", "stock-screener", "lhb-analyzer", "trap-detector", "deep-analysis"]
note: |
  ⚠️ MCP 行情接口 (get_quote/get_batch_quote/get_stock_info @ localhost:8080) 已废弃。
  实时行情必须走 Python data_sources 模块，不要尝试调用 MCP 行情工具。
  详见 Step 3 指令。
  📄 v3.5 新增：HTML 报告强制门禁 + 完成前自检清单，彻底杜绝跳过报告的情况。详见 Step 5 和底部自检清单。
trigger:
  required: ["新闻选股", "利好选股", "哪些股票有.*新闻", "热点对应个股", "政策利好股票", "并购重组.*股票"]
  conditional: ["市场热点", "情绪分析", "板块怎么样", "最近什么消息多"]
  exclude: ["单股行情查询", "个股估值", "龙虎榜席位", "杀猪盘", "纯宏观解读"]
---

# 新闻选股助手

## 核心能力

1. **新闻驱动选股** -- 从新闻/热点中识别 A 股候选标的
2. **多层数据验证** -- 实时行情校验、多源 fallback、失败可见
3. **条件增强分析** -- 宏观趋势、板块联动补涨、社交热榜（按需附加）

## 执行模式

### 默认模式（主链必跑 — HTML 报告不可跳过）

**ALL invocation paths MUST produce an HTML report.** 无论用户参数是"验证"、"查询"、"分析"、"筛选"还是其他变体，只要执行了股票识别和行情获取（Step 0-4），Step 5 就是强制门禁。不存在"纯验证模式跳过 HTML"的例外路径。

新闻检索 -> 股票识别 -> 行情校验 -> **Tier 分配引擎 (v3.6)** -> 结构化输出 -> **HTML 报告 + 自动打开 [GATE: BLOCKING]**

### Tier 分配引擎（v3.6 新增 — Step 4 核心逻辑）

选股结果不再仅凭情绪主观映射到 T1/T2/T3，而是通过 `contracts.compute_tier()` 量化计算：

```
tier_score = sentiment_norm × 0.35 + catalyst_norm × 0.25 + confidence × 0.25 + strategy_norm × 0.15
```

**影响 tier 得分的 5 个因子：**
1. **情绪归一化** (35%) — `SentimentLevel / 5.0`
2. **催化剂权重** (25%) — 各 `CatalystType` 的平均权重（政策/并购=1.0, 热点=0.4）
3. **置信度** (25%) — 催化剂时效衰减 + 多催化剂加成（见下方）
4. **策略标签** (15%) — `回调低吸`/`催化剂博弈` +1, `突破追击` -1（见 `classify_strategy_tag()`）
5. **涨停次日熔断** — 前一日涨幅≥9.5% → 强制 T3 上限（不参与公式计算）

### 增强模式（条件触发）
- **趋势/板块归因** -- 用户关心板块、主题、主线时启用
- **补涨联动分析** -- 检测到已验证的强势龙头时启用
- **社交热榜加权** -- 用户关心情绪热度或结果较少时启用

## 模块结构

本 skill 由以下模块协同工作（均位于 skill 目录内）：
- `skill.md` -- 入口契约（本文件）
- `config.py` -- 数据源凭据、路径、平台权重
- `contracts.py` -- 统一数据结构与状态值定义
- `data_sources.py` -- 多源行情 fallback 链与社交热榜抓取

## 情绪 5 档定义

| 等级 | 标签 | 含义 | 选股信号 |
|------|------|------|----------|
| 1 | 强烈看淡 | 重大利空、业绩暴跌、黑天鹅 | 规避 |
| 2 | 看淡 | 负面消息、行业景气下降 | 谨慎 |
| 3 | 中性 | 一般性信息、无明显利好利空 | 观望 |
| 4 | 看好 | 正面消息、业绩增长、订单落地 | 关注 |
| 5 | 强烈看好 | 重大利好、政策支持、技术突破、并购重组 | 重点关注 |

## 利好新闻分类

| 分类ID | 分类名 | 关键词 | 选股优先级 |
|--------|--------|--------|------------|
| TYPE_EARNINGS | 业绩超预期 | 业绩增长、净利润、同比、营收超预期、年报、季报 | 4星 |
| TYPE_POLICY | 政策利好 | 政策支持、补贴、政策利好、发改委、工信部、商务部、顶层文件 | 5星 |
| TYPE_MA | 并购重组 | 并购、重组、收购、资产注入、股权激励、定增 | 5星 |
| TYPE_TECH | 技术突破 | 突破、研发成功、新品发布、专利、独家技术 | 4星 |
| TYPE_COOP | 重要合作 | 合作、签约、订单、战略伙伴、独家供应 | 4星 |
| TYPE_INDUSTRY | 行业景气 | 行业复苏、景气上行、需求增长、价格上涨 | 3星 |
| TYPE_EQUITY | 股权变动 | 增持、回购、举牌、股东增减持、大股东 | 3星 |
| TYPE_HOT | 概念热点 | AI、人工智能、新能源、半导体、机器人等热门概念 | 3星 |
| TYPE_RATING | 机构评级 | 买入、增持、强烈推荐、上调评级、目标价 | 3星 |

## 执行流程

### Step 0: 解析用户意图
判断用户请求属于：新闻驱动选股 / 指定主题找股票 / 指定利好类型找股票 / 情绪热度导向筛选。

### Step 1: 新闻检索
通过 MCP 工具或 WebSearch 检索相关新闻。优先使用 MCP 多引擎搜索，失败时降级为通用搜索。

### Step 2: 股票识别与标准化
从新闻中提取股票代码（6 位数字）和名称。无法确认时标记为"待确认"，不丢弃。

### Step 3: 实时行情校验 （Python data_sources 模块 — 禁止使用 MCP 行情工具）

**CRITICAL**: 不要使用 `mcp__mcp-router__get_quote` / `get_batch_quote` / `get_stock_info`！
这些 MCP 工具依赖的 localhost:8080 后端已不可用。

正确做法：通过 Bash 执行 Python 调用 data_sources 模块：

```bash
cd "/c/Users/Administrator/.claude/skills/news-stock-selector" && python -c "
from data_sources import get_realtime_quote_fallback
import json
result = get_realtime_quote_fallback(['600584','002156','002371','688981'])
print(json.dumps({'source': result['source'], 'stocks_found': result['stocks_found'], 'stocks_missing': result['stocks_missing']}, ensure_ascii=False))
for code in result['stocks_found']:
    d = result['data'].get(code, {})
    print(f'{code}: price={d.get(\"price\")}, change={d.get(\"change_pct\")}%, source={d.get(\"_source\")}')
"
```

**Fallback 链** (v3.3, 实时爬虫优先, 无需 MCP):
`xueqiu(实时) -> tencent(实时) -> sina(实时) -> eastmoney(实时) -> tushare_free -> tushare_pro_daily(EOD兜底)`

- 实现见本 skill 目录下 `data_sources.py` 的 `get_realtime_quote_fallback()`
- 纯实时查询用 `get_intraday_quote()` (跳过 EOD 兜底)
- Fallback 追踪见 `contracts.py` 的 `FallbackRecord`
- 大单量(>5只)直接用 `tushare_pro_daily_batch()` 获取最新日线，更快更稳定

### Step 4: 聚合与输出（v3.6 Tier 引擎）

**4a. 单只股票评估**（对每只已识别的股票）：

```python
from contracts import (
    compute_tier, compute_catalyst_confidence, classify_strategy_tag,
    StockResult, CatalystType, SentimentLevel,
)

# 1. 计算催化剂置信度（含时效衰减 + 多催化加成）
multi = len(stock.catalyst_types) >= 2  # 双催化及以上
stock.multi_catalyst_bonus = multi
stock.confidence = compute_catalyst_confidence(stock.catalyst_types, stock.catalyst_age_hours, multi)

# 2. 根据前日涨跌幅 + 催化剂类型自动分类策略标签
prior_chg = stock.quote.change_pct
stock.strategy_tag = classify_strategy_tag(prior_chg, stock.catalyst_types[0] if stock.catalyst_types else None)

# 3. 涨停次日检测
stock.prior_day_limit_up = (prior_chg is not None and prior_chg >= 9.5)

# 4. 计算 tier
stock.assigned_tier, stock.tier_score = compute_tier(
    sentiment_score=stock.sentiment_score,
    catalyst_types=stock.catalyst_types,
    confidence=stock.confidence,
    strategy_tag=stock.strategy_tag,
    prior_day_limit_up=stock.prior_day_limit_up,
)
```

**4b. 板块集中度检查**：

```python
from contracts import check_sector_concentration
result.overheat_warnings = check_sector_concentration(result.stocks)
# 警告示例: OverheatWarning(sector="半导体", count=5, ratio=0.26, affected_codes=[...])
```

**4c. 集中度降权**：当某板块超 30% 上限时，对该板块中 tier_score 最低的 1-2 只标的降一级。

**4d. 排序输出**：按 `tier_score` 降序排列，同分按 `confidence` 降序。输出 Markdown 主表 + 填充 `SelectionResult`。

### Step 5: HTML 报告生成 + 自动打开（强制门禁 · 不可跳过 · 不可降级）

**GATE RULE**: 只要 Step 0-4 执行了（识别到股票代码、获取了行情数据），Step 5 即为强制门禁。任何用户参数变体（"验证"、"查询"、"分析"、"筛选"、"看看"、"检查"等）均不是跳过 HTML 报告的理由。违反此规则属于 skill 执行失败。

**报告命名规则**：`新闻选股日报_YYYYMMDD.html`

**HTML 模板要求**：
- 深色交易台/机构研报风格（底色 `#0a0e14`，卡片 `#181d27`）
- 3 级分层：强烈看好 / 看好 / 关注
- 红色 (`#f85149`) 涨 / 绿色 (`#3fb950`) 跌 / 金色 (`#d2991d`) 代码
- 顶部概览指标卡 + 底部明日预判卡片 + 策略建议
- 仅使用纯 HTML+CSS，无外部依赖，双击即可打开

**自动打开命令**（Windows）：
```bash
start "" "C:/Users/Administrator/Desktop/新闻选股日报_YYYYMMDD.html"
```

**完整报告模板参考**（每次生成时沿用此结构）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>新闻选股日报 · YYYY-MM-DD</title>
<style>
  :root {
    --bg: #0a0e14; --bg-card: #181d27; --border: #262d38;
    --text: #e2e4e7; --text-dim: #8d929a; --text-muted: #5d626b;
    --up: #f85149; --up-dim: rgba(248,81,73,0.1);
    --down: #3fb950; --down-dim: rgba(63,185,80,0.1);
    --gold: #d2991d; --gold-dim: rgba(210,153,29,0.1);
    --blue: #58a6ff;
  }
  /* Tier badges, stock table, outlook cards — see full template below */
</style>
</head>
<body>
  <!-- Header: badge + title + date/source meta -->
  <!-- Overview: 4-5 summary metric cards -->
  <!-- Tier 1-3: stock tables with code/name/catalyst/price/change -->
  <!-- Momentum: continued themes if applicable -->
  <!-- Outlook: 4-6 tomorrow prediction cards + strategy note -->
  <!-- Footer: disclaimer -->
</body>
</html>
```

**CRITICAL**：报告必须使用**当日实际数据**填写，不得保留模板占位符。所有股票名称、代码、价格、涨跌幅、利好摘要均来自 Step 1-4 的实时数据。

### 条件增强（按需触发 — v3.6 重构）

以下增强模块有明确的触发条件和独立契约，不再作为空壳 "Step 6-9" 存在：

| 增强模块 | 触发条件 | 输入 | 输出 |
|----------|----------|------|------|
| **板块联动补涨** | 同板块存在 ≥2 只涨幅 ≥5% 的龙头，且剩余标的涨幅 <2% | 龙头标的列表 + 同板块全量 | `catchup_opportunities`[] |
| **社交媒体情绪加权** | 结果数量 <5 或用户显式要求情绪热度 | 股票代码列表 | `hot_trend_overlay` dict |
| **板块趋势归因** | `overheat_warnings` 非空 或用户问"主线/板块" | 板块名称 | `sector_trend_context` str |

**规则**：任何增强失败不影响主链。增强输出写入 `SelectionResult` 对应字段，HTML 报告从这些字段渲染。不需要的不执行，没有"空 Step"。

## 输出格式

### 标准输出

```markdown
## 新闻选股结果

**筛选条件**：{条件描述}
**结果数量**：{N} 只

### 强烈看好（重点关注）
| 股票 | 代码 | 板块 | 利好类型 | 新闻摘要 | 来源 | 行情 |
|------|------|------|----------|----------|------|------|
| 贵州茅台 | 600519 | 白酒 | 政策利好 | ... | 东方财富 | +2.3% |

### 看好（值得关注）
| 股票 | 代码 | 板块 | 利好类型 | 新闻摘要 | 来源 | 行情 |
|------|------|------|----------|----------|------|------|
```

**关键规则：**
- 股票名称和代码为必填字段，无法确认的标为"待确认"
- 每只股票必须记录数据来源和行情状态
- `contracts.py` 定义了完整的状态值：`confirmed` / `pending_confirmation` / `failed` / `skipped`

## 触发示例

| 用户输入 | 触发动作 |
|----------|----------|
| "找出今天有政策利好新闻的股票" | 搜索"政策利好 A股"，识别并输出每只股票的代码 |
| "分析业绩超预期的个股" | 搜索"业绩超预期 A股"，每行输出必含代码 |
| "搜索 AI 相关的正面新闻，看哪些股票被提及" | 搜索"AI 利好"新闻 |
| "今天有哪些并购重组公告？" | 搜索"并购重组 A股公告" |
| "哪些股票有技术突破的新闻？" | 搜索"技术突破 研发成功"新闻 |
| "龙头股涨停了，同板块还有什么没涨的？" | 识别龙头 -> 触发板块联动补涨 |
| "AI 板块大涨，哪些还没涨的股票可以关注？" | 搜索 AI 板块涨幅落后的补涨股 |

## 搜索策略

| 利好类型 | 搜索关键词 |
|----------|-----------|
| 业绩超预期 | "业绩预增"、"年报业绩"、"净利润增长"、"营收超预期" |
| 政策利好 | "政策支持"、"补贴政策"、"顶层设计"、"工信部"、"发改委" |
| 并购重组 | "并购"、"重大资产重组"、"收购"、"定增收购" |
| 技术突破 | "技术突破"、"研发成功"、"新品发布"、"专利授权" |
| 重要合作 | "战略合作"、"签订合同"、"订单落地"、"独家供应" |
| 行业景气 | "行业复苏"、"景气上行"、"价格上涨"、"需求旺盛" |
| 股权变动 | "增持"、"回购"、"股东增持"、"股权激励" |
| 概念热点 | "AI概念"、"新能源"、"半导体"、"机器人"、"低空经济" |
| 机构评级 | "买入评级"、"强烈推荐"、"上调目标价"、"增持" |

## MCP 工具参考（仅搜索/新闻检索用 — 行情查询请用 data_sources.py）

```javascript
// 新闻搜索
mcp__mcp-router__search({ query: "关键词", engines: ["bing", "linuxdo"], limit: 20 })
mcp__mcp-router__web_search_exa({ query: "...", numResults: 20 })
mcp__mcp-router__fetchWebContent({ url: "https://...", readability: true })

// 股票代码查询
mcp__mcp-router__search_stock({ keyword: "股票名称或代码" })

// 板块/指数K线
mcp__mcp-router__get_kline({ code: "板块指数代码", type: "day" })
mcp__mcp-router__get_index({ code: "板块指数代码", type: "day" })
mcp__mcp-router__get_index_all({ code: "板块指数代码", type: "day", limit: 50 })

// 市场统计
mcp__mcp-router__get_market_stats()
```

## Python 数据源参考（行情查询用 — 替代 MCP 行情工具）

```python
# 在 skill 目录下执行
from data_sources import (
    get_realtime_quote_fallback,   # 完整 fallback 链
    get_intraday_quote,            # 纯实时（跳过EOD）
    tushare_pro_daily_batch,       # 日线批量（最快）
    get_tushare_pro,               # TuShare Pro 实例
    is_market_hours,               # 判断是否交易时段
)

# 获取实时行情（大单量推荐日线批量）
result = get_realtime_quote_fallback(['600584', '002156', '002371'])
# result['data'][code] = {name, price, change_pct, _source, ...}

# 日线批量（5只以上推荐，更快更稳定）
daily = tushare_pro_daily_batch(['600584', '002156', '002185', '688362', '002371', '688012'])
```

## 注意事项

1. **行情获取走 Python 模块** -- 严禁调用 `get_quote`/`get_batch_quote`/`get_stock_info` 等 MCP 行情工具（localhost:8080 已挂）。统一通过 Bash + Python 调用 `data_sources.py`
2. **数据验证优先** -- 遇到"涨停"/"涨幅X%"等关键词必须通过实时行情交叉验证，防止年份混淆
3. **降级可见** -- 数据源失败不隐藏，记录在 `attempted_sources` 和 `failure_reason` 中
4. **主链优先** -- 增强能力失败不能阻断核心结果输出
5. **代码必填** -- 无法确认代码的股票标为"待确认"，不可省略
6. **配置外置** -- 凭据和路径从环境变量或 `config.py` 读取
7. **输出兼容** -- 默认模式输出保持 Markdown 主表格式 + HTML 报告双通道
8. **HTML 报告强制生成** -- 只要产生了股票数据结果，必须生成 HTML 报告到桌面 (`C:/Users/Administrator/Desktop/新闻选股日报_YYYYMMDD.html`)，并用 `start "" "路径"` 自动打开浏览器。**没有例外路径**——"验证"、"查询"、"分析"等参数变体均不能跳过。如果用户验证的是历史报告（日期非当日），报告标题和内容应注明实际数据日期，但报告仍需生成。

### Step 5+: 次日验证反馈环（v3.6 新增 — 非阻塞）

每次运行后，将 `SelectionResult` 中的 `stocks[].assigned_tier` 和 `stocks[].tier_score` 写入反馈文件：

```bash
# 写入 .meta/feedback.jsonl（追加一行 JSON）
echo '{"date":"YYYYMMDD","code":"000859","assigned_tier":1,"tier_score":0.72}' >> skill/.meta/feedback.jsonl
```

下次运行复盘验证时，读取该文件计算 tier 分配准确性，用于后续权重调优。
此步骤失败不影响主链，仅记录 `feedback_status: "skipped"`。

## 完成前自检清单（CRITICAL — 回应用户前必须逐项确认）

在输出最终回复给用户之前，执行者必须逐项确认以下检查。**任何一项未通过 → 立即补全，不得跳过。**

| # | 检查项 | 通过条件 | 失败动作 |
|---|--------|----------|----------|
| 1 | HTML 报告已写入磁盘 | `C:/Users/Administrator/Desktop/新闻选股日报_YYYYMMDD.html` 文件存在且非空 | 重新执行 Step 5 生成报告 |
| 2 | 报告数据为实时/当日数据 | 所有股价、涨跌幅、股票名称来自 data_sources.py 实际输出，非模板占位符 | 重新拉取行情数据并填入报告 |
| 3 | 浏览器已自动打开 | 已执行 `start "" "路径"` 命令 | 执行打开命令 |
| 4 | 报告结构完整 | 概览指标卡 + 股票分层表格 + 明日预判卡片 + 策略建议 + 免责声明 全部存在 | 补全缺失区块 |
| 5 | **v3.6: Tier 引擎已执行** | 每只股票的 `tier_score`, `assigned_tier`, `strategy_tag`, `prior_day_limit_up` 已填充 | 重新执行 Step 4a |
| 6 | **v3.6: 板块集中度已检查** | `overheat_warnings` 已填充（可为空列表），超 30% 的板块已降权 | 重新执行 Step 4b-4c |
| 7 | **v3.6: TU因素(token)已配置** | 环境变量 `TUSHARE_TOKEN` 和 `TUSHARE_HTTP_URL` 已设置（或确认 TuShare Pro 层已跳过） | 提示用户配置环境变量 |

**此清单是 Step 5 的组成部分，不是独立文档。跳过清单 = 跳过 Step 5 = skill 执行失败。**

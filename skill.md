---
name: news-stock-selector
version: "5.1.0"
description: 新闻选股助手。v5.1 集成通达信本地数据(5537只A股全量扫描，0.6s)，8大投资流派(价值/成长/短线/技术/量化/事件驱动/宏观/投机)，搜索去重复化，流派感知Tier引擎，HTML报告+流派筛选UI。
markets_supported: ["A", "U"]
requires:
  mcp_tools: ["mcp__mcp-router__search", "mcp__mcp-router__web_search_exa", "mcp__mcp-router__fetchWebContent", "mcp__mcp-router__search_stock", "mcp__mcp-router__get_kline", "mcp__mcp-router__get_kline_history", "mcp__mcp-router__get_index", "mcp__mcp-router__get_index_all", "mcp__mcp-router__get_market_stats"]
  python_packages: ["tushare", "akshare", "requests"]
  local_modules: ["data_sources.py", "contracts.py", "supply_chain.py", "schools.py", "tdx_reader.py", "tdx_scanner.py"]
related_skills: ["ftshare-market-data-main", "stock-screener", "lhb-analyzer", "trap-detector", "deep-analysis"]
note: |
  MCP 行情接口 (get_quote/get_batch_quote/get_stock_info @ localhost:8080) 已废弃。
  v5.1: 通达信本地数据(TDX)集成。5537只A股全量扫描(0.6s)，tdx_reader.py+tdx_scanner.py
  v5.0: 8大投资流派集成(schools.py) + 搜索关键词轮换池 + 流派感知Tier引擎。
  v4.1: 融合 mingli30119/stock-analysis 模板体系。
  v4.0: 产业链 BOM 拆解 + 三高筛选（Step 5，主链必跑）。
  v3.7: Step 4 美股涨幅榜→A股映射 + 国内新闻交叉确认。
trigger:
  required: ["新闻选股", "利好选股", "哪些股票有.*新闻", "热点对应个股", "政策利好股票", "并购重组.*股票", "产业链", "上游.*下游", "三高.*选股", "BOM.*拆解"]
  conditional: ["市场热点", "情绪分析", "板块怎么样", "最近什么消息多", "美股.*映射", "美股.*A股"]
  exclude: ["单股行情查询", "个股估值", "龙虎榜席位", "杀猪盘", "纯宏观解读"]
---

# 新闻选股助手

## 核心能力

1. **新闻驱动选股** -- 从新闻/热点中识别 A 股候选标的
2. **美股→A股映射** (v3.7) -- 隔夜美股涨幅榜→A股主题映射 + 国内新闻交叉确认
3. **多层数据验证** -- 实时行情校验、多源 fallback、失败可见
4. **条件增强分析** -- 宏观趋势、板块联动补涨、社交热榜（按需附加）

## 执行模式

### 默认模式（主链必跑 — HTML 报告不可跳过）

**ALL invocation paths MUST produce an HTML report.** 无论用户参数是"验证"、"查询"、"分析"、"筛选"还是其他变体，只要执行了股票识别和行情获取（Step 1-8），Step 9 就是强制门禁。不存在"纯验证模式跳过 HTML"的例外路径。

**TDX本地全市场扫描 (v5.1)** -> 新闻检索 -> **美股涨幅榜映射 (v3.7)** -> **产业链 BOM 拆解 + 三高筛选 (v4.0)** -> 股票识别 -> 行情校验 -> **Tier 分配引擎 (v3.6, 含三高加成+流派感知)** -> 结构化输出 -> **HTML 报告 + 自动打开 [GATE: BLOCKING]**

### Tier 分配引擎（v5.4 — Step 8 核心逻辑）

选股结果不再仅凭情绪主观映射到 T1/T2/T3，而是通过 `contracts.compute_tier()` 量化计算：

```
tier_score = sentiment_norm × 0.30 + catalyst_norm × 0.20 + confidence × 0.20
           + strategy_norm × 0.10 + three_high_norm × 0.20
```

**v5.4 后处理规则（按优先级顺序执行）：**

| 优先级 | 规则 | 触发条件 | 效果 |
|--------|------|---------|------|
| 1 | 涨停次日熔断 | 前日涨停（板别感知） | 强制 T3 上限 |
| 2 | 板块狂热熔断 | 板块涨停数 ≥ 20 | 强制 T2 上限 |
| 3 | 近涨停降权 | 前日涨幅 ≥ 8% 但未涨停 | score × 0.80 |
| 4 | 市场谨慎折扣 | 板块集中度 > 30% 或板块狂热 | score × 0.85 |
| 5 | 独立逻辑加分 | 催化剂独立于主导主线 | score + 0.08 |

**影响 tier 得分的 6 个因子：**
1. **情绪归一化** (30%) — `SentimentLevel / 5.0`
2. **催化剂权重** (20%) — 各 `CatalystType` 的平均权重（政策/并购=1.0, 热点=0.4）
3. **置信度** (20%) — v5.4 含 `CATALYST_CERTAINTY` 确定性权重（业绩=1.0, 热点=0.3）+ 时效衰减 + 多催化剂加成
4. **策略标签** (10%) — `回调低吸`/`催化剂博弈` +1, `近涨停`/`突破追击` -1（见 `classify_strategy_tag()`）
5. **三高加成** (20%, v4.0) — 股票所在产业链环节的三高综合评分 / 10，来自 Step 5 `compute_three_high_bonus()`
6. **涨停次日熔断** — 前一日涨停 → 强制 T3 上限（不参与公式计算）

### 增强模式（条件触发）
- **趋势/板块归因** -- 用户关心板块、主题、主线时启用
- **补涨联动分析** -- 检测到已验证的强势龙头时启用
- **社交热榜加权** -- 用户关心情绪热度或结果较少时启用

## 模块结构

本 skill 由以下模块协同工作（均位于 skill 目录内）：
- `skill.md` -- 入口契约（本文件）
- `config.py` -- 数据源凭据、路径、平台权重
- `contracts.py` -- 统一数据结构、状态值、Tier 引擎、三高评分函数
- `data_sources.py` -- 多源行情 fallback 链、美股涨幅榜、社交热榜抓取
- `schools.py` -- (v5.0) 8大投资流派配置、搜索关键词轮换池、流派匹配
- `supply_chain.py` -- (v4.0) 产业链 BOM 拆解引擎、三高筛选、龙头定位、交叉增强
- `tdx_reader.py` -- (v5.1) 通达信本地 .day/.blk 文件解析器
- `tdx_scanner.py` -- (v5.1) 通达信全市场扫描引擎（5537只A股）
- `gen_report_from_data.py` -- (v4.1) HTML 报告生成器（JSON→完整报告）

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

### Step 1: 解析用户意图 + 投资流派选择 (v5.0增强)

判断用户请求属于：新闻驱动选股 / 指定主题找股票 / 指定利好类型找股票 / 情绪热度导向筛选。

**v5.0: 投资流派选择** — 从用户输入中识别流派偏好（如"我是价值投资者"、"短线操作"、"看看成长股"），映射到对应流派配置。未指定时默认使用**事件驱动派**（兼容旧版行为）。

识别规则：
- 用户说"价值"/"长期"/"低PE"/"巴菲特" → `value` (价值投资)
- 用户说"成长"/"高增长"/"科技股" → `growth` (成长投资)
- 用户说"短线"/"快进快出"/"日内" → `short_term` (短线交易)
- 用户说"技术面"/"K线"/"量价" → `technical` (技术分析)
- 用户说"量化"/"因子"/"模型" → `quant` (量化交易)
- 用户说"新闻"/"事件"/"催化剂" → `event` (事件驱动)
- 用户说"宏观"/"经济周期"/"行业轮动" → `macro` (宏观投资)
- 用户说"投机"/"高风险"/"小盘" → `speculative` (投机派)
- 无明确偏好 → `event` (事件驱动，默认)

流派配置详情见 `schools.py` 的 `SCHOOL_CONFIGS`。

### Step 2: TDX本地全市场扫描 (v5.1 新增)

**目的**：从通达信本地数据（5537只A股）获取全市场最新行情，替代硬编码38只候选池。

**执行**：
```bash
cd "/c/Users/Administrator/.claude/skills/news-stock-selector" && python -c "
from tdx_scanner import TDXScanner
scanner = TDXScanner()
print(f'全市场: {len(scanner.all_stocks)} 只A股')

# 涨幅榜Top30（成交额>1亿）
top = scanner.scan_top_gainers(30, min_amount=1e8)
for code, snap, chg in top:
    print(f'{code} chg={chg:+.2f}% close={snap.latest_close:.1f} amt={snap.latest_amount/1e8:.1f}亿 date={snap.latest_date}')

# 涨停扫描
lu = scanner.scan_limit_up_stocks(9.5)
print(f'涨停(>=9.5%): {len(lu)}只')

# 板块筛选（可选：按新闻主题筛选）
# semi = scanner.scan_by_sectors(['半导体'])
"
```

**注意**：TDX扫描替换 Step 7 的行情校验——TDX本地数据已包含价格/涨跌幅，无需再次用tencent-qt查询。

### Step 3: 新闻检索 (v5.0 日期注入+轮换关键词)

**v5.0 去重复化机制**：

**3a. 日期注入**：每次搜索必带当日日期，如"2026年7月5日 A股利好消息"。

**3b. 关键词轮换**：从 `schools.py` 的 `SEARCH_KEYWORD_POOL` 中按利好类型各随机选1个词。每次运行至少覆盖4种不同类型。

**3c. 多角度覆盖**：同时搜索3-5个不同角度的利好新闻，不重复搜同一主题。

通过 MCP 工具或 WebSearch 检索相关新闻。优先使用 MCP 多引擎搜索，失败时降级为通用搜索。

### Step 4: 美股涨幅榜映射（v3.7 新增 · 主链必跑）

**目的**：利用隔夜美股强势标的的溢出效应，提前锁定次日 A 股映射机会，结合国内新闻交叉确认增强信号可靠性。

**执行步骤**：

**4a. 获取美股最新收盘涨幅榜（v4.1 8-tier fallback + 质量过滤）**

**CRITICAL**: 优先使用 Python `data_sources.py` 的 `get_us_top_gainers()` 函数获取美股实时涨幅榜数据。该函数 (v4.1) 主源使用 yfinance Screener `day_gainers` 获取全市场真实涨幅排行，并通过 8 级 fallback 链保障数据可用性。

**v4.1 数据源优先级**:
  1. yfinance Screener 'day_gainers'      — 全市场真实涨幅榜 (PRIMARY)
  2. TradingView Scanner                  — 零认证扫描 API
  3. 同花顺 detailDefer                    — 抓取 HTML 表格，字段丰富（换手率/市盈率/52周高低）
  4. 新浪财经 Market_Center API           — 无需认证 GET API
  5. 东方财富 push2 API                    — 内部文档齐全的 API
  6. Alpha Vantage TOP_GAINERS_LOSERS     — 需 API key
  7. 腾讯 qt.gtimg.cn 扫描池兜底           — 最后兜底方案

**v4.1 质量过滤（默认开启）**：自动过滤权证(W后缀)、仙股(<$1)、低量(<10万股)、异常值(>500%)。
可通过 `get_us_top_gainers(quality_filter=False)` 关闭过滤，查看原始全市场数据。

**v5.4 A股映射质量过滤（新增）**：美股涨幅榜中的小盘仙股（价格<$5 或 市值<$1B）几乎无A股映射价值（如 CLRO $6.48, CWD $1.23）。仅对满足以下条件的美股执行A股映射：
- 股价 ≥ $5
- 市值 ≥ $1B（或无法获取市值时股价 ≥ $10 作为替代条件）
- 不满足条件的标记为"无A股映射价值"，跳过 Step 4b-4c 映射步骤

不要使用 `web_search_exa` / `search` MCP 工具搜新闻——新闻搜索返回的是几小时到几天前的文章，不是实时数据。

**执行步骤**：

1. **主数据源 — Python data_sources 模块（必须优先执行）**：
```bash
cd "/c/Users/Administrator/.claude/skills/news-stock-selector" && python -c "
from data_sources import get_us_top_gainers
import json
result = get_us_top_gainers(limit=10)
print(json.dumps({'source': result['source'], 'gainers_found': result['gainers_found'], 'gainers_missing': result.get('gainers_missing', 0)}, ensure_ascii=False))
for g in result.get('gainers', []):
    print(f\"{g['ticker']} | {g['company']} | price={g['price']} | chg={g['change_pct']}% | src={g.get('_source')}\")
"
```

2. **新闻补充 — 获取涨因驱动（仅在主数据源成功后执行）**：
   **CRITICAL: 对全部 Top 10 股票逐一搜索驱动因素，不得仅查 Top 5。**
   对涨幅 Top 10 全部股票的驱动因素进行 MCP 搜索：
```
对每只Top10逐一搜索: "{TICKER} stock why up today 2026年7月" 或 "{TICKER} 暴涨 原因"
搜索工具：mcp__mcp-router__web_search_exa 或 mcp__mcp-router__search
每只美股结果需记录：驱动因素、所属行业/赛道、是否具备A股映射潜力
```

3. **数据合并**：将 `get_us_top_gainers()` 的结构化行情数据 + MCP 搜索的驱动分析合并到 `USGainerMapping` 中。
   **全部 10 只必须完成合并**，即使部分标的无A股映射线索也需记录为"无确认"而非丢弃。

4. **失败降级**：只有当 `get_us_top_gainers()` 完全失败（`result['source'] == 'pending'`）时，才降级使用纯 MCP 搜索获取美股涨幅榜。

**4b. A股主题映射 （必须对全部10只执行）**

**CRITICAL**: 对 Top 10 全部美股逐一做A股映射，不可仅映射前5只。流程：

a) 对每只美股，提取核心驱动主题关键词（从公司业务、上涨驱动、所属行业推导）
b) 在 `contracts.py` 的 `US_THEME_TO_A_SHARE` 表中模糊匹配最相关条目
c) 搜索国内对应A股板块的利好新闻交叉验证
d) 输出：至少列出3-6只A股映射标的代码+名称
e) 无法映射的标记为"无确认"也不得丢弃

```python
from contracts import US_THEME_TO_A_SHARE

# 对每只美股（全部10只）提取核心驱动主题关键词
# 在 US_THEME_TO_A_SHARE 中模糊匹配最相关条目
# 匹配时同时考虑：公司业务描述、上涨驱动、所属行业
# 无法匹配的标为"无直接映射"，仍需记录
```

**4c. 国内新闻交叉确认**

对每个映射主题，搜索国内 A 股利好新闻交叉验证：

```
搜索关键词："{A股板块} 利好" 或 "{主题关键词} A股"
示例："光模块 利好 A股"、"AI服务器 政策支持"
```

交叉确认规则：
- **强确认** (cross_confirm=2)：美股大涨 + 国内同主题有利好新闻 → 对应 A 股映射置信度高
- **弱确认** (cross_confirm=1)：美股大涨 + 国内同主题无显著新闻 → 仅靠溢出效应，置信度中等
- **无确认** (cross_confirm=0)：无国内新闻映射 → 仅记录不推荐

**4d. 输出 USGainerMapping 列表**

```python
from contracts import USGainerMapping

mapping = USGainerMapping(
    rank=1,
    ticker="MRVL",
    company="Marvell Technology",
    change_pct=33.0,
    close_price=277.30,
    driver="黄仁勋Computex点名下一个万亿公司",
    a_share_theme="AI芯片/数据中心网络",
    suggested_a_stocks=["688256", "688981"],
    confirming_news=["国内AI芯片政策利好持续", "寒武纪获机构密集调研"],
)
result.us_gainers.append(mapping)
```

美股映射失败不影响主链，仅记录 `us_gainers: []`。

### Step 5: 产业链 BOM 拆解 + 三高筛选（v4.0 新增 · 主链必跑）

**目的**：用产业链思维挖掘牛股——BOM 拆解识别上下游环节 → 三高（高增长/高利润/高壁垒）筛选最优环节 → 定位环节龙头。博主"5个月45倍"的核心方法论。

**执行步骤**：

**5a. 提取行业主题**

从用户查询和 Step 3 新闻检索结果中提取核心行业/主题（如"AI算力"、"光通信"、"半导体"）。若用户查询已明确主题则直接使用，否则从新闻热词中自动提取 Top 1-2 个主题。

**5b. BOM 产业链拆解**

使用 LLM（AI）对每个主题进行产业链拆解。拆解提示词模板见 `supply_chain.py` 的 `BOM_DECOMPOSE_PROMPT`。

```
对"{行业}"进行产业链 BOM 拆解：
1. 拆解为上游/中游/下游，每个层级 2-5 个核心环节
2. 标注环节间供需关系（谁供给谁、谁依赖谁）
3. 给出每个环节的：年增速(%)、毛利率区间、壁垒等级+原因、供需状态
```

LLM 会返回结构化的 JSON，包含所有环节节点及其属性。

**5c. 三高评分**

对每个产业链环节调用 `contracts.compute_three_high_score()`：

```python
from contracts import compute_three_high_score

for node in supply_chain_nodes:
    node.three_high_score = compute_three_high_score(
        growth_rate=node.growth_rate,
        gross_margin_str=node.gross_margin_range,
        barrier_level=node.barrier_level,
        supply_demand_gap=node.supply_demand_gap,
    )
```

评分规则：
- **增长得分** (0-10)：≥30% → 9+, 20-30% → 7-8, 10-20% → 5-6
- **利润得分** (0-10)：≥50% → 9.5, 30-50% → 7.5, 20-30% → 5.5
- **壁垒得分** (0-10)：极高 → 9.5, 高 → 7.5, 中 → 5.0, 供需失衡额外 +0.5~1.0
- **综合** = growth×0.4 + profit×0.3 + barrier×0.3，≥ 7.0 视为"三高环节"

**5d. 环节龙头定位**

对每个三高环节，搜索 A 股对应的龙头公司和主要参与者：

```
搜索关键词："{环节名称} A股 龙头" 或 "{环节名称} 概念股 龙头"
```

使用 `supply_chain.py` 的 `LEADER_MAPPING_PROMPT` 让 LLM 系统性地映射每个环节的 A 股标的，输出包含代码、名称和入选理由。

**5e. 产业链分析汇总**

调用 `supply_chain.build_supply_chain_analysis()` 构建完整结果，写入 `SelectionResult.supply_chain_analysis`。

**5f. 交叉增强**

将产业链三高环节的龙头与新闻选股结果做交叉匹配：

```python
from supply_chain import merge_chain_with_stocks

# 对每只新闻选出的股票，计算三高加成
three_high_bonuses = merge_chain_with_stocks(
    analysis=result.supply_chain_analysis,
    stock_codes=[s.code for s in result.stocks],
    stock_sectors={s.code: s.sector for s in result.stocks},
)
# → 传入 Step 8 compute_tier(three_high_bonus=...)
```

**降级规则**：
- LLM 拆解失败 → 跳过产业链分析，`supply_chain_analysis` 为 None，三高加成全为 0（主链不受影响）
- 龙头映射失败 → 环节保留但 `a_share_leaders` 为空
- 评分数据缺失 → 使用默认值继续计算

### Step 6: 股票识别与标准化
从新闻中提取股票代码（6 位数字）和名称。无法确认时标记为"待确认"，不丢弃。

### Step 7: 实时行情校验 （Python data_sources 模块 — 禁止使用 MCP 行情工具）

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

### Step 8: 聚合与输出（v5.4 Tier 引擎）

**8a. 单只股票评估**（对每只已识别的股票，v5.4 增强）：

```python
from contracts import (
    compute_tier, compute_tier_for_school, compute_catalyst_confidence, classify_strategy_tag,
    detect_sector_frenzy, compute_independent_catalyst,
    StockResult, CatalystType, SentimentLevel, is_real_limit_up,
)

# Step 1 识别的流派（默认 event）
school = "value"  # 示例：价值投资派

# 0. v5.4: 板块狂热检测（全市场扫描 → 标记狂热板块）
# 基于 TDX 全市场扫描结果，检测涨停≥20只的板块
all_market_snaps = {code: snap for code, snap in scanner.all_stocks.items()}
frenzy_map = detect_sector_frenzy(
    [s.code for s in result.stocks],
    all_market_snaps,
)

# 0b. v5.4: 识别主导主题和独立逻辑
dominant_sectors = {sector for sector, count in sector_counter.items() if count >= 3}
dominant_catalyst = max(catalyst_counter, key=catalyst_counter.get) if catalyst_counter else None

for stock in result.stocks:
    # 1. 计算催化剂置信度（v5.4: 含 CATALYST_CERTAINTY 确定性权重）
    multi = len(stock.catalyst_types) >= 2
    stock.multi_catalyst_bonus = multi
    stock.confidence = compute_catalyst_confidence(stock.catalyst_types, stock.catalyst_age_hours, multi)

    # 2. 根据前日涨跌幅 + 催化剂类型自动分类策略标签
    prior_chg = stock.quote.change_pct
    stock.strategy_tag = classify_strategy_tag(prior_chg, stock.catalyst_types[0] if stock.catalyst_types else None)

    # 3. 涨停次日检测（板别感知）
    stock.prior_day_limit_up = is_real_limit_up(stock.code, prior_chg) if prior_chg is not None else False

    # 3b. v5.4: 近涨停检测（≥8%但未涨停）
    stock.near_limit_up = (
        prior_chg is not None
        and prior_chg >= 8.0
        and not stock.prior_day_limit_up
    )

    # 3c. v5.4: 板块狂热标记
    stock.sector_frenzy = frenzy_map.get(stock.code, False)

    # 3d. v5.4: 独立催化剂判断
    stock.independent_catalyst = compute_independent_catalyst(
        stock.sector, stock.catalyst_types,
        dominant_sectors, dominant_catalyst,
    )

    # 4. 计算三高加成 (v4.0)
    from contracts import compute_three_high_bonus
    three_high = compute_three_high_bonus(stock.code, result.supply_chain_analysis)

    # 5. v5.4: 市场谨慎判断（板块集中度>30% 或 板块狂热）
    market_caution = (
        len(result.overheat_warnings) > 0
        or stock.sector_frenzy
    )

    # 6. 计算 tier (v5.4: 6个新参数)
    stock.assigned_tier, stock.tier_score = compute_tier_for_school(
        sentiment_score=stock.sentiment_score,
        catalyst_types=stock.catalyst_types,
        confidence=stock.confidence,
        strategy_tag=stock.strategy_tag,
        prior_day_limit_up=stock.prior_day_limit_up,
        three_high_bonus=three_high,
        school=school,
        near_limit_up=stock.near_limit_up,           # v5.4 NEW
        sector_frenzy=stock.sector_frenzy,           # v5.4 NEW
        market_caution=market_caution,               # v5.4 NEW
        independent_catalyst=stock.independent_catalyst,  # v5.4 NEW
    )

    # 7. 流派匹配标签
    from schools import match_stocks_to_schools
    school_tags = match_stocks_to_schools([stocks_data])
```

**v5.4 新增 tier 后处理规则（按优先级）**：

| 优先级 | 规则 | 触发条件 | 效果 |
|--------|------|---------|------|
| 1 | 涨停次日熔断 | 前日涨停（板别感知） | 强制 T3 上限 |
| 2 | 板块狂热熔断 | 板块涨停数 ≥ 20 | 强制 T2 上限（全线降级） |
| 3 | 近涨停降权 | 前日涨幅 ≥ 8% 但未涨停 | tier_score × 0.80 |
| 4 | 市场谨慎折扣 | 板块集中度 > 30% 或板块狂热 | tier_score × 0.85 |
| 5 | 独立逻辑加分 | 催化剂独立于主导主线 | tier_score + 0.08 |

**v5.4 催化剂确定性权重**（`CATALYST_CERTAINTY`）：

| 催化剂类型 | 确定性 | 说明 |
|-----------|--------|------|
| EARNINGS 业绩超预期 | 1.0 | 数据可验证，确定性最高 |
| POLICY 政策利好 | 0.8 | 方向明确但落地有延迟 |
| MA 并购重组 | 0.8 | 确定性高但审批风险 |
| TECH 技术突破 | 0.7 | 中高确定性 |
| COOP 重要合作 | 0.7 | 中高确定性 |
| INDUSTRY 行业景气 | 0.5 | 中期趋势，短期不一定兑现 |
| EQUITY 股权变动 | 0.5 | 中期信号 |
| HOT 概念热点 | 0.3 | 纯情绪驱动，确定性最低 |
| RATING 机构评级 | 0.3 | 参考价值有限 |
```

**8b. 板块集中度检查**：

```python
from contracts import check_sector_concentration
result.overheat_warnings = check_sector_concentration(result.stocks)
# 警告示例: OverheatWarning(sector="半导体", count=5, ratio=0.26, affected_codes=[...])
```

**8c. v5.4 集中度降权 + 强制分散**：

当某板块超 30% 上限时，执行以下步骤（不仅是警告）：

1. **降权**：对该板块中 tier_score 最低的 1-2 只标的降一级
2. **强制补充**：从非热点板块搜索 ≥3 只独立逻辑标的（搜索关键词："{今日日期} 业绩预增 公告" / "政策利好 {今日日期}"），优先选择：
   - 有业绩预增公告的标的（确定性最高）
   - 有政策利好或并购重组的标的
   - 板块不在当前选股主导主题中
3. **独立催化剂标记**：补充标的自动标记 `independent_catalyst = True`，传入 `compute_tier()` 获得 +0.08 加分
4. **分散验证**：补充后重新检查板块集中度，确保 no single sector > 40%

```python
# 强制分散逻辑
if overheat_warnings:
    # 搜索非热点板块标的
    supplementary = search_independent_catalysts(
        exclude_sectors=dominant_sectors,
        min_results=3,
    )
    for stock in supplementary:
        stock.independent_catalyst = True
        result.stocks.append(stock)
    # 重新检查集中度
    result.overheat_warnings = check_sector_concentration(result.stocks)
```

**8d. 排序输出**：按 `tier_score` 降序排列，同分按 `confidence` 降序。输出 Markdown 主表 + 填充 `SelectionResult`。

### Step 9: HTML 报告生成 + 自动打开（强制门禁 · 不可跳过 · 不可降级）

**GATE RULE**: 只要 Step 1-8 执行了（识别到股票代码、获取了行情数据），Step 9 即为强制门禁。任何用户参数变体（"验证"、"查询"、"分析"、"筛选"、"看看"、"检查"等）均不是跳过 HTML 报告的理由。违反此规则属于 skill 执行失败。

**报告命名规则**：`新闻选股日报_YYYYMMDD.html`

**HTML 报告生成方式** (v4.1)：

> **推荐方式：使用 `gen_report_from_data.py` 脚本保证生成。**

将 Step 1-8 的选股结果组装为 JSON，通过 Python 脚本一步生成含完整模板 CSS/JS 的 HTML 报告，并自动打开浏览器。

**使用步骤**：
1. 将 `SelectionResult` 数据序列化为 JSON 文件
2. 运行脚本生成 HTML 报告

```bash
cd "/c/Users/Administrator/.claude/skills/news-stock-selector" && python gen_report_from_data.py /path/to/data.json
```

脚本自动：读取 `shared/template_base.css` + `shared/template_base.js` → 注入数据 → 渲染 HTML → 写入桌面 → 自动打开浏览器。

**JSON 输入格式**：

```json
{
    "query": "筛选条件", "date": "YYYYMMDD",
    "stocks": [{
        "code": "603986", "name": "兆易创新", "tier": 1,
        "price": 500.5, "chg": 5.59, "sector": "存储/半导体",
        "strategy": "催化剂博弈", "tier_score": 0.931,
        "news": "核心利好摘要", "limit_up": false
    }],
    "us_gainers": [{ "rank": 1, "ticker": "CHAI", "company": "...", "chg": 249.39, "price": "$2.87", "driver": "...", "theme": "AI应用", "a_stocks": "...", "confirm": "强确认", "confirm_text": "..." }],
    "supply_chain": { "has_data": true, "nodes": [...], "top_segment": "...", "summary": "..." },
    "outlook": [{ "title": "标题", "desc": "描述", "style": "bullish/caution/neutral" }],
    "strategies": ["策略1", "策略2"],
    "overheat_warnings": [{ "sector": "...", "count": 5, "ratio": 0.26 }],
    "sectors": [{ "name": "板块", "chg": 5.0 }]
}
```

> **备选方式（脚本不可用时）**：AI 直接手写 HTML，从 `shared/template_base.css` 和 `shared/template_base.js` 完整复制内容到 `<style>` / `<script>` 标签内。参考下方 HTML 结构。

**模板特性**：
- 双主题：深色 Bloomberg 终端风（默认）+ 浅色 Apple 玻璃拟态（手动切换按钮 ☀️/🌙）
- `shared/template_base.css` (~18KB)：CSS 变量驱动，33 个组件区块，响应式
- `shared/template_base.js` (~8KB)：主题切换 + ECharts 图表 + 导航滚动高亮 + 响应式 resize
- 图表可选：板块涨跌柱状图 + Tier 分布饼图 + 单股 K 线迷你图（需 ECharts CDN）
- 无 ECharts 时正常降级，所有图表容器静默跳过
- 仅使用纯 HTML+CSS+JS，无构建工具，双击即可打开

**自动打开命令**（Windows）：
```bash
start "" "C:/Users/Administrator/Desktop/新闻选股日报_YYYYMMDD.html"
```

**报告结构要点**（脚本不可用时的手写参考。模板 CSS/JS 权威来源为 `shared/template_base.css` 和 `shared/template_base.js`，不可凭记忆手写）：

- **顶部导航**: logo + 概览/产业链/美股映射/T1/T2/T3/预判 锚点链接 + 主题切换按钮
- **Header 卡片**: Badge + 标题 + 日期/条件/数量 meta
- **KPI 概览**: 5 张 kpi-card（T1/T2/T3 数量、上涨占比、平均涨跌）
- **产业链分析**: sc-table 表格 + 三高环节 badge-3h 高亮
- **美股映射**: us-gainer-card 列表 + cross-confirm 标签
- **T1/T2/T3 分层表格**: stock-table，每行含代码/名称/板块/利好类型/催化剂/现价/涨跌/策略/评分
- **板块过热预警**: overheat-warn（条件渲染）
- **明日预判**: outlook-grid（3 张卡片）+ strategy-box
- **Footer**: 免责声明
- **数据注入**: `window.__REPORT_DATA__` + `window.__SCHOOL_DATA__`（在模板 JS 之前）

**CRITICAL**：报告必须使用**当日实际数据**填写，不得保留模板占位符。所有股票名称、代码、价格、涨跌幅、利好摘要均来自 Step 3-8 的实时数据。

### 条件增强（按需触发 — v3.6 重构）

以下增强模块有明确的触发条件和独立契约，不再作为空壳 "Step 6-9" 存在：

| 增强模块 | 触发条件 | 输入 | 输出 |
|----------|----------|------|------|
| **板块联动补涨** | 同板块存在 ≥2 只涨幅 ≥5% 的龙头，且剩余标的涨幅 <2% | 龙头标的列表 + 同板块全量 | `catchup_opportunities`[] |
| **社交媒体情绪加权** | 结果数量 <5 或用户显式要求情绪热度 | 股票代码列表 | `hot_trend_overlay` dict |
| **板块趋势归因** | `overheat_warnings` 非空 或用户问"主线/板块" | 板块名称 | `sector_trend_context` str |

> **注意**：社交热榜抓取（微博/知乎/百度/抖音/头条/B站）依赖公开 API，各平台反爬策略频繁变更，**成功率不保证**。社交情绪加权模块失败不影响主链，仅跳过增强。

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

### v5.0 关键词轮换池（每次随机选取，避免重复）

> **权威来源**: `schools.py` 的 `SEARCH_KEYWORD_POOL`。以下为可读参考，实际执行以 Python 模块为准。

| 利好类型 | 搜索引擎关键词（轮换池） |

| 利好类型 | 搜索引擎关键词（轮换池） |
|----------|------------------------|
| 业绩超预期 | "业绩预增"、"净利润大增"、"营收超预期"、"业绩暴增"、"利润翻倍"、"业绩预告大增" |
| 政策利好 | "政策支持"、"补贴政策"、"顶层文件"、"国务院发文"、"发改委新规"、"工信部利好" |
| 并购重组 | "重大资产重组"、"并购公告"、"定增收购"、"借壳上市"、"资产注入" |
| 技术突破 | "技术突破"、"研发成功"、"新品发布"、"专利授权"、"国产替代" |
| 重要合作 | "战略合作"、"签订合同"、"订单落地"、"大单公告"、"合作协议" |
| 行业景气 | "行业复苏"、"景气上行"、"价格上涨"、"需求旺盛"、"供不应求" |
| 概念热点 | "AI概念"、"人工智能利好"、"半导体突破"、"机器人概念"、"低空经济" |

### 静态搜索参考（v4.x 保留兼容）

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

### 产业链拆解搜索策略（v4.0 新增）

| 搜索目标 | 搜索关键词 |
|----------|-----------|
| 产业链结构 | "{行业} 产业链 上游 中游 下游"、"{行业} BOM 拆解" |
| 环节增速 | "{环节} 市场规模 增速"、"{环节} 行业增长率" |
| 毛利率 | "{环节} 毛利率"、"{行业} 各环节 利润分布" |
| 壁垒分析 | "{环节} 技术壁垒"、"{环节} 进入门槛"、"{环节} 竞争格局" |
| 龙头定位 | "{环节} 龙头 A股"、"{环节} 概念股 龙头" |
| 供需状态 | "{环节} 供需 缺口"、"{环节} 产能 紧缺" |
| 国产替代 | "{环节} 国产替代 空间"、"{环节} 国产化率" |

### 美股涨幅榜搜索策略（v3.7 新增）

| 搜索目标 | 搜索关键词 |
|----------|-----------|
| 美股涨幅榜 | "US stock market top gainers today"、"美股 涨幅最大 收盘"、"美股 涨幅榜 最新" |
| 美股暴涨原因 | "{TICKER} stock why up today"、"{TICKER} 暴涨 原因" |
| A股映射确认 | "{A股主题} 利好 A股"、"{板块} 政策利好"、"{主题} 概念股" |
| 实时行情（v3.8主源） | Python get_us_top_gainers() → yfinance + 腾讯qt交叉验证 | 实时结构化数据，替代搜索 |
| 美股大盘情绪 | "US stock market today S&P 500 Nasdaq"、"费城半导体 SOX" |

## MCP 工具参考

### 新闻/搜索（可靠·主用）
```javascript
mcp__mcp-router__search({ query: "关键词", engines: ["bing"], limit: 20 })
mcp__mcp-router__web_search_exa({ query: "...", numResults: 20 })
mcp__mcp-router__fetchWebContent({ url: "https://...", readability: true })
mcp__mcp-router__search_stock({ keyword: "股票名称或代码" })
```

### 指数/板块K线（可选·降级到 data_sources.py）
```javascript
// 以下 MCP 工具可能可用，失败时降级到 Python data_sources.py 或 akshare
mcp__mcp-router__get_kline({ code: "板块指数代码", type: "day" })
mcp__mcp-router__get_index({ code: "板块指数代码", type: "day" })
mcp__mcp-router__get_index_all({ code: "板块指数代码", type: "day", limit: 50 })
mcp__mcp-router__get_market_stats()
```

### 已废弃（严禁调用）
```javascript
// ❌ 这些工具指向 localhost:8080 后端，已不可用
mcp__mcp-router__get_quote()        // → 使用 data_sources.get_realtime_quote_fallback()
mcp__mcp-router__get_batch_quote()  // → 使用 data_sources.get_realtime_quote_fallback()
mcp__mcp-router__get_stock_info()   // → 使用 data_sources 组合
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

## 产业链分析参考（v4.0 — Step 5 用）

```python
from supply_chain import (
    build_supply_chain_analysis,    # 完整分析流程：解析→评分→龙头→汇总
    parse_supply_chain_nodes,       # 解析 LLM 返回的 JSON 节点
    score_supply_chain_nodes,       # 三高评分批量计算
    merge_chain_with_stocks,        # 产业链×新闻选股交叉增强
    format_supply_chain_markdown,   # 格式化为 Markdown 输出
    export_analysis_for_report,     # 导出为 HTML 报告 dict
    BOM_DECOMPOSE_PROMPT,           # BOM 拆解提示词模板
    LEADER_MAPPING_PROMPT,          # 龙头映射提示词模板
)

from contracts import (
    compute_three_high_score,       # 单环节三高评分
    compute_three_high_bonus,       # 单股票三高加成 (0-10)
    SupplyChainNode, ThreeHighScore, SupplyChainAnalysis,
)
```

## 注意事项

1. **行情获取走 Python 模块** -- 严禁调用 `get_quote`/`get_batch_quote`/`get_stock_info` 等 MCP 行情工具（localhost:8080 已挂）。A股行情通过 data_sources.py 的 `get_realtime_quote_fallback()`，美股涨幅榜通过 `get_us_top_gainers()` 获取。统一走 Bash + Python 调用
2. **数据验证优先** -- 遇到"涨停"/"涨幅X%"等关键词必须通过实时行情交叉验证，防止年份混淆
3. **降级可见** -- 数据源失败不隐藏，记录在 `attempted_sources` 和 `failure_reason` 中
4. **主链优先** -- 增强能力失败不能阻断核心结果输出
5. **代码必填** -- 无法确认代码的股票标为"待确认"，不可省略
6. **配置外置** -- 凭据和路径从环境变量或 `config.py` 读取
7. **输出兼容** -- 默认模式输出保持 Markdown 主表格式 + HTML 报告双通道
8. **HTML 报告强制生成** -- 只要产生了股票数据结果，必须生成 HTML 报告到桌面 (`C:/Users/Administrator/Desktop/新闻选股日报_YYYYMMDD.html`)，并用 `start "" "路径"` 自动打开浏览器。**没有例外路径**——"验证"、"查询"、"分析"等参数变体均不能跳过。如果用户验证的是历史报告（日期非当日），报告标题和内容应注明实际数据日期，但报告仍需生成。

### Step 10: 次日验证反馈环（v3.6 新增 — 非阻塞）

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
| 1 | HTML 报告已写入磁盘 | `C:/Users/Administrator/Desktop/新闻选股日报_YYYYMMDD.html` 文件存在且非空 | 重新执行 Step 9 生成报告 |
| 2 | 报告数据为实时/当日数据 | 所有股价、涨跌幅、股票名称来自 data_sources.py 实际输出，非模板占位符 | 重新拉取行情数据并填入报告 |
| 3 | 浏览器已自动打开 | 已执行 `start "" "路径"` 命令 | 执行打开命令 |
| 4 | 报告结构完整 | 概览指标卡 + 股票分层表格 + 明日预判卡片 + 策略建议 + 免责声明 全部存在 | 补全缺失区块 |
| 5 | **v3.6: Tier 引擎已执行** | 每只股票的 `tier_score`, `assigned_tier`, `strategy_tag`, `prior_day_limit_up` 已填充 | 重新执行 Step 8a |
| 6 | **v3.6: 板块集中度已检查** | `overheat_warnings` 已填充（可为空列表），超 30% 的板块已降权 | 重新执行 Step 8b-8c |
| 7 | **v4.1: HTML 用脚本生成** | `gen_report_from_data.py` 成功执行或在无法调用脚本时手动生成的 HTML 文件存在且 > 10KB | 重新执行脚本或手动补全 HTML |
| 8 | **v3.7: 美股涨幅榜映射已执行（全部Top10）** | `SelectionResult.us_gainers` 已填充全部10只（部分可为"无确认"），HTML 报告中包含美股→A股映射表 | 重新执行 Step 4 |
| 9 | **v4.0: 产业链BOM拆解+三高已执行** | `SelectionResult.supply_chain_analysis` 已填充（失败时为 None），三高环节龙头已注入 tier 评分，HTML 报告含产业链分析表 | 重新执行 Step 5 |
| 10 | **v5.3: 补涨板块已检测** | `catchup_opportunities` 已填充（可为空列表），HTML 报告中含补涨板块表 | 重新执行 catchup 检测 |
| 11 | **v4.1: 数据源无死引用** | 未使用 MCP 行情工具(get_quote/get_batch_quote/get_stock_info)；行情通过 data_sources.py 获取 | 切换为正确的行情获取方式 |
| 12 | **v5.3: 一句话总结已生成** | `executive_summary` 已填充，HTML 报告 header 下方可见总结卡片 | 重新执行 Step 9 |
| 13 | **v5.3: 分阶段操作建议已生成** | `today_suggestions` + `tomorrow_suggestions` 各含 all_market + main_board 双通道，HTML 含今日/明日+新手分区 | 重新执行 Step 9 |
| 14 | **v5.4: 板块狂热已检测** | 全市场涨停扫描已执行，`sector_frenzy` 标记已传入 tier 引擎，狂热板块标的已降级 | 重新执行 Step 8a |
| 15 | **v5.4: 催化剂确定性权重已应用** | `CATALYST_CERTAINTY` 已参与 `compute_catalyst_confidence()` 计算，HOT 概念权重 0.3 vs EARNINGS 1.0 | 重新执行 Step 8a |
| 16 | **v5.4: 强制分散已执行** | 板块集中度>30%时，非热点板块补充标的已搜索并添加，independent_catalyst 标记已设置 | 重新执行 Step 8c |
| 17 | **v5.4: Tier 与预判一致** | 当板块集中度>30%或板块狂热时，`market_caution=True` 已传入 tier 引擎 | 重新执行 Step 8a |
| 18 | **v5.4: 美股映射质量过滤** | 仅价格≥$5且市值≥$1B的美股执行A股映射，小盘仙股已标记为"无映射价值" | 重新执行 Step 4 |

**此清单是 Step 9 的组成部分，不是独立文档。跳过清单 = 跳过 Step 9 = skill 执行失败。**

# 新闻选股助手 (News Stock Selector)

<p align="center">
  <img src="https://img.shields.io/badge/version-3.6.0-blue?style=flat-square" alt="Version 3.6.0">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Claude%20Code-Skill-8A2BE2?style=flat-square" alt="Claude Code Skill">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License MIT">
  <img src="https://img.shields.io/badge/market-A%20股-red?style=flat-square" alt="A-Share Market">
</p>

---

## 概述

**新闻选股助手** 是一个 Claude Code 技能（Skill），从新闻和热点中自动识别相关 A 股标的，通过多源行情验证和量化 Tier 评分引擎产出结构化选股结果，并**强制生成**深色交易台风格的 HTML 日报。

### 三大核心能力

| 能力 | 说明 |
|------|------|
| **新闻驱动选股** | 从政策、业绩、并购、技术突破等 9 类利好新闻中自动识别 A 股候选标的 |
| **多层数据验证** | 6 级行情 Fallback 链（雪球 -> 腾讯 -> 新浪 -> 东财 -> TuShare Free -> TuShare Pro），失败可见、降级可追踪 |
| **条件增强分析** | 按需触发板块联动补涨、社交热榜加权、板块趋势归因，不影响主链 |

---

## 系统架构

```
skill.md                  # 入口契约（触发词、执行流程、输出规范）
|
|-- config.py             # 外置配置（环境变量 / 凭据 / 路径 / 平台权重）
|-- contracts.py          # 统一数据契约（枚举 / Dataclass / Tier 分配引擎）
|-- data_sources.py       # 多源行情 Fallback 链 + 社交热榜抓取
|-- compute_tiers.py      # Tier 计算引擎（独立可执行，批量打分 + JSON 输出）
|
tests/
|-- __init__.py
|-- test_contracts.py     # contracts 模块单元测试
|-- test_data_sources.py  # 数据源模块单元测试

.meta/
|-- feedback.jsonl        # 次日验证反馈记录（v3.6 新增）
```

### 模块职责

| 模块 | 职责 | 关键导出 |
|------|------|----------|
| `skill.md` | Skill 入口，定义触发条件、执行步骤、输出规范 | 触发词列表、5 步执行流程、自检清单 |
| `config.py` | 环境变量读取、凭据管理、路径配置 | `TUSHARE_TOKEN`, `TUSHARE_HTTP_URL`, `REPORT_DIR`, `PROVIDER_LABELS` |
| `contracts.py` | 所有数据结构、枚举、Tier 分配算法 | `StockResult`, `SelectionResult`, `compute_tier()`, `classify_strategy_tag()`, `check_sector_concentration()` |
| `data_sources.py` | 多源行情抓取、社交热榜并行采集 | `get_realtime_quote_fallback()`, `get_intraday_quote()`, `tushare_pro_daily_batch()`, `fetch_hot_trends()` |
| `compute_tiers.py` | 独立可执行的 Tier 批量计算脚本 | 命令行运行，输出 JSON 格式评分结果 |

---

## Tier 分配引擎 v3.6 (核心亮点)

选股结果不再靠主观映射到 T1/T2/T3，而是通过量化公式计算。

### 核心公式

```
tier_score = sentiment_norm x 0.35 + catalyst_norm x 0.25 + confidence x 0.25 + strategy_norm x 0.15
```

### 五大因子

| 因子 | 权重 | 说明 |
|------|------|------|
| **情绪归一化** | 35% | `SentimentLevel / 5.0`，5 档情绪映射到 [0.2, 1.0] |
| **催化剂权重** | 25% | 各 `CatalystType` 权重均值（政策/并购=1.0，热点/评级=0.4） |
| **置信度** | 25% | 催化剂时效衰减 x 多催化剂加成（2 类及以上 x1.3） |
| **策略标签** | 15% | 回调低吸/催化剂博弈 +1，突破追击 -1，其余中性 |
| **熔断规则** | --- | 前日涨幅 >= 9.5% -> 强制 T3 上限，不参与公式计算 |

### 三级分层

| Tier | 标签 | 阈值 | 含义 |
|------|------|------|------|
| **T1** | 强力看好 | `tier_score >= 0.70` | 重点关注，高胜率标的 |
| **T2** | 值得关注 | `tier_score >= 0.40` | 可纳入观察池 |
| **T3** | 继续跟踪 | `tier_score >= 0.10` | 低优先级，仅跟踪 |

### 板块集中度限制

- **上限**：单一板块占比不超过 `30%`（`SECTOR_CONCENTRATION_CAP = 0.30`）
- **降权机制**：超限板块中 tier_score 最低的 1-2 只标的自动降一级
- **过热警告**：`OverheatWarning` 数据结构记录板块名称、数量、比例、受影响代码

### 六种策略标签

| 标签 | 英文 | Tier 调整 | 触发条件 |
|------|------|-----------|----------|
| 回调低吸 | `PULLBACK_BUY` | +1 | 跌超 5% + 业绩/并购/合作催化 |
| 催化剂博弈 | `CATALYST_PLAY` | +1 | 默认标签，有利好催化 |
| 趋势持有 | `MOMENTUM` | 0（中性） | 热点/机构评级类催化 |
| 突破追击 | `BREAKOUT_CHASE` | -1 | 前日涨停 (>=9.5%) |
| 超跌反弹 | `RECOVERY` | 0（中性） | 跌超 3% 但催化剂一般 |

---

## 五档情绪体系

| 等级 | 标签 | 含义 | 选股信号 |
|------|------|------|----------|
| 1 | 强烈看淡 | 重大利空、业绩暴跌、黑天鹅 | 规避 |
| 2 | 看淡 | 负面消息、行业景气下降 | 谨慎 |
| 3 | 中性 | 一般性信息、无明显利好利空 | 观望 |
| 4 | 看好 | 正面消息、业绩增长、订单落地 | 关注 |
| 5 | 强烈看好 | 重大利好、政策支持、技术突破、并购重组 | 重点关注 |

---

## 九类利好催化剂

| 分类 ID | 名称 | 权重 | 优先级 | 典型关键词 |
|---------|------|------|--------|-----------|
| `TYPE_POLICY` | 政策利好 | **1.0** | ★★★★★ | 政策支持、补贴、发改委、工信部、顶层文件 |
| `TYPE_MA` | 并购重组 | **1.0** | ★★★★★ | 并购、重组、收购、资产注入、定增 |
| `TYPE_EARNINGS` | 业绩超预期 | 0.8 | ★★★★ | 业绩增长、净利润、营收超预期、年报、季报 |
| `TYPE_TECH` | 技术突破 | 0.8 | ★★★★ | 突破、研发成功、新品发布、专利、独家技术 |
| `TYPE_COOP` | 重要合作 | 0.7 | ★★★★ | 合作、签约、订单、战略伙伴、独家供应 |
| `TYPE_EQUITY` | 股权变动 | 0.6 | ★★★ | 增持、回购、举牌、大股东增减持 |
| `TYPE_INDUSTRY` | 行业景气 | 0.5 | ★★★ | 行业复苏、景气上行、需求增长、价格上涨 |
| `TYPE_HOT` | 概念热点 | 0.4 | ★★★ | AI、人工智能、新能源、半导体、机器人 |
| `TYPE_RATING` | 机构评级 | 0.4 | ★★★ | 买入、增持、强烈推荐、上调评级、目标价 |

### 催化剂时效衰减

| 时间范围 | 衰减系数 | 含义 |
|----------|----------|------|
| 0 - 24 小时 | **1.00** | 最新消息，无衰减 |
| 24 - 72 小时 | **0.50** | 次新消息，半衰 |
| > 72 小时 | **0.25** | 陈旧消息，大幅衰减 |

---

## 执行流程

```
Step 0: 解析用户意图
   |
   v
Step 1: 新闻检索 (MCP 多引擎搜索)
   |
   v
Step 2: 股票识别与标准化 (代码 + 名称)
   |
   v
Step 3: 实时行情校验 (Python data_sources 模块)
   |      Fallback 链: 雪球 -> 腾讯 -> 新浪 -> 东方财富 -> TuShare Free -> TuShare Pro Daily
   |
   v
Step 4: Tier 分配引擎 + 板块集中度检查
   |      4a. 单股评分 (5因子公式)
   |      4b. 板块集中度检查
   |      4c. 集中度降权
   |      4d. 按 tier_score 降序排序输出
   |
   v
Step 5: HTML 报告生成 + 自动打开 [强制门禁]
         - 深色交易台风格 (底色 #0a0e14, 卡片 #181d27)
         - 三级分层表格 (T1/T2/T3)
         - 概览指标卡 + 明日预判 + 策略建议 + 免责声明
         - 自动写入桌面并用浏览器打开
```

### 行情 Fallback 链详解

```
xueqiu (实时, 4次重试)
  -> tencent qt.gtimg.cn (实时, GBK解码)
    -> sina hq.sinajs.cn (实时, GBK解码)
      -> eastmoney push2 (实时)
        -> tushare get_realtime_quotes (半实时)
          -> tushare_pro_daily (EOD 兜底)
            -> pending (全部失败, 标记待确认)
```

- **交易时段** (9:30-11:30, 13:00-15:00): 优先实时爬虫
- **大单量** (>5 只): 推荐 `tushare_pro_daily_batch()`，更快更稳定
- **纯实时场景**: 使用 `get_intraday_quote()` 跳过 EOD 兜底

### HTML 报告强制门禁 (GATE RULE)

> 无论用户参数是"验证"、"查询"、"分析"、"筛选"还是其他变体，只要 Step 0-4 执行了（识别到股票代码、获取了行情数据），Step 5 就是**强制门禁**，不可跳过、不可降级。

**报告规范：**
- 文件名格式：`新闻选股日报_YYYYMMDD.html`
- 保存路径：`C:/Users/Administrator/Desktop/`（可通过 `NEWS_STOCK_REPORT_DIR` 环境变量配置）
- 自动打开命令：`start "" "路径"`
- 风格：深色交易台 / 机构研报风格，纯 HTML+CSS，无外部依赖
- 颜色规范：红涨 (`#f85149`) / 绿跌 (`#3fb950`) / 金色代码 (`#d2991d`)

---

## 输出格式

### 标准 Markdown 主表

```markdown
## 新闻选股结果

**筛选条件**：{条件描述}
**结果数量**：{N} 只

### T1 强烈看好（重点关注）
| 股票 | 代码 | 板块 | 利好类型 | Tier分 | 策略标签 | 新闻摘要 | 行情 |
|------|------|------|----------|--------|----------|----------|------|
| 贵州茅台 | 600519 | 白酒 | 政策利好 | 0.82 | 催化剂博弈 | ... | +2.3% |

### T2 值得关注
| 股票 | 代码 | 板块 | 利好类型 | Tier分 | 策略标签 | 新闻摘要 | 行情 |
|------|------|------|----------|--------|----------|----------|------|
| ...

### T3 继续跟踪
| 股票 | 代码 | 板块 | 利好类型 | Tier分 | 策略标签 | 新闻摘要 | 行情 |
|------|------|------|----------|--------|----------|----------|------|
| ...
```

### HTML 日报结构

```
[Header] 标题徽章 + 日期 + 数据来源
[Overview] 4-5 个概览指标卡（标的总数、T1数量、板块集中度、市场情绪）
[Tier 1] 强力看好 - 股票表格（代码/名称/板块/催化剂/Tier分/策略/行情）
[Tier 2] 值得关注 - 股票表格
[Tier 3] 继续跟踪 - 股票表格（含涨停熔断标记）
[Momentum] 持续主题 / 板块联动（如有）
[Outlook] 4-6 个明日预判卡片 + 策略建议
[Footer] 免责声明
```

---

## 条件增强模块

以下增强模块有明确触发条件，不满足则不执行，无可执行步骤时不生成空 Section：

| 增强模块 | 触发条件 | 输入 | 输出 |
|----------|----------|------|------|
| **板块联动补涨** | 同板块 >= 2 只龙头涨停，其余涨幅 < 2% | 龙头列表 + 同板块全量 | `catchup_opportunities[]` |
| **社交情绪加权** | 结果 < 5 只或用户显式要求 | 股票代码列表 | `hot_trend_overlay` |
| **板块趋势归因** | `overheat_warnings` 非空或用户问"主线/板块" | 板块名称 | `sector_trend_context` |

---

## 安装与前置条件

### 环境要求

- Python >= 3.10
- Claude Code（作为 Skill 运行）

### MCP 工具依赖

| MCP 工具 | 用途 |
|----------|------|
| `mcp__mcp-router__search` | 多引擎新闻搜索（Bing, LinuxDo, 掘金等） |
| `mcp__mcp-router__web_search_exa` | Exa 语义搜索 |
| `mcp__mcp-router__fetchWebContent` | 网页正文提取 |
| `mcp__mcp-router__search_stock` | 股票代码/名称查询 |
| `mcp__mcp-router__get_kline` | 个股 K 线数据 |
| `mcp__mcp-router__get_kline_history` | 历史 K 线数据 |
| `mcp__mcp-router__get_index` | 指数 K 线数据 |
| `mcp__mcp-router__get_index_all` | 指数+成分股 K 线 |
| `mcp__mcp-router__get_market_stats` | 市场统计信息 |

> 注意：MCP 行情接口 (`get_quote` / `get_batch_quote` / `get_stock_info`) 已被标记为废弃，所有实时行情统一走 Python `data_sources.py` 模块。

### Python 包依赖

```bash
pip install tushare akshare requests
```

### 环境变量

| 变量 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `TUSHARE_TOKEN` | 推荐 | TuShare Pro API Token | 空（TuShare Pro 层自动降级） |
| `TUSHARE_HTTP_URL` | 推荐 | TuShare Pro HTTP 接口地址 | 空（TuShare Pro 层自动降级） |
| `NEWS_STOCK_REPORT_DIR` | 否 | HTML 报告输出目录 | `~/新闻选股报告/` |
| `NEWS_STOCK_AUTO_OPEN` | 否 | 是否自动打开浏览器 | `1`（开启） |

---

## 使用示例

| 用户输入 | 触发动作 |
|----------|----------|
| "找出今天有政策利好新闻的股票" | 搜索"政策利好 A股"，Tier 评分后输出结构化结果 |
| "分析业绩超预期的个股" | 搜索"业绩超预期 A股"，每行必含代码 |
| "搜索 AI 相关的正面新闻，看哪些股票被提及" | 搜索"AI 利好"新闻，识别标的 |
| "今天有哪些并购重组公告？" | 搜索"并购重组 A股公告"，标注 CatalystType.MA |
| "哪些股票有技术突破的新闻？" | 搜索"技术突破 研发成功"新闻 |
| "龙头股涨停了，同板块还有什么没涨的？" | 识别龙头 -> 触发板块联动补涨增强 |
| "AI 板块大涨，哪些还没涨的股票可以关注？" | 搜索 AI 板块涨幅落后的补涨股 |
| "最近市场有什么热点？" | 条件触发 -- 热点扫描 + 条件选股 |
| "半导体板块怎么样？" | 条件触发 -- 板块趋势归因 |

### 触发关键词

**必定触发：** `新闻选股` `利好选股` `哪些股票有.*新闻` `热点对应个股` `政策利好股票` `并购重组.*股票`

**条件触发：** `市场热点` `情绪分析` `板块怎么样` `最近什么消息多`

**排除（不触发）：** `单股行情查询` `个股估值` `龙虎榜席位` `杀猪盘` `纯宏观解读`

---

## 文件结构

```
news-stock-selector/
|-- .gitignore
|-- .git/                        # Git 仓库
|-- .meta/
|   |-- feedback.jsonl           # 次日验证反馈记录
|-- README.md                    # 本文件
|-- skill.md                     # Skill 入口契约
|-- config.py                    # 外置配置模块
|-- contracts.py                 # 数据契约与 Tier 引擎
|-- data_sources.py              # 多源行情 + 社交热榜
|-- compute_tiers.py             # Tier 独立计算脚本
|-- task_plan.md                 # 开发任务计划
|-- progress.md                  # 开发进度记录
|-- tests/
|   |-- __init__.py
|   |-- test_contracts.py        # contracts 单元测试
|   |-- test_data_sources.py     # 数据源单元测试
```

---

## 完成前自检清单

在执行完 Step 0-4 后，必须逐项确认以下检查，**任何一项未通过即补全，不允许跳过**：

| # | 检查项 | 通过条件 |
|---|--------|----------|
| 1 | HTML 报告已写入 | `新闻选股日报_YYYYMMDD.html` 文件存在且非空 |
| 2 | 报告数据真实 | 所有数据来自 `data_sources.py` 实际输出，非模板占位符 |
| 3 | 浏览器已打开 | 已执行 `start` 命令 |
| 4 | 报告结构完整 | 概览卡 + 分层表格 + 预判卡 + 策略建议 + 免责声明 |
| 5 | Tier 引擎已执行 | 每只股票的 `tier_score`, `assigned_tier`, `strategy_tag` 已填充 |
| 6 | 板块集中度已检查 | `overheat_warnings` 已填充，超限板块已降权 |
| 7 | TuShare 已配置 | `TUSHARE_TOKEN` 和 `TUSHARE_HTTP_URL` 已设置或确认跳过 |

---

## 次日验证反馈环 (v3.6)

每次运行后，将选股结果写入 `.meta/feedback.jsonl`：

```jsonl
{"date":"20260602","code":"000859","assigned_tier":1,"tier_score":0.72}
{"date":"20260602","code":"002156","assigned_tier":2,"tier_score":0.55}
```

下次运行时读取该文件，计算 Tier 分配准确率，用于后续权重调优。此步骤失败不影响主链。

---

## 搜索策略参考

| 利好类型 | 推荐搜索关键词 |
|----------|---------------|
| 业绩超预期 | "业绩预增" "年报业绩" "净利润增长" "营收超预期" |
| 政策利好 | "政策支持" "补贴政策" "顶层设计" "工信部" "发改委" |
| 并购重组 | "并购" "重大资产重组" "收购" "定增收购" |
| 技术突破 | "技术突破" "研发成功" "新品发布" "专利授权" |
| 重要合作 | "战略合作" "签订合同" "订单落地" "独家供应" |
| 行业景气 | "行业复苏" "景气上行" "价格上涨" "需求旺盛" |
| 股权变动 | "增持" "回购" "股东增持" "股权激励" |
| 概念热点 | "AI概念" "新能源" "半导体" "机器人" "低空经济" |
| 机构评级 | "买入评级" "强烈推荐" "上调目标价" "增持" |

---

## 相关技能

| 技能 | 关系 |
|------|------|
| [ftshare-market-data-main](https://github.com/AXBIAO/ftshare-market-data-main) | 底层金融数据接口（行情 / K线 / 指数 / ETF / 港股） |
| [stock-screener](https://github.com/AXBIAO/stock-screener) | 量化筛选器，按条件筛选全市场标的 |
| [lhb-analyzer](https://github.com/AXBIAO/lhb-analyzer) | 龙虎榜深度分析，识别游资席位与机构博弈 |
| [trap-detector](https://github.com/AXBIAO/trap-detector) | 杀猪盘检测，8 信号扫描 + 风险评级 |
| [deep-analysis](https://github.com/AXBIAO/deep-analysis) | 个股深度分析（22维数据 + DCF + 50人评审团） |

---

## 版本历史

### v3.6.0 (Current)

**首次公开发布**

- 显式化 Tier 分配算法（5 因子加权公式）
- 催化剂时效衰减机制（0-24h / 24-72h / >72h 三档）
- 板块集中度上限 (30%) + 自动降权
- 涨停次日熔断规则（>=9.5% 强制 T3）
- 策略标签自动分类（5 种策略类型）
- 次日验证反馈环（feedback.jsonl）
- 增强模块按需条件触发（不满足不执行，无空 Step）
- Python 多源行情 Fallback 链（雪球 / 腾讯 / 新浪 / 东财 / TuShare Free / TuShare Pro）
- HTML 报告强制门禁 + 完成前自检清单

---

## 免责声明

> **投资有风险，选股需谨慎。**
>
> 本工具为 AI 辅助决策工具，所有输出结果仅供参考，不构成任何投资建议。Tier 评分和选股结果基于新闻情绪和量化公式计算，不代表未来股价表现。
>
> 使用者应独立判断并承担投资风险。作者不对因使用本工具产生的任何投资损失承担责任。
>
> 历史表现不代表未来收益。市场有风险，入市须谨慎。

---

## License

MIT License. See [LICENSE](LICENSE) for details.

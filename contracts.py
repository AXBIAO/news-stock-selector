# contracts.py — news-stock-selector 统一数据契约
# skill.md 与 data_sources.py 共享的唯一真源。

from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Any, Optional


class FieldStatus(str, Enum):
    """统一字段状态值"""
    CONFIRMED = "confirmed"
    PENDING = "pending_confirmation"
    NOT_AVAILABLE = "not_available"
    SKIPPED = "skipped"
    FAILED = "failed"


class CatalystType(str, Enum):
    """9类利好分类"""
    POLICY = "TYPE_POLICY"
    EARNINGS = "TYPE_EARNINGS"
    MA = "TYPE_MA"
    TECH = "TYPE_TECH"
    COOP = "TYPE_COOP"
    INDUSTRY = "TYPE_INDUSTRY"
    EQUITY = "TYPE_EQUITY"
    HOT = "TYPE_HOT"
    RATING = "TYPE_RATING"


class SentimentLevel(int, Enum):
    """5档情绪"""
    STRONG_BEARISH = 1
    BEARISH = 2
    NEUTRAL = 3
    BULLISH = 4
    STRONG_BULLISH = 5


class StrategyTag(str, Enum):
    """策略标签 — 影响 tier 调整方向"""
    PULLBACK_BUY = "PULLBACK_BUY"         # 回调低吸 (+1 tier)
    CATALYST_PLAY = "CATALYST_PLAY"       # 催化剂博弈 (+1 tier)
    MOMENTUM = "MOMENTUM"                 # 趋势持有 (中性)
    BREAKOUT_CHASE = "BREAKOUT_CHASE"     # 突破追击 (-1 tier)
    RECOVERY = "RECOVERY"                 # 超跌反弹 (中性)
    NEAR_LIMIT_UP = "NEAR_LIMIT_UP"       # v5.4: 近涨停(≥8%)需谨慎 (-1 tier)


class TierLevel(IntEnum):
    """三层分级"""
    T1_STRONG_BUY = 1
    T2_WATCH = 2
    T3_TRACK = 3


# ── 催化剂权重 ──
CATALYST_WEIGHTS: dict[CatalystType, float] = {
    CatalystType.POLICY:    1.0,   # 政策利好
    CatalystType.MA:        1.0,   # 并购重组
    CatalystType.EARNINGS:  0.8,   # 业绩超预期
    CatalystType.TECH:      0.8,   # 技术突破
    CatalystType.COOP:      0.7,   # 重要合作
    CatalystType.EQUITY:    0.6,   # 股权变动
    CatalystType.INDUSTRY:  0.5,   # 行业景气
    CatalystType.HOT:       0.4,   # 概念热点
    CatalystType.RATING:    0.4,   # 机构评级
}

# ── 策略标签 tier 调整量 ──
STRATEGY_TIER_ADJUST: dict[StrategyTag, int] = {
    StrategyTag.PULLBACK_BUY:   +1,
    StrategyTag.CATALYST_PLAY:  +1,
    StrategyTag.MOMENTUM:        0,
    StrategyTag.BREAKOUT_CHASE: -1,
    StrategyTag.RECOVERY:        0,
    StrategyTag.NEAR_LIMIT_UP:  -1,  # v5.4: 近涨停谨慎
}

# ── Tier 分配阈值 ──
TIER_THRESHOLDS: dict[TierLevel, float] = {
    TierLevel.T1_STRONG_BUY: 0.70,
    TierLevel.T2_WATCH:      0.40,
    TierLevel.T3_TRACK:      0.10,
}

# ── 板块集中度上限 ──
SECTOR_CONCENTRATION_CAP = 0.30  # 单一板块占比上限

# ── 催化剂时效衰减（桶边界：≤24h → 1.0, 24-72h → 0.5, >72h → 0.25） ──
CATALYST_AGE_DECAY: dict[float, float] = {
    0.0:  1.00,   # 0-24h 无衰减
    24.0: 0.50,   # 24-72h 衰减至 50%
    72.0: 0.25,   # >72h 衰减至 25%
}

# ── 涨停次日阈值 ──
LIMIT_UP_THRESHOLD = 9.5  # 涨幅≥9.5%视为涨停（主板通用，科创板/创业板需用 is_real_limit_up）

# ── v5.4: 催化剂确定性权重 ──
# 不同催化剂类型的确定性不同：业绩预增确定性远高于概念热点
CATALYST_CERTAINTY: dict[CatalystType, float] = {
    CatalystType.EARNINGS:  1.0,   # 业绩超预期 — 最高确定性
    CatalystType.POLICY:    0.8,   # 政策利好 — 高确定性但落地有延迟
    CatalystType.MA:        0.8,   # 并购重组 — 高确定性但审批风险
    CatalystType.TECH:      0.7,   # 技术突破 — 中高确定性
    CatalystType.COOP:      0.7,   # 重要合作 — 中高确定性
    CatalystType.INDUSTRY:  0.5,   # 行业景气 — 中期趋势
    CatalystType.EQUITY:    0.5,   # 股权变动 — 中期信号
    CatalystType.HOT:       0.3,   # 概念热点 — 低确定性，情绪驱动
    CatalystType.RATING:    0.3,   # 机构评级 — 低确定性，参考价值有限
}

# ── v5.4: 板块狂热熔断 ──
SECTOR_FRENZY_THRESHOLD = 20   # 板块涨停数≥20触发狂热熔断
SECTOR_FRENZY_TIER_CAP = TierLevel.T2_WATCH  # 狂热板块所有标的强制上限 T2

# ── v5.4: 近涨停降权 ──
NEAR_LIMIT_UP_THRESHOLD = 8.0  # 涨幅≥8%但未涨停
NEAR_LIMIT_UP_PENALTY = 0.80   # tier_score × 0.80

# ── v5.4: 市场谨慎折扣 ──
MARKET_CAUTION_DISCOUNT = 0.85  # 板块过热时全局 tier_score 折扣

# ── v5.4: 独立逻辑加分 ──
INDEPENDENT_CATALYST_BONUS = 0.08  # 独立于主线的催化剂额外加分


def is_real_limit_up(code: str, chg_pct: float) -> bool:
    """板别感知的涨停检测。

    不同板块涨停幅度不同：
    - 主板(60xxxx/00xxxx): 10%
    - 科创板(688xxx): 20%
    - 创业板(300xxx/301xxx): 20%
    - 北交所(920xxx/83xxxx/87xxxx): 30%

    容差 0.5% 以兼容四舍五入。
    """
    if chg_pct is None:
        return False
    code_str = str(code)
    if code_str[:3] in ("920", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873"):
        return chg_pct >= 29.5  # 北交所 30%
    if code_str[:3] in ("300", "301", "688"):
        return chg_pct >= 19.5  # 科创板/创业板 20%
    return chg_pct >= 9.5  # 主板 10%


# 注意：以下 dataclass 故意不设 frozen=True。
# 这些对象在 skill 执行过程中逐步填充（如逐只股票追加 news_items、
# 逐层 fallback 更新 attempted_sources），使用可变对象更自然。
# 外部使用者不应直接修改这些字段，应通过 StockResult 的构造和方法来填充。
@dataclass
class FallbackRecord:
    """单次数据获取的 fallback 记录"""
    provider_label: str  # 对应 config.PROVIDER_LABELS
    attempted_sources: list[str] = field(default_factory=list)
    final_source: str = "pending"
    failure_reason: Optional[str] = None


@dataclass
class QuoteSnapshot:
    """统一的实时行情快照"""
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    source: str = "pending"
    status: FieldStatus = FieldStatus.PENDING
    fallback: FallbackRecord = field(default_factory=lambda: FallbackRecord(provider_label="pending"))


@dataclass
class ValuationData:
    """估值数据 — PE/PB/市值/换手率"""
    pe_ttm: Optional[float] = None          # 市盈率(TTM)
    pb: Optional[float] = None              # 市净率
    market_cap: Optional[float] = None      # 总市值(亿元)
    circ_market_cap: Optional[float] = None # 流通市值(亿元)
    turnover_rate: Optional[float] = None   # 换手率(%)


@dataclass
class StockResult:
    """统一的单只股票结果对象"""
    name: Optional[str] = None
    code: Optional[str] = None
    code_status: FieldStatus = FieldStatus.PENDING
    news_items: list[dict[str, Any]] = field(default_factory=list)
    sentiment_score: SentimentLevel = SentimentLevel.NEUTRAL
    catalyst_types: list[CatalystType] = field(default_factory=list)
    quote: QuoteSnapshot = field(default_factory=QuoteSnapshot)
    quote_status: FieldStatus = FieldStatus.PENDING
    quote_source: Optional[str] = None
    sector: Optional[str] = None
    sector_status: FieldStatus = FieldStatus.SKIPPED
    confidence: float = 0.0
    failure_notes: list[str] = field(default_factory=list)
    # v3.6: 新增字段
    strategy_tag: Optional["StrategyTag"] = None
    catalyst_age_hours: float = 0.0      # 最新催化剂距今小时数
    prior_day_limit_up: bool = False     # 前一日是否涨停
    multi_catalyst_bonus: bool = False   # 是否双催化加成
    tier_score: float = 0.0              # 分配算法得分
    assigned_tier: Optional["TierLevel"] = None
    # v5.2: 估值数据
    valuation: Optional["ValuationData"] = None


@dataclass
class OverheatWarning:
    """板块过热警告"""
    sector: str
    count: int
    ratio: float
    affected_codes: list[str] = field(default_factory=list)


# ── v3.7: 美股→A股映射数据结构 ──

@dataclass
class USGainerMapping:
    """单只美股涨幅冠军的 A 股映射"""
    rank: int                                    # 涨幅排名 (1-5)
    ticker: str                                  # 美股代码 (e.g. MRVL)
    company: str                                 # 公司名称
    change_pct: float                            # 涨幅百分比
    close_price: float                           # 收盘价 (USD)
    driver: str                                  # 上涨核心驱动
    a_share_theme: str                           # 映射 A 股主题板块
    suggested_a_stocks: list[str] = field(default_factory=list)  # 建议关注的 A 股代码列表
    confirming_news: list[str] = field(default_factory=list)     # 国内交叉确认的利好新闻摘要


# 美股主题 → A 股板块 + 典型标的映射表（v3.7）
US_THEME_TO_A_SHARE: dict[str, dict] = {
    "AI芯片/数据中心网络": {
        "sector": "AI芯片 / 半导体",
        "stocks": ["688256", "688981", "603986", "688008"],
        "search_keywords": ["AI芯片", "算力芯片", "GPU", "数据中心芯片"],
    },
    "光互联/光模块/CPO": {
        "sector": "光通信 / 光模块",
        "stocks": ["300308", "300502", "002281", "601869"],
        "search_keywords": ["光模块", "光通信", "800G", "1.6T", "CPO", "光互联"],
    },
    "AI服务器/算力基础设施": {
        "sector": "AI服务器 / 算力",
        "stocks": ["000977", "603019", "002475"],
        "search_keywords": ["AI服务器", "算力", "HPC", "超算"],
    },
    "半导体设备/制造": {
        "sector": "半导体设备 / 材料",
        "stocks": ["002371", "688012", "688536", "002129"],
        "search_keywords": ["半导体设备", "晶圆", "刻蚀", "封测"],
    },
    "先进封装/HBM": {
        "sector": "先进封装 / 存储",
        "stocks": ["002156", "688525", "002185"],
        "search_keywords": ["先进封装", "HBM", "Chiplet", "存储芯片"],
    },
    "光纤光缆/光器件": {
        "sector": "光纤光缆 / 光器件",
        "stocks": ["601869", "600585", "600522"],
        "search_keywords": ["光纤", "光缆", "光器件", "数据中心光纤"],
    },
    "新能源汽车/自动驾驶": {
        "sector": "新能源汽车 / 智驾",
        "stocks": ["601689", "002920", "300750", "002594"],
        "search_keywords": ["新能源车", "自动驾驶", "域控制器", "智能驾驶"],
    },
    "商业航天/卫星": {
        "sector": "商业航天 / 卫星",
        "stocks": ["600118", "600879", "603698"],
        "search_keywords": ["商业航天", "卫星", "SpaceX", "火箭"],
    },
    "云计算/SaaS": {
        "sector": "云计算 / 软件",
        "stocks": ["600588", "688111", "002410"],
        "search_keywords": ["云计算", "SaaS", "企业软件", "ERP"],
    },
    "机器人/自动化": {
        "sector": "机器人 / 自动化",
        "stocks": ["300124", "002747", "688017"],
        "search_keywords": ["机器人", "人形机器人", "自动化", "伺服"],
    },
    "消费电子/PC": {
        "sector": "消费电子 / PC",
        "stocks": ["002475", "002241", "002938"],
        "search_keywords": ["消费电子", "PC", "笔电", "AI PC"],
    },
    "医药生物/创新药": {
        "sector": "医药生物",
        "stocks": ["600276", "300760", "603259"],
        "search_keywords": ["创新药", "医药", "CXO", "生物医药"],
    },
}


@dataclass
class SelectionResult:
    """统一的选股结果容器"""
    query: str = ""
    filter_conditions: str = ""
    stock_count: int = 0
    stocks: list[StockResult] = field(default_factory=list)
    sector_trend_context: Optional[str] = None
    catchup_opportunities: list[dict[str, Any]] = field(default_factory=list)
    hot_trend_overlay: Optional[dict] = None
    # v3.6: 板块过热警告列表
    overheat_warnings: list[OverheatWarning] = field(default_factory=list)
    # v3.7: 美股涨幅榜 → A股映射
    us_gainers: list[USGainerMapping] = field(default_factory=list)
    # v4.0: 产业链 BOM 拆解 + 三高分析
    supply_chain_analysis: Optional["SupplyChainAnalysis"] = None
    feedback_records: list[dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# v4.0: 产业链 BOM 拆解 + 三高筛选 数据结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class SupplyChainNode:
    """产业链单个环节"""
    name: str                                    # 环节名称（如"光芯片"）
    level: str                                   # "上游" / "中游" / "下游"
    description: str = ""                        # 环节描述
    key_components: list[str] = field(default_factory=list)      # 关键组成部分
    upstream_of: list[str] = field(default_factory=list)         # 供给哪些下游环节
    downstream_of: list[str] = field(default_factory=list)       # 依赖哪些上游环节
    # 三高原始数据
    growth_rate: Optional[float] = None          # 年行业增速 (%)
    gross_margin_range: Optional[str] = None     # 典型毛利率区间
    barrier_level: Optional[str] = None          # 壁垒等级: "极高"/"高"/"中"/"低"
    barrier_reasons: list[str] = field(default_factory=list)     # 壁垒原因
    supply_demand_gap: Optional[str] = None      # 供需状态: "严重失衡"/"偏紧"/"平衡"/"过剩"
    # A股映射
    a_share_leaders: list[str] = field(default_factory=list)     # 龙头代码
    a_share_participants: list[str] = field(default_factory=list)  # 其他参与者
    leader_names: list[str] = field(default_factory=list)        # 龙头名称
    # 三高评分（填充后）
    three_high_score: Optional["ThreeHighScore"] = None


@dataclass
class ThreeHighScore:
    """三高评分"""
    growth_score: float = 0.0        # 0-10, 高增长评分
    profit_score: float = 0.0        # 0-10, 高利润评分
    barrier_score: float = 0.0       # 0-10, 高壁垒评分
    composite_score: float = 0.0     # 0-10, 综合 = growth×0.4 + profit×0.3 + barrier×0.3
    is_three_high: bool = False      # 是否满足三高标准（composite ≥ 7.0）
    evidence: list[str] = field(default_factory=list)  # 评分依据


@dataclass
class SupplyChainAnalysis:
    """产业链分析完整结果"""
    industry: str = ""                             # 分析的行业/主题
    nodes: list[SupplyChainNode] = field(default_factory=list)   # 产业链各环节
    top_segment: Optional[str] = None              # 最优环节名称
    top_segment_leaders: list[str] = field(default_factory=list) # 最优环节龙头代码
    three_high_nodes: list[str] = field(default_factory=list)    # 满足三高的环节名称
    analysis_summary: str = ""                     # 分析摘要（用于报告）
    analysis_timestamp: str = ""
    source: str = "ai-decomposition"


# 三高评分权重
THREE_HIGH_WEIGHTS = {
    "growth": 0.4,    # 高增长权重
    "profit": 0.3,    # 高利润权重
    "barrier": 0.3,   # 高壁垒权重
}

# 三高综合达标线
THREE_HIGH_THRESHOLD = 7.0  # composite ≥ 7.0 视为"三高环节"


# ═══════════════════════════════════════════════════════════════
# v3.6: Tier 分配引擎与辅助函数
# ═══════════════════════════════════════════════════════════════

def compute_catalyst_confidence(catalyst_types: list[CatalystType], age_hours: float, multi_catalyst: bool) -> float:
    """根据催化剂类型、时效、数量计算置信度 [0.0, 1.0]。

    公式 (v5.4): base = mean(catalyst_weights) × mean(catalyst_certainty) × decay × multi_bonus
    新增 certainty 因子区分业绩催化(确定性高)与概念热点(确定性低)。
    """
    if not catalyst_types:
        return 0.0
    base = sum(CATALYST_WEIGHTS.get(ct, 0.4) for ct in catalyst_types) / len(catalyst_types)
    certainty = sum(CATALYST_CERTAINTY.get(ct, 0.4) for ct in catalyst_types) / len(catalyst_types)
    decay = _compute_recency_decay(age_hours)
    bonus = 1.3 if multi_catalyst else 1.0
    return round(min(base * certainty * decay * bonus, 1.0), 4)


def compute_tier(
    sentiment_score: SentimentLevel,
    catalyst_types: list[CatalystType],
    confidence: float,
    strategy_tag: Optional[StrategyTag] = None,
    prior_day_limit_up: bool = False,
    three_high_bonus: float = 0.0,
    near_limit_up: bool = False,
    sector_frenzy: bool = False,
    market_caution: bool = False,
    independent_catalyst: bool = False,
) -> tuple[TierLevel, float]:
    """显式化 tier 分配算法 (v5.4)。

    公式: tier_score = sentiment_norm × 0.30 + catalyst_norm × 0.20
                      + confidence × 0.20 + strategy_norm × 0.10
                      + three_high_norm × 0.20
    其中 sentiment_norm = sentiment / 5.0, catalyst_norm = mean(weights),
    strategy_adj 来自 STRATEGY_TIER_ADJUST, three_high_norm = three_high_bonus / 10.0

    v5.4 后处理规则（按优先级）:
    1. prior_day_limit_up   → 强制 T3 (涨停次日分化风险)
    2. sector_frenzy        → 强制上限 T2 (板块狂热，全线降级)
    3. near_limit_up        → score × 0.80 (近涨停但未封板)
    4. market_caution       → score × 0.85 (板块过热全局折扣)
    5. independent_catalyst → score + 0.08 (独立逻辑，不与主线同涨跌)

    Returns: (assigned_tier, tier_score)
    """
    sentiment_norm = float(int(sentiment_score)) / 5.0
    cw = [CATALYST_WEIGHTS.get(ct, 0.4) for ct in catalyst_types]
    catalyst_norm = sum(cw) / len(cw) if cw else 0.0

    strategy_adj_raw = STRATEGY_TIER_ADJUST.get(strategy_tag, 0) if strategy_tag else 0
    strategy_norm = (strategy_adj_raw + 1) / 2.0  # map [-1, +1] → [0.0, 1.0]

    three_high_norm = three_high_bonus / 10.0   # map [0, 10] → [0.0, 1.0]

    score = round(
        sentiment_norm * 0.30 + catalyst_norm * 0.20 + confidence * 0.20
        + strategy_norm * 0.10 + three_high_norm * 0.20,
        4,
    )

    # ── v5.4 后处理规则（按优先级顺序） ──

    # Rule 1: 涨停次日 → 强制 T3（最严格的保护）
    if prior_day_limit_up and score > TIER_THRESHOLDS[TierLevel.T3_TRACK]:
        return TierLevel.T3_TRACK, score

    # Rule 2: 板块狂热 → 强制上限 T2（板块超20只涨停，全线降级）
    if sector_frenzy:
        capped_score = min(score, TIER_THRESHOLDS[TierLevel.T1_STRONG_BUY] - 0.01)
        score = round(capped_score, 4)

    # Rule 3: 近涨停未封板 → tier_score × 0.80
    if near_limit_up and not prior_day_limit_up:
        score = round(score * NEAR_LIMIT_UP_PENALTY, 4)

    # Rule 4: 板块过热全局折扣 → tier_score × 0.85
    if market_caution:
        score = round(score * MARKET_CAUTION_DISCOUNT, 4)

    # Rule 5: 独立逻辑加分 → tier_score + 0.08
    if independent_catalyst:
        score = round(min(score + INDEPENDENT_CATALYST_BONUS, 1.0), 4)

    # ── Tier 分配 ──
    if score >= TIER_THRESHOLDS[TierLevel.T1_STRONG_BUY]:
        return TierLevel.T1_STRONG_BUY, score
    elif score >= TIER_THRESHOLDS[TierLevel.T2_WATCH]:
        return TierLevel.T2_WATCH, score
    else:
        return TierLevel.T3_TRACK, score


def compute_tier_for_school(
    sentiment_score: SentimentLevel,
    catalyst_types: list[CatalystType],
    confidence: float,
    strategy_tag: Optional[StrategyTag] = None,
    prior_day_limit_up: bool = False,
    three_high_bonus: float = 0.0,
    school: Optional[str] = None,   # "value" / "growth" / "event" / etc.
    near_limit_up: bool = False,
    sector_frenzy: bool = False,
    market_caution: bool = False,
    independent_catalyst: bool = False,
) -> tuple[TierLevel, float]:
    """流派感知的 tier 分配算法 (v5.4)。

    若 school 为 None 或无效，等价于 compute_tier() (事件驱动派默认)。
    不同流派使用不同的5因子权重 + 催化剂覆盖 + 策略加分 + v5.4 后处理规则。
    """
    if school is None:
        return compute_tier(sentiment_score, catalyst_types, confidence, strategy_tag,
                          prior_day_limit_up, three_high_bonus,
                          near_limit_up, sector_frenzy, market_caution, independent_catalyst)

    # 延迟导入避免循环依赖
    from schools import InvestmentSchool, get_school_config, resolve_school, get_catalyst_weight_for_school
    try:
        sch = resolve_school(school)
    except Exception:
        return compute_tier(sentiment_score, catalyst_types, confidence, strategy_tag,
                          prior_day_limit_up, three_high_bonus,
                          near_limit_up, sector_frenzy, market_caution, independent_catalyst)

    cfg = get_school_config(sch)

    # 1. 情绪归一化
    sentiment_norm = float(int(sentiment_score)) / 5.0

    # 2. 催化剂归一化 (使用流派覆盖权重)
    if catalyst_types:
        cw = [get_catalyst_weight_for_school(ct.value, sch, CATALYST_WEIGHTS.get(ct, 0.4)) for ct in catalyst_types]
        catalyst_norm = sum(cw) / len(cw) if cw else 0.0
    else:
        catalyst_norm = 0.0

    # 3. 策略归一化 (含流派加分)
    strategy_adj_raw = STRATEGY_TIER_ADJUST.get(strategy_tag, 0) if strategy_tag else 0
    # 兼容 Enum 和 string 类型的 strategy_tag
    if hasattr(strategy_tag, 'value'):
        strategy_str = strategy_tag.value
    else:
        strategy_str = str(strategy_tag) if strategy_tag else ""
    strategy_bonus = cfg.strategy_bonus.get(strategy_str, 0.0)
    strategy_norm = max(0.0, min(1.0, (strategy_adj_raw + strategy_bonus + 1) / 2.0))

    # 4. 三高归一化
    three_high_norm = three_high_bonus / 10.0  # [0, 10] → [0, 1]

    # 5. 流派权重加权
    score = round(
        sentiment_norm * cfg.w_sentiment
        + catalyst_norm * cfg.w_catalyst
        + confidence * cfg.w_confidence
        + strategy_norm * cfg.w_strategy
        + three_high_norm * cfg.w_three_high,
        4,
    )

    # ── v5.4 后处理规则 ──

    # Rule 1: 涨停次日熔断 (投机派豁免)
    if prior_day_limit_up and cfg.avoid_limit_up and score > TIER_THRESHOLDS[TierLevel.T3_TRACK]:
        return TierLevel.T3_TRACK, score

    # Rule 2: 板块狂热 → 强制上限 T2
    if sector_frenzy:
        capped_score = min(score, TIER_THRESHOLDS[TierLevel.T1_STRONG_BUY] - 0.01)
        score = round(capped_score, 4)

    # Rule 3: 近涨停降权
    if near_limit_up and not prior_day_limit_up:
        score = round(score * NEAR_LIMIT_UP_PENALTY, 4)

    # Rule 4: 市场谨慎折扣
    if market_caution:
        score = round(score * MARKET_CAUTION_DISCOUNT, 4)

    # Rule 5: 独立逻辑加分
    if independent_catalyst:
        score = round(min(score + INDEPENDENT_CATALYST_BONUS, 1.0), 4)

    # ── Tier 分配 ──
    if score >= TIER_THRESHOLDS[TierLevel.T1_STRONG_BUY]:
        return TierLevel.T1_STRONG_BUY, score
    elif score >= TIER_THRESHOLDS[TierLevel.T2_WATCH]:
        return TierLevel.T2_WATCH, score
    else:
        return TierLevel.T3_TRACK, score


def classify_strategy_tag(
    prior_change_pct: Optional[float],
    catalyst_type: Optional[CatalystType],
    sector_context: Optional[str] = None,
) -> StrategyTag:
    """根据前日涨跌幅和催化剂类型自动分类策略标签 (v5.4)。

    v5.4 新增: 涨幅≥8%但未涨停 → NEAR_LIMIT_UP (近涨停需谨慎)
    """
    if prior_change_pct is None:
        return StrategyTag.CATALYST_PLAY
    if prior_change_pct >= LIMIT_UP_THRESHOLD:
        return StrategyTag.BREAKOUT_CHASE
    if prior_change_pct >= NEAR_LIMIT_UP_THRESHOLD:
        return StrategyTag.NEAR_LIMIT_UP  # v5.4: 近涨停未封板
    if prior_change_pct <= -5.0 and catalyst_type in (CatalystType.EARNINGS, CatalystType.MA, CatalystType.COOP):
        return StrategyTag.PULLBACK_BUY
    if prior_change_pct <= -3.0:
        return StrategyTag.RECOVERY
    if catalyst_type in (CatalystType.HOT, CatalystType.RATING):
        return StrategyTag.MOMENTUM
    return StrategyTag.CATALYST_PLAY


def check_sector_concentration(stocks: list[StockResult]) -> list[OverheatWarning]:
    """检测板块集中度，超过 SECTOR_CONCENTRATION_CAP 则生成警告。"""
    from collections import Counter
    sectors = [s.sector for s in stocks if s.sector]
    if not sectors:
        return []
    total = len(sectors)
    counts = Counter(sectors)
    warnings: list[OverheatWarning] = []
    for sector, count in counts.items():
        ratio = count / total
        if ratio > SECTOR_CONCENTRATION_CAP:
            affected = [s.code for s in stocks if s.sector == sector and s.code]
            warnings.append(OverheatWarning(sector=sector, count=count, ratio=round(ratio, 3), affected_codes=affected))
    return warnings


# ── v5.4: 板块狂热检测 ──

def detect_sector_frenzy(
    stock_codes: list[str],
    all_market_data: dict,  # {code: StockSnapshot} 来自 TDX 全市场扫描
    frenzy_threshold: int = SECTOR_FRENZY_THRESHOLD,
) -> dict[str, bool]:
    """检测板块是否处于狂热状态（≥N只涨停）。

    扫描全市场涨停股 → 按板块聚合 → 板块涨停数超过阈值则标记为狂热。
    返回 {code: True/False}，仅对传入的 stock_codes 标记。

    用于 Step 8a 板块狂热熔断：狂热板块所有标的强制上限 T2。
    """
    if not all_market_data:
        return {code: False for code in stock_codes}

    # 统计每个板块的涨停数
    from collections import Counter
    sector_limit_up_count: Counter[str] = Counter()

    for code, snap in all_market_data.items():
        chg = getattr(snap, 'change_pct', 0) or 0
        if chg >= LIMIT_UP_THRESHOLD:
            sector = getattr(snap, 'sector', '') or ''
            if sector:
                sector_limit_up_count[sector] += 1

    # 标记狂热板块
    frenzy_sectors: set[str] = set()
    for sector, count in sector_limit_up_count.items():
        if count >= frenzy_threshold:
            frenzy_sectors.add(sector)

    # 为传入的股票标记
    result: dict[str, bool] = {}
    for code in stock_codes:
        snap = all_market_data.get(code)
        if snap:
            sector = getattr(snap, 'sector', '') or ''
            result[code] = sector in frenzy_sectors
        else:
            result[code] = False

    return result


def compute_independent_catalyst(
    stock_sector: Optional[str],
    stock_catalyst_types: list[CatalystType],
    dominant_sectors: set[str],
    dominant_catalyst: Optional[CatalystType] = None,
) -> bool:
    """判断股票是否具有独立催化剂（不与主线同涨跌）。

    条件（满足任一即可）:
    - 股票板块不在主导板块集合中
    - 催化剂类型与主导催化剂不同且确定性高（EARNINGS/MA/POLICY 且主导为 HOT）
    """
    if not stock_sector:
        return False

    # 板块独立
    if stock_sector not in dominant_sectors:
        return True

    # 催化剂独立：业绩/并购/政策 vs 概念热点主线
    if dominant_catalyst and dominant_catalyst == CatalystType.HOT:
        high_certainty = {CatalystType.EARNINGS, CatalystType.MA, CatalystType.POLICY}
        if any(ct in high_certainty for ct in stock_catalyst_types):
            return True

    return False


# ── v4.0: 三高评分计算 ──

def compute_three_high_score(
    growth_rate: Optional[float],
    gross_margin_str: Optional[str],
    barrier_level: Optional[str],
    supply_demand_gap: Optional[str],
) -> ThreeHighScore:
    """根据产业链环节数据计算三高评分 (0-10)。

    增长得分 (0-10):
      - 年增速 ≥ 30%: 9-10
      - 20-30%: 7-8
      - 10-20%: 5-6
      - 5-10%: 3-4
      - < 5%: 1-2

    利润得分 (0-10):
      - 毛利率 ≥ 50%: 9-10
      - 30-50%: 7-8
      - 15-30%: 5-6
      - 5-15%: 3-4
      - < 5%: 1-2
      若 gross_margin_str 为定性描述，按"极高/高/中/低"映射

    壁垒得分 (0-10):
      - 极高壁垒: 9-10
      - 高壁垒: 7-8
      - 中等壁垒: 4-6
      - 低壁垒: 1-3
      同时考虑供需缺口：严重失衡 +1，偏紧 +0.5
    """
    evidence: list[str] = []

    # ── 增长得分 ──
    growth_score = 3.0  # default mid-low
    if growth_rate is not None:
        if growth_rate >= 50:
            growth_score = 10.0
            evidence.append(f"年增速≥50%({growth_rate}%)")
        elif growth_rate >= 30:
            growth_score = 9.0
            evidence.append(f"年增速≥30%({growth_rate}%)")
        elif growth_rate >= 20:
            growth_score = 7.5
            evidence.append(f"年增速20-30%({growth_rate}%)")
        elif growth_rate >= 10:
            growth_score = 5.5
            evidence.append(f"年增速10-20%({growth_rate}%)")
        elif growth_rate >= 5:
            growth_score = 3.5
            evidence.append(f"年增速5-10%({growth_rate}%)")
        else:
            growth_score = 1.5
            evidence.append(f"年增速<5%({growth_rate}%)")
    else:
        evidence.append("增速数据缺失，使用默认值")

    # ── 利润得分 ──
    profit_score = 3.0  # default
    margin_high = gross_margin_str or ""
    if margin_high:
        # 尝试提取数值范围的中位数（如 "50-60%" → 55）
        import re as _re
        _nums = _re.findall(r'(\d+(?:\.\d+)?)', margin_high)
        _margin_mid: Optional[float] = None
        if len(_nums) >= 2:
            try:
                _margin_mid = (float(_nums[0]) + float(_nums[1])) / 2
            except ValueError:
                pass
        elif len(_nums) == 1:
            try:
                _margin_mid = float(_nums[0])
            except ValueError:
                pass

        if _margin_mid is not None:
            if _margin_mid >= 50:
                profit_score = 9.5
            elif _margin_mid >= 30:
                profit_score = 7.5
            elif _margin_mid >= 20:
                profit_score = 5.5
            elif _margin_mid >= 10:
                profit_score = 3.5
            else:
                profit_score = 2.0
            evidence.append(f"毛利率~{_margin_mid:.0f}%({margin_high})")
        elif margin_high in ("极高", "很高", "非常高") or "≥50" in margin_high or ">50" in margin_high:
            profit_score = 9.5
            evidence.append(f"毛利率极高({margin_high})")
        elif margin_high in ("高", "较高"):
            profit_score = 7.5
            evidence.append(f"毛利率高({margin_high})")
        elif margin_high in ("中等", "中等偏上"):
            profit_score = 5.5
            evidence.append(f"毛利率中等({margin_high})")
        elif margin_high in ("低", "较低"):
            profit_score = 3.0
            evidence.append(f"毛利率偏低({margin_high})")
        else:
            profit_score = 4.0
            evidence.append(f"毛利率({margin_high})，取中间值")
    else:
        evidence.append("毛利率数据缺失，使用默认值")

    # ── 壁垒得分 ──
    barrier_score = 3.0  # default
    barrier = barrier_level or ""
    if barrier:
        if barrier in ("极高", "非常高", "极高壁垒"):
            barrier_score = 9.5
            evidence.append(f"壁垒{barrier}")
        elif barrier in ("高", "较高", "高壁垒"):
            barrier_score = 7.5
            evidence.append(f"壁垒{barrier}")
        elif barrier in ("中", "中等", "中等壁垒"):
            barrier_score = 5.0
            evidence.append(f"壁垒{barrier}")
        elif barrier in ("低", "较低", "低壁垒"):
            barrier_score = 2.0
            evidence.append(f"壁垒{barrier}")
        else:
            barrier_score = 4.0
            evidence.append(f"壁垒({barrier})，取中间值")

    # 供需缺口加分
    gap = supply_demand_gap or ""
    if "严重失衡" in gap or "严重短缺" in gap:
        barrier_score = min(10.0, barrier_score + 1.0)
        growth_score = min(10.0, growth_score + 0.5)
        evidence.append(f"供需严重失衡(+1.0壁垒/+0.5增长)")
    elif "偏紧" in gap or "供不应求" in gap:
        barrier_score = min(10.0, barrier_score + 0.5)
        evidence.append(f"供需偏紧(+0.5壁垒)")

    # ── 综合 ──
    w = THREE_HIGH_WEIGHTS
    composite = round(growth_score * w["growth"] + profit_score * w["profit"] + barrier_score * w["barrier"], 1)
    is_high = composite >= THREE_HIGH_THRESHOLD

    return ThreeHighScore(
        growth_score=round(growth_score, 1),
        profit_score=round(profit_score, 1),
        barrier_score=round(barrier_score, 1),
        composite_score=composite,
        is_three_high=is_high,
        evidence=evidence,
    )


def compute_three_high_bonus(stock_code: str, analysis: Optional["SupplyChainAnalysis"]) -> float:
    """计算单只股票的三高加成 (0-10)。

    若该股票所在环节被标记为三高环节，返回该环节的 composite_score；
    若在最优环节中且是龙头，额外 +1.0；
    若不在任何三高环节中，返回 0。
    """
    if analysis is None or not analysis.nodes:
        return 0.0

    bonus = 0.0
    for node in analysis.nodes:
        if stock_code in node.a_share_leaders:
            if node.three_high_score and node.three_high_score.is_three_high:
                bonus = max(bonus, node.three_high_score.composite_score)
                if node.name == analysis.top_segment:
                    bonus = min(10.0, bonus + 1.0)
            elif node.name in analysis.three_high_nodes:
                bonus = max(bonus, 5.0)  # 至少给基础分
            break
        elif stock_code in node.a_share_participants:
            if node.three_high_score and node.three_high_score.is_three_high:
                bonus = max(bonus, node.three_high_score.composite_score - 2.0)  # 参与者减2
            break

    return bonus


# ── v5.2: 估值归一化 ──

def normalize_pe_for_tier(pe_ttm: Optional[float]) -> float:
    """PE归一化到 [0,1]。PE越低越好 (价值投资偏好低PE)。
    <10→1.0, 10-25→0.7, 25-50→0.4, 50-100→0.2, >100→0.05, None→0.5 """
    if pe_ttm is None:
        return 0.5
    if pe_ttm <= 0:
        return 0.5  # 亏损企业不评价
    if pe_ttm < 10:
        return 1.0
    if pe_ttm < 25:
        return 0.7
    if pe_ttm < 50:
        return 0.4
    if pe_ttm < 100:
        return 0.2
    return 0.05


def normalize_market_cap_for_tier(mcap_yi: Optional[float]) -> float:
    """市值归一化到 [0,1]。市值越大越稳定 (宏观/价值偏好大市值)。
    >1000亿→1.0, 500-1000→0.8, 100-500→0.5, 50-100→0.3, <50→0.1, None→0.4 """
    if mcap_yi is None:
        return 0.4
    if mcap_yi > 1000:
        return 1.0
    if mcap_yi > 500:
        return 0.8
    if mcap_yi > 100:
        return 0.5
    if mcap_yi > 50:
        return 0.3
    return 0.1


def normalize_turnover_for_tier(turnover: Optional[float]) -> float:
    """换手率归一化到 [0,1]。适中换手(3-10%)最好, 过高(>20%)减分。
    3-10%→1.0, 1-3%→0.7, 10-20%→0.5, <1%→0.3, >20%→0.2, None→0.5 """
    if turnover is None:
        return 0.5
    if 3.0 <= turnover <= 10.0:
        return 1.0
    if 1.0 <= turnover < 3.0:
        return 0.7
    if 10.0 < turnover <= 20.0:
        return 0.5
    if turnover < 1.0:
        return 0.3
    return 0.2


# ── 内部辅助 ──

def _compute_recency_decay(age_hours: float) -> float:
    """根据催化剂距今时间计算衰减系数。
    规则：<24h → 1.0, 24-72h → 0.5, ≥72h → 0.25。
    """
    thresholds = sorted(CATALYST_AGE_DECAY.keys())
    # 找最大的阈值 ≤ age_hours
    best_decay = 1.0
    for h in thresholds:
        if age_hours >= h:
            best_decay = CATALYST_AGE_DECAY[h]
        else:
            break
    return best_decay

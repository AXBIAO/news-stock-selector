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
LIMIT_UP_THRESHOLD = 9.5  # 涨幅≥9.5%视为涨停


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


@dataclass
class OverheatWarning:
    """板块过热警告"""
    sector: str
    count: int
    ratio: float
    affected_codes: list[str] = field(default_factory=list)


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
    feedback_records: list[dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# v3.6: Tier 分配引擎与辅助函数
# ═══════════════════════════════════════════════════════════════

def compute_catalyst_confidence(catalyst_types: list[CatalystType], age_hours: float, multi_catalyst: bool) -> float:
    """根据催化剂类型、时效、数量计算置信度 [0.0, 1.0]。

    公式: base = mean(catalyst_weights) × decay × multi_bonus
    """
    if not catalyst_types:
        return 0.0
    base = sum(CATALYST_WEIGHTS.get(ct, 0.4) for ct in catalyst_types) / len(catalyst_types)
    decay = _compute_recency_decay(age_hours)
    bonus = 1.3 if multi_catalyst else 1.0
    return round(min(base * decay * bonus, 1.0), 4)


def compute_tier(
    sentiment_score: SentimentLevel,
    catalyst_types: list[CatalystType],
    confidence: float,
    strategy_tag: Optional[StrategyTag] = None,
    prior_day_limit_up: bool = False,
) -> tuple[TierLevel, float]:
    """显式化 tier 分配算法。

    公式: tier_score = sentiment_norm × 0.35 + catalyst_norm × 0.25 + confidence × 0.25 + strategy_adj × 0.15
    其中 sentiment_norm = sentiment / 5.0, catalyst_norm = mean(weights), strategy_adj 来自 STRATEGY_TIER_ADJUST

    附加规则:
    - prior_day_limit_up=True → 强制上限 T3 (涨停次日分化风险)
    - strategy_tag 调整在归一化得分后应用

    Returns: (assigned_tier, tier_score)
    """
    sentiment_norm = float(int(sentiment_score)) / 5.0
    cw = [CATALYST_WEIGHTS.get(ct, 0.4) for ct in catalyst_types]
    catalyst_norm = sum(cw) / len(cw) if cw else 0.0

    strategy_adj_raw = STRATEGY_TIER_ADJUST.get(strategy_tag, 0) if strategy_tag else 0
    strategy_norm = (strategy_adj_raw + 1) / 2.0  # map [-1, +1] → [0.0, 1.0]

    score = round(
        sentiment_norm * 0.35 + catalyst_norm * 0.25 + confidence * 0.25 + strategy_norm * 0.15,
        4,
    )

    if prior_day_limit_up and score > TIER_THRESHOLDS[TierLevel.T3_TRACK]:
        return TierLevel.T3_TRACK, score  # 涨停次日强制封顶

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
    """根据前日涨跌幅和催化剂类型自动分类策略标签。"""
    if prior_change_pct is None:
        return StrategyTag.CATALYST_PLAY
    if prior_change_pct >= LIMIT_UP_THRESHOLD:
        return StrategyTag.BREAKOUT_CHASE
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

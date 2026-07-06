# -*- coding: utf-8 -*-
"""8大投资流派 (Investment Schools) 模块 — v5.0

定义8大流派配置、权重调整、股票-流派匹配逻辑。
与 contracts.py 的 Tier 引擎深度集成，实现差异化选股输出。

设计原则：
- 每个流派是一组权重+筛选条件的组合，不创建独立选股逻辑
- 同一批新闻驱动的候选股票，不同流派看到不同的T1/T2/T3分层
- 默认"事件驱动派"保持兼容旧版行为
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# 流派枚举
# ═══════════════════════════════════════════════════════════════


class InvestmentSchool(str, Enum):
    """8大投资流派"""
    VALUE = "value"            # 价值投资派
    GROWTH = "growth"          # 成长投资派
    SHORT_TERM = "short_term"  # 短线交易派
    TECHNICAL = "technical"    # 技术分析派
    QUANT = "quant"            # 量化交易派
    EVENT_DRIVEN = "event"     # 事件驱动派 (默认)
    MACRO = "macro"            # 宏观投资派
    SPECULATIVE = "speculative"# 投机派


# ═══════════════════════════════════════════════════════════════
# 流派配置
# ═══════════════════════════════════════════════════════════════


@dataclass
class SchoolConfig:
    """单个流派的完整配置"""
    school: InvestmentSchool
    label_zh: str              # 中文名
    icon: str                  # 图标 emoji
    description: str           # 一句话描述
    risk_level: str            # 风险等级: "低"/"中"/"高"/"极高"

    # Tier 5因子权重 (总和应≈1.0, 用于替代默认权重分配)
    w_sentiment: float = 0.30    # 情绪权重
    w_catalyst: float = 0.20     # 催化剂权重
    w_confidence: float = 0.20   # 置信度权重
    w_strategy: float = 0.10     # 策略权重
    w_three_high: float = 0.20   # 三高权重

    # 催化剂类型权重覆盖 (key=CatalystType字符串值, value=覆盖权重)
    # 只存需要覆盖的，未覆盖的保留 CATALYST_WEIGHTS 默认值
    catalyst_overrides: dict[str, float] = field(default_factory=dict)

    # 筛选条件 (None=不限)
    pe_max: Optional[float] = None        # 市盈率上限
    pe_min: Optional[float] = None        # 市盈率下限
    market_cap_min: Optional[float] = None  # 市值下限 (亿元)
    market_cap_max: Optional[float] = None  # 市值上限 (亿元)
    chg_min: Optional[float] = None       # 最低涨跌幅要求 (%)
    chg_max: Optional[float] = None       # 最高涨跌幅限制 (%)

    # 板块偏好
    preferred_sectors: list[str] = field(default_factory=list)
    excluded_sectors: list[str] = field(default_factory=list)

    # 策略标签偏好加分 (key=StrategyTag字符串值, value=额外加分)
    strategy_bonus: dict[str, float] = field(default_factory=dict)

    # 特殊规则
    prefer_three_high: bool = False       # 是否优先三高环节
    require_three_high: bool = False      # 是否只要三高环节股票
    avoid_limit_up: bool = True           # 是否规避涨停次日
    prefer_large_cap: bool = False        # 偏好大盘股
    prefer_small_cap: bool = False        # 偏好小盘股


# ═══════════════════════════════════════════════════════════════
# 8大流派完整配置
# ═══════════════════════════════════════════════════════════════

SCHOOL_CONFIGS: dict[InvestmentSchool, SchoolConfig] = {
    InvestmentSchool.EVENT_DRIVEN: SchoolConfig(
        school=InvestmentSchool.EVENT_DRIVEN,
        label_zh="事件驱动",
        icon="📰",
        description="新闻、政策、公司大事件驱动，对催化剂最敏感",
        risk_level="中",
        # 默认权重（等价于旧版compute_tier）
        w_sentiment=0.30, w_catalyst=0.20, w_confidence=0.20,
        w_strategy=0.10, w_three_high=0.20,
        # 所有催化剂平等对待（不覆盖）
        strategy_bonus={"CATALYST_PLAY": 0.05, "PULLBACK_BUY": 0.03},
    ),

    InvestmentSchool.VALUE: SchoolConfig(
        school=InvestmentSchool.VALUE,
        label_zh="价值投资",
        icon="💎",
        description="看企业内在价值，长期持有，低PE高股息",
        risk_level="低",
        w_sentiment=0.25, w_catalyst=0.15, w_confidence=0.20,
        w_strategy=0.15, w_three_high=0.25,
        catalyst_overrides={
            "TYPE_POLICY": 1.0,    # 政策利好加分
            "TYPE_HOT": 0.2,       # 概念热点降权
            "TYPE_RATING": 0.5,
        },
        pe_max=25,                # PE<25
        market_cap_min=300,       # 市值>300亿
        prefer_large_cap=True,
        avoid_limit_up=True,
        strategy_bonus={"PULLBACK_BUY": 0.10, "RECOVERY": 0.05},
    ),

    InvestmentSchool.GROWTH: SchoolConfig(
        school=InvestmentSchool.GROWTH,
        label_zh="成长投资",
        icon="🚀",
        description="追业绩高速成长公司，长线潜力大",
        risk_level="高",
        w_sentiment=0.25, w_catalyst=0.20, w_confidence=0.20,
        w_strategy=0.10, w_three_high=0.25,
        catalyst_overrides={
            "TYPE_TECH": 1.0,      # 技术突破加分
            "TYPE_EARNINGS": 0.9,  # 业绩加分
            "TYPE_HOT": 0.3,       # 概念降权
        },
        market_cap_min=50,        # >50亿
        market_cap_max=1000,      # <1000亿
        prefer_three_high=True,
        strategy_bonus={"CATALYST_PLAY": 0.08, "MOMENTUM": 0.05},
    ),

    InvestmentSchool.SHORT_TERM: SchoolConfig(
        school=InvestmentSchool.SHORT_TERM,
        label_zh="短线交易",
        icon="⚡",
        description="快进快出，捕捉短期波动收益，高换手高弹性",
        risk_level="极高",
        w_sentiment=0.20, w_catalyst=0.25, w_confidence=0.15,
        w_strategy=0.25, w_three_high=0.15,
        catalyst_overrides={
            "TYPE_HOT": 1.0,       # 概念热点最重
            "TYPE_POLICY": 0.6,    # 政策降权
            "TYPE_EARNINGS": 0.5,  # 业绩降权
        },
        market_cap_max=200,       # 偏好小盘
        chg_min=0.5,              # 当日已有涨幅
        prefer_small_cap=True,
        strategy_bonus={"BREAKOUT_CHASE": -0.15, "CATALYST_PLAY": 0.10},
    ),

    InvestmentSchool.TECHNICAL: SchoolConfig(
        school=InvestmentSchool.TECHNICAL,
        label_zh="技术分析",
        icon="📊",
        description="研究K线形态和量价指标，抓趋势看图表",
        risk_level="高",
        w_sentiment=0.20, w_catalyst=0.15, w_confidence=0.15,
        w_strategy=0.30, w_three_high=0.20,
        # 技术分析不依赖催化剂类型，用策略标签权重
        strategy_bonus={
            "CATALYST_PLAY": 0.12,
            "MOMENTUM": 0.10,
            "PULLBACK_BUY": 0.08,
            "BREAKOUT_CHASE": -0.20,  # 追高减分
        },
        prefer_small_cap=False,
        prefer_large_cap=False,
    ),

    InvestmentSchool.QUANT: SchoolConfig(
        school=InvestmentSchool.QUANT,
        label_zh="量化交易",
        icon="🤖",
        description="数据建模程序交易，纪律性强多因子均衡",
        risk_level="中",
        w_sentiment=0.30, w_catalyst=0.20, w_confidence=0.20,
        w_strategy=0.15, w_three_high=0.15,
        # 量化：最均衡的权重，不偏不倚
        # 不覆盖任何催化剂权重
        strategy_bonus={
            "CATALYST_PLAY": 0.03,
            "PULLBACK_BUY": 0.03,
            "MOMENTUM": 0.03,
        },
    ),

    InvestmentSchool.MACRO: SchoolConfig(
        school=InvestmentSchool.MACRO,
        label_zh="宏观投资",
        icon="🌍",
        description="研究经济周期配置资产，关注行业轮动和顶层政策",
        risk_level="低",
        w_sentiment=0.20, w_catalyst=0.15, w_confidence=0.15,
        w_strategy=0.10, w_three_high=0.40,  # 三高权重最高
        catalyst_overrides={
            "TYPE_POLICY": 1.0,     # 政策最重要
            "TYPE_INDUSTRY": 0.9,   # 行业景气
            "TYPE_HOT": 0.2,        # 概念降权
        },
        market_cap_min=500,         # 只选大盘
        prefer_large_cap=True,
        prefer_three_high=True,
        require_three_high=False,
        strategy_bonus={"PULLBACK_BUY": 0.08, "RECOVERY": 0.06},
    ),

    InvestmentSchool.SPECULATIVE: SchoolConfig(
        school=InvestmentSchool.SPECULATIVE,
        label_zh="投机派",
        icon="🎰",
        description="高风险高收益，追热点短线博弈，小盘高Beta",
        risk_level="极高",
        w_sentiment=0.15, w_catalyst=0.25, w_confidence=0.10,
        w_strategy=0.30, w_three_high=0.20,
        catalyst_overrides={
            "TYPE_HOT": 1.0,        # 热点最重
            "TYPE_MA": 0.9,         # 并购重组
            "TYPE_POLICY": 0.3,     # 政策降权
            "TYPE_EARNINGS": 0.3,   # 业绩忽略
        },
        market_cap_max=100,         # 只选小盘
        prefer_small_cap=True,
        avoid_limit_up=False,       # 不规避涨停
        strategy_bonus={
            "BREAKOUT_CHASE": 0.12,  # 敢于追高
            "CATALYST_PLAY": 0.05,
            "MOMENTUM": 0.05,
        },
    ),
}

# 流派默认（兼容旧版行为）
DEFAULT_SCHOOL = InvestmentSchool.EVENT_DRIVEN

# 流派快捷名称映射
SCHOOL_ALIASES: dict[str, InvestmentSchool] = {
    "价值": InvestmentSchool.VALUE,
    "价值投资": InvestmentSchool.VALUE,
    "value": InvestmentSchool.VALUE,
    "成长": InvestmentSchool.GROWTH,
    "成长投资": InvestmentSchool.GROWTH,
    "growth": InvestmentSchool.GROWTH,
    "短线": InvestmentSchool.SHORT_TERM,
    "短线交易": InvestmentSchool.SHORT_TERM,
    "short": InvestmentSchool.SHORT_TERM,
    "技术": InvestmentSchool.TECHNICAL,
    "技术分析": InvestmentSchool.TECHNICAL,
    "technical": InvestmentSchool.TECHNICAL,
    "量化": InvestmentSchool.QUANT,
    "量化交易": InvestmentSchool.QUANT,
    "quant": InvestmentSchool.QUANT,
    "事件": InvestmentSchool.EVENT_DRIVEN,
    "事件驱动": InvestmentSchool.EVENT_DRIVEN,
    "event": InvestmentSchool.EVENT_DRIVEN,
    "宏观": InvestmentSchool.MACRO,
    "宏观投资": InvestmentSchool.MACRO,
    "macro": InvestmentSchool.MACRO,
    "投机": InvestmentSchool.SPECULATIVE,
    "speculative": InvestmentSchool.SPECULATIVE,
}

# ═══════════════════════════════════════════════════════════════
# 搜索关键词轮换池 (v5.0 新增 — 去重复化)
# ═══════════════════════════════════════════════════════════════

SEARCH_KEYWORD_POOL: dict[str, list[str]] = {
    "业绩超预期": ["业绩预增", "净利润大增", "营收超预期", "业绩暴增", "利润翻倍", "业绩预告大增"],
    "政策利好": ["政策支持", "补贴政策", "顶层文件", "国务院发文", "发改委新规", "工信部利好", "商务部支持"],
    "并购重组": ["重大资产重组", "并购公告", "定增收购", "借壳上市", "资产注入", "股权收购"],
    "技术突破": ["技术突破", "研发成功", "新品发布", "专利授权", "重大突破", "国产替代"],
    "重要合作": ["战略合作", "签订合同", "订单落地", "大单公告", "合作协议", "独家供应"],
    "行业景气": ["行业复苏", "景气上行", "价格上涨", "需求旺盛", "供不应求", "行业拐点"],
    "股权变动": ["增持", "回购", "股东增持", "股权激励", "举牌", "大股东增持"],
    "概念热点": ["AI概念", "人工智能利好", "半导体突破", "机器人概念", "低空经济", "算力利好"],
    "机构评级": ["买入评级", "强烈推荐", "上调目标价", "增持评级", "首次覆盖"],
}

# 默认每次搜索覆盖的主题数
DEFAULT_SEARCH_THEME_COUNT = 4


# ═══════════════════════════════════════════════════════════════
# 流派匹配与筛选函数
# ═══════════════════════════════════════════════════════════════

def resolve_school(identifier: str | InvestmentSchool | None) -> InvestmentSchool:
    """解析流派标识符（字符串别名/枚举/None → 枚举值）"""
    if identifier is None:
        return DEFAULT_SCHOOL
    if isinstance(identifier, InvestmentSchool):
        return identifier
    if isinstance(identifier, str):
        lowered = identifier.strip().lower()
        if lowered in SCHOOL_ALIASES:
            return SCHOOL_ALIASES[lowered]
        # 尝试匹配枚举值
        for s in InvestmentSchool:
            if s.value == lowered:
                return s
    return DEFAULT_SCHOOL


def get_school_config(school: InvestmentSchool) -> SchoolConfig:
    """获取流派配置"""
    return SCHOOL_CONFIGS.get(school, SCHOOL_CONFIGS[DEFAULT_SCHOOL])


def get_catalyst_weight_for_school(
    catalyst_type_str: str,
    school: InvestmentSchool,
    default_weight: float,
) -> float:
    """根据流派获取催化剂类型权重（流派覆盖 > 默认值）"""
    config = get_school_config(school)
    return config.catalyst_overrides.get(catalyst_type_str, default_weight)


def get_strategy_bonus_for_school(strategy_tag_str: str, school: InvestmentSchool) -> float:
    """获取流派的策略标签加分"""
    config = get_school_config(school)
    return config.strategy_bonus.get(strategy_tag_str, 0.0)


def match_stocks_to_schools(
    stocks: list[dict],
) -> dict[str, list[str]]:
    """给每只股票匹配最适合的流派。

    返回 {school_value: [code, ...]}，按匹配度从高到低排列。
    每只股票至少匹配1个流派。
    """
    school_matches: dict[str, list[str]] = {s.value: [] for s in InvestmentSchool}

    for s in stocks:
        code = s.get("code", "")
        price = s.get("price", 0) or 0
        chg = s.get("chg", 0) or 0
        sector = s.get("sector", "")
        sentiment = s.get("sentiment", 3)
        catalyst_types = s.get("catalyst_types", [])

        # v5.2: 使用真实市值和PE数据，替代旧的 price 近似
        market_cap = s.get("market_cap") or s.get("valuation", {}).get("market_cap") if isinstance(s.get("valuation"), dict) else None
        pe_ttm = s.get("pe_ttm") or s.get("valuation", {}).get("pe_ttm") if isinstance(s.get("valuation"), dict) else None

        # 市值判定
        is_large = market_cap is not None and market_cap > 500
        is_small = market_cap is not None and market_cap < 100
        # fallback: 无市值数据时使用旧的价格近似（但标记为不准确）
        if market_cap is None:
            is_large = price > 500 or "银行" in sector or "煤炭" in sector
            is_small = price < 20 and "机器人" not in sector

        scores = {}
        for school in InvestmentSchool:
            cfg = get_school_config(school)
            score = 0.0

            # 市值匹配
            if cfg.prefer_large_cap and is_large:
                score += 2
            if cfg.prefer_small_cap and is_small:
                score += 2

            # 三高匹配
            three_high = s.get("three_high", 0) or 0
            if cfg.prefer_three_high and three_high >= 7.0:
                score += 2
            if cfg.require_three_high and three_high < 7.0:
                score -= 3

            # v5.2: PE/市值 硬过滤 (定义但从未执行过的筛选条件)
            if cfg.pe_max is not None and pe_ttm is not None and pe_ttm > cfg.pe_max:
                score -= 3  # 严重不符合流派PE标准
            if cfg.pe_min is not None and pe_ttm is not None and pe_ttm < cfg.pe_min:
                score -= 2
            if cfg.market_cap_min is not None and market_cap is not None and market_cap < cfg.market_cap_min:
                score -= 3  # 市值不达标
            if cfg.market_cap_max is not None and market_cap is not None and market_cap > cfg.market_cap_max:
                score -= 2  # 市值超标

            # 涨跌匹配
            if cfg.chg_min is not None and chg < cfg.chg_min:
                score -= 1
            if cfg.chg_max is not None and chg > cfg.chg_max:
                score -= 1

            # 催化剂类型匹配
            cat_strs = [str(c) for c in catalyst_types] if catalyst_types else []
            for cat_str in cat_strs:
                if cat_str in cfg.catalyst_overrides:
                    override = cfg.catalyst_overrides[cat_str]
                    if override >= 0.8:
                        score += 1.5

            # 策略匹配
            strategy = s.get("strategy", "")
            if strategy in cfg.strategy_bonus:
                bonus = cfg.strategy_bonus[strategy]
                if bonus >= 0.08:
                    score += 1

            # 板块匹配
            if cfg.preferred_sectors:
                for pref in cfg.preferred_sectors:
                    if pref in sector:
                        score += 1
                        break

            scores[school] = score

        # 找出最佳匹配（score > 0 的流派）
        best_matches = [sch.value for sch, sc in scores.items() if sc > 0]
        if not best_matches:
            best_matches = [DEFAULT_SCHOOL.value]

        # 取前3个最佳匹配
        sorted_schools = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_schools = [sch.value for sch, sc in sorted_schools[:3] if sc > -2]

        for sch_val in top_schools:
            school_matches[sch_val].append(code)

    return school_matches


def apply_school_filter(
    stocks: list[dict],
    school: InvestmentSchool,
) -> list[dict]:
    """按流派筛选股票，返回调整后的排序结果。

    不删除股票，而是调整tier_score，使排序发生变化。
    """
    import copy
    from contracts import (
        CatalystType, StrategyTag, CATALYST_WEIGHTS,
        STRATEGY_TIER_ADJUST, TIER_THRESHOLDS, LIMIT_UP_THRESHOLD,
        TierLevel,
    )

    config = get_school_config(school)
    filtered = []

    for s in stocks:
        ss = copy.deepcopy(s)
        sentiment = ss.get("sentiment", 3)
        chg = ss.get("chg", 0) or 0
        limit_up = chg >= LIMIT_UP_THRESHOLD
        three_high = ss.get("three_high", 0) or 0

        # 使用流派权重计算新tier_score
        sentiment_norm = float(sentiment) / 5.0
        catalyst_norm = _compute_school_catalyst_norm(ss, school)
        confidence = ss.get("confidence", 0.5) or 0.5
        strategy_norm = _compute_school_strategy_norm(ss, school)
        three_high_norm = three_high / 10.0

        score = round(
            sentiment_norm * config.w_sentiment
            + catalyst_norm * config.w_catalyst
            + confidence * config.w_confidence
            + strategy_norm * config.w_strategy
            + three_high_norm * config.w_three_high,
            4,
        )

        # 涨停熔断 (投机派豁免)
        if limit_up and config.avoid_limit_up and score > TIER_THRESHOLDS[TierLevel.T3_TRACK]:
            ss["school_tier"] = 3
        elif score >= TIER_THRESHOLDS[TierLevel.T1_STRONG_BUY]:
            ss["school_tier"] = 1
        elif score >= TIER_THRESHOLDS[TierLevel.T2_WATCH]:
            ss["school_tier"] = 2
        else:
            ss["school_tier"] = 3

        ss["school_tier_score"] = score
        ss["_school"] = school.value
        filtered.append(ss)

    # 按流派调整后的score排序
    filtered.sort(key=lambda x: x.get("school_tier_score", 0), reverse=True)
    return filtered


def _compute_school_catalyst_norm(stock: dict, school: InvestmentSchool) -> float:
    """计算流派调整后的催化剂归一化值"""
    catalyst_types = stock.get("catalyst_types", [])
    if not catalyst_types:
        return 0.0

    from contracts import CATALYST_WEIGHTS
    config = get_school_config(school)
    weights = []
    for ct in catalyst_types:
        ct_str = ct.value if isinstance(ct, Enum) else str(ct)
        w = config.catalyst_overrides.get(ct_str, CATALYST_WEIGHTS.get(ct, 0.4))
        weights.append(w)
    return sum(weights) / len(weights)


def _compute_school_strategy_norm(stock: dict, school: InvestmentSchool) -> float:
    """计算流派调整后的策略归一化值"""
    from contracts import STRATEGY_TIER_ADJUST, StrategyTag
    strategy_tag = stock.get("strategy", "")
    if not strategy_tag:
        return 0.5

    config = get_school_config(school)

    # 尝试匹配StrategyTag
    base = 0.0
    if isinstance(strategy_tag, Enum):
        base = STRATEGY_TIER_ADJUST.get(strategy_tag, 0)
    elif isinstance(strategy_tag, str):
        for st in StrategyTag:
            if st.value == strategy_tag:
                base = STRATEGY_TIER_ADJUST.get(st, 0)
                break

    # 流派策略加分
    strategy_str = strategy_tag.value if isinstance(strategy_tag, Enum) else str(strategy_tag)
    bonus = config.strategy_bonus.get(strategy_str, 0.0)

    # map [-1, +1] → [0.0, 1.0]
    raw = base + bonus
    return max(0.0, min(1.0, (raw + 1) / 2.0))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regime_detector.py — 市场状态检测引擎 (v5.5)

news-stock-selector Step 2.5 核心模块。
每次选股主链必跑：全市场扫描 → 状态分类 → 评分权重调整。

核心能力:
  1. MarketRegime 四态分类 (RISK_ON / RISK_OFF / ROTATION / NEUTRAL)
  2. 广度/量比/板块集中度三维信号
  3. 状态特定的 tier 评分权重调整表
  4. 防御因子: 低波动/高确定性/独立逻辑加成

设计原则:
  - 输入：TDX 全市场数据（已有，不增加额外数据源）
  - 输出：RegimeResult（可序列化，注入 compute_tier）
  - 失败不阻断主链：降级为 NEUTRAL 状态
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MarketRegime(str, Enum):
    """市场四态"""
    RISK_ON = "risk_on"        # 普涨，成长领涨，做多窗口
    RISK_OFF = "risk_off"      # 普跌，防御领涨，避险窗口
    ROTATION = "rotation"      # 板块分化，结构性行情
    NEUTRAL = "neutral"        # 无明确信号，维持默认


@dataclass
class RegimeResult:
    """市场状态检测完整结果"""
    regime: MarketRegime = MarketRegime.NEUTRAL
    confidence: float = 0.5            # 状态置信度 [0, 1]
    breadth_up_pct: float = 50.0       # 上涨股票占比 (%)
    breadth_volume_ratio: float = 1.0  # 上涨总成交额 / 下跌总成交额
    avg_change_pct: float = 0.0        # 全市场平均涨跌幅 (%)
    sector_herfindahl: float = 0.0     # 板块涨跌幅集中度 (0=完全分散, 1=完全集中)
    leading_sectors: list[str] = field(default_factory=list)   # 领涨板块 Top 3
    lagging_sectors: list[str] = field(default_factory=list)   # 领跌板块 Top 3
    total_stocks: int = 0
    diagnosis: str = ""                # 一句话诊断
    signal_details: list[str] = field(default_factory=list)    # 信号明细


# ── 状态 → 5因子权重调整 ──
# 每个状态的权重表：sentiment, catalyst, confidence, strategy, three_high, quality(新增)
# RISK_OFF 时强调确定性(confidence↑)和防御(quality)，淡化情绪(sentiment↓)

REGIME_WEIGHTS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.RISK_ON: {
        "sentiment":   0.30,
        "catalyst":    0.20,
        "confidence":  0.20,
        "strategy":    0.10,
        "three_high":  0.20,
        "quality":     0.00,   # 牛市不使用防御因子
    },
    MarketRegime.RISK_OFF: {
        "sentiment":   0.15,   # ↓ 情绪不可靠
        "catalyst":    0.10,   # ↓ 催化剂在下跌市被压制
        "confidence":  0.30,   # ↑ 确定性最重要
        "strategy":    0.10,
        "three_high":  0.15,
        "quality":     0.20,   # ↑ 防御因子：低波/低负债/高股息
    },
    MarketRegime.ROTATION: {
        "sentiment":   0.25,
        "catalyst":    0.15,
        "confidence":  0.20,
        "strategy":    0.15,   # ↑ 轮动中策略选择更重要
        "three_high":  0.25,   # ↑ 结构市中产业链壁垒更关键
        "quality":     0.00,
    },
    MarketRegime.NEUTRAL: {
        "sentiment":   0.30,
        "catalyst":    0.20,
        "confidence":  0.20,
        "strategy":    0.10,
        "three_high":  0.20,
        "quality":     0.00,
    },
}

# ── 状态检测阈值 ──
RISK_ON_BREADTH_THRESHOLD = 55.0    # 上涨占比 ≥ 55%
RISK_OFF_BREADTH_THRESHOLD = 40.0   # 上涨占比 ≤ 40%
ROTATION_HERFINDAHL_MIN = 0.08      # 板块集中度 > 8% 视为分化
RISK_OFF_AVG_CHG_THRESHOLD = -1.0   # 全市场平均跌幅 ≥ 1%
RISK_ON_VOLUME_RATIO_MIN = 1.2      # 上涨量/下跌量 ≥ 1.2

# ── 防御行业分类 ──
DEFENSIVE_SECTORS = {"银行", "公用事业", "电力", "煤炭", "石油", "交通运输",
                     "食品饮料", "医药", "农业", "高速公路", "水务"}

GROWTH_SECTORS = {"半导体", "AI", "人工智能", "机器人", "新能源", "储能",
                  "低空经济", "商业航天", "创新药", "消费电子", "软件"}


def detect_market_regime(
    all_stocks: dict,  # {code: StockSnapshot} 来自 TDXScanner.all_stocks
    sector_map: Optional[dict[str, str]] = None,  # {code: sector_name}
) -> RegimeResult:
    """从全市场数据检测当前市场状态。

    使用三维信号:
    1. 广度 (breadth): 上涨占比 + 涨跌量比
    2. 集中度 (concentration): 板块涨跌幅的 Herfindahl 指数
    3. 领涨板块属性: 成长 vs 防御

    Args:
        all_stocks: TDXScanner.all_stocks (dict of code → StockSnapshot)
        sector_map: 可选，股票代码到板块名称的映射

    Returns:
        RegimeResult: 包含状态分类、置信度、诊断和推荐权重调整
    """
    if not all_stocks:
        return RegimeResult(
            regime=MarketRegime.NEUTRAL,
            confidence=0.3,
            diagnosis="全市场数据不可用，降级为中性状态",
            signal_details=["no_data"],
        )

    # ── 1. 广度计算 ──
    up_count = 0
    down_count = 0
    flat_count = 0
    up_volume = 0.0
    down_volume = 0.0
    total_change = 0.0
    valid_count = 0

    for code, snap in all_stocks.items():
        chg = getattr(snap, 'change_pct', None)
        vol = getattr(snap, 'latest_amount', None) or 0
        if chg is None:
            continue
        valid_count += 1
        total_change += chg
        if chg > 0.5:
            up_count += 1
            up_volume += vol
        elif chg < -0.5:
            down_count += 1
            down_volume += vol
        else:
            flat_count += 1

    if valid_count == 0:
        return RegimeResult(
            regime=MarketRegime.NEUTRAL,
            confidence=0.3,
            diagnosis="无有效行情数据",
            signal_details=["no_valid_data"],
        )

    breadth_up_pct = round(up_count / valid_count * 100, 1)
    avg_change = round(total_change / valid_count, 2)
    vol_ratio = round(up_volume / down_volume, 1) if down_volume > 0 else (2.0 if up_volume > 0 else 1.0)

    # ── 2. 板块集中度 (Herfindahl) ──
    sector_chgs: dict[str, list[float]] = {}
    if sector_map:
        for code, snap in all_stocks.items():
            sector = sector_map.get(code, "")
            if not sector:
                continue
            chg = getattr(snap, 'change_pct', None)
            if chg is not None:
                sector_chgs.setdefault(sector, []).append(chg)

    sector_avg_chgs: dict[str, float] = {}
    for sec, chgs in sector_chgs.items():
        if len(chgs) >= 3:  # 至少3只股票才计入板块
            sector_avg_chgs[sec] = sum(chgs) / len(chgs)

    herfindahl = 0.0
    leading_sectors: list[str] = []
    lagging_sectors: list[str] = []
    if sector_avg_chgs:
        total_abs = sum(abs(v) for v in sector_avg_chgs.values())
        if total_abs > 0:
            herfindahl = round(sum((v / total_abs) ** 2 for v in sector_avg_chgs.values()), 4)
        sorted_sec = sorted(sector_avg_chgs.items(), key=lambda x: x[1], reverse=True)
        leading_sectors = [s for s, _ in sorted_sec[:3]]
        lagging_sectors = [s for s, _ in sorted_sec[-3:]]

    # ── 3. 领涨板块属性判断 ──
    growth_leading = any(any(g in sec for g in GROWTH_SECTORS) for sec in leading_sectors)
    defensive_leading = any(any(d in sec for d in DEFENSIVE_SECTORS) for sec in leading_sectors)

    # ── 4. 状态分类 ──
    signals: list[str] = []
    regime = MarketRegime.NEUTRAL
    confidence = 0.5

    # RISK_ON: 广度≥55% + 成长领涨 + 量比≥1.2
    if breadth_up_pct >= RISK_ON_BREADTH_THRESHOLD and growth_leading:
        regime = MarketRegime.RISK_ON
        confidence = min(0.95, 0.6 + (breadth_up_pct - 55) * 0.01 + (0.1 if vol_ratio >= RISK_ON_VOLUME_RATIO_MIN else 0))
        signals.append(f"上涨占比{breadth_up_pct}%≥{RISK_ON_BREADTH_THRESHOLD}%")
        signals.append(f"成长板块领涨: {', '.join(leading_sectors[:2])}")

    # RISK_OFF: 广度≤40% + (防御领涨 或 均跌幅≥1%)
    elif breadth_up_pct <= RISK_OFF_BREADTH_THRESHOLD and (defensive_leading or avg_change <= RISK_OFF_AVG_CHG_THRESHOLD):
        regime = MarketRegime.RISK_OFF
        confidence = min(0.95, 0.6 + (40 - breadth_up_pct) * 0.015 + (0.1 if defensive_leading else 0))
        signals.append(f"上涨占比{breadth_up_pct}%≤{RISK_OFF_BREADTH_THRESHOLD}%")
        if defensive_leading:
            signals.append(f"防御板块领涨: {', '.join(leading_sectors[:2])}")
        if avg_change <= RISK_OFF_AVG_CHG_THRESHOLD:
            signals.append(f"全市场均跌幅{avg_change}%≥{abs(RISK_OFF_AVG_CHG_THRESHOLD)}%")

    # ROTATION: 板块集中度高 + 广度在40-55%之间
    elif herfindahl >= ROTATION_HERFINDAHL_MIN and RISK_OFF_BREADTH_THRESHOLD < breadth_up_pct < RISK_ON_BREADTH_THRESHOLD:
        regime = MarketRegime.ROTATION
        confidence = min(0.9, 0.5 + herfindahl * 3)
        signals.append(f"板块集中度{herfindahl:.3f}≥{ROTATION_HERFINDAHL_MIN}")
        signals.append(f"领涨: {', '.join(leading_sectors[:2])} | 领跌: {', '.join(lagging_sectors[:2])}")

    # NEUTRAL: 无明确信号
    else:
        regime = MarketRegime.NEUTRAL
        confidence = 0.45
        signals.append(f"广度{breadth_up_pct}%在中性区间，板块集中度{herfindahl:.3f}未触发分化信号")

    # ── 5. 生成诊断 ──
    diagnosis_map = {
        MarketRegime.RISK_ON: f"普涨行情(广度{breadth_up_pct}%)，成长板块领涨，做多窗口 — 维持标准激进评分",
        MarketRegime.RISK_OFF: f"避险行情(广度{breadth_up_pct}%)，防御板块领涨 — 切换保守评分，强调确定性和防御因子",
        MarketRegime.ROTATION: f"结构性分化(广度{breadth_up_pct}%)，{', '.join(leading_sectors[:1])}强{', '.join(lagging_sectors[:1])}弱 — 强调产业链壁垒和板块选择",
        MarketRegime.NEUTRAL: f"方向不明确(广度{breadth_up_pct}%)，维持默认均衡评分",
    }

    return RegimeResult(
        regime=regime,
        confidence=round(confidence, 2),
        breadth_up_pct=breadth_up_pct,
        breadth_volume_ratio=vol_ratio,
        avg_change_pct=avg_change,
        sector_herfindahl=herfindahl,
        leading_sectors=leading_sectors,
        lagging_sectors=lagging_sectors,
        total_stocks=valid_count,
        diagnosis=diagnosis_map.get(regime, diagnosis_map[MarketRegime.NEUTRAL]),
        signal_details=signals,
    )


def get_regime_weight(wt_name: str, regime: MarketRegime) -> float:
    """获取指定状态下的因子权重。"""
    wts = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS[MarketRegime.NEUTRAL])
    return wts.get(wt_name, 0.0)


def compute_quality_factor(
    stock_code: str,
    sector: Optional[str] = None,
    market_cap_yi: Optional[float] = None,
    pe_ttm: Optional[float] = None,
    change_pct: Optional[float] = None,
) -> float:
    """计算防御质量因子 [0, 1]。

    仅在 RISK_OFF 状态下启用，综合评估：
    - 防御板块归属 (0-0.3)
    - 低波动 (0-0.2)
    - 大盘市值 (0-0.25)
    - 合理PE (0-0.25)

    得分高 → 防御性强 → 适合避险配置。
    """
    score = 0.0
    details: list[str] = []

    # 防御板块加分
    if sector:
        for ds in DEFENSIVE_SECTORS:
            if ds in sector:
                score += 0.30
                details.append(f"防御板块({ds})+0.30")
                break

    # 低波动加分 (涨跌幅绝对值 ≤ 3%)
    if change_pct is not None:
        abs_chg = abs(change_pct)
        if abs_chg <= 1.0:
            score += 0.20
            details.append(f"极低波动({change_pct:+.1f}%)+0.20")
        elif abs_chg <= 3.0:
            score += 0.12
            details.append(f"低波动({change_pct:+.1f}%)+0.12")
        elif abs_chg >= 8.0:
            score -= 0.10
            details.append(f"高波动({change_pct:+.1f}%)-0.10")

    # 大市值加分
    if market_cap_yi is not None:
        if market_cap_yi > 500:
            score += 0.25
            details.append(f"大盘({market_cap_yi:.0f}亿)+0.25")
        elif market_cap_yi > 200:
            score += 0.15
            details.append(f"中大盘({market_cap_yi:.0f}亿)+0.15")
        elif market_cap_yi < 30:
            score -= 0.10
            details.append(f"小盘({market_cap_yi:.0f}亿)-0.10")

    # PE合理区间加分
    if pe_ttm is not None and pe_ttm > 0:
        if 10 <= pe_ttm <= 25:
            score += 0.25
            details.append(f"PE合理({pe_ttm:.0f})+0.25")
        elif pe_ttm < 50:
            score += 0.15
            details.append(f"PE中等({pe_ttm:.0f})+0.15")
        elif pe_ttm > 100:
            score -= 0.10
            details.append(f"PE过高({pe_ttm:.0f})-0.10")

    # 锁在 [0, 1]
    return round(max(0.0, min(1.0, score)), 4)


def compute_sector_covariance_penalty(
    stock_sector: Optional[str],
    same_sector_count: int,
    tier_rank_in_sector: int,  # 1 = 同板块最强, 2 = 第二, ...
) -> float:
    """计算同板块集中惩罚 [0, 0.15]。

    同一板块在同一 Tier 内出现多只股票时，对排名靠后的股票施加惩罚。
    - 第1只（最强）：无惩罚
    - 第2只：-0.05
    - 第3只：-0.08
    - 第4+只：-0.12

    目的：强制 Tier 内板块分散化，避免化工双跌停式集中踩雷。
    """
    if not stock_sector or same_sector_count < 2:
        return 0.0

    if tier_rank_in_sector <= 1:
        return 0.0
    elif tier_rank_in_sector == 2:
        return 0.05
    elif tier_rank_in_sector == 3:
        return 0.08
    else:
        return 0.12


def enforce_tier_diversification(
    stocks: list,  # list of dict with keys: code, sector, tier_score, assigned_tier
    max_sector_pct_per_tier: float = 0.40,
) -> list:
    """强制 Tier 内板块分散化。

    规则：
    1. 同一 Tier 内，若某板块占比 > max_sector_pct_per_tier，降级最弱标的
    2. 每个 Tier 至少包含 2 个不同板块（股票数≥2时）
    3. 降级后重新排序

    Args:
        stocks: 已分配 tier 的股票列表（每项含 code, sector, tier_score, assigned_tier）
        max_sector_pct_per_tier: 单板块在 Tier 内的最大占比

    Returns:
        调整后的股票列表（原地修改 assigned_tier + 返回）
    """
    from collections import Counter

    if len(stocks) < 3:
        return stocks

    # 按 tier 分组
    tiers: dict[int, list[dict]] = {1: [], 2: [], 3: []}
    for s in stocks:
        t = s.get("assigned_tier", 3)
        tiers.setdefault(t, []).append(s)

    for tier_level in [1, 2]:  # 只检查 T1 和 T2
        tier_stocks = tiers.get(tier_level, [])
        if len(tier_stocks) < 2:
            continue

        total = len(tier_stocks)
        sectors_in_tier = Counter(s.get("sector", "未知") for s in tier_stocks)

        for sector, count in sectors_in_tier.items():
            if sector == "未知":
                continue
            ratio = count / total
            if ratio > max_sector_pct_per_tier:
                # 找到该板块在此 tier 中 score 最低的股票，降级
                sector_stocks = sorted(
                    [s for s in tier_stocks if s.get("sector") == sector],
                    key=lambda x: x.get("tier_score", 0),
                )
                # 降级超额部分（保留 ceil(max_sector_pct_per_tier * total) 只）
                keep_count = max(1, int(max_sector_pct_per_tier * total))
                for s in sector_stocks[keep_count:]:
                    new_tier = min(3, tier_level + 1)
                    s["assigned_tier"] = new_tier
                    s["_diversification_downgrade"] = True
                    s["_downgrade_reason"] = (
                        f"板块集中: {sector}在T{tier_level}占比{ratio:.0%}>{max_sector_pct_per_tier:.0%}"
                    )

    # 重新排序
    stocks.sort(key=lambda x: (x.get("assigned_tier", 3), -(x.get("tier_score", 0))))
    return stocks

# technical.py — 技术指标计算模块 (v5.2)
# 基于 TDX 日线数据计算 MA/MACD/RSI/KDJ/量比

import math
from dataclasses import dataclass
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@dataclass
class TechnicalIndicators:
    """单只股票的技术指标集合"""
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ma_trend: str = "震荡"           # 多头排列/空头排列/金叉/死叉/震荡

    macd_dif: Optional[float] = None
    macd_dea: Optional[float] = None
    macd_hist: Optional[float] = None
    macd_signal: str = "无信号"      # 金叉/死叉/多头/空头

    rsi_6: Optional[float] = None
    rsi_14: Optional[float] = None
    rsi_signal: str = "中性"         # 超买/超卖/中性

    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None

    volume_ratio: Optional[float] = None  # 量比 (当日量/5日均量)

    atr_14: Optional[float] = None        # 平均真实波幅
    boll_upper: Optional[float] = None
    boll_mid: Optional[float] = None
    boll_lower: Optional[float] = None


def _ema(data: list[float], period: int) -> list[float]:
    """计算指数移动平均 (EMA)。"""
    if len(data) < period:
        return [None] * len(data)
    k = 2.0 / (period + 1)
    result = [None] * (period - 1) + [sum(data[:period]) / period]
    for i in range(period, len(data)):
        result.append(data[i] * k + result[i - 1] * (1 - k))
    return result


def _sma(data: list[float], period: int) -> list[float]:
    """简单移动平均"""
    if len(data) < period:
        return [None] * len(data)
    result = [None] * (period - 1)
    for i in range(period - 1, len(data)):
        result.append(sum(data[i - period + 1:i + 1]) / period)
    return result


def compute_indicators(bars: list) -> TechnicalIndicators:
    """从 DailyBar 列表计算所有技术指标。

    Args:
        bars: 至少40条 DailyBar (按日期升序)

    Returns:
        TechnicalIndicators with all computed values
    """
    if not bars or len(bars) < 5:
        return TechnicalIndicators()

    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    volumes = [float(b.volume) for b in bars]
    n = len(closes)

    ind = TechnicalIndicators()

    # ── 均线 ──
    if n >= 5:
        ma5_vals = _sma(closes, 5)
        ind.ma5 = ma5_vals[-1]
    if n >= 10:
        ma10_vals = _sma(closes, 10)
        ind.ma10 = ma10_vals[-1]
    if n >= 20:
        ma20_vals = _sma(closes, 20)
        ind.ma20 = ma20_vals[-1]
    if n >= 60:
        ma60_vals = _sma(closes, 60)
        ind.ma60 = ma60_vals[-1]

    # 均线趋势判断
    if ind.ma5 and ind.ma10 and ind.ma20:
        if ind.ma5 > ind.ma10 > ind.ma20:
            ind.ma_trend = "多头排列"
        elif ind.ma5 < ind.ma10 < ind.ma20:
            ind.ma_trend = "空头排列"
        elif ind.ma5 and ind.ma10:
            # 检查金叉/死叉
            if n >= 6:
                prev_ma5 = _sma(closes[:-1], 5)[-1]
                prev_ma10 = _sma(closes[:-1], 10)[-1]
                if prev_ma5 and prev_ma10:
                    if prev_ma5 <= prev_ma10 and ind.ma5 > ind.ma10:
                        ind.ma_trend = "金叉"
                    elif prev_ma5 >= prev_ma10 and ind.ma5 < ind.ma10:
                        ind.ma_trend = "死叉"

    # ── MACD (12, 26, 9) ──
    if n >= 35:
        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        dif = []
        for i in range(len(closes)):
            if ema12[i] is not None and ema26[i] is not None:
                dif.append(ema12[i] - ema26[i])
            else:
                dif.append(None)

        dea = _ema([d for d in dif if d is not None], 9)
        # 对齐: dea 比 dif 短 (period-1) 个元素
        dea_full = [None] * len(dif)
        dea_start = len(dif) - len([d for d in dif if d is not None]) + 8
        for i, d_val in enumerate(dea):
            if i + dea_start < len(dea_full):
                dea_full[i + dea_start] = d_val

        if dif[-1] is not None:
            ind.macd_dif = round(dif[-1], 4)
        if dea_full[-1] is not None:
            ind.macd_dea = round(dea_full[-1], 4)
        if ind.macd_dif is not None and ind.macd_dea is not None:
            ind.macd_hist = round((ind.macd_dif - ind.macd_dea) * 2, 4)

        # MACD信号
        if ind.macd_dif is not None and ind.macd_dea is not None:
            if ind.macd_dif > ind.macd_dea:
                ind.macd_signal = "多头"
            else:
                ind.macd_signal = "空头"
            # 金叉/死叉检测
            if n >= 36 and dif[-2] is not None and dea_full[-2] is not None:
                if dif[-2] <= dea_full[-2] and dif[-1] > dea_full[-1]:
                    ind.macd_signal = "金叉"
                elif dif[-2] >= dea_full[-2] and dif[-1] < dea_full[-1]:
                    ind.macd_signal = "死叉"

    # ── RSI (14) ──
    if n >= 15:
        rsi14 = _calc_rsi(closes, 14)
        if rsi14 is not None:
            ind.rsi_14 = round(rsi14, 2)
            if rsi14 > 80:
                ind.rsi_signal = "超买"
            elif rsi14 < 20:
                ind.rsi_signal = "超卖"
            else:
                ind.rsi_signal = "中性"

    if n >= 7:
        rsi6 = _calc_rsi(closes, 6)
        if rsi6 is not None:
            ind.rsi_6 = round(rsi6, 2)

    # ── KDJ (9, 3, 3) ──
    if n >= 12:
        kdj = _calc_kdj(highs, lows, closes, 9)
        if kdj:
            ind.kdj_k = round(kdj[0], 2)
            ind.kdj_d = round(kdj[1], 2)
            ind.kdj_j = round(kdj[2], 2)

    # ── 量比 ──
    if n >= 5:
        avg_vol_5 = sum(volumes[-6:-1]) / 5.0 if n >= 6 else sum(volumes[-5:]) / 5.0
        if avg_vol_5 > 0:
            ind.volume_ratio = round(volumes[-1] / avg_vol_5, 2)

    # ── ATR (14) ──
    if n >= 15:
        tr_vals = []
        for i in range(1, 15):
            tr = max(
                highs[-i] - lows[-i],
                abs(highs[-i] - closes[-i - 1]),
                abs(lows[-i] - closes[-i - 1]),
            )
            tr_vals.append(tr)
        ind.atr_14 = round(sum(tr_vals) / len(tr_vals), 2)

    # ── 布林带 (20) ──
    if n >= 20 and ind.ma20:
        recent = closes[-20:]
        mean = sum(recent) / 20.0
        variance = sum((x - mean) ** 2 for x in recent) / 20.0
        std = math.sqrt(variance)
        ind.boll_mid = ind.ma20
        ind.boll_upper = round(mean + 2 * std, 2)
        ind.boll_lower = round(mean - 2 * std, 2)

    return ind


def _calc_rsi(closes: list[float], period: int = 14) -> Optional[float]:
    """计算 RSI。"""
    if len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses += abs(diff)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _calc_kdj(highs: list[float], lows: list[float], closes: list[float],
              period: int = 9) -> Optional[tuple[float, float, float]]:
    """计算 KDJ (9,3,3)。"""
    if len(closes) < period + 2:
        return None
    # 取最近 period 根K线的最高最低
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return (50.0, 50.0, 50.0)
    rsv = (closes[-1] - ll) / (hh - ll) * 100.0

    # 需要前一日 K,D 值，这里简化用 RSV 递推
    # 取前两日数据递推
    k_prev = 50.0
    d_prev = 50.0
    for i in range(-period - 1, 0):
        hh_i = max(highs[i - period + 1:i + 1]) if i - period + 1 >= 0 else max(highs[:i + 1])
        ll_i = min(lows[i - period + 1:i + 1]) if i - period + 1 >= 0 else min(lows[:i + 1])
        if hh_i != ll_i:
            rsv_i = (closes[i] - ll_i) / (hh_i - ll_i) * 100.0
        else:
            rsv_i = 50.0
        k_new = 2.0 / 3.0 * k_prev + 1.0 / 3.0 * rsv_i
        d_new = 2.0 / 3.0 * d_prev + 1.0 / 3.0 * k_new
        k_prev = k_new
        d_prev = d_new

    k = 2.0 / 3.0 * k_prev + 1.0 / 3.0 * rsv
    d = 2.0 / 3.0 * d_prev + 1.0 / 3.0 * k
    j = 3.0 * k - 2.0 * d
    return (k, d, j)


def compute_indicators_from_tdx(market: str, code: str, reader) -> Optional[TechnicalIndicators]:
    """从 TDX reader 计算技术指标 (便捷函数)。

    Args:
        market: 'sh' / 'sz' / 'bj'
        code: 6位股票代码
        reader: TDXReader 实例

    Returns:
        TechnicalIndicators or None if data unavailable
    """
    try:
        bars = reader.get_last_n_bars(market, code, n=60)
        if not bars or len(bars) < 5:
            return None
        return compute_indicators(bars)
    except Exception:
        return None


def normalize_technical_for_tier(tech: Optional[TechnicalIndicators]) -> float:
    """技术面综合评分归一化到 [0, 1]。

    评分规则:
    - 多头排列: +0.30
    - 金叉/均线金叉: +0.20
    - MACD多头/金叉: +0.15
    - RSI 30-70 中性区间: +0.15
    - 量比 1.0-2.0: +0.10
    - 价格在布林带中轨上方: +0.05
    - 超买(RSI>80): -0.10
    - 空头排列: -0.10
    - 基线: 0.35
    """
    if tech is None:
        return 0.5  # 无数据时中性

    score = 0.35

    # 均线趋势
    if tech.ma_trend == "多头排列":
        score += 0.30
    elif tech.ma_trend == "金叉":
        score += 0.20
    elif tech.ma_trend == "空头排列":
        score -= 0.10

    # MACD 信号
    if tech.macd_signal == "金叉":
        score += 0.15
    elif tech.macd_signal == "多头":
        score += 0.08

    # RSI
    if tech.rsi_14 is not None:
        if 30 <= tech.rsi_14 <= 70:
            score += 0.15
        elif tech.rsi_14 > 80:
            score -= 0.10

    # 量比
    if tech.volume_ratio is not None:
        if 1.0 <= tech.volume_ratio <= 2.0:
            score += 0.10
        elif tech.volume_ratio > 2.5:
            score += 0.05

    # 布林带位置
    if tech.boll_mid is not None and tech.ma5 is not None:
        if tech.ma5 > tech.boll_mid:
            score += 0.05

    return round(min(max(score, 0.0), 1.0), 3)

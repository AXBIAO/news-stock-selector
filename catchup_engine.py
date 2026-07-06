# catchup_engine.py — 板块联动补涨引擎 (v5.2)
# 自动发现同板块龙头涨停后的二线补涨标的

from dataclasses import dataclass, field
from typing import Optional
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@dataclass
class CatchupOpportunity:
    """单个板块的补涨机会"""
    sector: str                                    # 板块名称
    leaders: list[tuple[str, str, float]] = field(default_factory=list)  # [(code, name, chg%), ...]
    laggards: list[tuple[str, str, float]] = field(default_factory=list)  # [(code, name, chg%), ...]
    leader_avg_chg: float = 0.0
    laggard_avg_chg: float = 0.0
    heat_score: float = 0.0                         # 0-10 热度评分


def detect_catchup(
    scanner,
    threshold_leader: float = 5.0,
    threshold_laggard: float = 2.0,
    min_leaders: int = 2,
    min_laggards: int = 1,
    max_results: int = 5,
) -> list[CatchupOpportunity]:
    """从 TDX 概念板块数据中检测补涨机会。

    Args:
        scanner: TDXScanner 实例
        threshold_leader: 龙头涨幅阈值（%）
        threshold_laggard: 补涨标的涨幅上限（%）
        min_leaders: 最少龙头数量
        min_laggards: 最少补涨候选数量
        max_results: 最多返回板块数

    Returns:
        按热度评分排序的补涨机会列表
    """
    opportunities: list[CatchupOpportunity] = []
    all_stocks = scanner.all_stocks
    if not all_stocks:
        return opportunities

    # 获取所有涨幅榜数据（成交量>5000万）
    top_gainers = scanner.scan_top_gainers(200, min_amount=5e7)
    # 构建涨幅映射 {code: (change_pct, name)}
    chg_map: dict[str, tuple[float, str]] = {}
    for code, snap, chg in top_gainers:
        name = getattr(snap, 'name', '') or all_stocks.get(code, type('x', (), {'name': code})()).name
        if hasattr(name, '__call__'):
            name = code
        chg_map[code] = (chg, str(name))

    # 遍历 TDX 概念板块 .blk 文件
    try:
        block_files = scanner.reader.list_block_files() if hasattr(scanner, 'reader') and scanner.reader else []
    except Exception:
        block_files = []

    for blk_name in block_files:
        try:
            members = scanner.reader.read_block_file(blk_name)
        except Exception:
            continue
        if not members or len(members) < min_leaders + min_laggards:
            continue

        leaders = []
        laggards = []
        for code in members:
            if code not in chg_map:
                continue
            chg, name = chg_map[code]
            if chg >= threshold_leader:
                leaders.append((code, name, chg))
            elif chg < threshold_laggard:
                laggards.append((code, name, chg))

        if len(leaders) >= min_leaders and len(laggards) >= min_laggards:
            leader_avg = sum(l[2] for l in leaders) / len(leaders)
            laggard_avg = sum(l[2] for l in laggards) / len(laggards) if laggards else 0
            heat = leader_avg * len(leaders) * 1.0 + (5.0 - abs(laggard_avg)) * 0.5

            opportunities.append(CatchupOpportunity(
                sector=blk_name.replace('.blk', ''),
                leaders=sorted(leaders, key=lambda x: x[2], reverse=True)[:5],
                laggards=sorted(laggards, key=lambda x: x[2], reverse=True)[:8],
                leader_avg_chg=round(leader_avg, 2),
                laggard_avg_chg=round(laggard_avg, 2),
                heat_score=round(min(heat, 10.0), 1),
            ))

    # 降级: 如果 .blk 文件扫描无结果，使用 sector keywords 做粗略分组
    if not opportunities:
        opportunities = _detect_catchup_fallback(scanner, chg_map, threshold_leader, threshold_laggard,
                                                  min_leaders, min_laggards)

    return sorted(opportunities, key=lambda x: x.heat_score, reverse=True)[:max_results]


def _detect_catchup_fallback(
    scanner,
    chg_map: dict,
    threshold_leader: float,
    threshold_laggard: float,
    min_leaders: int,
    min_laggards: int,
) -> list[CatchupOpportunity]:
    """降级方案: 使用 scan_by_sectors() API 做板块分组检测补涨。"""
    from tdx_scanner import SECTOR_KEYWORDS

    opportunities = []

    for sector_name in SECTOR_KEYWORDS:
        # v5.3: 使用 scan_by_sectors API 获取该板块实际股票列表
        try:
            sector_stocks_raw = scanner.scan_by_sectors([sector_name])
        except Exception:
            continue

        if not sector_stocks_raw or len(sector_stocks_raw) < min_leaders + min_laggards:
            continue

        # sector_stocks_raw is dict[code, StockSnapshot]
        # v5.3: use relative performance — leaders are top gainers, laggards are sector mates with lower (but mostly positive) gains
        sector_matches = []
        for code, snap in (sector_stocks_raw.items() if isinstance(sector_stocks_raw, dict) else []):
            if code not in chg_map:
                continue
            chg, name = chg_map[code]
            sector_matches.append((code, name, chg))

        if len(sector_matches) < min_leaders + min_laggards:
            continue

        # Sort by change descending
        sector_matches.sort(key=lambda x: x[2], reverse=True)

        # v5.3: percentile-based leader/laggard detection (works in both hot and cold markets)
        # Leaders: top 25% by gain (min 2, max 5)
        # Laggards: bottom 50% by gain, gain > -3% (min 1, max 8)
        n = len(sector_matches)
        leader_cutoff = max(min_leaders, n // 4)
        laggard_start = n // 2  # bottom half
        laggard_end = n  # all the way to bottom

        leaders = sector_matches[:leader_cutoff]
        leader_avg = sum(l[2] for l in leaders) / len(leaders)

        # Only consider as valid laggards if they're positive (or mildly negative) and significantly behind leaders
        laggard_candidates = [(c, n, chg) for c, n, chg in sector_matches[laggard_start:laggard_end]
                              if chg > -3.0]
        # Also filter: must be at least 30% behind leader average
        laggards = [(c, n, chg) for c, n, chg in laggard_candidates
                     if chg < leader_avg * 0.7]

        if len(leaders) >= min_leaders and len(laggards) >= min_laggards:
            laggard_avg = sum(l[2] for l in laggards) / len(laggards)
            # Heat score: leader momentum * number of leaders * (1 + spread between leaders and laggards)
            spread = leader_avg - laggard_avg
            heat = leader_avg * len(leaders) * 0.5 + spread * 2.0
            opportunities.append(CatchupOpportunity(
                sector=sector_name,
                leaders=sorted(leaders, key=lambda x: x[2], reverse=True)[:5],
                laggards=sorted(laggards, key=lambda x: x[2], reverse=True)[:8],
                leader_avg_chg=round(leader_avg, 2),
                laggard_avg_chg=round(laggard_avg, 2),
                heat_score=round(min(heat, 10.0), 1),
            ))

    return sorted(opportunities, key=lambda x: x.heat_score, reverse=True)[:5]


def format_catchup_markdown(opps: list[CatchupOpportunity]) -> str:
    """格式化补涨机会为 Markdown。"""
    if not opps:
        return ""
    lines = ["## 板块补涨机会\n"]
    for opp in opps:
        leaders_str = "、".join(f"{n}({c} +{chg:.1f}%)" for c, n, chg in opp.leaders[:3])
        laggards_str = "、".join(f"{n}({c})" for c, n, chg in opp.laggards[:5])
        lines.append(f"### {opp.sector} (热度 {opp.heat_score:.1f})")
        lines.append(f"- 龙头: {leaders_str}")
        lines.append(f"- 补涨候选: {laggards_str}")
        lines.append("")
    return "\n".join(lines)

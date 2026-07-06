#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
supply_chain.py — 产业链 BOM 拆解 + 三高筛选引擎 (v4.0)

news-stock-selector Step 5 核心模块。
每次选股主链必跑：提取行业主题 → BOM拆解 → 三高评分 → 龙头定位。

职责:
  1. 生成产业链 BOM 拆解提示词
  2. 解析结构化产业链节点数据
  3. 对每个节点计算三高评分
  4. 定位每个环节的 A 股龙头
  5. 与新闻选股结果交叉增强
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from contracts import (
    SupplyChainAnalysis,
    SupplyChainNode,
    ThreeHighScore,
    compute_three_high_score,
    compute_three_high_bonus,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# BOM 拆解提示词模板
# ═══════════════════════════════════════════════════════════════

BOM_DECOMPOSE_PROMPT = """你是一个产业链分析专家。请对"{industry}"进行产业链 BOM（物料清单）拆解。

## 拆解要求

1. **识别产业链层级**: 将产业链拆解为上游、中游、下游，每个层级识别 2-5 个核心环节
2. **环节描述**: 每个环节说明其核心价值、关键技术和代表性产品
3. **供需关系**: 标注环节之间的供需关系（谁供给谁，谁依赖谁）
4. **关键数据**: 尽可能给出每个环节的：
   - 年行业增速（%）
   - 典型毛利率区间
   - 壁垒等级（极高/高/中/低）+ 壁垒原因
   - 供需状态（严重失衡/偏紧/平衡/过剩）

## 输出格式（严格 JSON）

```json
{{
  "industry": "{industry}",
  "nodes": [
    {{
      "name": "环节名称（如 光芯片）",
      "level": "上游/中游/下游",
      "description": "环节简述",
      "key_components": ["关键产品1", "关键产品2"],
      "upstream_of": ["供给的下游环节名称"],
      "downstream_of": ["依赖的上游环节名称"],
      "growth_rate": 25.0,
      "gross_margin_range": "30-50%",
      "barrier_level": "高/极高/中/低",
      "barrier_reasons": ["技术壁垒：需EUV光刻", "认证周期：2-3年"],
      "supply_demand_gap": "偏紧/严重失衡/平衡/过剩"
    }}
  ]
}}
```

## 注意事项
- 环节名称要具体，不要泛化为"上游材料"这种模糊表述
- 数据尽量基于公开市场研报和行业共识，不确定的标注为 null
- 优先识别国产替代空间大、供需失衡严重的高价值环节
- 如果行业很新（如量子计算、可控核聚变），可以适当降低数据精确度要求
"""

LEADER_MAPPING_PROMPT = """你是一个A股行业分析师。已知产业链"{industry}"的以下环节需要映射A股标的：

{segment_descriptions}

请为每个环节找出A股市场中对应的龙头公司和主要参与者。

## 输出格式（严格 JSON）

```json
{{
  "mappings": [
    {{
      "node_name": "环节名称",
      "leaders": [
        {{"code": "600xxx", "name": "公司名", "reason": "入选理由"}}
      ],
      "participants": [
        {{"code": "002xxx", "name": "公司名", "reason": "入选理由"}}
      ]
    }}
  ]
}}
```

## 注意事项
- 优先选择行业公认龙头（市场份额最高、技术最强）
- 代码必须是6位A股数字代码，如不确定代码用"待确认"标注
- 每个环节龙头不超过3家，参与者不超过5家
- 如果某个环节在A股没有纯正标的，标注"暂无A股纯正标的"并给出最接近的替代标的
"""


# ═══════════════════════════════════════════════════════════════
# JSON 提取工具
# ═══════════════════════════════════════════════════════════════

def _extract_json(text: str) -> str | None:
    """从 LLM 返回文本中提取 JSON 内容（处理 markdown 代码块包裹）。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return match.group() if match else None


# ═══════════════════════════════════════════════════════════════
# 产业链节点解析
# ═══════════════════════════════════════════════════════════════

def parse_supply_chain_nodes(raw_json: str) -> list[SupplyChainNode]:
    """将 LLM 返回的 JSON 解析为 SupplyChainNode 列表。

    Args:
        raw_json: LLM 返回的 JSON 字符串（可能包含 markdown 代码块包裹）

    Returns:
        list[SupplyChainNode]: 解析后的节点列表，解析失败返回空列表
    """
    text = _extract_json(raw_json)
    if not text:
        logger.warning("No JSON found in supply chain output")
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse supply chain JSON")
        return []

    nodes_raw = data.get("nodes", [])
    nodes: list[SupplyChainNode] = []
    for n in nodes_raw:
        try:
            node = SupplyChainNode(
                name=n.get("name", ""),
                level=n.get("level", "中游"),
                description=n.get("description", ""),
                key_components=n.get("key_components", []),
                upstream_of=n.get("upstream_of", []),
                downstream_of=n.get("downstream_of", []),
                growth_rate=n.get("growth_rate"),
                gross_margin_range=n.get("gross_margin_range"),
                barrier_level=n.get("barrier_level"),
                barrier_reasons=n.get("barrier_reasons", []),
                supply_demand_gap=n.get("supply_demand_gap"),
            )
            nodes.append(node)
        except Exception as e:
            logger.warning(f"Failed to parse node {n.get('name', '?')}: {e}")
            continue

    return nodes


def parse_leader_mappings(raw_json: str) -> dict[str, dict]:
    """将 LLM 返回的龙头映射 JSON 解析为 dict。

    Returns:
        dict: {node_name: {"leaders": [{"code": ..., "name": ...}], "participants": [...]}}
    """
    text = _extract_json(raw_json)
    if not text:
        return {}

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}

    mappings: dict[str, dict] = {}
    for m in data.get("mappings", []):
        node_name = m.get("node_name", "")
        if node_name:
            mappings[node_name] = {
                "leaders": m.get("leaders", []),
                "participants": m.get("participants", []),
            }

    return mappings


# ═══════════════════════════════════════════════════════════════
# 三高评分与排序
# ═══════════════════════════════════════════════════════════════

def score_supply_chain_nodes(nodes: list[SupplyChainNode]) -> list[SupplyChainNode]:
    """对产业链所有节点计算三高评分。

    对每个节点调用 compute_three_high_score()，将评分结果写入 node.three_high_score。
    返回按 composite_score 降序排列的新列表（不修改原列表顺序）。
    """
    for node in nodes:
        node.three_high_score = compute_three_high_score(
            growth_rate=node.growth_rate,
            gross_margin_str=node.gross_margin_range,
            barrier_level=node.barrier_level,
            supply_demand_gap=node.supply_demand_gap,
        )

    # 返回按三高综合评分降序的新列表
    sorted_nodes = sorted(
        nodes,
        key=lambda n: n.three_high_score.composite_score if n.three_high_score else 0,
        reverse=True,
    )
    return sorted_nodes


def apply_leader_mappings(
    nodes: list[SupplyChainNode],
    mappings: dict[str, dict],
) -> list[SupplyChainNode]:
    """将龙头映射结果写入产业链节点。

    Args:
        nodes: 产业链节点列表
        mappings: parse_leader_mappings() 的返回结果

    Returns:
        更新后的节点列表（原地修改 + 返回）
    """
    for node in nodes:
        m = mappings.get(node.name)
        if not m:
            # 模糊匹配
            for key in mappings:
                if node.name in key or key in node.name:
                    m = mappings[key]
                    break
        if m:
            node.a_share_leaders = [ld.get("code", "") for ld in m.get("leaders", [])]
            node.a_share_participants = [p.get("code", "") for p in m.get("participants", [])]
            node.leader_names = [ld.get("name", "") for ld in m.get("leaders", [])]

    return nodes


# ═══════════════════════════════════════════════════════════════
# 顶层 API：完整分析流程
# ═══════════════════════════════════════════════════════════════

def build_supply_chain_analysis(
    industry: str,
    nodes_json: str,
    leader_json: str = "",
) -> SupplyChainAnalysis:
    """构建完整的产业链分析结果。

    这是 Step 1.6 的主入口函数。

    Args:
        industry: 行业/主题名称
        nodes_json: BOM 拆解的 JSON 输出（来自 LLM）
        leader_json: 龙头映射的 JSON 输出（来自 LLM），可选

    Returns:
        SupplyChainAnalysis: 完整的产业链分析结果
    """
    # 1. 解析节点
    nodes = parse_supply_chain_nodes(nodes_json)
    if not nodes:
        return SupplyChainAnalysis(
            industry=industry,
            analysis_summary=f"产业链拆解失败：无法解析 {industry} 的产业链结构",
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # 2. 三高评分
    nodes = score_supply_chain_nodes(nodes)

    # 3. 龙头映射
    if leader_json:
        mappings = parse_leader_mappings(leader_json)
        nodes = apply_leader_mappings(nodes, mappings)

    # 4. 找出最优环节和三高环节
    three_high_names: list[str] = []
    for node in nodes:
        if node.three_high_score and node.three_high_score.is_three_high:
            three_high_names.append(node.name)

    top_segment = nodes[0].name if nodes else None
    top_leaders = nodes[0].a_share_leaders if nodes else []

    # 5. 生成摘要
    upstream_count = sum(1 for n in nodes if n.level == "上游")
    midstream_count = sum(1 for n in nodes if n.level == "中游")
    downstream_count = sum(1 for n in nodes if n.level == "下游")

    summary_parts = [
        f"{industry}产业链共识别 {len(nodes)} 个核心环节",
        f"(上游{upstream_count} / 中游{midstream_count} / 下游{downstream_count})",
    ]
    if three_high_names:
        summary_parts.append(f"三高环节({len(three_high_names)}个): {', '.join(three_high_names)}")
    if top_segment:
        summary_parts.append(f"最优环节: {top_segment} (综合评分 {nodes[0].three_high_score.composite_score if nodes[0].three_high_score else 'N/A'})")

    return SupplyChainAnalysis(
        industry=industry,
        nodes=nodes,
        top_segment=top_segment,
        top_segment_leaders=top_leaders,
        three_high_nodes=three_high_names,
        analysis_summary="；".join(summary_parts) + "。",
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        source="ai-decomposition",
    )


def format_supply_chain_markdown(analysis: SupplyChainAnalysis) -> str:
    """将产业链分析结果格式化为 Markdown 输出。

    用于 skill 的 Markdown 主输出和 HTML 报告的文本内容。
    """
    if not analysis.nodes:
        return f"*产业链分析: {analysis.analysis_summary}*"

    lines = [
        f"## 产业链拆解: {analysis.industry}",
        "",
        f"**{analysis.analysis_summary}**",
        "",
        "| 层级 | 环节 | 增速 | 毛利率 | 壁垒 | 三高评分 | 龙头标的 |",
        "|------|------|------|--------|------|----------|----------|",
    ]

    for node in analysis.nodes:
        level_emoji = {"上游": "⬆️", "中游": "➡️", "下游": "⬇️"}.get(node.level, "")
        growth = f"{node.growth_rate}%" if node.growth_rate else "-"
        margin = node.gross_margin_range or "-"
        barrier = node.barrier_level or "-"
        score = f"{node.three_high_score.composite_score}" if node.three_high_score else "-"
        is_3h = " 🔥" if (node.three_high_score and node.three_high_score.is_three_high) else ""

        leaders_str = ", ".join(node.leader_names[:3]) if node.leader_names else (
            ", ".join(node.a_share_leaders[:3]) if node.a_share_leaders else "-"
        )

        lines.append(
            f"| {level_emoji}{node.level} | **{node.name}**{is_3h} | {growth} | {margin} | {barrier} | {score} | {leaders_str} |"
        )

    # 三高环节详细说明
    three_high = [n for n in analysis.nodes if n.three_high_score and n.three_high_score.is_three_high]
    if three_high:
        lines.append("")
        lines.append("### 🔥 三高环节详情")
        for node in three_high:
            score = node.three_high_score
            lines.append(f"**{node.name}** (综合 {score.composite_score}/10)")
            lines.append(f"- 增长: {score.growth_score}/10 | 利润: {score.profit_score}/10 | 壁垒: {score.barrier_score}/10")
            if node.barrier_reasons:
                lines.append(f"- 壁垒来源: {'; '.join(node.barrier_reasons[:3])}")
            if node.a_share_leaders:
                lines.append(f"- A股龙头: {', '.join(node.a_share_leaders)}")
            lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 与新闻选股结果交叉增强
# ═══════════════════════════════════════════════════════════════

def merge_chain_with_stocks(
    analysis: SupplyChainAnalysis,
    stock_codes: list[str],
    stock_sectors: dict[str, str],
) -> dict[str, float]:
    """将产业链分析与新闻选股结果交叉增强。

    对于每只新闻选出的股票，如果它处于产业链的三高环节中，
    计算三高加成值，用于提升该股票的 tier_score。

    Args:
        analysis: 产业链分析结果
        stock_codes: 新闻选股识别出的股票代码列表
        stock_sectors: {code: sector_name} 股票代码到板块名称的映射

    Returns:
        dict[str, float]: {code: three_high_bonus} 每只股票的三高加成 (0-10)
    """
    if not analysis.nodes:
        return {code: 0.0 for code in stock_codes}

    bonuses: dict[str, float] = {}
    for code in stock_codes:
        bonus = compute_three_high_bonus(code, analysis)
        if bonus == 0.0:
            # 尝试通过板块名称模糊匹配
            sector = stock_sectors.get(code, "")
            if sector:
                for node in analysis.nodes:
                    if (node.three_high_score and node.three_high_score.is_three_high
                            and (node.name in sector or sector in node.name)):
                        bonus = node.three_high_score.composite_score - 1.0  # 模糊匹配减1
                        break
        bonuses[code] = round(bonus, 1)

    return bonuses


def export_analysis_for_report(analysis: SupplyChainAnalysis) -> dict[str, Any]:
    """将 SupplyChainAnalysis 导出为 HTML 报告可直接使用的 dict。

    用于 skill.md Step 5 HTML 报告生成时引用产业链分析数据。
    """
    if not analysis.nodes:
        return {"has_data": False, "summary": analysis.analysis_summary}

    nodes_data = []
    for node in analysis.nodes:
        score = node.three_high_score
        nodes_data.append({
            "name": node.name,
            "level": node.level,
            "description": node.description,
            "growth_rate": node.growth_rate,
            "gross_margin": node.gross_margin_range,
            "barrier_level": node.barrier_level,
            "barrier_reasons": node.barrier_reasons,
            "supply_demand": node.supply_demand_gap,
            "is_three_high": score.is_three_high if score else False,
            "composite_score": score.composite_score if score else 0,
            "growth_score": score.growth_score if score else 0,
            "profit_score": score.profit_score if score else 0,
            "barrier_score": score.barrier_score if score else 0,
            "leaders": node.a_share_leaders,
            "leader_names": node.leader_names,
            "participants": node.a_share_participants,
        })

    return {
        "has_data": True,
        "industry": analysis.industry,
        "summary": analysis.analysis_summary,
        "top_segment": analysis.top_segment,
        "top_segment_leaders": analysis.top_segment_leaders,
        "three_high_count": len(analysis.three_high_nodes),
        "three_high_nodes": analysis.three_high_nodes,
        "total_nodes": len(analysis.nodes),
        "upstream_count": sum(1 for n in analysis.nodes if n.level == "上游"),
        "midstream_count": sum(1 for n in analysis.nodes if n.level == "中游"),
        "downstream_count": sum(1 for n in analysis.nodes if n.level == "下游"),
        "nodes": nodes_data,
    }

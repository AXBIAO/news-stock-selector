#!/usr/bin/env python3
"""新闻选股日报 HTML 报告生成器 v4.1
从 JSON 数据 + 模板文件生成完整的 HTML 报告。
用法:
  python gen_report_from_data.py data.json              # 从文件读取
  echo '{"stocks":[...]}' | python gen_report_from_data.py  # 从 stdin 读取
输出: C:/Users/Administrator/Desktop/新闻选股日报_YYYYMMDD.html
"""
import json as _json
import os
import sys
from datetime import date

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SKILL_DIR)
SHARED_DIR = os.path.join(SKILL_DIR, "shared")
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Desktop")

# ── v5.1: 多流派 tier 计算 ──
try:
    from contracts import compute_tier_for_school, classify_strategy_tag, CatalystType, LIMIT_UP_THRESHOLD as _LIMIT_UP, is_real_limit_up
    from schools import resolve_school as _resolve_school, SCHOOL_CONFIGS as _SCHOOL_CONFIGS
    _HAS_SCHOOLS = True
except ImportError as e:
    _HAS_SCHOOLS = False
    print(f"[WARN] schools/contracts import failed: {e}", file=sys.stderr)
    def is_real_limit_up(code, chg):
        return bool(chg is not None and chg >= 9.5)

ALL_SCHOOL_IDS = ["event", "value", "growth", "short_term", "technical", "quant", "macro", "speculative"]
SCHOOL_LABELS = {"value":"价值","growth":"成长","short_term":"短线","technical":"技术","quant":"量化","event":"事件","macro":"宏观","speculative":"投机"}

def _infer_catalyst_types(news: str) -> list:
    """从新闻摘要文本推断催化剂类型列表。"""
    cats = []
    if any(kw in news for kw in ["涨价","业绩","EPS","净利润","利润翻倍"]): cats.append(CatalystType.EARNINGS)
    if any(kw in news for kw in ["政策","工信部","发改委","国务院","部委","发文"]): cats.append(CatalystType.POLICY)
    if any(kw in news for kw in ["并购","重组","收购","资产注入"]): cats.append(CatalystType.MA)
    if any(kw in news for kw in ["技术突破","研发","国产替代","专利","流片"]): cats.append(CatalystType.TECH)
    if any(kw in news for kw in ["合作","订单","签约","供应链","特斯拉","供应商"]): cats.append(CatalystType.COOP)
    if any(kw in news for kw in ["复苏","景气","需求","产能","扩产"]): cats.append(CatalystType.INDUSTRY)
    if any(kw in news for kw in ["增持","回购","股权激励"]): cats.append(CatalystType.EQUITY)
    if any(kw in news for kw in ["AI","机器人","半导体","新能源","芯片","算力"]): cats.append(CatalystType.HOT)
    return cats if cats else [CatalystType.HOT]


def _infer_cat_label(news: str) -> str:
    """从新闻摘要推断催化剂类型标签（用于 HTML 显示）。"""
    cats = []
    if any(kw in news for kw in ["涨价","业绩","EPS","利润"]): cats.append("业绩")
    if any(kw in news for kw in ["政策","工信部","发改委","国务院","部委"]): cats.append("政策")
    if any(kw in news for kw in ["并购","重组","收购"]): cats.append("并购")
    if any(kw in news for kw in ["技术","研发","国产替代","专利","流片"]): cats.append("技术")
    if any(kw in news for kw in ["合作","订单","签约","供应链","特斯拉"]): cats.append("合作")
    if any(kw in news for kw in ["复苏","景气","需求","产能","涨价"]): cats.append("景气")
    if cats: cats = cats[:2]
    return "+".join(cats) if cats else "热点"


def _compute_stock_confidence(stock: dict) -> float:
    """从股票数据动态计算置信度，替代硬编码的 0.5。

    置信度因子:
    - 基础: 0.35 (中性基线)
    - 情绪加成: sentiment 4→+0.10, 5→+0.20
    - 多催化剂: 2+ → +0.10, 3+ → +0.15
    - 有明确合作/订单/业绩催化剂 → +0.05
    - 涨停首日 → 上限 0.55 (防止追高)
    """
    sentiment = stock.get("sentiment", 3)
    news = stock.get("news", "")
    cats = _infer_catalyst_types(news)

    conf = 0.35  # 基线

    if sentiment >= 5:
        conf += 0.20
    elif sentiment >= 4:
        conf += 0.10

    if len(cats) >= 3:
        conf += 0.15
    elif len(cats) >= 2:
        conf += 0.10

    from contracts import CatalystType as _CT
    high_quality = {_CT.EARNINGS, _CT.TECH, _CT.COOP, _CT.POLICY}
    if any(c in high_quality for c in cats):
        conf += 0.05

    chg = stock.get("chg", 0) or 0
    if stock.get("limit_up", False) or is_real_limit_up(stock.get("code", ""), chg):
        conf = min(conf, 0.55)

    return round(min(conf, 1.0), 3)


def _compute_stock_three_high(stock: dict) -> float:
    """从股票板块/新闻动态推断三高加成，替代硬编码的 5.0。"""
    sector = stock.get("sector", "")
    news = stock.get("news", "")
    combined = sector + news

    score = 5.0
    if any(kw in combined for kw in ["减速器", "谐波", "RV减速器", "丝杠"]):
        score = 8.5
    elif any(kw in combined for kw in ["伺服", "电机", "驱动器", "控制器"]):
        score = 7.5
    elif any(kw in combined for kw in ["传感器", "视觉", "PEEK"]):
        score = 8.0
    elif any(kw in combined for kw in ["芯片", "半导体", "存储"]):
        score = 7.5
    elif any(kw in combined for kw in ["轴承", "液压", "关节"]):
        score = 7.0
    elif any(kw in combined for kw in ["军工", "航天", "卫星"]):
        score = 6.5
    elif any(kw in combined for kw in ["碳纤维", "复材"]):
        score = 6.0
    return score


def _compute_all_school_tiers(stock):
    """为一只股票预计算所有8个流派的 tier 和 score。"""
    if not _HAS_SCHOOLS:
        return {"event": {"tier": stock.get("tier", 2), "score": stock.get("tier_score", 0.5), "strategy": stock.get("strategy", "催化剂博弈")}}
    chg = stock.get("chg", 0) or 0
    prior_limit = stock.get("limit_up", False) or is_real_limit_up(stock.get("code", ""), chg)
    sentiment = stock.get("sentiment", 3)
    cats = _infer_catalyst_types(stock.get("news", ""))

    strategy = stock.get("strategy", "催化剂博弈")
    confidence = _compute_stock_confidence(stock)
    three_high = _compute_stock_three_high(stock)
    sector = stock.get("sector", "")

    result = {}
    for school_id in ALL_SCHOOL_IDS:
        try:
            tier, score = compute_tier_for_school(
                sentiment_score=sentiment,
                catalyst_types=cats,
                confidence=confidence,
                strategy_tag=strategy,
                prior_day_limit_up=prior_limit,
                three_high_bonus=three_high,
                school=school_id,
            )
            result[school_id] = {"tier": tier, "score": round(score, 3), "strategy": strategy}
        except Exception:
            result[school_id] = {"tier": stock.get("tier", 2), "score": stock.get("tier_score", 0.5), "strategy": strategy}
    return result

# ── 读取模板文件 ──
def _read_template(filename: str) -> str:
    path = os.path.join(SHARED_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    print(f"[WARN] template not found: {path}", file=sys.stderr)
    return ""

TEMPLATE_CSS = _read_template("template_base.css")
TEMPLATE_JS = _read_template("template_base.js")

# ── 工具函数 ──
def _chg_cls(v: float) -> str:
    return "chg-up" if v >= 0 else "chg-down"

def _chg_sign(v: float) -> str:
    return f"+{v}" if v >= 0 else str(v)

def _esc(text: str) -> str:
    """HTML-escape text content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ── HTML 片段生成 ──

def _is_main_board(code: str) -> bool:
    """判断是否为主板/中小板（新手可交易），排除创业板(300/301)、科创板(688)、北交所(920/8xx)"""
    if not code or len(code) < 3:
        return False
    prefix = code[:3]
    return prefix not in ("300", "301", "688", "920", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839")


def _render_executive_summary(data: dict) -> str:
    """一句话总结卡片 — 放在 header 之后、KPI 之前"""
    summary = data.get("executive_summary", "")
    if not summary:
        # 自动从数据生成 fallback
        stocks = data.get("stocks", [])
        t1 = [s for s in stocks if s.get("tier") == 1]
        up_count = sum(1 for s in stocks if s.get("chg", 0) >= 0)
        avg_chg = round(sum(s.get("chg", 0) for s in stocks) / len(stocks), 2) if stocks else 0
        themes = list(set(s.get("sector", "") for s in t1))[:3]
        theme_str = "、".join(themes) if themes else "多板块"
        direction = "偏暖" if avg_chg > 0 else "分化调整"
        summary = f"{len(stocks)}只标的中{len(t1)}只强烈看好，核心主题集中在{theme_str}，整体情绪{direction}（均涨跌{avg_chg:+.2f}%），建议聚焦业绩确定性和产业链三高环节。"
    return f"""<div class="card summary-card" data-nav-section="overview" style="background:linear-gradient(135deg,var(--bg-card),color-mix(in srgb,var(--up) 8%,var(--bg-card)));border-left:3px solid var(--gold-light);">
    <div class="section-title" style="margin-bottom:4px;"><span class="icon">📋</span> 今日一句话总结</div>
    <p style="font-size:15px;line-height:1.7;color:var(--text-primary);margin:0;">{_esc(summary)}</p>
    </div>"""


def _is_main_board(code: str) -> bool:
    """新手可交易的主板/中小板"""
    if not code or len(code) < 3:
        return False
    prefix = code[:3]
    return prefix not in ("300","301","688","920","830","831","832","833","834","835","836","837","838","839")


def _render_executive_summary(data: dict) -> str:
    """一句话总结 — header下方、KPI上方"""
    summary = data.get("executive_summary", "")
    if not summary:
        stocks = data.get("stocks", [])
        t1 = [s for s in stocks if s.get("tier") == 1]
        up_count = sum(1 for s in stocks if s.get("chg", 0) >= 0)
        avg_chg = round(sum(s.get("chg", 0) for s in stocks) / len(stocks), 2) if stocks else 0
        themes = list(set(s.get("sector", "") for s in t1))[:3]
        theme_str = "、".join(themes) if themes else "多板块"
        direction = "偏暖" if avg_chg > 0 else "分化调整"
        summary = f"{len(stocks)}只标的中{len(t1)}只T1强烈看好,核心主题{theme_str},整体情绪{direction}(均涨跌{avg_chg:+.2f}%),建议聚焦业绩预增+产业链三高环节。"
    return f"""<div class="card summary-card" data-nav-section="overview" style="background:linear-gradient(135deg,var(--bg-card),color-mix(in srgb,var(--up) 8%,var(--bg-card)));border-left:3px solid var(--gold-light);">
    <div class="section-title" style="margin-bottom:4px;"><span class="icon">📋</span> 今日一句话总结</div>
    <p style="font-size:15px;line-height:1.7;color:var(--text-primary);margin:0;">{_esc(summary)}</p>
    </div>"""


def _render_kpi_cards(data: dict) -> str:
    t1 = [s for s in data.get("stocks", []) if s.get("tier") == 1]
    t2 = [s for s in data.get("stocks", []) if s.get("tier") == 2]
    t3 = [s for s in data.get("stocks", []) if s.get("tier") == 3]
    stocks = data.get("stocks", [])
    up_count = sum(1 for s in stocks if s.get("chg", 0) >= 0)
    up_ratio = round(up_count / len(stocks) * 100) if stocks else 0
    avg_chg = round(sum(s.get("chg", 0) for s in stocks) / len(stocks), 2) if stocks else 0
    core_theme = data.get("core_theme", data.get("query", "-"))
    return f"""<div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-value" style="color:var(--up)">{len(t1)}</div><div class="kpi-label">🔥 强烈看好</div><div class="kpi-sub">score >= 0.70</div></div>
    <div class="kpi-card"><div class="kpi-value" style="color:var(--blue)">{len(t2)}</div><div class="kpi-label">📈 看好</div><div class="kpi-sub">确定性中等</div></div>
    <div class="kpi-card"><div class="kpi-value" style="color:var(--t3)">{len(t3)}</div><div class="kpi-label">👀 关注</div><div class="kpi-sub">涨停次日/待确认</div></div>
    <div class="kpi-card"><div class="kpi-value" style="color:var(--up)">{up_ratio}%</div><div class="kpi-label">上涨占比</div><div class="kpi-sub">{up_count}/{len(stocks)} 只上涨</div></div>
    <div class="kpi-card"><div class="kpi-value" style="color:var(--gold-light)">{avg_chg}%</div><div class="kpi-label">平均涨跌</div><div class="kpi-sub">{_esc(core_theme[:20])}</div></div>
    </div>"""


def _render_stock_row(s: dict) -> str:
    limit_up = s.get("limit_up", False) or s.get("prior_day_limit_up", False)
    lu_badge = '<span class="limit-up-badge">涨停</span>' if limit_up else ""
    strategy = s.get("strategy", s.get("strategy_tag", "催化剂博弈"))
    if "回调" in strategy:
        sc = "tag-pullback"
    elif "突破" in strategy:
        sc = "tag-breakout"
    elif "趋势" in strategy:
        sc = "tag-momentum"
    else:
        sc = "tag-catalyst"
    tier = s.get("tier", s.get("school_tier", 2))
    # v5.1: multi-school data for client-side re-ranking
    school_scores_json = _json.dumps(s.get("_school_tiers", {}), ensure_ascii=False) if s.get("_school_tiers") else "{}"
    # 催化剂类型标签 (从 news 中推断)
    cat_label = _infer_cat_label(s.get('news', ''))

    # v5.2: 估值 + 技术指标列
    val = s.get("_valuation", {}) or {}
    pe_str = f'{val["pe_ttm"]:.1f}' if val.get("pe_ttm") is not None else '-'
    mcap_str = f'{val["market_cap"]:.0f}亿' if val.get("market_cap") is not None else '-'
    tech = s.get("_technical", {}) or {}
    tech_signal = tech.get("ma_trend", "") or tech.get("macd_signal", "") or "-"
    tech_badge = ""
    if "多头" in tech_signal or "金叉" in tech_signal:
        tech_badge = '<span style="color:var(--up);font-size:11px;">' + tech_signal + '</span>'
    elif "空头" in tech_signal or "死叉" in tech_signal:
        tech_badge = '<span style="color:var(--down);font-size:11px;">' + tech_signal + '</span>'
    else:
        tech_badge = '<span style="color:var(--text-muted);font-size:11px;">' + tech_signal[:4] + '</span>'

    return f"""<tr data-school-scores='{_esc(school_scores_json)}' data-tier="{tier}">
<td><span class="code">{_esc(str(s.get('code','')))}</span>{lu_badge}</td>
<td><span class="name">{_esc(str(s.get('name','')))}</span></td>
<td style="color:var(--text-secondary);font-size:12px;">{_esc(str(s.get('sector','')))}</td>
<td style="font-size:12px;">{_esc(cat_label)}</td>
<td style="font-size:12px;color:var(--text-secondary);max-width:240px;">{_esc(str(s.get('news',''))[:50])}</td>
<td class="price">{s.get('price','-')}</td>
<td class="{_chg_cls(s.get('chg',0))}">{_chg_sign(s.get('chg',0))}%</td>
<td style="font-size:12px;text-align:right;">{pe_str}</td>
<td style="font-size:12px;text-align:right;">{mcap_str}</td>
<td style="font-size:12px;">{tech_badge}</td>
<td><span class="tag {sc}">{_esc(strategy)}</span></td>
<td class="score">{s.get('tier_score', s.get('school_tier_score', s.get('score','-')))}</td>
</tr>"""


def _render_us_gainer_card(g: dict) -> str:
    price_str = f' <span style="color:var(--text-muted);font-size:12px;margin-left:4px;">{g.get("price","")}</span>' if g.get("price") else ""
    confirm = g.get("confirm", "弱确认")
    confirm_cls = "cross-confirm-strong" if "强" in str(confirm) else "cross-confirm-weak"
    confirm_text = g.get("confirm_text", "")
    return f"""<div class="us-gainer-card">
<span style="color:var(--text-muted);font-size:11px;">#{g.get('rank','-')}</span>
<span class="ticker">{_esc(str(g.get('ticker','')))}</span>
<span class="company">{_esc(str(g.get('company','')))}</span>
<span class="change">+{g.get('chg', g.get('change_pct', 0))}%</span>{price_str}
<div class="driver">📰 驱动：{_esc(str(g.get('driver','')))}</div>
<div class="map">🎯 A股映射：<strong>{_esc(str(g.get('theme',g.get('a_share_theme',''))))}</strong> — {_esc(str(g.get('a_stocks','')))} | 交叉确认：<span class="{confirm_cls}">● {_esc(confirm)}</span>
{('<span style="color:var(--text-muted);font-size:11px;display:block;margin-top:2px;">' + _esc(confirm_text) + '</span>') if confirm_text else ''}</div>
</div>"""


def _render_supply_chain(data: dict) -> str:
    sc = data.get("supply_chain", {})
    if not sc or not sc.get("has_data"):
        return '<div class="card"><div class="section-title"><span class="icon">🏭</span> 产业链三高分析</div><div class="empty-state"><span class="emoji">🏭</span>产业链分析未生成，不影响选股结果</div></div>'

    rows = ""
    for node in sc.get("nodes", []):
        # v5.1: 兼容多种字段名 - growth_rate/growth, gross_margin/margin, barrier_level/barrier, composite_score/three_high
        growth = node.get("growth_rate") or node.get("growth") or "-"
        margin = node.get("gross_margin") or node.get("margin") or "-"
        barrier = node.get("barrier_level") or node.get("barrier") or "-"
        score_val = node.get("composite_score") or node.get("three_high") or node.get("score") or 0
        try: score_val = float(score_val)
        except (TypeError, ValueError): score_val = 0
        is_3h = node.get("is_three_high", score_val >= 7.0)
        tr_cls = ' class="sc-3h"' if is_3h else ""
        badge = f'<span class="badge-3h">{score_val:.1f}</span>' if is_3h else f'{score_val:.1f}'
        leaders_raw = node.get("leader_names") or node.get("leaders") or "-"
        leaders = " / ".join(leaders_raw[:3]) if isinstance(leaders_raw, list) else str(leaders_raw)
        level = node.get("level") or node.get("tier") or ""
        name = node.get("name") or "-"
        rows += f"""<tr{tr_cls}><td>{_esc(str(level))} {_esc(str(name))}</td><td>{_esc(str(growth))}</td><td>{_esc(str(margin))}</td><td>{_esc(str(barrier))}</td><td>{badge}</td><td><span class="code">{_esc(str(leaders))}</span></td></tr>"""

    top_detail = ""
    if sc.get("top_segment"):
        top_leaders = "、".join(sc.get("top_segment_leaders", [])[:3]) or "-"
        top_detail = f'<div class="sc-detail-card"><strong>🔥 最优环节：{sc["top_segment"]}</strong> — 龙头：{top_leaders}</div>'

    return f"""<div class="card" data-nav-section="supply-chain">
<div class="section-title"><span class="icon">🏭</span> 产业链三高分析</div>
<div class="sc-summary">{_esc(str(sc.get('summary','')))}</div>
<table class="sc-table">
<thead><tr><th>层级/环节</th><th>增速</th><th>毛利率</th><th>壁垒</th><th>三高评分</th><th>龙头标的</th></tr></thead>
<tbody>{rows}</tbody>
</table>
{top_detail}
</div>"""


def _render_catchup_section(data: dict) -> str:
    """渲染板块补涨机会区块 (v5.3 — 预计算数据优先, 兼容多种数据格式)"""
    opps = data.get("catchup_opportunities", [])
    if not opps:
        return ""

    rows = ""
    for opp in opps[:5]:
        # 兼容: leaders 可以是字符串或dict列表
        leaders_raw = opp.get("leaders", [])
        if isinstance(leaders_raw, list) and leaders_raw and isinstance(leaders_raw[0], dict):
            leaders_str = "、".join(f"{l['name']}({l['code']})" for l in leaders_raw[:3])
        elif isinstance(leaders_raw, list):
            leaders_str = "、".join(str(l) for l in leaders_raw[:3])
        else:
            leaders_str = str(leaders_raw) if leaders_raw else "-"

        # 兼容: laggards/catchup 可以是字符串、字符串列表或dict列表
        laggards_raw = opp.get("laggards") or opp.get("catchup") or []
        if isinstance(laggards_raw, list) and laggards_raw and isinstance(laggards_raw[0], dict):
            laggards_str = "、".join(f"{l['name']}({l['code']} {l.get('chg',0):+.1f}%)" for l in laggards_raw[:6])
        elif isinstance(laggards_raw, list):
            laggards_str = "、".join(str(l) for l in laggards_raw[:6])
        else:
            laggards_str = str(laggards_raw) if laggards_raw else "-"

        # 兼容: leader可以是单个字符串或dict
        leader_raw = opp.get("leader", "")
        if isinstance(leader_raw, dict):
            leader_str = f"{leader_raw.get('name','')}({leader_raw.get('code','')})"
        else:
            leader_str = str(leader_raw) if leader_raw else ""

        note = opp.get("note", "")
        heat = opp.get("heat_score", 0)
        leader_avg = opp.get("leader_avg_chg", 0)

        rows += f"""<div class="catchup-card">
    <span class="catchup-sector">{_esc(opp.get('sector',''))}</span>
    <span style="color:var(--gold-light);margin-left:8px;">{f"热度 {heat:.1f}" if heat else ""}</span>
    {f'<span style="color:var(--text-secondary);margin-left:8px;">龙头均涨幅 +{leader_avg:.1f}%</span>' if leader_avg else ''}
    <div class="catchup-leaders">龙头: {_esc(leaders_str or leader_str or '-')}</div>
    <div class="catchup-laggards">补涨候选: {_esc(laggards_str)}</div>
    {f'<div style="color:var(--text-muted);font-size:11px;margin-top:4px;">{_esc(note)}</div>' if note else ''}
    </div>"""

    return f"""<div class="card" data-nav-section="catchup">
    <div class="section-title"><span class="icon">🔗</span> 板块联动补涨机会 <span style="color:var(--text-muted);font-size:11px;font-weight:normal;">v5.3 · 同板块龙头涨停带动低涨幅标的补涨效应</span></div>
    {rows}
    </div>"""


def _render_outlook(data: dict) -> str:
    outlooks = data.get("outlook", [])
    if not outlooks:
        outlooks = [
            {"title": "📌 持续性主题", "desc": "关注主线板块的持续性和资金流向", "style": "bullish"},
            {"title": "⚡ 短期催化剂", "desc": "关注近期政策和业绩窗口期的催化机会", "style": "bullish"},
            {"title": "🛡️ 风险提示", "desc": "涨停次日标的注意分化风险；板块过热标的控制仓位", "style": "caution"},
        ]
    cards = ""
    for o in outlooks:
        style = o.get("style", "neutral")
        cards += f'<div class="outlook-card {style}"><div class="ol-title">{_esc(o["title"])}</div><div class="ol-desc">{_esc(o["desc"])}</div></div>'

    # ── 时间判定 ──
    from datetime import datetime
    now = datetime.now()
    hour = now.hour

    if 9 <= hour < 15 and now.weekday() < 5:
        time_note = "盘中"
        time_tip = "主力资金活跃时段,关注量能变化和板块轮动方向"
    elif 15 <= hour < 21:
        time_note = "盘后"
        time_tip = "复盘今日走势,结合新闻面筛选明日标的"
    else:
        time_note = "盘前"
        time_tip = "隔夜美股和早间新闻将影响今日开盘方向"

    # ── v5.3: 持仓比例建议 ──
    school = data.get("school", "event")
    if school in ("speculative", "short_term"):
        position_pct = "30%-50%"
        position_note = "短线/投机风格可适度提高仓位,但严格止损(建议-5%止损线)"
    elif school in ("value", "macro"):
        position_pct = "15%-25%"
        position_note = "价值/宏观风格仓位适中,分批建仓,金字塔加仓(跌5%加仓1/3)"
    elif school == "growth":
        position_pct = "20%-35%"
        position_note = "成长风格中高仓位,集中持仓3-5只核心标的"
    elif school == "technical":
        position_pct = "20%-30%"
        position_note = "技术分析风格仓位灵活,破位即止损,站稳加仓"
    else:  # event / quant
        position_pct = "20%-30%"
        position_note = "事件驱动风格中等仓位,单票不超过总仓位15%,分批进出"

    # ── 今日操作建议 ──
    today_all = data.get("today_suggestions", {}).get("all_market",
        "关注主线板块回调机会,T1标的优先关注,逢低分批建仓。T2标的关注盘中量能变化,放量突破可跟进。")
    today_main = data.get("today_suggestions", {}).get("main_board",
        "优先关注主板业绩确定性高且流动性好的标的,回调至均线支撑可分批介入。")
    today_beginner = data.get("today_suggestions", {}).get("beginner",
        "新手建议控制仓位在{0}以内,优先选择成交额大(>10亿)的主板标的,不追涨停板。".format(position_pct))

    # ── 明日预判 ──
    tomorrow_all = data.get("tomorrow_suggestions", {}).get("all_market",
        "明日关注主线板块持续性和新催化剂,业绩预增线持续发酵,回调至5日/10日均线可加仓。")
    tomorrow_main = data.get("tomorrow_suggestions", {}).get("main_board",
        "明日主板关注回调企稳信号,业绩确定性标的优先,分批介入不追高。")
    tomorrow_beginner = data.get("tomorrow_suggestions", {}).get("beginner",
        "明日若板块回调3%-5%,可轻仓试探性买入。建议优先选择成交额大(>30亿)、机构持仓稳定的标的。不要一次性满仓,分批买入。")

    def _rsug(items, fallback=""):
        if isinstance(items, list):
            return "".join(f"<li>{_esc(s)}</li>" for s in items)
        return f"<li>{_esc(items if items else fallback)}</li>"

    return f"""<div class="card" data-nav-section="outlook">
    <div class="section-title"><span class="icon">🔮</span> 市场预判 <span style="color:var(--text-muted);font-size:11px;font-weight:normal;">当前: {now.strftime("%H:%M")} {time_note} · {time_tip}</span></div>
    <div class="outlook-grid">{cards}</div>
    </div>

    <!-- ═══ v5.3: 今日操作建议 (独立区块) ═══ -->
    <div class="card" data-nav-section="today-ops" style="border-left:3px solid var(--up);">
    <div class="section-title"><span class="icon">📊</span> 今日操作建议 <span style="color:var(--text-muted);font-size:11px;font-weight:normal;">{time_note} · 推荐仓位: {position_pct}</span></div>
    <div style="margin-bottom:12px;padding:10px 14px;background:color-mix(in srgb,var(--gold-light) 10%,transparent);border-radius:6px;font-size:13px;color:var(--text-secondary);">
    <strong>💰 持仓策略</strong>: {_esc(position_note)}<br>
    <strong>📋 建议持仓比例</strong>: T1标的 40-50% | T2标的 30-35% | T3标的 15-20% | 现金预留 5-10%
    </div>
    <div class="strategy-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
    <div class="strategy-box">
    <h3>🟢 今日操作（全市场）</h3>
    <p style="color:var(--text-secondary);font-size:12px;margin:4px 0 8px;">含创业板/科创板/北交所,适合有权限的投资者 | 推荐仓位 {position_pct}</p>
    <ul>{_rsug(today_all)}</ul>
    </div>
    <div class="strategy-box" style="border-left:3px solid var(--blue);">
    <h3>🔵 今日操作（新手适用 · 仅主板/中小板）</h3>
    <p style="color:var(--text-secondary);font-size:12px;margin:4px 0 8px;">仅含000/001/002/003/600/601/603/605代码,新手可直接交易 | 推荐仓位 10%-20%</p>
    <ul>{_rsug(today_main)}</ul>
    <div style="margin-top:8px;font-size:12px;color:var(--text-muted);padding:8px;background:color-mix(in srgb,var(--blue) 8%,transparent);border-radius:4px;">
    <strong>新手提示</strong>: {_esc(today_beginner)}
    </div>
    </div>
    </div>
    </div>

    <!-- ═══ v5.3: 明日预判 (独立区块) ═══ -->
    <div class="card" data-nav-section="tomorrow-outlook" style="border-left:3px solid var(--gold-light);">
    <div class="section-title"><span class="icon">🔭</span> 明日预判与操作 <span style="color:var(--text-muted);font-size:11px;font-weight:normal;">基于最新行情与新闻面的前瞻性推断</span></div>
    <div class="strategy-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
    <div class="strategy-box">
    <h3>🔴 明日预判（全市场）</h3>
    <p style="color:var(--text-secondary);font-size:12px;margin:4px 0 8px;">基于产业趋势和市场情绪的次日推断</p>
    <ul>{_rsug(tomorrow_all)}</ul>
    </div>
    <div class="strategy-box" style="border-left:3px solid var(--gold-light);">
    <h3>🟡 明日预判（新手适用 · 仅主板/中小板）</h3>
    <p style="color:var(--text-secondary);font-size:12px;margin:4px 0 8px;">不含创业板(300/301)、科创板(688)、北交所(920/8xx),新手可直接参考</p>
    <ul>{_rsug(tomorrow_main)}</ul>
    <div style="margin-top:8px;font-size:12px;color:var(--text-muted);padding:8px;background:color-mix(in srgb,var(--gold) 8%,transparent);border-radius:4px;">
    <strong>新手提示</strong>: {_esc(tomorrow_beginner)}
    </div>
    </div>
    </div>
    </div>

    <div style="margin-top:16px;padding:12px;background:color-mix(in srgb,var(--text-muted) 8%,transparent);border-radius:8px;font-size:12px;color:var(--text-muted);">
    <strong>新手提示</strong>: A股代码前缀含义 — 000/001/002/003 深圳主板中小板 | 600/601/603/605 上海主板 | 300/301 创业板(2年经验+10万资产) | 688 科创板(2年+50万) | 920/8xx 北交所(2年+50万)。新手建议从主板(6开头/0开头)开始交易,流动性更好。
    </div>"""


# ── v5.0: 流派筛选片段 ──

SCHOOL_INFO = [
    ("event", "📰 事件驱动", "新闻/政策/大事件驱动，对催化剂最敏感"),
    ("value", "💎 价值投资", "低PE/高股息/高ROE，长期持有"),
    ("growth", "🚀 成长投资", "高营收增速/高研发，长线潜力大"),
    ("short_term", "⚡ 短线交易", "快进快出，高换手高弹性小盘"),
    ("technical", "📊 技术分析", "K线形态/量价指标，抓趋势看图表"),
    ("quant", "🤖 量化交易", "多因子均衡，数据建模程序交易"),
    ("macro", "🌍 宏观投资", "经济周期/行业轮动，三高权重最高"),
    ("speculative", "🎰 投机派", "高风险高收益，追热点小盘博弈"),
]

def _render_school_tabs(data: dict) -> str:
    """渲染流派选择tab栏 — v5.3: 仅显示数据中实际包含的流派，默认显示用户所选流派"""
    default_school = data.get("school", "event")
    # v5.3: 检查数据中实际预计算了哪些流派的tier数据
    stocks = data.get("stocks", [])
    available_schools = set()
    for s in stocks:
        school_tiers = s.get("_school_tiers", {})
        for sid in school_tiers:
            available_schools.add(sid)
    # 如果数据中没有预计算信息（旧版兼容），显示所有流派
    if not available_schools:
        available_schools = set(ALL_SCHOOL_IDS)
    # 确保默认流派在列表中
    available_schools.add(default_school)

    tabs = ""
    first_rendered = False
    for sch_id, sch_label, sch_desc in SCHOOL_INFO:
        if sch_id not in available_schools:
            continue  # 跳过未运行的流派
        # 默认激活用户选择的流派
        active = ' active' if sch_id == default_school else ''
        if sch_id == default_school:
            first_rendered = True
        tabs += f'<button class="school-tab{active}" data-school="{sch_id}" title="{_esc(sch_desc)}">{sch_label}</button>'
    # 如果用户流派不在标准列表中，也添加一个tab
    if not first_rendered and default_school in SCHOOL_LABELS:
        tabs = f'<button class="school-tab active" data-school="{default_school}" title="当前选股流派">{SCHOOL_LABELS[default_school]}</button>' + tabs

    school_count = len([s for s in SCHOOL_INFO if s[0] in available_schools])
    return f'<div class="card" id="school-filter"><div class="section-title"><span class="icon">🎯</span> 投资流派视角 <span style="color:var(--text-muted);font-size:11px;font-weight:normal;margin-left:8px;">当前：{SCHOOL_LABELS.get(default_school, default_school)} · 点击切换不同流派的选股排序</span></div><div class="school-tabs">{tabs}</div></div>'

def _render_school_legend() -> str:
    """渲染流派图例"""
    items = ""
    for sch_id, sch_label, _ in SCHOOL_INFO:
        items += f'<span class="school-legend-item" data-school="{sch_id}">{sch_label}</span>'
    return f'<div class="school-legend" style="display:none;">{items}</div>'

# ── 主生成函数 ──

def generate_html(data: dict) -> str:
    """从结构化数据生成完整 HTML 报告。"""
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    query = data.get("query", "新闻驱动选股")
    stock_count = len(data.get("stocks", []))

    # v5.1: 预计算所有流派 tier（注入到每只股票数据中）
    for s in data.get("stocks", []):
        if not s.get("_school_tiers"):
            s["_school_tiers"] = _compute_all_school_tiers(s)

    # v5.2: 获取估值数据 (PE/市值/换手率) — 仅用腾讯快速获取PE
    stock_codes = [s.get("code", "") for s in data.get("stocks", []) if s.get("code")]
    _valuations = {}
    if stock_codes:
        try:
            from data_sources import _fetch_price_tencent_qt
            for code in stock_codes[:30]:
                try:
                    d = _fetch_price_tencent_qt("A", code)
                    if d and d.get("price"):
                        _valuations[code] = {
                            "pe_ttm": d.get("pe_ttm"),
                            "pb": d.get("pb"),
                            "market_cap": None,
                            "turnover_rate": None,
                            "_source": "tencent-qt",
                        }
                except Exception:
                    pass
        except Exception:
            pass
    for s in data.get("stocks", []):
        code = s.get("code", "")
        if code in _valuations:
            s["_valuation"] = _valuations[code]

    # 分层（按默认 event 流派）
    t1 = [s for s in data.get("stocks", []) if s.get("tier") == 1]
    t2 = [s for s in data.get("stocks", []) if s.get("tier") == 2]
    t3 = [s for s in data.get("stocks", []) if s.get("tier") == 3]

    # v5.1: 所有流派汇总数据
    school_summary = {}
    for sid in ALL_SCHOOL_IDS:
        st1 = sum(1 for s in data.get("stocks", []) if s.get("_school_tiers", {}).get(sid, {}).get("tier") == 1)
        st2 = sum(1 for s in data.get("stocks", []) if s.get("_school_tiers", {}).get(sid, {}).get("tier") == 2)
        st3 = sum(1 for s in data.get("stocks", []) if s.get("_school_tiers", {}).get(sid, {}).get("tier") == 3)
        school_summary[sid] = {"t1": st1, "t2": st2, "t3": st3}
    school_summary_json = _json.dumps(school_summary, ensure_ascii=False)

    # 美股映射
    us_gainers_html = ""
    us_list = data.get("us_gainers", [])
    if us_list:
        us_gainers_html = "".join(_render_us_gainer_card(g) for g in us_list)
    else:
        us_gainers_html = '<div class="empty-state"><span class="emoji">🌙</span>今日无显著美股→A股映射信号</div>'

    # 涨停提醒
    limit_up_stocks = [s for s in t3 if s.get("limit_up") or s.get("prior_day_limit_up")]
    warn_box = ""
    if limit_up_stocks:
        codes = "、".join(s.get("code", "?") for s in limit_up_stocks)
        warn_box = f"""<div class="warning-box" id="tier3-warn-box">
<div class="warn-title">⚠️ 涨停次日熔断提醒</div>
<div class="warn-body">{len(limit_up_stocks)}只标的今日涨停（{codes}），根据Tier引擎规则已强制降为T3。涨停次日追高风险较大，建议等待回调确认后再考虑介入。</div>
</div>"""

    # 板块过热
    overheat_html = ""
    overheat = data.get("overheat_warnings", [])
    if overheat:
        for oh in overheat:
            overheat_html += f'<div class="overheat-warn">⚠️ {oh["sector"]}板块占比 {oh["ratio"]*100:.0f}% ({oh["count"]}只)，超过30%上限需关注分化风险</div>'
        overheat_html = f'<div class="card"><div class="section-title"><span class="icon">⚠️</span> 板块集中度预警</div>{overheat_html}</div>'

    # 报告数据注入
    report_data = {
        "sectors": data.get("sectors", []),
        "sentiment": {"t1_count": len(t1), "t2_count": len(t2), "t3_count": len(t3)},
        "stocks": [{"code": s.get("code", ""), "name": s.get("name", ""), "kline_data": s.get("kline_data", [])} for s in data.get("stocks", [])],
    }
    report_data_json = _json.dumps(report_data, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>新闻选股日报 · {today_str}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>
<style>
/* ═══ shared/template_base.css ═══ */
{TEMPLATE_CSS}
</style>
</head>
<body>

<nav class="top-nav">
  <div class="logo">
    <div class="logo-icon">N</div>
    <div>
      <div class="nav-title">新闻选股日报</div>
      <div class="nav-meta">{today_str} · {_esc(query[:30])} · {stock_count} 只标的</div>
    </div>
  </div>
  <div class="nav-links">
    <a href="#overview" class="active">概览</a>
    <a href="#supply-chain">产业链</a>
    <a href="#us-gainers">美股映射</a>
    <a href="#catchup">补涨</a>
    <a href="#tier1">T1</a>
    <a href="#tier2">T2</a>
    <a href="#tier3">T3</a>
    <a href="#outlook">预判</a>
  </div>
  <button class="theme-toggle" id="themeToggle">☀️ 浅色模式</button>
</nav>

<div class="container">

<div class="card header" data-nav-section="overview">
  <div class="badge">News-Driven Stock Selection</div>
  <h1>新闻选股日报</h1>
  <div class="meta">
    <span>📅 {today_str}</span>
    <span>🔍 {_esc(query[:40])}</span>
    <span>📊 {stock_count} 只标的</span>
  </div>
</div>

{_render_executive_summary(data)}

{_render_kpi_cards(data)}

{_render_supply_chain(data)}

<div class="card" data-nav-section="us-gainers">
  <div class="section-title"><span class="icon">🇺🇸</span> 隔夜美股 → A股主题映射</div>
  {us_gainers_html}
</div>

{_render_school_tabs(data)}

<div class="card" data-nav-section="tier1">
  <div class="section-title"><span class="icon">🔥</span> 强烈看好 <span class="tier-badge tier-t1">T1</span></div>
  <table class="stock-table">
    <thead><tr><th>代码</th><th>名称</th><th>板块</th><th>利好</th><th>催化剂</th><th>现价</th><th>涨跌</th><th>PE</th><th>市值</th><th>技术</th><th>策略</th><th>评分</th></tr></thead>
    <tbody>{"".join(_render_stock_row(s) for s in t1) if t1 else '<tr><td colspan="12" style="text-align:center;color:var(--text-muted);padding:20px;">暂无 T1 标的</td></tr>'}</tbody>
  </table>
</div>

<div class="card" data-nav-section="tier2">
  <div class="section-title"><span class="icon">📈</span> 看好 <span class="tier-badge tier-t2">T2</span></div>
  <table class="stock-table">
    <thead><tr><th>代码</th><th>名称</th><th>板块</th><th>利好</th><th>催化剂</th><th>现价</th><th>涨跌</th><th>PE</th><th>市值</th><th>技术</th><th>策略</th><th>评分</th></tr></thead>
    <tbody>{"".join(_render_stock_row(s) for s in t2) if t2 else '<tr><td colspan="12" style="text-align:center;color:var(--text-muted);padding:20px;">暂无 T2 标的</td></tr>'}</tbody>
  </table>
</div>

<div class="card" data-nav-section="tier3">
  <div class="section-title"><span class="icon">👀</span> 关注 <span class="tier-badge tier-t3">T3</span></div>
  {warn_box}
  <table class="stock-table">
    <thead><tr><th>代码</th><th>名称</th><th>板块</th><th>利好</th><th>催化剂</th><th>现价</th><th>涨跌</th><th>PE</th><th>市值</th><th>技术</th><th>策略</th><th>评分</th></tr></thead>
    <tbody>{"".join(_render_stock_row(s) for s in t3) if t3 else '<tr><td colspan="12" style="text-align:center;color:var(--text-muted);padding:20px;">暂无 T3 标的</td></tr>'}</tbody>
  </table>
</div>

{overheat_html}

{_render_catchup_section(data)}

{_render_outlook(data)}

<div class="footer">
  <strong>免责声明</strong>：本报告由AI自动生成，基于公开新闻和实时行情数据，仅供参考，不构成投资建议。股市有风险，投资需谨慎。<br>
  数据源: 同花顺(美股涨幅榜) + Exa/Bing(新闻搜索) + 腾讯qt(A股实时行情)。Tier评分基于量化模型。<br>
  Generated by news-stock-selector v5.2 · {today_str}
</div>

</div>

<script>
window.__REPORT_DATA__ = {report_data_json};
window.__SCHOOL_DATA__ = {school_summary_json};
</script>
<script>
/* ═══ shared/template_base.js ═══ */
{TEMPLATE_JS}
</script>
</body>
</html>"""


def main():
    # 读取输入数据
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        with open(input_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
    else:
        data = _json.load(sys.stdin)

    # 确定日期
    date_str = data.get("date", date.today().strftime("%Y%m%d"))
    if len(date_str) == 8:
        filename = f"新闻选股日报_{date_str}.html"
    else:
        filename = f"新闻选股日报_{date.today().strftime('%Y%m%d')}.html"

    # 生成 HTML
    html = generate_html(data)

    # 写入
    output_path = os.path.join(OUTPUT_DIR, filename)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"OK: {output_path} ({size_kb:.1f} KB)")
    print(f"  Stocks: {len(data.get('stocks',[]))} | US Gainers: {len(data.get('us_gainers',[]))} | Supply Chain: {bool(data.get('supply_chain',{}).get('has_data'))}")
    print(f"  CSS: {'loaded' if TEMPLATE_CSS else 'MISSING'} ({len(TEMPLATE_CSS):,} chars)")
    print(f"  JS:  {'loaded' if TEMPLATE_JS else 'MISSING'} ({len(TEMPLATE_JS):,} chars)")

    # 自动打开
    if os.environ.get("NEWS_STOCK_AUTO_OPEN", "1") == "1":
        os.startfile(output_path)


if __name__ == "__main__":
    main()

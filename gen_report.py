#!/usr/bin/env python
"""新闻选股日报 HTML 报告生成器 v4.1
集成 shared/template_base.css (双主题CSS) + shared/template_base.js (图表+交互)
"""
import os
from datetime import date

today = date.today().strftime('%Y%m%d')
today_display = f'{today[:4]}-{today[4:6]}-{today[6:]}'

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(SKILL_DIR, 'shared')

def read_template(filename):
    path = os.path.join(SHARED_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    print(f'WARN: template file not found: {path}')
    return ''

TEMPLATE_CSS = read_template('template_base.css')
TEMPLATE_JS  = read_template('template_base.js')

# ── 工具函数 ──
def chg_class(v):
    return 'chg-up' if v >= 0 else 'chg-down'

def chg_sign(v):
    return f'+{v}' if v >= 0 else str(v)

# ── 样本数据（实际使用时由 AI / 数据源填充） ──
stocks = [
    {"tier":1,"code":"603986","name":"兆易创新","price":500.5,"chg":5.59,"sector":"存储/半导体","strategy":"催化剂博弈","score":0.931,"news":"长鑫科技IPO过会(关联交易57亿)；2025净利预增46%；英伟达SK海力士合作下一代AI内存"},
    {"tier":1,"code":"688256","name":"寒武纪","price":1270.01,"chg":1.57,"sector":"AI芯片","strategy":"催化剂博弈","score":0.905,"news":"2025扭亏为盈净利20.59亿；昇腾910C突破利好国产算力链；AI算力需求爆发"},
    {"tier":1,"code":"300502","name":"新易盛","price":785.73,"chg":8.38,"sector":"光模块/AI算力","strategy":"催化剂博弈","score":0.874,"news":"2025净利94-99亿同比增231-249%；光纤预制棒价格暴涨550%；光模块CPO重回强势"},
    {"tier":1,"code":"300308","name":"中际旭创","price":1180.0,"chg":2.17,"sector":"光模块/AI算力","strategy":"催化剂博弈","score":0.874,"news":"2025净利98-118亿同比增90-128%；台积电资本开支验证AI算力长期需求；光模块全球龙头"},
    {"tier":1,"code":"002371","name":"北方华创","price":617.1,"chg":5.35,"sector":"半导体设备","strategy":"催化剂博弈","score":0.861,"news":"华为韬定律发布带动先进封装需求；国产替代加速；半导体设备景气上行"},
    {"tier":1,"code":"002475","name":"立讯精密","price":69.34,"chg":4.84,"sector":"消费电子/AI硬件","strategy":"催化剂博弈","score":0.861,"news":"2025净利165-172亿增24-29%；AI端侧硬件+数据中心互联+机器人战略布局"},
    {"tier":1,"code":"688017","name":"绿的谐波","price":420.17,"chg":-1.89,"sector":"机器人","strategy":"回调低吸","score":0.828,"news":"宇树科技IPO过会；英伟达开放人形机器人参考设计；国常会推进智能制造；今日回调低吸机会"},
    {"tier":1,"code":"002600","name":"领益智造","price":14.86,"chg":3.63,"sector":"AI硬件/液冷","strategy":"催化剂博弈","score":0.746,"news":"港股IPO通过聆讯；英伟达认证液冷+AI服务器电源双驱动；物理AI布局"},
    {"tier":2,"code":"300604","name":"长川科技","price":212.73,"chg":6.15,"sector":"半导体设备","strategy":"催化剂博弈","score":0.68,"news":"半导体设备国产替代加速；科创板集成电路净利增86.3%"},
    {"tier":3,"code":"603929","name":"亚翔集成","price":205.81,"chg":10.0,"sector":"半导体洁净室","strategy":"突破追击-T3","score":0.68,"news":"2025净利目标达成率161%；半导体基建政策驱动；今日涨停(涨停次日暂观望)","limit_up":True},
    {"tier":3,"code":"605111","name":"新洁能","price":61.99,"chg":10.01,"sector":"功率半导体","strategy":"突破追击-T3","score":0.48,"news":"瑞银上调至买入目标81.3元；碳化硅新超级周期；今日涨停(涨停次日暂观望)","limit_up":True},
]

us_gainers = [
    {"rank":1,"ticker":"CHAI","company":"Core AI Holdings","chg":249.39,"price":"$2.87","driver":"OpenAI秘密提交S-1注册声明，引发AI概念小盘股投机狂潮","theme":"AI应用/大模型","a_stocks":"寒武纪(688256)、中际旭创(300308)","confirm":"强确认","confirm_cls":"cross-confirm-strong","confirm_text":"智谱AI拟募资150亿冲刺科创板；华为昇腾910C完成1.6万亿参数DeepSeek全参数训练"},
    {"rank":2,"ticker":"NUVL","company":"Nuvalent","chg":38.86,"price":"$122.88","driver":"GSK以106亿美元现金收购，溢价40%，获三款肺癌创新药管线","theme":"创新药/CXO","a_stocks":"药明康德(603259)、君实生物(688180)","confirm":"弱确认","confirm_cls":"cross-confirm-weak","confirm_text":"超50家生物医药A股公司2025年业绩预盈；国产创新药出海业绩亮眼"},
    {"rank":3,"ticker":"SOX","company":"费城半导体指数","chg":5.6,"price":"","driver":"台积电重申520-560亿美金资本开支；英伟达SK海力士合作AI内存；英特尔获谷歌/英伟达订单","theme":"AI芯片/半导体设备","a_stocks":"北方华创(002371)、兆易创新(603986)、长川科技(300604)","confirm":"强确认","confirm_cls":"cross-confirm-strong","confirm_text":"长鑫科技IPO过会市值冲击2万亿；华为韬定律发布；瑞银:功率半导体新超级周期"},
]

t1 = [s for s in stocks if s['tier']==1]
t2 = [s for s in stocks if s['tier']==2]
t3 = [s for s in stocks if s['tier']==3]

up_count = sum(1 for s in stocks if s['chg'] >= 0)
up_ratio = round(up_count / len(stocks) * 100) if stocks else 0
avg_chg = round(sum(s['chg'] for s in stocks) / len(stocks), 2) if stocks else 0

def stock_row(s):
    lu = '<span class="limit-up-badge">涨停</span>' if s.get('limit_up') else ''
    sc = 'tag-catalyst' if '催化剂' in s['strategy'] else 'tag-pullback' if '回调' in s['strategy'] else 'tag-breakout'
    return f'''<tr>
<td><span class="code">{s['code']}</span>{lu}</td>
<td><span class="name">{s['name']}</span></td>
<td style="color:var(--text-secondary);font-size:12px;">{s['sector']}</td>
<td style="font-size:12px;">-</td>
<td style="font-size:12px;color:var(--text-secondary);">{s['news'][:40]}...</td>
<td class="price">{s['price']}</td>
<td class="{chg_class(s['chg'])}">{chg_sign(s['chg'])}%</td>
<td><span class="tag {sc}">{s['strategy']}</span></td>
<td class="score">{s['score']}</td>
</tr>'''

def us_card(g):
    price_str = f' <span style="color:var(--text-muted);font-size:12px;margin-left:4px;">{g["price"]}</span>' if g['price'] else ''
    return f'''<div class="us-gainer-card">
<span style="color:var(--text-muted);font-size:11px;">#{g['rank']}</span>
<span class="ticker">{g['ticker']}</span>
<span class="company">{g['company']}</span>
<span class="change">+{g['chg']}%</span>{price_str}
<div class="driver">📰 驱动：{g['driver']}</div>
<div class="map">🎯 A股映射：<strong>{g['theme']}</strong> — {g['a_stocks']} | 交叉确认：<span class="{g['confirm_cls']}">● {g['confirm']}</span>
<span style="color:var(--text-muted);font-size:11px;display:block;margin-top:2px;">{g['confirm_text']}</span></div>
</div>'''

limit_up_t3 = any(s.get('limit_up') for s in t3)
warn_box = f'''<div class="warning-box">
<div class="warn-title">⚠️ 涨停次日熔断提醒</div>
<div class="warn-body">以下{sum(1 for s in t3 if s.get('limit_up'))}只标的今日涨停，根据Tier引擎规则已强制降为T3。涨停次日追高风险较大，建议等待回调确认后再考虑介入。</div>
</div>''' if limit_up_t3 else ''

# ── 数据注入 JSON（供 template_base.js 的 ECharts 使用） ──
import json as _json
report_data = {
    "sectors": [
        {"name": "光模块/AI算力", "chg": 5.27},
        {"name": "半导体设备", "chg": 5.75},
        {"name": "AI芯片", "chg": 1.57},
        {"name": "机器人", "chg": -1.89},
        {"name": "AI硬件/液冷", "chg": 3.63},
        {"name": "功率半导体", "chg": 10.01},
    ],
    "sentiment": {
        "t1_count": len(t1),
        "t2_count": len(t2),
        "t3_count": len(t3),
    },
    "stocks": [
        {"code": s['code'], "name": s['name'], "kline_data": []}
        for s in stocks
    ],
}
REPORT_DATA_JSON = _json.dumps(report_data, ensure_ascii=False, indent=2)

# ── 组装 HTML ──
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>新闻选股日报 · {today_display}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>
<style>
/* ═══ 从 shared/template_base.css 完整复制 ═══ */
{TEMPLATE_CSS}
</style>
</head>
<body>

<!-- ═══ 顶部导航 ═══ -->
<nav class="top-nav">
  <div class="logo">
    <div class="logo-icon">N</div>
    <div>
      <div class="nav-title">新闻选股日报</div>
      <div class="nav-meta">{today_display} · AI算力+半导体主线 · {len(stocks)} 只标的</div>
    </div>
  </div>
  <div class="nav-links">
    <a href="#overview" class="active">概览</a>
    <a href="#supply-chain">产业链</a>
    <a href="#us-gainers">美股映射</a>
    <a href="#tier1">T1</a>
    <a href="#tier2">T2</a>
    <a href="#tier3">T3</a>
    <a href="#outlook">预判</a>
  </div>
  <button class="theme-toggle" id="themeToggle">☀️ 浅色模式</button>
</nav>

<div class="container">

  <!-- ═══ Header ═══ -->
  <div class="card header" data-nav-section="overview">
    <div class="badge">News-Driven Stock Selection</div>
    <h1>新闻选股日报</h1>
    <div class="meta">
      <span>📅 {today_display}</span>
      <span>🔍 AI算力+半导体</span>
      <span>📊 {len(stocks)} 只标的</span>
    </div>
  </div>

  <!-- ═══ KPI 概览 ═══ -->
  <div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-value" style="color:var(--up)">{len(t1)}</div><div class="kpi-label">🔥 强烈看好</div><div class="kpi-sub">score >= 0.70</div></div>
    <div class="kpi-card"><div class="kpi-value" style="color:var(--blue)">{len(t2)}</div><div class="kpi-label">📈 看好</div><div class="kpi-sub">确定性中等</div></div>
    <div class="kpi-card"><div class="kpi-value" style="color:var(--t3)">{len(t3)}</div><div class="kpi-label">👀 关注</div><div class="kpi-sub">涨停次日观察</div></div>
    <div class="kpi-card"><div class="kpi-value" style="color:var(--up)">{up_ratio}%</div><div class="kpi-label">上涨占比</div><div class="kpi-sub">{up_count}/{len(stocks)} 只上涨</div></div>
    <div class="kpi-card"><div class="kpi-value" style="color:var(--gold-light)">{avg_chg}%</div><div class="kpi-label">平均涨跌</div><div class="kpi-sub">AI算力+半导体主线</div></div>
  </div>

  <!-- ═══ 板块涨跌图表 (ECharts) ═══ -->
  <div class="card" data-nav-section="supply-chain">
    <div class="section-title"><span class="icon">📊</span> 板块涨跌一览</div>
    <div class="chart-container" id="chart-sector-bar"></div>
  </div>

  <!-- ═══ 产业链三高分析 ═══ -->
  <div class="card">
    <div class="section-title"><span class="icon">🏭</span> 产业链三高分析</div>
    <div class="sc-summary">AI算力产业链 — 上游光芯片/存储为最优环节，中游设备制造跟随，下游应用待爆发</div>
    <table class="sc-table">
      <thead><tr><th>层级</th><th>环节</th><th>增速</th><th>毛利率</th><th>壁垒</th><th>三高评分</th><th>龙头标的</th></tr></thead>
      <tbody>
        <tr class="sc-3h"><td>⬆️ 上游</td><td>光芯片/光模块</td><td>35%+</td><td>50-65%</td><td>极高</td><td><span class="badge-3h">9.7</span></td><td><span class="code">300502</span> / <span class="code">300308</span></td></tr>
        <tr class="sc-3h"><td>⬆️ 上游</td><td>AI芯片/GPU</td><td>40%+</td><td>55-70%</td><td>极高</td><td><span class="badge-3h">9.5</span></td><td><span class="code">688256</span></td></tr>
        <tr class="sc-3h"><td>⬆️ 上游</td><td>存储芯片</td><td>25-30%</td><td>35-50%</td><td>极高</td><td><span class="badge-3h">8.8</span></td><td><span class="code">603986</span></td></tr>
        <tr><td>⬆️ 中游</td><td>半导体设备</td><td>20-25%</td><td>40-50%</td><td>高</td><td>8.2</td><td><span class="code">002371</span> / <span class="code">300604</span></td></tr>
        <tr><td>⬆️ 中游</td><td>封装测试</td><td>12-18%</td><td>20-30%</td><td>中</td><td>6.5</td><td><span class="code">002600</span></td></tr>
        <tr><td>⬇️ 下游</td><td>AI服务器/数据中心</td><td>30%+</td><td>15-25%</td><td>中</td><td>7.2</td><td><span class="code">002475</span></td></tr>
      </tbody>
    </table>
    <div class="sc-detail-card"><strong>🔥 最优环节：光芯片/光模块</strong> — 增长9.5/10 · 利润9.5/10 · 壁垒10/10 · 供需严重失衡 · 龙头：新易盛(300502)、中际旭创(300308)</div>
  </div>

  <!-- ═══ 美股→A股映射 ═══ -->
  <div class="card" data-nav-section="us-gainers">
    <div class="section-title"><span class="icon">🇺🇸</span> 隔夜美股 → A股主题映射</div>
    {''.join(us_card(g) for g in us_gainers)}
  </div>

  <!-- ═══ Tier 1 ═══ -->
  <div class="card" data-nav-section="tier1">
    <div class="section-title"><span class="icon">🔥</span> 强烈看好 <span class="tier-badge tier-t1">T1</span></div>
    <table class="stock-table">
      <thead><tr><th>代码</th><th>名称</th><th>板块</th><th>利好类型</th><th>催化剂</th><th>现价</th><th>涨跌</th><th>策略</th><th>评分</th></tr></thead>
      <tbody>{''.join(stock_row(s) for s in t1)}</tbody>
    </table>
  </div>

  <!-- ═══ Tier 2 ═══ -->
  <div class="card" data-nav-section="tier2">
    <div class="section-title"><span class="icon">📈</span> 看好 <span class="tier-badge tier-t2">T2</span></div>
    <table class="stock-table">
      <thead><tr><th>代码</th><th>名称</th><th>板块</th><th>利好类型</th><th>催化剂</th><th>现价</th><th>涨跌</th><th>策略</th><th>评分</th></tr></thead>
      <tbody>{''.join(stock_row(s) for s in t2)}</tbody>
    </table>
  </div>

  <!-- ═══ Tier 3 ═══ -->
  <div class="card" data-nav-section="tier3">
    <div class="section-title"><span class="icon">👀</span> 关注 <span class="tier-badge tier-t3">T3</span></div>
    {warn_box}
    <table class="stock-table">
      <thead><tr><th>代码</th><th>名称</th><th>板块</th><th>利好类型</th><th>催化剂</th><th>现价</th><th>涨跌</th><th>策略</th><th>评分</th></tr></thead>
      <tbody>{''.join(stock_row(s) for s in t3)}</tbody>
    </table>
  </div>

  <!-- ═══ 明日预判 + 策略建议 ═══ -->
  <div class="card" data-nav-section="outlook">
    <div class="section-title"><span class="icon">🔮</span> 明日预判与策略建议</div>
    <div class="outlook-grid">
      <div class="outlook-card bullish">
        <div class="ol-title">📌 AI算力延续强势</div>
        <div class="ol-desc">台积电资本开支+英伟达SK海力士合作+光纤预制棒暴涨三重验证。光模块(300502/300308)和存储(603986)继续受益。</div>
      </div>
      <div class="outlook-card bullish">
        <div class="ol-title">📌 国产算力链催化密集</div>
        <div class="ol-desc">昇腾910C成功训练1.6万亿参数模型。长鑫科技IPO过会持续为半导体设备/材料链注入预期。</div>
      </div>
      <div class="outlook-card bullish">
        <div class="ol-title">📌 机器人主线回调是机会</div>
        <div class="ol-desc">宇树科技IPO+英伟达参考设计+国常会定调。绿的谐波(688017)回调关注低吸。特斯拉Optimus量产是6-7月关键催化剂。</div>
      </div>
      <div class="outlook-card caution">
        <div class="ol-title">⚠️ 涨停次日追高风险</div>
        <div class="ol-desc">新洁能(605111)、亚翔集成(603929)今日涨停不宜追高。碳化硅新周期中长期看好，短期建议等2-3天回调确认。</div>
      </div>
      <div class="outlook-card caution">
        <div class="ol-title">⚠️ 风险提示</div>
        <div class="ol-desc">1. 美股CHAI等AI概念大涨纯属投机<br>2. 涨停标的次日获利回吐压力<br>3. 美股隔夜冲高回落注意开盘情绪<br>4. 光模块板块累计涨幅较大</div>
      </div>
      <div class="outlook-card neutral">
        <div class="ol-title">💡 策略建议</div>
        <div class="ol-desc"><strong>进攻型</strong>：关注T1光模块/半导体<br><strong>稳健型</strong>：关注回调中的机器人<br><strong>观望型</strong>：T3涨停股等回调确认</div>
      </div>
    </div>
    <div class="strategy-box">
      <h3>💡 明日操作建议</h3>
      <ul>
        <li><strong>T1 标的</strong>可择机建仓，优先三高环节龙头 + 多催化剂共振标的</li>
        <li><strong>T2 标的</strong>关注次日竞价强度，高开不超过3%可参与</li>
        <li><strong>T3 标的</strong>多为情绪驱动/涨停次日，等待回踩确认再考虑</li>
      </ul>
    </div>
  </div>

  <!-- ═══ Footer ═══ -->
  <div class="footer">
    <strong>免责声明</strong>：本报告由AI自动生成，基于公开新闻和实时行情数据，仅供参考，不构成投资建议。股市有风险，投资需谨慎。<br>
    数据源: 同花顺(美股涨幅榜) + Exa/Bing(新闻搜索) + 腾讯qt(A股实时行情)。Tier评分基于量化模型（情绪30% + 催化剂20% + 置信度20% + 策略10% + 三高20%）。<br>
    Generated by news-stock-selector v4.1 · {today_display}
  </div>

</div>

<!-- ═══ 数据注入 ═══ -->
<script>
window.__REPORT_DATA__ = {REPORT_DATA_JSON};
</script>
<script>
/* ═══ 从 shared/template_base.js 完整复制 ═══ */
{TEMPLATE_JS}
</script>
</body>
</html>'''

output_path = f'C:/Users/Administrator/Desktop/新闻选股日报_{today}.html'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'OK: {output_path} ({os.path.getsize(output_path):,} bytes)')
print(f'  CSS template: {"loaded" if TEMPLATE_CSS else "MISSING"} ({len(TEMPLATE_CSS):,} chars)')
print(f'  JS  template: {"loaded" if TEMPLATE_JS else "MISSING"} ({len(TEMPLATE_JS):,} chars)')

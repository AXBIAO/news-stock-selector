#!/usr/bin/env python
"""Generate ETF fund selection HTML report."""
import os

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>新闻选基日报 2026-06-02</title>
<style>
  :root {
    --bg: #0a0e14; --bg-card: #181d27; --border: #262d38;
    --text: #e2e4e7; --text-dim: #8d929a; --text-muted: #5d626b;
    --up: #f85149; --up-dim: rgba(248,81,73,0.1);
    --down: #3fb950; --down-dim: rgba(63,185,80,0.1);
    --gold: #d2991d; --gold-dim: rgba(210,153,29,0.1);
    --blue: #58a6ff; --t1: #f0883e; --t1-dim: rgba(240,136,62,0.1);
    --t2: #58a6ff; --t2-dim: rgba(88,166,255,0.1);
    --t3: #8d929a;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; line-height: 1.6; padding: 20px; }
  .container { max-width: 1100px; margin: 0 auto; }
  .header { text-align: center; padding: 32px 0; border-bottom: 1px solid var(--border); margin-bottom: 28px; }
  .header .badge { display: inline-block; background: var(--t1); color: #000; padding: 4px 14px; border-radius: 4px; font-size: 13px; font-weight: 700; letter-spacing: 1px; margin-bottom: 12px; }
  .header h1 { font-size: 26px; font-weight: 700; margin: 8px 0; color: #fff; }
  .header .meta { color: var(--text-dim); font-size: 13px; }
  .summary-cards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 28px; }
  .summary-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 18px; text-align: center; }
  .summary-card .value { font-size: 28px; font-weight: 700; margin: 6px 0; }
  .summary-card .label { font-size: 12px; color: var(--text-dim); }
  .section { margin-bottom: 28px; }
  .section-title { font-size: 17px; font-weight: 700; margin-bottom: 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; }
  .tier-badge { display: inline-block; padding: 3px 10px; border-radius: 3px; font-size: 12px; font-weight: 700; }
  .tier-badge.t1 { background: var(--t1); color: #000; }
  .tier-badge.t2 { background: var(--t2); color: #fff; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: var(--bg); color: var(--text-dim); text-align: left; padding: 10px 12px; font-weight: 600; border-bottom: 2px solid var(--border); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
  td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
  tr:hover { background: rgba(255,255,255,0.02); }
  .code { color: var(--gold); font-weight: 600; font-family: 'SF Mono', 'Consolas', monospace; }
  .up { color: var(--up); font-weight: 600; }
  .score { font-weight: 600; font-size: 12px; }
  .score.t1 { color: var(--t1); }
  .score.t2 { color: var(--t2); }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; margin: 1px 2px; }
  .tag.policy { background: rgba(88,166,255,0.15); color: var(--blue); }
  .tag.tech { background: rgba(210,153,29,0.15); color: var(--gold); }
  .tag.hot { background: rgba(240,136,62,0.15); color: var(--t1); }
  .tag.industry { background: rgba(139,148,158,0.15); color: var(--text-dim); }
  .tag.multi { background: rgba(63,185,80,0.15); color: var(--down); }
  .outlook-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
  .outlook-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 18px; }
  .outlook-card h4 { font-size: 14px; margin-bottom: 8px; color: #fff; }
  .outlook-card .arrow { float: right; font-size: 18px; }
  .outlook-card p { font-size: 12px; color: var(--text-dim); line-height: 1.7; }
  .outlook-card.bullish { border-left: 3px solid var(--up); }
  .outlook-card.caution { border-left: 3px solid var(--gold); }
  .outlook-card.neutral { border-left: 3px solid var(--blue); }
  .news-item { display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border); align-items: flex-start; }
  .news-item .time { color: var(--text-muted); font-size: 12px; white-space: nowrap; min-width: 70px; }
  .news-item .content { font-size: 13px; }
  .news-item .src { color: var(--text-muted); font-size: 11px; }
  .disclaimer { margin-top: 32px; padding: 16px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; font-size: 11px; color: var(--text-muted); line-height: 1.8; }
  .signal-chip { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
  .signal-chip.buy { background: var(--up-dim); color: var(--up); }
  .signal-chip.hold { background: var(--t2-dim); color: var(--t2); }
  .signal-chip.watch { background: var(--gold-dim); color: var(--gold); }
  @media (max-width: 768px) { .summary-cards { grid-template-columns: repeat(2, 1fr); } .outlook-cards { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="badge">ETF 基金日报</div>
    <h1>新闻选基日报</h1>
    <div class="meta">
      <span>2026年6月2日 周二</span><span>|</span>
      <span>沪深300: 4,936 (+1.40%) | 沪指: +0.34% | 深成指: +0.85%</span><span>|</span>
      <span>数据来源: TuShare Pro + 新浪/腾讯 实时行情</span>
    </div>
  </div>
  <div class="summary-cards">
    <div class="summary-card"><div class="label">市场情绪</div><div class="value" style="color:var(--up)">偏多</div><div class="label">超4100只个股上涨</div></div>
    <div class="summary-card"><div class="label">成交额</div><div class="value" style="color:var(--gold)">1.59万亿</div><div class="label">较前日缩量</div></div>
    <div class="summary-card"><div class="label">今日最强板块</div><div class="value" style="color:var(--up)">有色金属</div><div class="label">有色ETF +3.39%</div></div>
    <div class="summary-card"><div class="label">核心催化</div><div class="value" style="color:var(--blue)">政策+科技</div><div class="label">绿电新规 | 智谱IPO | 宇树过会</div></div>
    <div class="summary-card"><div class="label">筛选结果</div><div class="value" style="color:var(--gold)">12只ETF</div><div class="label">T1: 7只 / T2: 5只</div></div>
  </div>
  <div class="section">
    <div class="section-title">今日重磅新闻速览</div>
    <div class="news-item"><div class="time">6月1日</div><div class="content">智谱宣布科创板IPO募资150亿元，80%投向大模型研发，大模型双雄加速回A。<span class="src"> 科创板日报</span></div></div>
    <div class="news-item"><div class="time">6月1日</div><div class="content">宇树科技科创板IPO过会，A股将迎"具身智能第一股"，人形机器人出货量全球第一。<span class="src"> 经济参考报 / 新华社</span></div></div>
    <div class="news-item"><div class="time">近日</div><div class="content">五部门联合出台《非化石能源电力消费核算指南（试行）》，利好绿证市场与新能源。<span class="src"> 国家发改委/能源局</span></div></div>
    <div class="news-item"><div class="time">近日</div><div class="content">国务院印发《城市更新"十五五"规划》，市场总容量预计超15万亿，房地产连续飘红。<span class="src"> 经济参考报</span></div></div>
    <div class="news-item"><div class="time">近日</div><div class="content">工信部启动普惠算力赋能行动，首次提出探索算力银行、算力超市等创新业务。<span class="src"> 东方财富</span></div></div>
    <div class="news-item"><div class="time">今日</div><div class="content">英伟达Vera Rubin芯片发布，进入PC市场并与宇树合作机器人；黄仁勋称Token就是资产。<span class="src"> 网易 / 钛媒体</span></div></div>
    <div class="news-item"><div class="time">今日</div><div class="content">东阳光签署100-120亿算力采购合同；新易盛1.6T光模块订单大幅增长。<span class="src"> 上市公司公告</span></div></div>
    <div class="news-item"><div class="time">今日</div><div class="content">李强签署国务院令公布《对外投资规定》，7月1日施行，推进高水平对外开放。<span class="src"> 新华社</span></div></div>
  </div>
  <div class="section">
    <div class="section-title"><span class="tier-badge t1">T1</span> 强烈看好 (tier_score >= 0.70)</div>
    <table><thead><tr><th>基金名称</th><th>代码</th><th>板块</th><th>催化剂</th><th>现价</th><th>涨跌幅</th><th>Tier得分</th><th>策略信号</th></tr></thead><tbody>
      <tr><td><strong>碳中和ETF</strong></td><td class="code">562990</td><td>新能源/绿电</td><td><span class="tag policy">政策利好</span></td><td>1.081</td><td class="up">+1.22%</td><td class="score t1">0.930</td><td><span class="signal-chip buy">催化剂博弈</span> <span class="signal-chip buy">回调低吸</span></td></tr>
      <tr><td><strong>人工智能ETF</strong></td><td class="code">159819</td><td>AI/人工智能</td><td><span class="tag tech">科技突破</span> <span class="tag policy">政策利好</span> <span class="tag multi">三催化</span></td><td>1.970</td><td class="up">+2.82%</td><td class="score t1">0.922</td><td><span class="signal-chip buy">催化剂博弈</span> <span class="signal-chip buy">三催化共振</span></td></tr>
      <tr><td><strong>机器人ETF</strong></td><td class="code">562500</td><td>机器人/具身智能</td><td><span class="tag tech">科技突破</span> <span class="tag hot">概念热点</span> <span class="tag multi">双催化</span></td><td>1.122</td><td class="up">+1.81%</td><td class="score t1">0.845</td><td><span class="signal-chip buy">催化剂博弈</span> <span class="signal-chip buy">科技突破</span></td></tr>
      <tr><td><strong>机器人ETF(2)</strong></td><td class="code">159770</td><td>机器人/具身智能</td><td><span class="tag tech">科技突破</span> <span class="tag hot">概念热点</span> <span class="tag multi">双催化</span></td><td>1.161</td><td class="up">+1.75%</td><td class="score t1">0.845</td><td><span class="signal-chip buy">催化剂博弈</span></td></tr>
      <tr><td><strong>半导体ETF</strong></td><td class="code">512480</td><td>半导体</td><td><span class="tag tech">科技突破</span> <span class="tag industry">行业景气</span> <span class="tag multi">双催化</span></td><td>2.080</td><td class="up">+1.66%</td><td class="score t1">0.804</td><td><span class="signal-chip buy">催化剂博弈</span> <span class="signal-chip hold">趋势持有</span></td></tr>
      <tr><td><strong>芯片ETF</strong></td><td class="code">159995</td><td>半导体/芯片</td><td><span class="tag tech">科技突破</span> <span class="tag hot">概念热点</span> <span class="tag multi">双催化</span></td><td>2.396</td><td class="up">+1.65%</td><td class="score t1">0.775</td><td><span class="signal-chip buy">催化剂博弈</span> <span class="signal-chip hold">趋势持有</span></td></tr>
      <tr><td><strong>云计算ETF</strong></td><td class="code">516510</td><td>AI/算力</td><td><span class="tag policy">政策利好</span> <span class="tag hot">概念热点</span> <span class="tag multi">双催化</span></td><td>1.806</td><td class="up">+0.78%</td><td class="score t1">0.719</td><td><span class="signal-chip buy">催化剂博弈</span> <span class="signal-chip watch">低位关注</span></td></tr>
    </tbody></table>
  </div>
  <div class="section">
    <div class="section-title"><span class="tier-badge t2">T2</span> 看好 (tier_score >= 0.55)</div>
    <table><thead><tr><th>基金名称</th><th>代码</th><th>板块</th><th>催化剂</th><th>现价</th><th>涨跌幅</th><th>Tier得分</th><th>策略信号</th></tr></thead><tbody>
      <tr><td><strong>有色金属ETF</strong></td><td class="code">512400</td><td>有色金属</td><td><span class="tag industry">行业景气</span> <span class="tag hot">概念热点</span> <span class="tag multi">双催化</span></td><td>2.015</td><td class="up">+3.39%</td><td class="score t2">0.689</td><td><span class="signal-chip buy">催化剂博弈</span> <span class="signal-chip watch">短线动能强</span></td></tr>
      <tr><td><strong>有色ETF</strong></td><td class="code">159871</td><td>有色金属</td><td><span class="tag industry">行业景气</span> <span class="tag hot">概念热点</span> <span class="tag multi">双催化</span></td><td>1.013</td><td class="up">+2.95%</td><td class="score t2">0.689</td><td><span class="signal-chip buy">催化剂博弈</span> <span class="signal-chip watch">强势追击</span></td></tr>
      <tr><td><strong>沪深300ETF</strong></td><td class="code">510300</td><td>宽基</td><td><span class="tag industry">行业景气</span></td><td>4.936</td><td class="up">+1.40%</td><td class="score t2">0.610</td><td><span class="signal-chip hold">均衡配置</span> <span class="signal-chip buy">百亿申购信号</span></td></tr>
      <tr><td><strong>上证50ETF</strong></td><td class="code">510050</td><td>宽基</td><td><span class="tag industry">行业景气</span></td><td>2.993</td><td class="up">+0.84%</td><td class="score t2">0.610</td><td><span class="signal-chip hold">防御配置</span></td></tr>
      <tr><td><strong>证券ETF</strong></td><td class="code">512880</td><td>券商</td><td><span class="tag industry">行业景气</span></td><td>1.037</td><td class="up">+0.19%</td><td class="score t2">0.547</td><td><span class="signal-chip hold">滞涨关注</span> <span class="signal-chip watch">低估值修复</span></td></tr>
    </tbody></table>
  </div>
  <div class="section">
    <div class="section-title">明日预判 &amp; 策略建议</div>
    <div class="outlook-cards">
      <div class="outlook-card bullish"><h4>AI/算力主线延续 <span class="arrow" style="color:var(--up)">&#8593;</span></h4><p>英伟达新芯片+智谱IPO双催化共振，AI产业链（算力/光模块/芯片）短期动能充足。关注<b>人工智能ETF(159819)</b>和<b>云计算ETF(516510)</b>的低吸机会。新易盛1.6T光模块订单大增、东阳光百亿算力大单为板块提供业绩验证。</p></div>
      <div class="outlook-card bullish"><h4>机器人/具身智能新赛道 <span class="arrow" style="color:var(--up)">&#8593;</span></h4><p>宇树科技IPO过会打开产业链想象空间，人形机器人正处于从技术突破迈向规模商业化的破晓时刻。<b>机器人ETF(562500/159770)</b>建议分批建仓，中长期持有，关注后续产业链配套企业IPO进度。</p></div>
      <div class="outlook-card bullish"><h4>绿电/碳中和政策驱动 <span class="arrow" style="color:var(--up)">&#8593;</span></h4><p>五部门绿电核算新规落地，碳排放双控制度加速推进，利好绿证交易市场活跃度提升。<b>碳中和ETF(562990)</b>政策催化剂置信度最高，Tier得分0.930领跑所有标的，适合稳健型配置。</p></div>
      <div class="outlook-card caution"><h4>有色金属短线追高风险 <span class="arrow" style="color:var(--gold)">&#8593;</span></h4><p>有色板块今日领涨(+3.39%)，锡业股份等多股涨停。Tier引擎因催化剂属性偏行业/热点而给予T2评级。短线动能强但已积累一定涨幅，建议轻仓参与、设好止损，不宜重仓追高。</p></div>
      <div class="outlook-card neutral"><h4>宽基底仓配置 <span class="arrow" style="color:var(--blue)">&#8594;</span></h4><p>宽基ETF时隔多月再现百亿申购，大资金认可当前市场性价比。华西证券建议重回均衡配置，<b>沪深300ETF(510300)</b>和<b>上证50ETF(510050)</b>适合作为底仓长期持有。</p></div>
      <div class="outlook-card caution"><h4>券商板块滞涨待催化 <span class="arrow" style="color:var(--gold)">&#8593;</span></h4><p>证券ETF(512880)今日仅微涨0.19%，但非银金融主力资金净流入居首，估值处历史低位。开源证券看好春季攻势，需等待成交额放大或政策催化确认右侧信号。</p></div>
    </div>
  </div>
  <div class="section" style="background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:20px;">
    <div class="section-title" style="border:none; margin-bottom:12px;">组合配置建议</div>
    <table><thead><tr><th>配置类型</th><th>推荐ETF</th><th>建议仓位</th><th>持有周期</th><th>逻辑</th></tr></thead><tbody>
      <tr><td><span class="signal-chip buy">进攻型</span></td><td>人工智能ETF(159819) + 机器人ETF(562500)</td><td>30%</td><td>1-3个月</td><td>英伟达+智谱+宇树三重科技催化，产业趋势确定性强</td></tr>
      <tr><td><span class="signal-chip buy">主题型</span></td><td>碳中和ETF(562990) + 半导体ETF(512480)</td><td>25%</td><td>2-6个月</td><td>政策驱动+景气上行，Tier得分最高，置信度领先</td></tr>
      <tr><td><span class="signal-chip hold">底仓型</span></td><td>沪深300ETF(510300) + 上证50ETF(510050)</td><td>30%</td><td>6-12个月</td><td>百亿申购信号+估值性价比+券商一致看多，均衡配置</td></tr>
      <tr><td><span class="signal-chip watch">卫星型</span></td><td>有色金属ETF(512400) + 证券ETF(512880)</td><td>15%</td><td>短线/事件驱动</td><td>有色短期动能强但追高谨慎；券商低估值滞涨等催化</td></tr>
    </tbody></table>
  </div>
  <div class="disclaimer">
    <strong>免责声明</strong><br>
    本报告由AI基于公开新闻和实时行情数据自动生成，数据来源包括TuShare Pro、东方财富、新浪财经、腾讯财经等。ETF价格和涨跌幅为2026年6月2日盘中实时数据（部分为前一交易日收盘价）。<br>
    本报告不构成任何投资建议，仅供信息参考。市场有风险，投资需谨慎。Tier评分基于量化模型（情绪35% + 催化剂25% + 置信度25% + 策略15%），不保证预测准确性。<br>
    生成时间：2026-06-02 15:04 CST | 数据引擎：news-stock-selector v3.6 | Tier引擎：contracts.compute_tier()
  </div>
</div>
</body>
</html>"""

OUTPUT = r"C:/Users/Administrator/Desktop/新闻选股日报_20260602.html"

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

print(f"OK: {len(HTML_CONTENT)} bytes written to {OUTPUT}")
print(f"File exists: {os.path.exists(OUTPUT)}, size: {os.path.getsize(OUTPUT)}")

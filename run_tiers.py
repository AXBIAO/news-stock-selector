#!/usr/bin/env python3
"""Compute tiers and output JSON for today's news-driven stock picks."""
import sys, json
sys.path.insert(0, r'C:\Users\Administrator\.claude\skills\news-stock-selector')
from contracts import (
    compute_tier, compute_catalyst_confidence, classify_strategy_tag,
    CatalystType, SentimentLevel,
)
from collections import Counter

stocks_data = [
    # ===== AI PC (英伟达 RTX Spark) =====
    {'code':'603890','name':'春秋电子','sector':'消费电子/AIPC','catalyst_types':[CatalystType.HOT, CatalystType.COOP],'catalyst_age_hours':12,'sentiment_score':4,'news_summary':'英伟达发布RTX Spark超级芯片进军PC市场，3连板涨停（公司澄清暂不涉及AIPC产品，注意分化风险）','prior_chg':10.0,'news_source':'网易/东方财富','catalyst_str':'英伟达AIPC催化+戴尔供应链'},

    {'code':'300956','name':'英力股份','sector':'消费电子/AIPC','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':4,'news_summary':'英伟达RTX Spark引爆AIPC概念，英力股份大涨13%领涨板块','prior_chg':13.11,'news_source':'网易','catalyst_str':'AIPC概念强势(追高风险)'},

    {'code':'301236','name':'软通动力','sector':'IT服务/AIPC','catalyst_types':[CatalystType.HOT, CatalystType.TECH],'catalyst_age_hours':12,'sentiment_score':4,'news_summary':'AIPC概念大涨，软通动力涨6.96%，IT服务龙头受益AI终端升级浪潮','prior_chg':6.96,'news_source':'东方财富','catalyst_str':'AIPC+IT服务双催化'},

    {'code':'002426','name':'胜利精密','sector':'消费电子/AIPC','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'AIPC概念整体走强，胜利精密涨幅滞后仅1.37%，低价低位具备补涨潜力','prior_chg':1.37,'news_source':'东方财富','catalyst_str':'AIPC补涨潜力(低价低位)'},

    {'code':'301329','name':'信音电子','sector':'消费电子','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'昨日20cm涨停，今日回调-4.3%，消费电子连接器龙头，回调后关注低吸机会','prior_chg':-4.3,'news_source':'同花顺','catalyst_str':'消费电子(涨停后回调低吸)'},

    # ===== AI算力/信创 =====
    {'code':'688227','name':'品高股份','sector':'云计算/AI','catalyst_types':[CatalystType.HOT, CatalystType.TECH],'catalyst_age_hours':12,'sentiment_score':4,'news_summary':'卫星互联网+AI算力双主线爆发，午后20%涨停，云计算与信创双受益','prior_chg':3.8,'news_source':'新浪财经','catalyst_str':'卫星互联网+AI算力双主线'},

    {'code':'301396','name':'宏景科技','sector':'AI算力','catalyst_types':[CatalystType.HOT, CatalystType.COOP],'catalyst_age_hours':12,'sentiment_score':4,'news_summary':'AI算力板块活跃，尾盘20cm涨停，算力服务需求持续旺盛','prior_chg':2.2,'news_source':'新浪财经','catalyst_str':'AI算力+算力服务(今日涨停)'},

    {'code':'603189','name':'*ST网达','sector':'AI/信创','catalyst_types':[CatalystType.TECH, CatalystType.EARNINGS],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'AI业务成第一大收入来源，信创大单落地，涨停5%（*ST风险警示股，需注意退市风险）','prior_chg':5.0,'news_source':'新浪财经','catalyst_str':'AI+信创双驱动(*ST风险)'},

    # ===== 新能源/储能 (政策催化) =====
    {'code':'301439','name':'泓淋电力','sector':'电力设备/储能','catalyst_types':[CatalystType.POLICY, CatalystType.HOT],'catalyst_age_hours':24,'sentiment_score':4,'news_summary':'国家能源局将分布式光伏储能纳入新型经营主体，2连板后今日回调-4%，政策利好确定性强','prior_chg':-4.09,'news_source':'国家能源局/证券时报','catalyst_str':'储能政策利好(连板后回调)'},

    {'code':'000539','name':'粤电力A','sector':'电力','catalyst_types':[CatalystType.HOT, CatalystType.POLICY],'catalyst_age_hours':24,'sentiment_score':4,'news_summary':'夏季用电高峰+电力改革政策推进，4连板后深度回调-6.55%，龙头辨识度高','prior_chg':-6.55,'news_source':'东方财富','catalyst_str':'电力改革龙头(深度回调)'},

    {'code':'000767','name':'晋控电力','sector':'电力','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':2,'news_summary':'2连板后公司澄清未开展算力相关业务，算电协同概念证伪（风险提示，建议规避）','prior_chg':-0.49,'news_source':'新浪财经','catalyst_str':'澄清无算力(风险提示-规避)'},

    # ===== 煤炭 (行业景气) =====
    {'code':'601088','name':'中国神华','sector':'煤炭','catalyst_types':[CatalystType.INDUSTRY],'catalyst_age_hours':24,'sentiment_score':4,'news_summary':'煤炭板块大涨5.53%领涨全市场，炼焦煤供应趋紧逻辑持续，高股息防御价值突出','prior_chg':-1.41,'news_source':'证券时报','catalyst_str':'煤炭龙头+高股息防御'},

    {'code':'600188','name':'兖矿能源','sector':'煤炭','catalyst_types':[CatalystType.INDUSTRY],'catalyst_age_hours':24,'sentiment_score':4,'news_summary':'煤炭板块强势领涨，炼焦煤供应趋紧，兖矿能源高位强势整理','prior_chg':-0.46,'news_source':'证券时报','catalyst_str':'煤炭景气+供应趋紧'},

    {'code':'601225','name':'陕西煤业','sector':'煤炭','catalyst_types':[CatalystType.INDUSTRY],'catalyst_age_hours':24,'sentiment_score':4,'news_summary':'煤炭行业景气上行，板块大涨后小幅回调-1.57%，高股息率防御配置首选','prior_chg':-1.57,'news_source':'证券时报','catalyst_str':'煤炭高股息+景气确认'},

    # ===== 其他热点 =====
    {'code':'300197','name':'节能铁汉','sector':'基础建设/环保','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'基础建设板块走强，节能铁汉20cm涨停，低价股炒作需注意追高风险','prior_chg':20.21,'news_source':'同花顺','catalyst_str':'基建热点(涨停追高风险)'},

    {'code':'301107','name':'瑜欣电子','sector':'通用设备','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'通用设备板块活跃，瑜欣电子涨5.92%，小市值低估值，弹性较大','prior_chg':5.92,'news_source':'同花顺','catalyst_str':'通用设备热点(弹性小票)'},

    {'code':'300649','name':'杭州园林','sector':'基础建设','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'基础建设板块活跃，杭州园林涨3.13%，园林生态修复概念','prior_chg':3.13,'news_source':'同花顺','catalyst_str':'基建板块联动'},

    {'code':'600011','name':'华能国际','sector':'电力','catalyst_types':[CatalystType.HOT, CatalystType.INDUSTRY],'catalyst_age_hours':24,'sentiment_score':3,'news_summary':'电力板块延续活跃，华能国际高位深度回调-6.86%，夏季用电高峰提供基本面支撑','prior_chg':-6.86,'news_source':'东方财富','catalyst_str':'电力龙头(深度回调低吸)'},

    {'code':'002328','name':'新朋股份','sector':'汽车零部件','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'昨日涨停，今日大幅回调-6.86%，汽车零部件+储能概念叠加','prior_chg':-6.86,'news_source':'同花顺','catalyst_str':'汽车零部件(涨停后回调)'},

    {'code':'300103','name':'达刚控股','sector':'专用设备','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'昨日涨停，今日回调-6.47%，专用设备小市值弹性标的','prior_chg':-6.47,'news_source':'同花顺','catalyst_str':'专用设备(涨停后深度回调)'},

    {'code':'300849','name':'锦盛新材','sector':'化妆品包装','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':2,'news_summary':'化妆品包装概念，涨幅1%力度偏弱，缺乏明确催化剂','prior_chg':1.03,'news_source':'同花顺','catalyst_str':'化妆品(缺乏强催化)'},
]

for s in stocks_data:
    multi = len(s['catalyst_types']) >= 2
    s['multi_catalyst_bonus'] = multi
    conf = compute_catalyst_confidence(s['catalyst_types'], s['catalyst_age_hours'], multi)
    s['confidence'] = conf
    tag = classify_strategy_tag(s['prior_chg'], s['catalyst_types'][0])
    s['strategy_tag'] = tag.value if hasattr(tag, 'value') else str(tag)
    s['prior_day_limit_up'] = (s['prior_chg'] is not None and s['prior_chg'] >= 9.5)
    tier, score = compute_tier(
        sentiment_score=s['sentiment_score'],
        catalyst_types=s['catalyst_types'],
        confidence=s['confidence'],
        strategy_tag=tag,
        prior_day_limit_up=s['prior_day_limit_up'],
    )
    s['assigned_tier'] = int(tier)
    s['tier_score'] = score

stocks_data.sort(key=lambda x: x['tier_score'], reverse=True)

# Sector concentration check
sectors = [s['sector'].split('/')[0] for s in stocks_data]
sector_counts = Counter(sectors)
total = len(stocks_data)
overheat_warnings = []
for sector, count in sector_counts.items():
    ratio = count / total
    if ratio > 0.30:
        affected = [s['code'] for s in stocks_data if s['sector'].startswith(sector)]
        overheat_warnings.append({'sector':sector,'count':count,'ratio':round(ratio,3),'affected':affected})

# Apply concentration downgrade: for sectors > 30%, downgrade lowest tier_score stocks
for w in overheat_warnings:
    affected_stocks = [s for s in stocks_data if s['code'] in w['affected']]
    affected_stocks.sort(key=lambda x: x['tier_score'])
    to_downgrade = affected_stocks[:min(2, max(1, w['count'] - int(total * 0.30)))]
    for s in to_downgrade:
        if s['assigned_tier'] < 3:
            s['assigned_tier'] += 1
            s['concentration_downgraded'] = True
        else:
            s['concentration_downgraded'] = False

print('=== OVERHEAT WARNINGS ===')
for w in overheat_warnings:
    print(f"  {w['sector']}: {w['count']}/{total}={w['ratio']:.0%} -> {w['affected']}")

print('\n=== TIER RESULTS ===')
tier_names = {1:'T1-强烈看好', 2:'T2-看好', 3:'T3-关注'}
for t in [1,2,3]:
    ts = [s for s in stocks_data if s['assigned_tier']==t]
    print(f'\n--- {tier_names[t]} [{len(ts)}只] ---')
    for s in ts:
        dw = ' [降权]' if s.get('concentration_downgraded') else ''
        print(f'{s["code"]} {s["name"]:6s} | score={s["tier_score"]:.3f} | conf={s["confidence"]:.2f} | tag={s["strategy_tag"]} | luk={s["prior_day_limit_up"]} | {s["catalyst_str"]}{dw}')

print('\n===JSON_START===')
print(json.dumps({
    'date': '20260602',
    'stocks': [{
        'code':s['code'],'name':s['name'],'sector':s['sector'],
        'tier':s['assigned_tier'],'tier_score':round(s['tier_score'],3),
        'confidence':round(s['confidence'],2),'strategy_tag':s['strategy_tag'],
        'sentiment':s['sentiment_score'],'news_summary':s['news_summary'],
        'news_source':s['news_source'],'catalyst_str':s['catalyst_str'],
        'prior_chg':s['prior_chg'],'limit_up':s['prior_day_limit_up'],
        'multi_catalyst':s['multi_catalyst_bonus']
    } for s in stocks_data],
    'overheat_warnings': overheat_warnings,
    'total_count': len(stocks_data)
}, ensure_ascii=False))
print('===JSON_END===')

#!/usr/bin/env python3
"""Compute tier scores and generate data for HTML report."""

import sys
sys.path.insert(0, r"C:\Users\Administrator\.claude\skills\news-stock-selector")

from contracts import (
    compute_tier, compute_catalyst_confidence, classify_strategy_tag,
    CatalystType,
)
import json

stocks_data = [
    {'code':'300308','name':'中际旭创','sector':'通信/光模块','catalyst_types':[CatalystType.INDUSTRY, CatalystType.HOT],'catalyst_age_hours':24,'sentiment_score':5,'news_summary':'CPO龙头，总市值跃升至1.2万亿，登顶沪深300第一大权重股','prior_chg':6.11,'news_source':'新浪财经','catalyst_str':'行业景气+AI算力涨价传导'},
    {'code':'688146','name':'中船特气','sector':'电子化学品','catalyst_types':[CatalystType.TECH, CatalystType.INDUSTRY],'catalyst_age_hours':72,'sentiment_score':5,'news_summary':'打败日韩厂商，六氟化钨全球龙头，日韩厂商下半年或停产','prior_chg':11.71,'news_source':'新浪财经','catalyst_str':'技术突破+国产替代'},
    {'code':'003004','name':'声迅股份','sector':'安防/光电子','catalyst_types':[CatalystType.MA],'catalyst_age_hours':12,'sentiment_score':5,'news_summary':'拟2.51亿元收购中科锐择51%股权，切入特种光器件与模块赛道','prior_chg':2.98,'news_source':'新浪财经','catalyst_str':'并购重组切入光电'},
    {'code':'688079','name':'美迪凯','sector':'半导体','catalyst_types':[CatalystType.COOP, CatalystType.TECH],'catalyst_age_hours':12,'sentiment_score':5,'news_summary':'12寸玻璃晶圆批量出货，已成功切入三星供应链体系','prior_chg':20.0,'news_source':'新浪财经','catalyst_str':'切入三星+技术突破'},
    {'code':'601686','name':'友发集团','sector':'钢铁/并购','catalyst_types':[CatalystType.MA],'catalyst_age_hours':12,'sentiment_score':5,'news_summary':'拟6.72亿元收购沧州隆泰迪53%股权','prior_chg':10.02,'news_source':'新浪财经','catalyst_str':'并购重组'},
    {'code':'002384','name':'东山精密','sector':'电子制造','catalyst_types':[CatalystType.EARNINGS],'catalyst_age_hours':48,'sentiment_score':5,'news_summary':'一季报业绩预增，一字板涨停，三日两板','prior_chg':9.1,'news_source':'财联社','catalyst_str':'业绩超预期'},
    {'code':'300475','name':'香农芯创','sector':'半导体/存储','catalyst_types':[CatalystType.EARNINGS, CatalystType.HOT],'catalyst_age_hours':48,'sentiment_score':5,'news_summary':'Q1净利预增6714%-8747%，AGI驱动企业级存储价格上涨','prior_chg':6.62,'news_source':'财联社','catalyst_str':'业绩暴增+存储涨价'},
    {'code':'301205','name':'联特科技','sector':'通信/光模块','catalyst_types':[CatalystType.HOT, CatalystType.INDUSTRY],'catalyst_age_hours':24,'sentiment_score':4,'news_summary':'CPO概念午后爆发，20cm涨停，迈威尔业绩超预期驱动','prior_chg':8.24,'news_source':'每日新闻','catalyst_str':'CPO景气+海外映射'},
    {'code':'300620','name':'光库科技','sector':'通信/光器件','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':24,'sentiment_score':4,'news_summary':'CPO概念爆发，涨超13%，光通信器件核心供应商','prior_chg':13.4,'news_source':'每日新闻','catalyst_str':'CPO景气爆发'},
    {'code':'002653','name':'海思科','sector':'医药','catalyst_types':[CatalystType.COOP],'catalyst_age_hours':12,'sentiment_score':4,'news_summary':'与礼来战略合作，最高8700万美元首付款+多疾病领域创新药','prior_chg':2.05,'news_source':'新浪财经','catalyst_str':'与礼来战略合作'},
    {'code':'600673','name':'东阳光','sector':'综合/算力','catalyst_types':[CatalystType.COOP],'catalyst_age_hours':12,'sentiment_score':4,'news_summary':'子公司签署算力服务采购合同，预计总金额100亿-120亿元','prior_chg':0.84,'news_source':'新浪财经','catalyst_str':'百亿算力大单'},
    {'code':'002709','name':'天赐材料','sector':'新能源/电解液','catalyst_types':[CatalystType.COOP],'catalyst_age_hours':12,'sentiment_score':4,'news_summary':'与楚能新能源签合作协议，电解液供应量上调至不少于101万吨','prior_chg':-0.35,'news_source':'新浪财经','catalyst_str':'电解液大单'},
    {'code':'000063','name':'中兴通讯','sector':'通信设备','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':48,'sentiment_score':3,'news_summary':'通信板块爆发涨停，AI算力+5G双主线驱动','prior_chg':2.17,'news_source':'每日新闻','catalyst_str':'通信设备龙头'},
    {'code':'002156','name':'通富微电','sector':'半导体封测','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':24,'sentiment_score':3,'news_summary':'半导体封测龙头，AI芯片封装需求旺盛','prior_chg':4.33,'news_source':'市场数据','catalyst_str':'AI芯片封装'},
    {'code':'002294','name':'信立泰','sector':'医药','catalyst_types':[CatalystType.EQUITY],'catalyst_age_hours':12,'sentiment_score':3,'news_summary':'拟3亿元-5亿元回购股份','prior_chg':0.3,'news_source':'新浪财经','catalyst_str':'股份回购'},
    {'code':'002460','name':'赣锋锂业','sector':'有色金属/锂电','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':24,'sentiment_score':3,'news_summary':'电池产业链集体爆发，机构+游资买入，但今日回撤','prior_chg':-2.28,'news_source':'财联社','catalyst_str':'锂电龙头(高位回落)'},
    {'code':'600196','name':'复星医药','sector':'医药','catalyst_types':[CatalystType.TECH],'catalyst_age_hours':72,'sentiment_score':3,'news_summary':'帕妥珠单抗获FDA/EC/NMPA批准，覆盖原研全部适应症','prior_chg':-1.35,'news_source':'新浪财经','catalyst_str':'创新药获批'},
    {'code':'000767','name':'晋控电力','sector':'电力','catalyst_types':[CatalystType.HOT],'catalyst_age_hours':12,'sentiment_score':2,'news_summary':'两连板后澄清：未开展算力相关业务，算电协同未布局','prior_chg':3.58,'news_source':'新浪财经','catalyst_str':'澄清无算力(风险提示)'},
]

for s in stocks_data:
    multi = len(s['catalyst_types']) >= 2
    s['multi_catalyst_bonus'] = multi
    conf = compute_catalyst_confidence(s['catalyst_types'], s['catalyst_age_hours'], multi)
    s['confidence'] = conf
    tag = classify_strategy_tag(s['prior_chg'], s['catalyst_types'][0])
    s['strategy_tag'] = tag
    s['prior_day_limit_up'] = (s['prior_chg'] is not None and s['prior_chg'] >= 9.5)
    tier, score = compute_tier(
        sentiment_score=s['sentiment_score'],
        catalyst_types=s['catalyst_types'],
        confidence=s['confidence'],
        strategy_tag=s['strategy_tag'],
        prior_day_limit_up=s['prior_day_limit_up'],
    )
    s['assigned_tier'] = tier
    s['tier_score'] = score

stocks_data.sort(key=lambda x: x['tier_score'], reverse=True)

# Manual sector check
from collections import Counter
sector_counts = Counter(s['sector'] for s in stocks_data)
total = len(stocks_data)
for sector, count in sector_counts.items():
    ratio = count / total
    if ratio > 0.3:
        print(f"OVERHEAT: {sector}: {count}/{total} = {ratio:.1%}")

print('=== Tier Results ===')
for s in stocks_data:
    print(f"T{s['assigned_tier']} | {s['code']} {s['name']:6s} | score={s['tier_score']:.3f} | conf={s['confidence']:.2f} | tag={s['strategy_tag']} | limit_up={s['prior_day_limit_up']} | {s['catalyst_str']}")

print('\n===JSON_START===')
print(json.dumps([{
    'code': s['code'], 'name': s['name'], 'sector': s['sector'],
    'tier': s['assigned_tier'], 'tier_score': round(s['tier_score'], 3),
    'confidence': round(s['confidence'], 2), 'strategy_tag': s['strategy_tag'],
    'sentiment': s['sentiment_score'], 'news_summary': s['news_summary'],
    'news_source': s['news_source'], 'catalyst_str': s['catalyst_str'],
    'prior_chg': s['prior_chg'], 'limit_up': s['prior_day_limit_up'],
    'multi_catalyst': s['multi_catalyst_bonus']
} for s in stocks_data], ensure_ascii=False))
print('===JSON_END===')

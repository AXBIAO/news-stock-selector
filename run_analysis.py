#!/usr/bin/env python3
"""Run full analysis for news-stock-selector"""
from contracts import (
    compute_tier, compute_catalyst_confidence, classify_strategy_tag,
    StockResult, CatalystType, SentimentLevel, SelectionResult,
    USGainerMapping, check_sector_concentration
)
import json

# --- US Gainers Mapping ---
us_gainers = [
    USGainerMapping(
        rank=1, ticker='CHAI', company='Core AI Holdings',
        change_pct=249.39, close_price=2.87,
        driver='OpenAI秘密提交S-1注册声明，引发AI概念小盘股投机狂潮',
        a_share_theme='AI应用/大模型',
        suggested_a_stocks=['688256', '300308'],
        confirming_news=['智谱AI拟募资150亿冲刺科创板', '华为昇腾910C完成1.6万亿参数DeepSeek全参数训练', '国内AI算力需求持续爆发']
    ),
    USGainerMapping(
        rank=2, ticker='NUVL', company='Nuvalent',
        change_pct=38.86, close_price=122.88,
        driver='GSK以106亿美元现金收购，溢价40%，获三款肺癌创新药管线',
        a_share_theme='创新药/CXO',
        suggested_a_stocks=['603259', '688180'],
        confirming_news=['超50家生物医药A股公司2025年业绩预盈', '国产创新药出海业绩亮眼']
    ),
    USGainerMapping(
        rank=3, ticker='SOX', company='费城半导体指数',
        change_pct=5.6, close_price=0,
        driver='台积电重申520-560亿美金资本开支；英伟达SK海力士合作AI内存；英特尔获谷歌/英伟达订单',
        a_share_theme='AI芯片/半导体设备',
        suggested_a_stocks=['002371', '603986', '300604'],
        confirming_news=['长鑫科技IPO过会市值冲击2万亿', '华为韬定律发布', '瑞银:功率半导体新超级周期']
    ),
]

# --- Stock Analysis Data ---
stock_data = [
    {'code':'300502','name':'新易盛','price':785.73,'chg':8.38,'sector':'光模块/AI算力',
     'sentiment':5,'catalysts':[CatalystType.EARNINGS, CatalystType.INDUSTRY],
     'catalyst_age':0,'news':'2025净利94-99亿同比增231-249%；光纤预制棒价格暴涨550%；光模块CPO重回强势'},
    {'code':'300308','name':'中际旭创','price':1180.0,'chg':2.17,'sector':'光模块/AI算力',
     'sentiment':5,'catalysts':[CatalystType.EARNINGS, CatalystType.INDUSTRY],
     'catalyst_age':0,'news':'2025净利98-118亿同比增90-128%；台积电资本开支验证AI算力长期需求；光模块全球龙头'},
    {'code':'603986','name':'兆易创新','price':500.5,'chg':5.59,'sector':'存储/半导体',
     'sentiment':5,'catalysts':[CatalystType.INDUSTRY, CatalystType.POLICY],
     'catalyst_age':0,'news':'长鑫科技IPO过会(关联交易57亿)；2025净利预增46%；英伟达SK海力士合作下一代AI内存'},
    {'code':'002371','name':'北方华创','price':617.1,'chg':5.35,'sector':'半导体设备',
     'sentiment':4,'catalysts':[CatalystType.POLICY, CatalystType.INDUSTRY],
     'catalyst_age':0,'news':'华为韬定律发布带动先进封装需求；国产替代加速；半导体设备景气上行'},
    {'code':'688256','name':'寒武纪','price':1270.01,'chg':1.57,'sector':'AI芯片',
     'sentiment':4,'catalysts':[CatalystType.TECH, CatalystType.POLICY],
     'catalyst_age':0,'news':'2025扭亏为盈净利20.59亿；昇腾910C突破利好国产算力链；AI算力需求爆发'},
    {'code':'002475','name':'立讯精密','price':69.34,'chg':4.84,'sector':'消费电子/AI硬件',
     'sentiment':4,'catalysts':[CatalystType.EARNINGS, CatalystType.COOP],
     'catalyst_age':0,'news':'2025净利165-172亿增24-29%；AI端侧硬件+数据中心互联+机器人战略布局'},
    {'code':'300604','name':'长川科技','price':212.73,'chg':6.15,'sector':'半导体设备',
     'sentiment':4,'catalysts':[CatalystType.INDUSTRY],
     'catalyst_age':0,'news':'半导体设备国产替代加速；科创板集成电路净利增86.3%'},
    {'code':'605111','name':'新洁能','price':61.99,'chg':10.01,'sector':'功率半导体',
     'sentiment':4,'catalysts':[CatalystType.RATING],
     'catalyst_age':0,'news':'瑞银上调至买入目标81.3元；碳化硅新超级周期；今日涨停'},
    {'code':'688017','name':'绿的谐波','price':420.17,'chg':-1.89,'sector':'机器人',
     'sentiment':5,'catalysts':[CatalystType.HOT, CatalystType.POLICY],
     'catalyst_age':0,'news':'宇树科技IPO过会；英伟达开放人形机器人参考设计；国常会推进智能制造；今日回调低吸机会'},
    {'code':'603929','name':'亚翔集成','price':205.81,'chg':10.0,'sector':'半导体洁净室',
     'sentiment':4,'catalysts':[CatalystType.EARNINGS],
     'catalyst_age':0,'news':'2025净利目标达成率161%；半导体基建政策驱动；今日涨停'},
    {'code':'002600','name':'领益智造','price':14.86,'chg':3.63,'sector':'AI硬件/液冷',
     'sentiment':4,'catalysts':[CatalystType.COOP, CatalystType.HOT],
     'catalyst_age':0,'news':'港股IPO通过聆讯；英伟达认证液冷+AI服务器电源双驱动；物理AI布局'},
]

results = []
for s in stock_data:
    multi = len(s['catalysts']) >= 2
    conf = compute_catalyst_confidence(s['catalysts'], s['catalyst_age'], multi)
    strategy = classify_strategy_tag(s['chg'], s['catalysts'][0])
    limit_up = (s['chg'] >= 9.5)
    tier, score = compute_tier(s['sentiment'], s['catalysts'], conf, strategy, limit_up)
    results.append({
        'code': s['code'], 'name': s['name'], 'price': s['price'], 'chg': s['chg'],
        'sector': s['sector'], 'sentiment': s['sentiment'], 'confidence': round(conf, 2),
        'strategy_tag': strategy, 'limit_up': limit_up,
        'tier': tier, 'tier_score': round(score, 3),
        'news': s['news'], 'multi_catalyst': multi
    })

# Sort by tier_score desc
results.sort(key=lambda x: x['tier_score'], reverse=True)

# Check sector concentration
sectors = {}
for r in results:
    sec = r['sector'].split('/')[0]
    sectors.setdefault(sec, []).append(r['code'])
overheat = []
for sec, codes in sectors.items():
    ratio = len(codes) / len(results)
    if ratio > 0.3:
        sec_results = [r for r in results if r['sector'].startswith(sec)]
        sec_results.sort(key=lambda x: x['tier_score'])
        demote_code = sec_results[0]['code']
        overheat.append({'sector': sec, 'count': len(codes), 'ratio': round(ratio, 2), 'demote': demote_code})
        # Apply demotion
        for r in results:
            if r['code'] == demote_code and r['tier'] < 3:
                r['tier'] += 1

print('=== TIER RESULTS ===')
for r in results:
    print(f"T{r['tier']} | {r['code']} {r['name']} | {r['price']} | {r['chg']:+.2f}% | score={r['tier_score']} | conf={r['confidence']} | {r['strategy_tag']} | {'LIMIT_UP!' if r['limit_up'] else ''} | {r['sector']}")

print('\n=== OVERHEAT ===')
for o in overheat:
    print(f"{o['sector']}: {o['count']} stocks, ratio={o['ratio']}, demote={o['demote']}")

print('\n--- JSON_OUTPUT ---')
out = {
    'results': results,
    'overheat': overheat,
    'us_gainers': [{'rank': g.rank, 'ticker': g.ticker, 'company': g.company, 'change_pct': g.change_pct, 'close_price': g.close_price, 'driver': g.driver, 'a_share_theme': g.a_share_theme, 'suggested_a_stocks': g.suggested_a_stocks, 'confirming_news': g.confirming_news} for g in us_gainers]
}
print(json.dumps(out, ensure_ascii=False, indent=2))

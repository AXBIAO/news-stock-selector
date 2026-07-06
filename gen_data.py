#!/usr/bin/env python3
"""Generate report_data.json with all stock selection results."""
import json, os

data = {
    "query": "完整选股流程：反内卷+AI算力+机器人+创新药",
    "date": "20260705",
    "display_date": "2026-07-05 (周日，基于7月3日周五收盘数据)",
    "stocks": [
        {"code":"688256","name":"寒武纪","tier":1,"price":1353.0,"chg":-1.38,"sector":"AI芯片","strategy":"催化剂博弈","tier_score":0.825,"news":"H20恢复短期扰动+国产AI芯片渗透率提升是长期趋势(42%->49%)","limit_up":False},
        {"code":"688012","name":"中微公司","tier":1,"price":413.69,"chg":1.17,"sector":"半导体设备","strategy":"催化剂博弈","tier_score":0.813,"news":"半导体设备国产替代加速+大基金三期注资1140亿","limit_up":False},
        {"code":"002371","name":"北方华创","tier":1,"price":816.0,"chg":-2.98,"sector":"半导体设备","strategy":"回调低吸","tier_score":0.813,"news":"半导体设备龙头+国产替代加速+大基金三期利好","limit_up":False},
        {"code":"600276","name":"恒瑞医药","tier":1,"price":54.45,"chg":1.79,"sector":"创新药","strategy":"催化剂博弈","tier_score":0.797,"news":"创新药新政全链条支持+新药纳入优先审评+行业景气回升","limit_up":False},
        {"code":"300308","name":"中际旭创","tier":1,"price":1116.0,"chg":-2.36,"sector":"光模块","strategy":"回调低吸","tier_score":0.768,"news":"光模块龙头+1.6T订单锁定至2027Q2+对英伟达供货60%","limit_up":False},
        {"code":"300124","name":"汇川技术","tier":1,"price":72.15,"chg":5.48,"sector":"机器人/伺服系统","strategy":"催化剂博弈","tier_score":0.757,"news":"机器人产业链全面爆发+伺服系统龙头+宇树IPO催化","limit_up":False},
        {"code":"600438","name":"通威股份","tier":1,"price":11.8,"chg":-2.4,"sector":"光伏/多晶硅","strategy":"回调低吸","tier_score":0.734,"news":"反内卷核心龙头+多晶硅价格反弹28%+全球市占率30%","limit_up":False},
        {"code":"300274","name":"阳光电源","tier":1,"price":126.16,"chg":-1.31,"sector":"光伏/逆变器","strategy":"催化剂博弈","tier_score":0.731,"news":"光伏逆变器龙头+储能双主线+海外储能需求旺盛","limit_up":False},
        {"code":"300502","name":"新易盛","tier":1,"price":526.0,"chg":3.34,"sector":"光通信/CPO","strategy":"催化剂博弈","tier_score":0.719,"news":"AI算力需求爆发+1.6T光模块量产在即","limit_up":False},
        {"code":"603986","name":"兆易创新","tier":1,"price":677.77,"chg":-2.45,"sector":"存储芯片","strategy":"回调低吸","tier_score":0.719,"news":"存储芯片周期反转+DRAM/NAND价格年内涨幅可达120%","limit_up":False},
        {"code":"600585","name":"海螺水泥","tier":2,"price":17.14,"chg":1.72,"sector":"水泥/建材","strategy":"催化剂博弈","tier_score":0.690,"news":"反内卷核心受益+水泥协会发文+产能置换方案落地","limit_up":False},
        {"code":"688981","name":"中芯国际","tier":2,"price":140.31,"chg":-2.63,"sector":"晶圆代工","strategy":"回调低吸","tier_score":0.690,"news":"成熟制程反内卷+H20利好配套+国产替代长期趋势","limit_up":False},
        {"code":"600019","name":"宝钢股份","tier":2,"price":5.59,"chg":-0.36,"sector":"钢铁","strategy":"催化剂博弈","tier_score":0.680,"news":"反内卷核心受益+国企占比高去产能阻力小+利润由亏转盈","limit_up":False},
        {"code":"002594","name":"比亚迪","tier":2,"price":88.47,"chg":5.86,"sector":"新能源汽车","strategy":"催化剂博弈","tier_score":0.674,"news":"新能源车反内卷政策利好+海外出货量大增+韩国投资者持续买入","limit_up":False},
        {"code":"688017","name":"绿的谐波","tier":3,"price":488.0,"chg":18.15,"sector":"机器人/减速器","strategy":"涨停次日熔断","tier_score":0.658,"news":"宇树科技科创板IPO获批+人形机器人第一股+前日涨停触发熔断","limit_up":True},
        {"code":"300750","name":"宁德时代","tier":2,"price":380.0,"chg":-0.61,"sector":"锂电池","strategy":"催化剂博弈","tier_score":0.657,"news":"锂电反内卷预期+储能市场爆发+龙头份额持续提升","limit_up":False},
        {"code":"601012","name":"隆基绿能","tier":2,"price":12.55,"chg":-1.8,"sector":"光伏/硅片","strategy":"催化剂博弈","tier_score":0.649,"news":"光伏反内卷受益+BC技术领先+组件出货全球前五","limit_up":False},
        {"code":"601088","name":"中国神华","tier":2,"price":40.7,"chg":-0.17,"sector":"煤炭","strategy":"催化剂博弈","tier_score":0.640,"news":"煤炭反内卷+高股息防御价值+港口库存回落煤价企稳","limit_up":False},
        {"code":"002156","name":"通富微电","tier":2,"price":64.8,"chg":-3.81,"sector":"先进封装","strategy":"回调低吸","tier_score":0.550,"news":"AMD MI308恢复对华出口+先进封装需求+Chiplet趋势","limit_up":False},
        {"code":"002460","name":"赣锋锂业","tier":2,"price":62.97,"chg":-1.59,"sector":"锂矿","strategy":"催化剂博弈","tier_score":0.540,"news":"锂矿反内卷预期+碳酸锂价格底部企稳","limit_up":False},
    ],
    "us_gainers": [
        {"rank":1,"ticker":"CLRO","company":"ClearOne通讯","chg":101.24,"price":"6.48","driver":"通信设备需求超预期","theme":"通信设备","a_stocks":"AI算力/5G设备","confirm":"弱确认","confirm_text":"国内通信设备板块无显著催化，美股小盘股异动对A股映射有限"},
    ],
    "supply_chain": {
        "has_data": True,
        "top_segment": "AI算力·AI芯片设计",
        "summary": "AI算力产业链三高环节：AI芯片设计(3H=9.4) > 半导体设备(3H=8.8) > 光模块/CPO(3H=8.2)。光伏产业链三高环节：逆变器(3H=7.7) > 多晶硅料(3H=7.3) > 光伏玻璃(3H=6.1)。最强三高环节为AI芯片设计：增长35%+毛利率50-60%+严重供不应求。",
        "chains": [
            {"name":"AI算力产业链","nodes":[
                {"name":"AI芯片设计","tier":"上游","growth":35,"margin":"50-60%","barrier":"极高","barrier_reason":"IP/架构壁垒+代工限制","sd_gap":"严重供不应求","three_high_score":9.4,"leaders":["寒武纪(688256)","海光信息(688041)"]},
                {"name":"半导体设备","tier":"上游","growth":30,"margin":"40-55%","barrier":"极高","barrier_reason":"技术壁垒+认证周期长","sd_gap":"供不应求","three_high_score":8.8,"leaders":["北方华创(002371)","中微公司(688012)"]},
                {"name":"半导体材料","tier":"上游","growth":25,"margin":"30-50%","barrier":"高","barrier_reason":"纯度要求+客户认证","sd_gap":"供需偏紧","three_high_score":7.7,"leaders":["中瓷电子(003031)","安集科技(688019)"]},
                {"name":"晶圆代工","tier":"中游","growth":28,"margin":"25-45%","barrier":"极高","barrier_reason":"资本密集+工艺壁垒","sd_gap":"先进制程紧缺","three_high_score":8.1,"leaders":["中芯国际(688981)","华虹公司(688347)"]},
                {"name":"封装测试","tier":"下游","growth":18,"margin":"15-25%","barrier":"中","barrier_reason":"规模效应+先进封装演进","sd_gap":"供需平衡","three_high_score":5.3,"leaders":["通富微电(002156)","长电科技(600584)"]},
                {"name":"光模块/CPO","tier":"下游","growth":40,"margin":"30-50%","barrier":"高","barrier_reason":"高速率技术壁垒+客户认证","sd_gap":"严重供不应求","three_high_score":8.2,"leaders":["中际旭创(300308)","新易盛(300502)"]},
                {"name":"存储芯片","tier":"中游","growth":30,"margin":"35-55%","barrier":"高","barrier_reason":"制程壁垒+周期性强","sd_gap":"供需偏紧","three_high_score":8.2,"leaders":["兆易创新(603986)","佰维存储(688525)"]},
            ]},
            {"name":"光伏产业链","nodes":[
                {"name":"多晶硅料","tier":"上游","growth":15,"margin":"30-50%","barrier":"极高","barrier_reason":"资本密集+高能耗+技术壁垒","sd_gap":"严重过剩->限产改善","three_high_score":7.3,"leaders":["通威股份(600438)","大全能源(688303)"]},
                {"name":"硅片","tier":"上游","growth":12,"margin":"15-25%","barrier":"高","barrier_reason":"规模+成本控制+大尺寸化","sd_gap":"过剩->整合出清","three_high_score":6.1,"leaders":["隆基绿能(601012)","TCL中环(002129)"]},
                {"name":"电池片","tier":"中游","growth":20,"margin":"10-20%","barrier":"中","barrier_reason":"技术迭代快+效率竞赛","sd_gap":"供需平衡偏过剩","three_high_score":5.5,"leaders":["通威股份(600438)","晶澳科技(002459)"]},
                {"name":"组件","tier":"下游","growth":18,"margin":"8-15%","barrier":"中","barrier_reason":"品牌+渠道+一体化","sd_gap":"供需平衡","three_high_score":4.8,"leaders":["隆基绿能(601012)","天合光能(688599)"]},
                {"name":"逆变器","tier":"下游","growth":25,"margin":"30-45%","barrier":"高","barrier_reason":"技术壁垒+品牌+渠道","sd_gap":"供需偏紧","three_high_score":7.7,"leaders":["阳光电源(300274)","固德威(688390)"]},
                {"name":"光伏玻璃","tier":"上游","growth":15,"margin":"20-35%","barrier":"高","barrier_reason":"高能耗+产能指标限制","sd_gap":"过剩->联合减产30%","three_high_score":6.1,"leaders":["福莱特(601865)","金晶科技(600586)"]},
            ]},
        ]
    },
    "outlook": [
        {"title":"反内卷：跨行业主线延续","desc":"价格法修正草案落地+政治局会议定调，反内卷从钢铁/水泥/煤炭向上游资源品和下游高端制造扩散。重点关注光伏多晶硅限产+锂电产能出清两条暗线。","style":"bullish"},
        {"title":"AI算力：业绩验证窗口来临","desc":"中报季将至，AI算力链将迎来成色检验。光模块/CPO和半导体设备订单确定性最高，存储芯片周期反转趋势明确。高估值题材股注意回调风险。","style":"bullish"},
        {"title":"机器人：宇树IPO催化新主线","desc":"宇树科技科创板IPO获批，人形机器人第一股落地。减速器/伺服/传感器全线受益。绿的谐波已涨18%触发涨停次日熔断，追高需谨慎。","style":"bullish"},
        {"title":"科技内部分化风险","desc":"双创指数高位震荡，科技板块从赛道普涨转向业绩分化。高位AI标的需通过中报证明自己，缺乏业绩支撑的纯概念股可能面临回调。","style":"caution"},
        {"title":"海外扰动：费城半导体暴跌6%","desc":"7月2日费城半导体指数暴跌超6%，美光/ARM/科磊等算力设备股大跌。Meta出售闲置算力引发AI投资过热担忧，需关注对A股半导体的传导。","style":"caution"},
    ],
    "strategies": [
        "T1标的优先关注三高环节龙头(光模块/半导体设备/AI芯片)，回调即是布局机会",
        "T2反内卷标的关注政策落地节奏，水泥/钢铁可左侧布局等待催化",
        "T3机器人概念追高需谨慎(绿的谐波已涨18.15%触发涨停次日熔断)",
        "整体仓位建议6-7成，科技(40%)+反内卷(40%)+防御(20%)均衡配置",
    ],
    "overheat_warnings": [],
    "sectors": [
        {"name":"机器人","chg":5.0},{"name":"新能源汽车","chg":2.5},
        {"name":"创新药","chg":1.5},{"name":"水泥建材","chg":2.0},
        {"name":"半导体设备","chg":2.0},{"name":"光通信","chg":1.0},
        {"name":"光伏","chg":-1.0},{"name":"锂电池","chg":-0.5},
        {"name":"钢铁","chg":1.0},{"name":"煤炭","chg":0.5},
    ],
    "kpi": {
        "t1_count":10,"t2_count":9,"t3_count":1,
        "up_ratio":35,"avg_chg":0.68,"total":20,
    }
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_data.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Written: {out_path}")
print(f"T1={data['kpi']['t1_count']} T2={data['kpi']['t2_count']} T3={data['kpi']['t3_count']}")

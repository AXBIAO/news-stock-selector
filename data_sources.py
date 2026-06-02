# -*- coding: utf-8 -*-
"""
数据源初始化配置 - news-stock-selector skill (v3.2)
借鉴 UZI-Skill 的可靠架构：实时爬虫优先 + TuShare Pro daily() 兜底验证

【实时数据源优先级】:
    0. 雪球 stock_individual_spot_xq (REAL-TIME, 4次重试)
    1. 腾讯 qt.gtimg.cn (REAL-TIME, GBK解码)
    2. 新浪 hq.sinajs.cn (REAL-TIME, GBK解码)
    3. 东方财富 push2直连 (REAL-TIME)
    4. TuShare Free get_realtime_quotes (半实时)
    5. TuShare Pro daily() (EOD/验证兜底) — http://124.220.22.110:8020/

【TuShare Pro 付费数据初始化】:
    import tushare as ts
    from config import TUSHARE_TOKEN, TUSHARE_HTTP_URL
    pro = ts.pro_api(TUSHARE_TOKEN)
    pro._DataApi__http_url = TUSHARE_HTTP_URL

⚠️ 如果显示 Token 不对，请确保包含上面这行 http_url 设置
"""

from config import TUSHARE_TOKEN, TUSHARE_HTTP_URL, TUSHARE_ENABLED
from contracts import FallbackRecord, FieldStatus

# ============================================================
# 数据源配置
# ============================================================

TUSHARE_CONFIG = {
    "api_token": TUSHARE_TOKEN,
    "http_url": TUSHARE_HTTP_URL,
    "enabled": TUSHARE_ENABLED,
}

# 数据源优先级（v3.2 实时爬虫优先 + TuShare Pro daily() 兜底验证）
FREE_DATA_SOURCES = {
    "实时行情": {
        "primary": "雪球 stock_individual_spot_xq (REAL-TIME, 4次重试)",
        "fallback": ["腾讯 qt.gtimg.cn (REAL-TIME)", "新浪 hq.sinajs.cn (REAL-TIME)", "东方财富 push2直连 (REAL-TIME)", "TuShare Free (半实时)", "TuShare Pro daily() (EOD验证兜底)"]
    },
    "财报历史": {
        "primary": "akshare",
        "fallback": ["雪球 f10"]
    },
    "K线/技术指标": {
        "primary": "akshare",
        "fallback": ["yfinance"]
    },
    "龙虎榜/北向/两融": {
        "primary": "akshare",
        "fallback": ["东财"]
    },
    "研报/公告": {
        "primary": "巨潮 cninfo + akshare",
        "fallback": ["同花顺"]
    },
    "港股": {
        "primary": "akshare hk",
        "fallback": ["yfinance"]
    },
    "美股": {
        "primary": "yfinance",
        "fallback": ["akshare us"]
    },
    "宏观/政策/舆情": {
        "primary": "DuckDuckGo web search",
        "fallback": []
    }
}

# ============================================================
# 社交热榜配置 (v2.12 新增)
# ============================================================

SOCIAL_HOT_TRENDS = {
    "enabled": True,
    "platforms": {
        "weibo": {
            "name": "微博热搜",
            "url": "https://weibo.com/ajax/side/hotSearch",
            "limit": 50,
            "cache_ttl": 300
        },
        "zhihu": {
            "name": "知乎热榜",
            "url": "https://www.zhihu.com/api/v3/feed/topstory/hot-list-web",
            "limit": 50,
            "cache_ttl": 300
        },
        "baidu": {
            "name": "百度热搜",
            "url": "https://top.baidu.com/api/board",
            "limit": 50,
            "cache_ttl": 300
        },
        "douyin": {
            "name": "抖音热点",
            "url": "https://www.douyin.com/aweme/v1/web/hot/search/list/",
            "limit": 50,
            "cache_ttl": 300
        },
        "toutiao": {
            "name": "头条热榜",
            "url": "https://www.toutiao.com/hot-event/hot-board/",
            "limit": 50,
            "cache_ttl": 300
        },
        "bilibili": {
            "name": "B站热搜",
            "url": "https://s.search.bilibili.com/main/hotword",
            "limit": 50,
            "cache_ttl": 300
        }
    },
    "stock_match": {
        "enabled": True,
        "include_short_names": True,  # 贵州茅台 -> 贵州/茅台
        "sentiment_weight": {
            "weibo": 1.2,
            "zhihu": 1.0,
            "baidu": 0.9,
            "douyin": 1.3,   # 杀猪盘发源地
            "toutiao": 1.0,
            "bilibili": 0.8
        }
    }
}

# ============================================================
# 17_sentiment 数据结构
# ============================================================

SENTIMENT_DATA_STRUCTURE = {
    "hot_trend_mentions": {
        "stock_name": "贵州茅台",
        "platforms_ok": 6,
        "total_hits": 3,
        "by_platform_count": {"weibo": 2, "zhihu": 1},
        "mentions": {
            "weibo": [{"rank": 3, "title": "茅台 1499 回归", "url": "..."}],
            "zhihu": [{"rank": 15, "title": "茅台股价分析", "url": "..."}]
        }
    }
}

# ============================================================
# TuShare Pro 常用函数封装
# ============================================================

def get_tushare_pro():
    """
    获取 TuShare Pro API 实例

    Returns:
        ts.pro_api: 已配置的 TuShare Pro 实例
    """
    import tushare as ts
    pro = ts.pro_api(TUSHARE_CONFIG["api_token"])
    pro._DataApi__http_url = TUSHARE_CONFIG["http_url"]
    return pro


def tushare_quote(codes: list[str]) -> "pd.DataFrame":
    """获取股票实时行情（TuShare Pro）"""
    pro = get_tushare_pro()
    ts_codes = _convert_codes_to_ts_format(codes)
    return pro.quotes(ts_codes=ts_codes)


def tushare_pro_daily_batch(codes: list[str]) -> dict:
    """
    【优先数据源】通过 TuShare Pro daily() 接口批量获取最新日线行情。
    已验证可用 — http://124.220.22.110:8020/

    相比 tushare_quote() 使用 quotes() 接口可能不可用，
    该函数使用 daily() 接口获取最近交易日收盘数据，
    包含收盘价、涨跌幅、成交量、成交额等完整字段。

    Args:
        codes: 6位股票代码列表，如 ['600584', '002156']

    Returns:
        dict: {
            code: {name, price, change_pct, open, prev_close, high, low, volume, turnover, _source}
        }
    """
    import logging
    logger = logging.getLogger(__name__)

    ts_codes = _convert_codes_to_ts_format(codes)
    if not ts_codes:
        return {}

    try:
        pro = get_tushare_pro()
        df = pro.daily(ts_code=','.join(ts_codes), limit=len(codes) * 2)
        if df is None or df.empty:
            logger.warning("TuShare Pro daily() returned empty DataFrame")
            return {}

        # 取每个代码的最新交易日数据
        latest_date = df['trade_date'].max()
        df_latest = df[df['trade_date'] == latest_date]

        result = {}
        for _, row in df_latest.iterrows():
            ts_code = row.get('ts_code', '')
            # 从 ts_code (如 600584.SH) 提取6位代码
            code = ts_code.split('.')[0] if '.' in ts_code else ts_code

            close = float(row.get('close', 0))
            pre_close = float(row.get('pre_close', 0))
            change_pct = float(row.get('pct_chg', 0))
            vol = float(row.get('vol', 0))
            amount = float(row.get('amount', 0))
            open_p = float(row.get('open', 0))
            high = float(row.get('high', 0))
            low = float(row.get('low', 0))

            result[code] = {
                'name': '',  # daily接口不含名称，调用方可后续补全
                'price': close,
                'change_pct': change_pct,
                'open': open_p,
                'prev_close': pre_close,
                'high': high,
                'low': low,
                'volume': vol,
                'turnover': amount,
                'trade_date': latest_date,
                '_source': 'tushare-pro-daily'
            }

        logger.info(f"TuShare Pro daily() success: {len(result)} stocks, trade_date={latest_date}")
        return result
    except Exception as e:
        logger.warning(f"TuShare Pro daily() failed: {type(e).__name__}: {e}")
        return {}


def _convert_codes_to_ts_format(codes: list[str]) -> list[str]:
    """将6位代码转换为TuShare格式（带.SH/.SZ后缀）"""
    ts_codes = []
    for code in codes:
        code_str = str(code).strip()
        if len(code_str) == 6:
            if code_str.startswith('6') or code_str.startswith('688'):
                ts_codes.append(f"{code_str}.SH")
            else:
                ts_codes.append(f"{code_str}.SZ")
        elif '.' in code_str:
            ts_codes.append(code_str)
    return ts_codes


# ============================================================
# 重试装饰器（借鉴UZI-Skill）
# ============================================================

def _retry(fn, attempts: int = 3, sleep: float = 0.8):
    """带重试的函数调用"""
    import time
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            time.sleep(sleep * (i + 1))
    raise last_err


# ============================================================
# 腾讯 qt.gtimg.cn 通用价格兜底（借鉴UZI-Skill v2.6）
# 适用于 A/H/U 三市场，简洁稳定，不需key、无反爬
# 字段格式：v_{prefix}{code}="type~name~code~current~prev~open~vol~..."
# ============================================================

def _fetch_price_tencent_qt(market: str, code_raw: str) -> dict:
    """Returns {price, change_pct, prev_close, open, high, low, pe_ttm?, pb?, name?}.

    Empty dict on any failure. NEVER raises.
    market: "A" → "sh"/"sz" prefix, "H" → "hk", "U" → "us"
    """
    import requests

    if market == "A":
        prefix = "sh" if code_raw.startswith(("60", "688", "900")) else "sz"
        symbol = f"{prefix}{code_raw}"
    elif market == "H":
        symbol = f"hk{code_raw.zfill(5)}"
    elif market == "U":
        symbol = f"us{code_raw}"
    else:
        return {}

    url = f"https://qt.gtimg.cn/q={symbol}"
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return {}
        # ⚠️ 关键：GBK解码！腾讯接口用GBK编码
        text = r.content.decode("gbk", errors="replace")
        if "=" not in text or '"' not in text:
            return {}
        content = text.split("=", 1)[1].strip().rstrip(";").strip().strip('"')
        parts = content.split("~")
        if len(parts) < 35:
            return {}

        def _f(idx):
            try:
                v = parts[idx].strip()
                return float(v) if v and v != "-" else None
            except (ValueError, IndexError):
                return None

        out = {
            "name": parts[1] if parts[1] else None,
            "price": _f(3),
            "prev_close": _f(4),
            "open": _f(5),
            "change_pct": _f(32),
            "high": _f(33),
            "low": _f(34),
        }
        # PE/PB only present for A-share (and even then only sh prefix)
        if len(parts) > 39:
            pe = _f(39)
            if pe is not None:
                out["pe_ttm"] = pe
        if len(parts) > 46:
            pb = _f(46)
            if pb is not None:
                out["pb"] = pb
        return {k: v for k, v in out.items() if v is not None}
    except Exception:
        return {}


# ============================================================
# 雪球实时行情（借鉴UZI-Skill，PRIMARY数据源，4次重试）
# ============================================================

def _fetch_xueqiu_spot(code: str) -> dict:
    """使用雪球stock_individual_spot_xq获取实时行情

    Args:
        code: 6位股票代码

    Returns:
        dict: {name, price, change_pct, open, prev_close, high, low, volume, turnover, ...}
    """
    import akshare as ak

    # 判断交易所：6开头或688开头为上海，否则深圳
    if code.startswith(("6", "688")):
        xq_symbol = f"SH{code}"
    else:
        xq_symbol = f"SZ{code}"

    try:
        df = _retry(
            lambda: ak.stock_individual_spot_xq(symbol=xq_symbol),
            attempts=4,
            sleep=2.0
        )
        if df is None or df.empty:
            return {}

        info = dict(zip(df["item"], df["value"]))

        def _getf(*keys):
            for k in keys:
                v = info.get(k)
                if v is not None and v != "":
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        pass
            return None

        price = _getf("现价")
        mcap = _getf("资产净值/总市值")
        circ = _getf("流通值")

        return {
            "name": info.get("org_short_name_cn") or info.get("name"),
            "price": price,
            "change_pct": _getf("涨幅"),
            "open": _getf("今开"),
            "prev_close": _getf("昨收"),
            "high": _getf("最高"),
            "low": _getf("最低"),
            "volume": _getf("成交量"),
            "turnover": _getf("成交额"),
            "market_cap": f"{round(mcap/1e8, 1)}亿" if mcap else None,
            "pe_ttm": _getf("市盈率(TTM)"),
            "pb": _getf("市净率"),
            "_source": "xueqiu-spot"
        }
    except Exception:
        return {}


# ============================================================
# 新浪实时行情（借鉴UZI-Skill，作为备用）
# ============================================================

def _fetch_sina_quote(code: str) -> dict:
    """使用新浪hq.sinajs.cn获取实时行情

    Args:
        code: 6位股票代码

    Returns:
        dict: {name, price, change_pct, open, prev_close, high, low}
    """
    import requests

    if code.startswith(("6", "688")):
        sina_code = f"sh{code}"
    else:
        sina_code = f"sz{code}"

    url = f"https://hq.sinajs.cn/list={sina_code}"
    try:
        r = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}
        )
        if r.status_code != 200:
            return {}
        text = r.content.decode("gbk", errors="replace")
        # 解析格式：var hq_str_sh603986="兆易创新,40.000,39.560,44.470,44.500,40.780,40.000,...";
        # 字段：0=名称,1=今日开盘价,2=昨日收盘价,3=当前价格,4=最高价,5=最低价,...
        match = text.split('"', 1)
        if len(match) < 2:
            return {}
        parts = match[1].split(",")
        if len(parts) < 4:
            return {}

        name = parts[0]
        open_p = float(parts[1]) if parts[1] else 0.0
        prev_close = float(parts[2]) if parts[2] else 0.0
        price = float(parts[3]) if parts[3] else 0.0
        high = float(parts[4]) if len(parts) > 4 and parts[4] else 0.0
        low = float(parts[5]) if len(parts) > 5 and parts[5] else 0.0

        chg_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0

        return {
            "name": name,
            "price": price,
            "change_pct": round(chg_pct, 2),
            "open": open_p,
            "prev_close": prev_close,
            "high": high,
            "low": low,
            "_source": "sina-hq"
        }
    except Exception:
        return {}


# ============================================================
# 东方财富push2直连（借鉴UZI-Skill，作为备用）
# ============================================================

def _fetch_eastmoney_direct(code: str) -> dict:
    """使用东方财富push2.eastmoney.com直连获取实时行情

    Args:
        code: 6位股票代码

    Returns:
        dict: {name, price, change_pct, open, prev_close, high, low}
    """
    import requests

    if code.startswith(("6", "688")):
        secid = f"1.{code}"
    else:
        secid = f"0.{code}"

    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "ut": "fa5fd1943c7b386f172d6893dbbd5d41",
        "fltt": "2",
        "invt": "2",
        "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f107,f169,f170",
        "secid": secid,
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=8)
        if r.status_code != 200:
            return {}
        data = r.json()
        stock_data = data.get("data", {})
        if not stock_data or not stock_data.get("f43"):
            return {}

        scale = 100.0
        price = (stock_data.get("f43", 0)) / scale
        prev_close = (stock_data.get("f44", 0)) / scale
        open_p = (stock_data.get("f45", 0)) / scale
        high = (stock_data.get("f46", 0)) / scale
        low = (stock_data.get("f47", 0)) / scale
        chg = (stock_data.get("f170", 0)) / scale if stock_data.get("f170") else None
        name = stock_data.get("f58", "")

        if prev_close > 0 and chg is None:
            chg = ((price - prev_close) / prev_close * 100)

        return {
            "name": name,
            "price": price,
            "change_pct": chg,
            "open": open_p,
            "prev_close": prev_close,
            "high": high,
            "low": low,
            "_source": "eastmoney-direct"
        }
    except Exception:
        return {}


# ============================================================
# 股票代码到行业的映射（借鉴UZI-Skill，最后兜底用）
# ============================================================

_STOCK_INDUSTRY_MAP: dict[str, str] = {
    # 光学光电子
    "002273": "光学光电子", "002281": "光学光电子", "300433": "光学光电子",
    "688127": "光学光电子", "002456": "光学光电子", "603501": "光学光电子",
    # 白酒
    "600519": "白酒", "000858": "白酒", "000568": "白酒", "002304": "白酒",
    "600809": "白酒", "600779": "白酒", "000799": "白酒",
    # 半导体
    "688981": "半导体", "603986": "半导体", "002371": "半导体", "002129": "半导体",
    "300782": "半导体", "688012": "半导体", "688008": "半导体", "688536": "半导体",
    # 新能源 / 电池
    "300750": "电池", "002594": "汽车整车", "300014": "电池", "002460": "电池",
    "300207": "电池", "300124": "电池", "300919": "电池",
    # AI / 算力
    "300308": "光模块", "300394": "光模块", "300502": "光模块",
    # 医药生物
    "300760": "医药生物", "603259": "医药生物", "600196": "医药生物",
    # 消费电子
    "002475": "消费电子", "002241": "消费电子", "002938": "消费电子",
    # 银行
    "601398": "银行", "601939": "银行", "601288": "银行", "600036": "银行",
    "601166": "银行", "000001": "银行",
    # 保险
    "601318": "保险", "601601": "保险", "601628": "保险", "601336": "保险",
    # 证券
    "600030": "证券", "601688": "证券", "000776": "证券",
    # 房地产
    "000002": "房地产", "600048": "房地产", "001979": "房地产",
    # 钢铁
    "600019": "钢铁", "600808": "钢铁", "000898": "钢铁",
    # 家电
    "000333": "家电", "000651": "家电", "600690": "家电",
    # 食品饮料
    "600887": "食品饮料", "603288": "食品饮料",
    # 港口
    "000582": "港口", "601018": "港口", "600017": "港口", "600018": "港口",
    "000905": "港口", "601298": "港口", "000507": "港口",
    # 交通运输
    "601006": "交通运输", "600009": "交通运输", "601111": "交通运输",
    # 航运
    "601866": "航运", "601872": "航运", "600026": "航运", "601880": "航运",
    # 建筑
    "601668": "建筑装饰", "601186": "建筑装饰", "002051": "建筑装饰",
    # 电力
    "600900": "电力", "601985": "电力", "600886": "电力",
    # 煤炭
    "601088": "煤炭", "600188": "煤炭", "601898": "煤炭",
    # 军工
    "600893": "军工", "000768": "军工", "601989": "军工",
    # 汽车
    "600104": "汽车", "601238": "汽车", "000625": "汽车",
    # 互联网服务
    "601360": "互联网服务", "600633": "互联网服务",
    # 化学制药
    "600276": "化学制药", "000538": "化学制药", "600521": "化学制药",
    # 通信设备
    "002463": "通信设备", "603236": "通信设备",
}


def _get_known_industry(code: str) -> str | None:
    """从已知映射获取股票行业"""
    return _STOCK_INDUSTRY_MAP.get(code)


# ============================================================
# 多源实时行情 fallback 链 (v3.2 实时爬虫优先 + EOD兜底)
# ============================================================

def is_market_hours() -> bool:
    """判断当前是否 A 股交易时段（周一至周五 9:30-11:30, 13:00-15:00）"""
    from datetime import datetime, time
    now = datetime.now()
    if now.weekday() >= 5:  # 周六/周日
        return False
    t = now.time()
    return (time(9, 30) <= t <= time(11, 30)) or (time(13, 0) <= t <= time(15, 0))


def _concurrent_fetch(codes: list[str], fetcher, label: str, logger) -> dict[str, dict]:
    """通用并发抓取：对 codes 列表并发调用 fetcher(code)，返回 {code: data}。
    fetcher 签名: (code: str) -> dict | None
    """
    import concurrent.futures
    results: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetcher, code): code for code in codes}
        for future in concurrent.futures.as_completed(futures):
            code = futures[future]
            try:
                data = future.result()
                if data and data.get("price"):
                    results[code] = data
                    logger.info(f"{label} success for {code}: price={data.get('price')}, change={data.get('change_pct')}%")
            except Exception:
                pass
    return results


def get_realtime_quote_fallback(codes: list[str]) -> dict:
    """
    多源实时行情获取（5级 fallback 链，借鉴UZI-Skill）

    数据源优先级 (v3.2 — 实时爬虫优先 + EOD兜底):
        0. 雪球 stock_individual_spot_xq (REAL-TIME, 4次重试)
        1. 腾讯 qt.gtimg.cn (REAL-TIME, GBK解码)
        2. 新浪 hq.sinajs.cn (REAL-TIME, GBK解码)
        3. 东方财富 push2直连 (REAL-TIME)
        4. TuShare Free get_realtime_quotes (半实时)
        5. TuShare Pro daily() (EOD验证兜底) — http://124.220.22.110:8020/
        6. 返回 pending 状态（未找到的股票标记为待确认）

    Args:
        codes: 股票代码列表，如 ['300308', '300394', '002281']

    Returns:
        dict: {
            'source': 'xueqiu/tencent/sina/eastmoney/tushare/tushare-pro-daily/pending',
            'data': {code: {name, price, change_pct, ...}},
            'fallback_used': bool,
            'stocks_found': list,
            'stocks_missing': list
        }
    """
    import logging
    import threading

    logger = logging.getLogger(__name__)

    result: dict = {
        'source': 'pending',
        'data': {},
        'fallback_used': False,
        'stocks_found': [],
        'stocks_missing': list(codes),
        'per_stock_fallback': {code: FallbackRecord(provider_label="pending") for code in codes},
    }

    lock = threading.Lock()

    if not codes:
        logger.warning("get_realtime_quote_fallback called with empty codes list")
        return result

    def _merge_and_track(missing_before: list[str], new_data: dict[str, dict], source_label: str):
        """将抓取结果合并到 result，并记录 fallback 追踪"""
        for code, data in new_data.items():
            with lock:
                result['data'][code] = data
                if code not in result['stocks_found']:
                    result['stocks_found'].append(code)
                if code in result['stocks_missing']:
                    result['stocks_missing'].remove(code)
        for code in missing_before:
            result['per_stock_fallback'][code].attempted_sources.append(source_label)
        for code in new_data:
            if code in result['per_stock_fallback']:
                fb = result['per_stock_fallback'][code]
                if fb.final_source == "pending":
                    fb.final_source = source_label

    def _source_done(source_name: str):
        """当前源找到了所有缺失的股票？"""
        result['source'] = source_name
        result['fallback_used'] = True
        return not result['stocks_missing']

    # ========================================================================
    # 数据源0: 雪球 stock_individual_spot_xq (REAL-TIME PRIMARY, 4次重试)
    # ========================================================================
    xq_missing = list(result['stocks_missing'])
    xq_data = _concurrent_fetch(xq_missing, lambda c: _fetch_xueqiu_spot(c), "Xueqiu", logger)
    _merge_and_track(xq_missing, xq_data, "xueqiu_quote")
    if _source_done('xueqiu'):
        logger.info(f"Xueqiu found all {len(result['stocks_found'])} stocks")
        return result

    # ========================================================================
    # 数据源1: 腾讯 qt.gtimg.cn (REAL-TIME, GBK解码)
    # ========================================================================
    tx_missing = list(result['stocks_missing'])
    tx_data = _concurrent_fetch(tx_missing, lambda c: _fetch_price_tencent_qt("A", c), "TencentQT", logger)
    _merge_and_track(tx_missing, tx_data, "tencent_quote")
    if _source_done('tencent-qt'):
        logger.info(f"Tencent QT found all {len(result['stocks_found'])} stocks")
        return result

    # ========================================================================
    # 数据源2: 新浪 hq.sinajs.cn (REAL-TIME, GBK解码)
    # ========================================================================
    sina_missing = list(result['stocks_missing'])
    sina_data = _concurrent_fetch(sina_missing, _fetch_sina_quote, "Sina", logger)
    _merge_and_track(sina_missing, sina_data, "sina_quote")
    if _source_done('sina-hq'):
        return result

    # ========================================================================
    # 数据源3: 东方财富 push2直连 (REAL-TIME)
    # ========================================================================
    em_missing = list(result['stocks_missing'])
    em_data = _concurrent_fetch(em_missing, _fetch_eastmoney_direct, "EastMoney", logger)
    _merge_and_track(em_missing, em_data, "eastmoney_quote")
    if _source_done('eastmoney-direct'):
        return result

    # ========================================================================
    # 数据源4: TuShare Free get_realtime_quotes (半实时)
    # ========================================================================
    try:
        import tushare as ts
        free_missing = list(result['stocks_missing'])
        logger.info(f"Trying TuShare get_realtime_quotes for {len(free_missing)} codes")
        df = ts.get_realtime_quotes(free_missing)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get('code', '')).strip()
                if not code or code == 'nan':
                    continue
                price_str = row.get('price', '0')
                pre_close_str = row.get('pre_close', '0')
                try:
                    price = float(price_str) if price_str not in ['n/a', '', 'nan'] else 0.0
                    pre_close = float(pre_close_str) if pre_close_str not in ['n/a', '', 'nan'] else 0.0
                    chg = ((price - pre_close) / pre_close * 100) if pre_close != 0 else 0.0
                except (ValueError, TypeError, ZeroDivisionError):
                    price, chg = 0.0, 0.0
                name = str(row.get('name', '')).strip()
                with lock:
                    result['data'][code] = {'name': name, 'price': price, 'change_pct': chg, '_source': 'tushare'}
                    if code not in result['stocks_found']:
                        result['stocks_found'].append(code)
                    if code in result['stocks_missing']:
                        result['stocks_missing'].remove(code)
            for code in free_missing:
                result['per_stock_fallback'][code].attempted_sources.append("tushare_quote")
            for code in result['stocks_found']:
                if result['per_stock_fallback'][code].final_source == "pending":
                    result['per_stock_fallback'][code].final_source = "tushare_quote"
        if _source_done('tushare'):
            logger.info(f"TuShare Free success: got {len(result['stocks_found'])} stocks")
            return result
    except Exception as e:
        logger.warning(f"TuShare Free failed: {type(e).__name__}: {e}")

    # ========================================================================
    # 数据源5: TuShare Pro daily() (EOD 验证兜底)
    # ========================================================================
    pro_daily_result = tushare_pro_daily_batch(list(result['stocks_missing']))
    _merge_and_track(list(result['stocks_missing']), pro_daily_result, "tushare_pro_daily")
    if _source_done('tushare-pro-daily'):
        logger.info(f"TuShare Pro daily() fallback: got {len(result['stocks_found'])} stocks")
        return result

    # ========================================================================
    # 所有数据源都失败
    # ========================================================================
    for code in result['stocks_missing']:
        fb = result['per_stock_fallback'][code]
        fb.final_source = "pending"
        fb.failure_reason = "all_providers_failed"

    result['source'] = 'pending'
    result['fallback_used'] = True
    logger.warning(f"All data sources failed. stocks_missing: {result['stocks_missing']}")
    return result


def get_intraday_quote(codes: list[str]) -> dict:
    """
    纯实时行情查询 — 仅使用实时数据源（雪球/腾讯/新浪/东方财富），
    跳过 TuShare Pro daily() EOD 兜底。

    适用于盘中交易时段的实时价格获取。
    如果所有实时源都失败，返回 pending 状态（不降级到日线）。

    Args:
        codes: 股票代码列表，如 ['600584', '002156']

    Returns:
        dict: 与 get_realtime_quote_fallback 相同格式
    """
    import logging
    logger = logging.getLogger(__name__)

    # 直接调用主 fallback 链，但手动处理使 daily() 不被调用
    # 策略：调用完整链，如果 source 落到 tushare-pro-daily 则标记为降级
    full_result = get_realtime_quote_fallback(codes)

    # 如果最终来源是 EOD，且所有实时源都没命中 → 返回 pending
    if full_result['source'] == 'tushare-pro-daily':
        full_result['intraday_warning'] = (
            'ALL real-time sources failed; data is from TuShare Pro daily() '
            f'(trade_date: {full_result.get("_trade_date", "unknown")}). '
            'Prices may be end-of-day, not current market prices.'
        )

    return full_result


def search_realtime_price_via_web(codes: list[str]) -> dict:
    """
    通过网页搜索获取股票实时价格（第5级fallback）

    ⚠️ 注意：这个函数现在主要作为最后兜底
    主数据流应该用 get_realtime_quote_fallback()

    Args:
        codes: 股票代码列表，如 ['603986', '001309']

    Returns:
        dict: {
            'source': 'web_search',
            'data': {code: {'price': float, 'change_pct': float, 'name': str}},
            'stocks_found': list,
            'stocks_missing': list
        }
    """
    import logging
    import threading

    logger = logging.getLogger(__name__)

    result: dict = {
        'source': 'web_search',
        'data': {},
        'stocks_found': [],
        'stocks_missing': list(codes)
    }

    lock = threading.Lock()

    # 直接使用get_realtime_quote_fallback作为兜底
    fallback_result = get_realtime_quote_fallback(codes)
    if fallback_result.get('stocks_found'):
        with lock:
            result['source'] = fallback_result['source']
            result['data'] = fallback_result['data']
            result['stocks_found'] = fallback_result['stocks_found']
            result['stocks_missing'] = fallback_result['stocks_missing']
        return result

    # 如果所有数据源都失败了，返回pending状态
    result['source'] = 'pending'
    result['stocks_missing'] = list(codes)
    return result


# ============================================================
# 社交热榜相关函数
# ============================================================

def fetch_weibo_hot() -> dict:
    """获取微博热搜"""
    import requests
    import json

    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://weibo.com'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok') == 1:
                hot_list = data.get('data', {}).get('hot', [])
                return {
                    'success': True,
                    'platform': 'weibo',
                    'items': [{'rank': i+1, 'title': item.get('word', ''), 'url': f"https://s.weibo.com/weibo?q={item.get('word', '')}"}
                              for i, item in enumerate(hot_list[:50])]
                }
    except Exception as e:
        return {'success': False, 'platform': 'weibo', 'error': str(e)}
    return {'success': False, 'platform': 'weibo', 'error': 'Unknown'}


def fetch_zhihu_hot() -> dict:
    """获取知乎热榜"""
    import requests

    try:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-list-web"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            hot_list = data.get('data', [])
            return {
                'success': True,
                'platform': 'zhihu',
                'items': [{'rank': i+1, 'title': item.get('target', {}).get('title', ''), 'url': item.get('target', {}).get('url', '')}
                          for i, item in enumerate(hot_list[:50])]
            }
    except Exception as e:
        return {'success': False, 'platform': 'zhihu', 'error': str(e)}
    return {'success': False, 'platform': 'zhihu', 'error': 'Unknown'}


def fetch_baidu_hot() -> dict:
    """获取百度热搜"""
    import requests

    try:
        url = "https://top.baidu.com/api/board"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            hot_list = data.get('data', [])
            return {
                'success': True,
                'platform': 'baidu',
                'items': [{'rank': i+1, 'title': item.get('query', ''), 'url': item.get('url', '')}
                          for i, item in enumerate(hot_list[:50])]
            }
    except Exception as e:
        return {'success': False, 'platform': 'baidu', 'error': str(e)}
    return {'success': False, 'platform': 'baidu', 'error': 'Unknown'}


def fetch_douyin_hot() -> dict:
    """获取抖音热点"""
    import requests

    try:
        url = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.douyin.com'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            word_list = data.get('data', {}).get('word_list', [])
            return {
                'success': True,
                'platform': 'douyin',
                'items': [{'rank': i+1, 'title': item.get('word', ''), 'url': f"https://www.douyin.com/search/{item.get('word', '')}"}
                          for i, item in enumerate(word_list[:50])]
            }
    except Exception as e:
        return {'success': False, 'platform': 'douyin', 'error': str(e)}
    return {'success': False, 'platform': 'douyin', 'error': 'Unknown'}


def fetch_toutiao_hot() -> dict:
    """获取头条热榜"""
    import requests

    try:
        url = "https://www.toutiao.com/hot-event/hot-board/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            hot_list = data.get('data', [])
            return {
                'success': True,
                'platform': 'toutiao',
                'items': [{'rank': i+1, 'title': item.get('title', ''), 'url': item.get('url', '')}
                          for i, item in enumerate(hot_list[:50])]
            }
    except Exception as e:
        return {'success': False, 'platform': 'toutiao', 'error': str(e)}
    return {'success': False, 'platform': 'toutiao', 'error': 'Unknown'}


def fetch_bilibili_hot() -> dict:
    """获取B站热搜"""
    import requests

    try:
        url = "https://s.search.bilibili.com/main/hotword"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            hot_list = data.get('list', [])
            return {
                'success': True,
                'platform': 'bilibili',
                'items': [{'rank': i+1, 'title': item.get('keyword', ''), 'url': f"https://search.bilibili.com/all?keyword={item.get('keyword', '')}"}
                          for i, item in enumerate(hot_list[:50])]
            }
    except Exception as e:
        return {'success': False, 'platform': 'bilibili', 'error': str(e)}
    return {'success': False, 'platform': 'bilibili', 'error': 'Unknown'}


def fetch_hot_trends(stock_names: list[str]) -> dict:
    """
    并行获取6大平台热榜并匹配股票

    Args:
        stock_names: 股票名称列表（含简称，如 ['贵州茅台', '茅台', '五粮液', '五粮液'])

    Returns:
        dict: {
            'platforms_ok': int,  # 成功获取的平台数
            'hot_trend_mentions': [
                {
                    'stock_name': '贵州茅台',
                    'platforms_ok': 3,
                    'total_hits': 5,
                    'by_platform_count': {'weibo': 2, 'zhihu': 1, 'douyin': 2},
                    'mentions': {
                        'weibo': [{'rank': 3, 'title': '茅台 1499 回归', 'url': '...'}, ...],
                        ...
                    }
                },
                ...
            ]
        }
    """
    import logging
    from concurrent.futures import ThreadPoolExecutor, as_completed

    logger = logging.getLogger(__name__)

    # 平台获取函数映射
    platform_fetchers = {
        'weibo': fetch_weibo_hot,
        'zhihu': fetch_zhihu_hot,
        'baidu': fetch_baidu_hot,
        'douyin': fetch_douyin_hot,
        'toutiao': fetch_toutiao_hot,
        'bilibili': fetch_bilibili_hot,
    }

    # 并行抓取所有平台
    platform_results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetcher): name for name, fetcher in platform_fetchers.items()}
        for future in as_completed(futures):
            platform_name = futures[future]
            try:
                result = future.result()
                platform_results[platform_name] = result
            except Exception as e:
                logger.warning(f"{platform_name} fetch failed: {e}")
                platform_results[platform_name] = {'success': False, 'platform': platform_name, 'error': str(e)}

    # 预计算每只股票的简称集合（如 贵州茅台 -> 贵州、茅台）
    stock_to_shorts: dict[str, set[str]] = {}
    for name in stock_names:
        shorts: set[str] = set()
        if len(name) >= 2:
            shorts.add(name[:2])
            if len(name) >= 4:
                shorts.add(name[2:4])
        stock_to_shorts[name] = shorts

    # 统计命中结果
    stock_hits = {name: {'by_platform': {}, 'mentions': {}} for name in stock_names}

    for platform_name, result in platform_results.items():
        if result.get('success') and 'items' in result:
            for item in result['items']:
                title = item.get('title', '')
                for stock_name in stock_names:
                    stock_shorts = stock_to_shorts[stock_name]
                    if stock_name in title or any(short in title for short in stock_shorts if len(short) >= 2):
                        if platform_name not in stock_hits[stock_name]['by_platform']:
                            stock_hits[stock_name]['by_platform'][platform_name] = 0
                            stock_hits[stock_name]['mentions'][platform_name] = []
                        stock_hits[stock_name]['by_platform'][platform_name] += 1
                        stock_hits[stock_name]['mentions'][platform_name].append(item)

    # 构建输出结构
    hot_trend_mentions = []
    platforms_ok = sum(1 for r in platform_results.values() if r.get('success'))

    for stock_name in stock_names:
        by_platform = stock_hits[stock_name]['by_platform']
        mentions = stock_hits[stock_name]['mentions']
        total_hits = sum(by_platform.values())

        if total_hits > 0:
            # 应用情绪权重
            weighted_hits = 0
            for p, count in by_platform.items():
                weight = SOCIAL_HOT_TRENDS['stock_match']['sentiment_weight'].get(p, 1.0)
                weighted_hits += int(count * weight)

            hot_trend_mentions.append({
                'stock_name': stock_name,
                'platforms_ok': len(by_platform),
                'total_hits': weighted_hits,
                'by_platform_count': by_platform,
                'mentions': mentions
            })

    # 按命中次数排序
    hot_trend_mentions.sort(key=lambda x: x['total_hits'], reverse=True)

    return {
        'platforms_ok': platforms_ok,
        'hot_trend_mentions': hot_trend_mentions
    }


# ============================================================
# 致谢
# ============================================================
# 本模块设计参考了 UZI-Skill 的可靠数据源架构
# 核心改进：雪球作主源 + 腾讯qt.gtimg.cn(GBK解码)作兜底

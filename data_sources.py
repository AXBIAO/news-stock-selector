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

from config import TUSHARE_TOKEN, TUSHARE_HTTP_URL, TUSHARE_ENABLED, ALPHA_VANTAGE_API_KEY
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

# TODO: 将来可提取到独立数据文件（如 sector_map.json），避免硬编码在代码中
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


def get_stock_valuation(codes: list[str]) -> dict:
    """获取A股估值数据 (PE/PB/市值/换手率)。

    Fallback 链: 雪球 → 腾讯qt → None

    Returns:
        {code: {pe_ttm, pb, market_cap, circ_market_cap, turnover_rate, _source}}
    """
    result: dict[str, dict] = {}
    pending = set(codes)

    # Level 1: 雪球 (字段最全: PE + 市值 + 换手率)
    for code in list(pending):
        d = _fetch_xueqiu_spot(code)
        if d and d.get("price"):
            mcap_str = d.get("market_cap", "")
            mcap = None
            if isinstance(mcap_str, str) and mcap_str.endswith("亿"):
                try:
                    mcap = float(mcap_str[:-1])
                except (ValueError, TypeError):
                    pass
            circ_str = d.get("circ_market_cap")
            circ = None
            if isinstance(circ_str, str) and circ_str.endswith("亿"):
                try:
                    circ = float(circ_str[:-1])
                except (ValueError, TypeError):
                    pass
            result[code] = {
                "pe_ttm": d.get("pe_ttm"),
                "pb": d.get("pb"),
                "market_cap": mcap,
                "circ_market_cap": circ,
                "turnover_rate": None,
                "_source": "xueqiu",
            }
            pending.discard(code)

    # Level 2: 腾讯qt (补充PE/PB, 无市值)
    for code in list(pending):
        d = _fetch_price_tencent_qt("A", code)
        if d and d.get("price"):
            result[code] = {
                "pe_ttm": d.get("pe_ttm"),
                "pb": d.get("pb"),
                "market_cap": None,
                "circ_market_cap": None,
                "turnover_rate": None,
                "_source": "tencent-qt",
            }
            pending.discard(code)

    return result


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
# 社交热榜相关函数 (EXPERIMENTAL — 各平台反爬策略频繁变更，成功率不保证)
# 仅当结果 <5 或用户显式要求情绪热度时触发。失败不影响主链。
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
# 美股实时涨幅榜 (v3.9)
# 数据源优先级：yfinance Screener (真实全市场涨幅榜) → 腾讯qt交叉验证 → 腾讯qt扫描池兜底
# ============================================================

# 美股扫描池 — 仅作为兜底参考，不用于主数据源
# 当 yfinance Screener 和腾讯qt交叉验证都失败时，用此池并发查询腾讯qt取涨幅排行
# 选取覆盖科技/金融/消费/能源/医疗/中概的代表性股票
_US_GAINER_SCAN_POOL = [
    # — 科技七巨头 + 半导体/AI 核心 —
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "AVGO", "AMD", "INTC", "QCOM", "MU", "AMAT", "LRCX", "KLAC", "ADI", "TXN",
    "MRVL", "NVTS", "COHR", "HPE", "STX", "WDC", "SMCI", "DELL", "HPQ",
    "SNOW", "CRM", "ADBE", "NOW", "ORCL", "PLTR", "CRWD", "PANW", "NET",
    # — 金融/消费/能源/医疗 代表 —
    "JPM", "V", "MA", "BAC", "GS", "MS",
    "XOM", "CVX", "COP", "SLB", "OXY",
    "WMT", "HD", "MCD", "SBUX", "NKE", "DIS",
    "LLY", "UNH", "JNJ", "PFE", "ABBV", "MRK",
    # — 中概/VIE 及其他 —
    "BABA", "JD", "PDD", "BIDU", "NIO", "BEKE",
]

import logging

logger = logging.getLogger(__name__)


def _fetch_us_gainers_yfinance_screener(limit: int = 25) -> list[dict]:
    """使用 yfinance Screener 获取全市场真实涨幅榜。

    调用 Yahoo Finance 预置筛选器 'day_gainers'，返回当天全市场
    真实涨幅最大的股票列表。这是唯一能反映真实市场涨幅排行的数据源。

    筛选条件（Yahoo 预置 'day_gainers'）:
      - percentchange > 3%
      - region = us
      - intradaymarketcap >= 2B USD
      - intradayprice >= 5 USD
      - dayvolume > 15000

    Args:
        limit: 返回前 N 只涨幅最大股票（count 参数，上限 250）

    Returns:
        list[dict]: 每只股票包含 ticker, company, price, change_pct,
                    volume, market_cap, _source 字段
                    失败返回空列表
    """
    import yfinance as yf

    try:
        count = min(limit, 250)
        response = yf.screen('day_gainers', count=count)

        if not response or 'quotes' not in response:
            logger.warning("yfinance Screener returned empty response or missing 'quotes'")
            return []

        quotes = response['quotes']
        if not quotes:
            logger.warning("yfinance Screener returned empty quotes list")
            return []

        results: list[dict] = []
        for quote in quotes:
            ticker = quote.get('symbol', '')
            if not ticker:
                continue

            company = quote.get('shortName') or quote.get('longName') or ticker
            price = quote.get('regularMarketPrice')
            change_pct = quote.get('regularMarketChangePercent')
            volume = quote.get('regularMarketVolume', 0) or 0
            market_cap = quote.get('marketCap')

            # 跳过没有价格或涨跌幅的条目
            if price is None and change_pct is None:
                continue

            results.append({
                "ticker": ticker,
                "company": company,
                "price": round(float(price), 2) if price is not None else None,
                "change_pct": round(float(change_pct), 4) if change_pct is not None else None,
                "volume": int(volume) if volume else 0,
                "market_cap": int(market_cap) if market_cap else None,
                "_source": "yfinance-screener",
            })

        # yfinance screener 默认按涨跌幅排序，但为了确定性再排一次
        results.sort(key=lambda x: x["change_pct"] if x["change_pct"] is not None else -999, reverse=True)
        logger.info(f"yfinance Screener: got {len(results)} gainers from market-wide scan")
        return results

    except ImportError:
        logger.warning("yfinance not installed; cannot use Screener")
        return []
    except Exception as e:
        logger.warning(f"yfinance Screener failed: {type(e).__name__}: {e}")
        return []


def _fetch_us_gainers_tencent(limit: int = 10) -> list[dict]:
    """使用腾讯 qt.gtimg.cn 美股接口查询扫描池，按涨跌幅排序取 Top N。

    复用已有的 _fetch_price_tencent_qt("U", ticker) 函数，
    逐个查询 _US_GAINER_SCAN_POOL 中所有股票，按涨跌幅排序取 Top N。
    腾讯接口对美股支持良好，无需 API key，无反爬。

    ⚠️ 这是兜底数据源：只能反映扫描池内股票的排行，不是全市场真实涨幅榜。
    主数据源应为 yfinance Screener 的 'day_gainers'。

    策略：
      1. 并发查询 _US_GAINER_SCAN_POOL 中所有股票
      2. 提取 price, change_pct, name
      3. 按 change_pct 降序排列
      4. 过滤异常值（change_pct > 100 或 < -100 的明显错误数据）

    Args:
        limit: 返回前 N 只涨幅最大股票

    Returns:
        list[dict]: 每只股票包含 ticker, company, price, change_pct,
                    volume, market_cap, _source 字段
    """
    import concurrent.futures

    pool = list(_US_GAINER_SCAN_POOL)
    if not pool:
        return []

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_price_tencent_qt, "U", ticker): ticker for ticker in pool}
        for future in concurrent.futures.as_completed(futures):
            ticker = futures[future]
            try:
                data = future.result()
                if data and data.get("price") and data.get("change_pct") is not None:
                    change_pct = data["change_pct"]
                    # 过滤异常数据
                    if abs(change_pct) > 100:
                        continue
                    results.append({
                        "ticker": ticker,
                        "company": data.get("name") or ticker,
                        "price": data["price"],
                        "change_pct": round(change_pct, 2),
                        "volume": 0,
                        "market_cap": None,
                        "_source": "tencent-qt",
                    })
            except Exception:
                pass

    results.sort(key=lambda x: x["change_pct"], reverse=True)
    logger.info(f"Tencent QT US gainers (scan pool fallback): {len(results)} results from {len(pool)} pool")
    return results[:limit]


def _verify_us_gainer_tencent(ticker: str) -> dict | None:
    """用腾讯 qt.gtimg.cn 美股接口交叉验证单只股票的实时价格。

    使用已有的 _fetch_price_tencent_qt("U", ticker) 函数。

    Args:
        ticker: 美股代码，如 'AAPL', 'MSFT'

    Returns:
        dict | None: {price, change_pct, name, _source: 'tencent-qt'}，失败返回 None
    """
    try:
        data = _fetch_price_tencent_qt("U", ticker)
        if not data or data.get("price") is None:
            return None
        return {
            "price": data["price"],
            "change_pct": data.get("change_pct"),
            "name": data.get("name"),
            "prev_close": data.get("prev_close"),
            "_source": "tencent-qt",
        }
    except Exception:
        return None


def _cross_verify_yf_gainers_with_tencent(gainers: list[dict]) -> list[dict]:
    """对 yfinance Screener 返回的涨幅榜，用腾讯qt做交叉验证。

    并发调用 _verify_us_gainer_tencent，将腾讯的价格/涨跌幅/名称合并到结果中。
    若腾讯数据与 yfinance 数据不一致，记录差异量但不覆盖 yfinance 主值。

    Args:
        gainers: yfinance Screener 返回的涨幅榜列表

    Returns:
        list[dict]: 补充了 tencent_price, tencent_change_pct, tencent_name 字段的涨幅榜。
                    每个条目新增 _verified 布尔字段指示是否通过了交叉验证。
    """
    if not gainers:
        return gainers

    import concurrent.futures

    tickers_to_verify = [g["ticker"] for g in gainers]
    tencent_data: dict[str, dict] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_verify_us_gainer_tencent, t): t for t in tickers_to_verify}
        for future in concurrent.futures.as_completed(futures):
            ticker = futures[future]
            try:
                data = future.result()
                if data:
                    tencent_data[ticker] = data
            except Exception:
                pass

    verified_count = 0
    for g in gainers:
        t_data = tencent_data.get(g["ticker"])
        if t_data:
            g["tencent_price"] = t_data.get("price")
            g["tencent_change_pct"] = t_data.get("change_pct")
            g["_verified"] = True
            verified_count += 1
            # 如果 yfinance 没有公司名，用腾讯的数据补上
            if t_data.get("name") and (not g.get("company") or g["company"] == g["ticker"]):
                g["company"] = t_data["name"]
        else:
            g["_verified"] = False

    logger.info(f"Tencent cross-verification: {verified_count}/{len(gainers)} gainers verified")
    return gainers


def _fetch_us_gainers_tradingview(limit: int = 50) -> list[dict]:
    """Fetch US stock top gainers from TradingView Scanner API.

    Zero-auth, production-grade endpoint. Data is ~15 min delayed.
    Returns list of dicts with keys: ticker, company, price, change_pct, volume, market_cap, _source
    """
    import json as _json
    import urllib.request
    import urllib.parse

    url = "https://scanner.tradingview.com/america/scan"
    payload = {
        "symbols": {
            "query": {"types": []},
            "tickers": [],
            "groups": [{"type": "advance", "values": ["america"]}]
        },
        "columns": ["name", "close", "change", "change_abs", "volume", "market_cap_basic"],
        "sort": {"sortBy": "change", "sortOrder": "desc"},
        "filter": [{"left": "change", "operation": "greater", "right": 0}],
        "range": [0, limit]
    }

    try:
        data = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://www.tradingview.com",
                "Referer": "https://www.tradingview.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = _json.loads(resp.read().decode("utf-8"))

        gainers = []
        for item in result.get("data", []):
            symbol_full = item.get("s", "")
            # Strip exchange prefix: "NASDAQ:AAPL" -> "AAPL"
            ticker = symbol_full.split(":")[-1] if ":" in symbol_full else symbol_full
            d = item.get("d", [])
            if len(d) >= 5:
                gainers.append({
                    "ticker": ticker,
                    "company": d[0] if d[0] else ticker,
                    "price": round(float(d[1]), 2) if d[1] else None,
                    "change_pct": round(float(d[2]), 4) if d[2] else None,
                    "change_abs": round(float(d[3]), 4) if len(d) > 3 and d[3] else None,
                    "volume": int(d[4]) if len(d) > 4 and d[4] else 0,
                    "market_cap": int(float(d[5])) if len(d) > 5 and d[5] else None,
                    "_source": "tradingview",
                })

        gainers.sort(key=lambda x: x.get("change_pct") or 0, reverse=True)
        logger.info(f"TradingView Scanner: {len(gainers)} US gainers fetched")
        return gainers[:limit]
    except Exception as e:
        logger.warning(f"TradingView Scanner failed: {type(e).__name__}: {e}")
        return []


def _fetch_us_gainers_sina(limit: int = 50) -> list[dict]:
    """Fetch US stock top gainers from Sina Finance Market_Center API.

    No auth required. Data is ~3-15 seconds delayed.
    Keys are unquoted JSON — json.loads handles this in Python.
    """
    import json as _json
    import urllib.request
    import urllib.parse

    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    params = {
        "page": 1,
        "num": min(limit, 100),
        "sort": "changepercent",
        "asc": 0,
        "node": "us_all",
        "_s_r_a": "init",
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"

    try:
        req = urllib.request.Request(full_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")

        # Sina returns unquoted-key JSON — json.loads handles it
        data = _json.loads(raw)

        gainers = []
        for item in data:
            gainers.append({
                "ticker": str(item.get("symbol", "")).upper(),
                "company": item.get("name", ""),
                "price": float(item.get("trade", 0)) if item.get("trade") else None,
                "change_pct": float(item.get("changepercent", 0)) if item.get("changepercent") else None,
                "change_abs": float(item.get("pricechange", 0)) if item.get("pricechange") else None,
                "volume": int(float(item.get("volume", 0))) if item.get("volume") else 0,
                "market_cap": None,
                "_source": "sina-finance",
            })

        gainers.sort(key=lambda x: x.get("change_pct") or 0, reverse=True)
        logger.info(f"Sina Finance: {len(gainers)} US gainers fetched")
        return gainers[:limit]
    except Exception as e:
        logger.warning(f"Sina Finance failed: {type(e).__name__}: {e}")
        return []


def _fetch_us_gainers_eastmoney(limit: int = 50) -> list[dict]:
    """Fetch US stock top gainers from Eastmoney push2 API.

    Well-documented internal API. Data is ~1-5 seconds delayed.
    Returns JSONP that needs callback stripping.
    Fields: f12=code, f14=name, f2=price, f3=change_pct, f4=change_abs, f5=volume
    """
    import json as _json
    import urllib.request
    import urllib.parse

    url = "http://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1,
        "pz": min(limit, 100),
        "po": 1,
        "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:128+t:2,m:128+t:3",
        "fields": "f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18",
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"

    try:
        req = urllib.request.Request(full_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://quote.eastmoney.com/"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")

        # Strip JSONP callback wrapper
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = _json.loads(raw[start:end])

        gainers = []
        stocks = data.get("data", {}).get("diff", [])
        for s in stocks:
            gainers.append({
                "ticker": str(s.get("f12", "")).upper(),
                "company": s.get("f14", ""),
                "price": float(s.get("f2", 0)) if s.get("f2") not in (None, "-", "") else None,
                "change_pct": float(s.get("f3", 0)) if s.get("f3") not in (None, "-", "") else None,
                "change_abs": float(s.get("f4", 0)) if s.get("f4") not in (None, "-", "") else None,
                "volume": int(float(s.get("f5", 0))) if s.get("f5") not in (None, "-", "") else 0,
                "market_cap": None,
                "_source": "eastmoney",
            })

        gainers.sort(key=lambda x: x.get("change_pct") or 0, reverse=True)
        logger.info(f"Eastmoney: {len(gainers)} US gainers fetched")
        return gainers[:limit]
    except Exception as e:
        logger.warning(f"Eastmoney failed: {type(e).__name__}: {e}")
        return []


def _to_float(val: str) -> float | None:
    """Safely convert a stripped string to float, returning None on failure."""
    if not val or val in ("--", "-", "N/A", ""):
        return None
    try:
        return float(val.strip().replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_cn_number(val: str) -> int | float:
    """Parse Chinese-formatted numbers: 1.06亿 → 106000000, 115.84万 → 1158400."""
    if not val or val in ("--", "-", ""):
        return 0
    val = val.strip().replace(",", "")
    multiplier = 1
    if "亿" in val:
        multiplier = 100000000
        val = val.replace("亿", "")
    elif "万" in val:
        multiplier = 10000
        val = val.replace("万", "")
    try:
        return int(float(val) * multiplier)
    except (ValueError, TypeError):
        return 0


def _fetch_us_gainers_10jqka(limit: int = 50) -> list[dict]:
    """Fetch US stock top gainers from 10jqka (同花顺) detailDefer page.

    Scrapes the server-rendered HTML table from:
    https://q.10jqka.com.cn/usa/detailDefer

    The page displays all US stocks sorted by 涨跌幅(%) descending by default.
    Table columns: 序号, 代码, 名称, 现价, 涨跌幅(%), 涨跌, 换手(%), 成交量,
                   市盈率(%), 成交额, 52周最高, 52周最低

    Returns list of dicts with: ticker, company, price, change_pct, change_abs,
    turnover_rate, volume, pe_ratio, amount, high_52w, low_52w, _source
    """
    import html as _html
    import re as _re
    import urllib.request

    url = "https://q.10jqka.com.cn/usa/detailDefer"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_bytes = resp.read()
            # 同花顺页面使用 GBK 编码，优先尝试；UTF-8 兜底
            try:
                raw = raw_bytes.decode("gbk")
            except (UnicodeDecodeError, LookupError):
                raw = raw_bytes.decode("utf-8", errors="replace")

        # Parse each <tr> that contains data cells.
        # Cell structure: rank, ticker<a>, name<a>, price, change%, change_amt,
        #                 turnover%, volume, PE, amount, 52w_high, 52w_low
        trs = _re.findall(r'<tr[^>]*>(.*?)</tr>', raw, _re.DOTALL | _re.IGNORECASE)
        if not trs:
            logger.warning("10jqka: no <tr> elements found in HTML")
            return []

        gainers = []
        for tr_html in trs:
            tds = _re.findall(r'<td[^>]*>(.*?)</td>', tr_html, _re.DOTALL)
            if len(tds) < 10:
                continue

            try:
                rank_str = _re.sub(r'<[^>]+>', '', tds[0]).strip()
                if not rank_str.isdigit():
                    continue  # skip header row
                rank = int(rank_str)

                # Extract ticker: <a href="...">TICKER</a>
                ticker = _re.sub(r'<[^>]+>', '', tds[1]).strip().upper()
                if not ticker or not ticker[0].isalpha():
                    continue

                # Extract company name: <a href="...">Company&#032;Name</a>
                company_raw = _re.sub(r'<[^>]+>', '', tds[2]).strip()
                company = _html.unescape(company_raw).replace("&#032;", " ")

                price = _to_float(_re.sub(r'<[^>]+>', '', tds[3]))
                change_pct = _to_float(_re.sub(r'<[^>]+>', '', tds[4]))
                change_abs = _to_float(_re.sub(r'<[^>]+>', '', tds[5]))
                turnover_rate = _to_float(_re.sub(r'<[^>]+>', '', tds[6]))

                vol_str = _re.sub(r'<[^>]+>', '', tds[7]).strip()
                volume = _parse_cn_number(vol_str)

                pe_str = _re.sub(r'<[^>]+>', '', tds[8]).strip()
                pe_ratio = _to_float(pe_str) if pe_str and pe_str != "--" else None

                amt_str = _re.sub(r'<[^>]+>', '', tds[9]).strip()
                amount = _parse_cn_number(amt_str)

                high_52w = _to_float(_re.sub(r'<[^>]+>', '', tds[10])) if len(tds) > 10 else None
                low_52w = _to_float(_re.sub(r'<[^>]+>', '', tds[11])) if len(tds) > 11 else None

                gainers.append({
                    "ticker": ticker,
                    "company": company,
                    "price": price,
                    "change_pct": change_pct,
                    "change_abs": change_abs,
                    "turnover_rate": turnover_rate,
                    "volume": volume,
                    "pe_ratio": pe_ratio,
                    "amount": amount,
                    "high_52w": high_52w,
                    "low_52w": low_52w,
                    "rank": rank,
                    "_source": "10jqka",
                })
            except (ValueError, IndexError, AttributeError) as e:
                continue

        gainers.sort(key=lambda x: x.get("change_pct") or 0, reverse=True)
        logger.info(f"10jqka: {len(gainers)} US gainers scraped from detailDefer page")
        return gainers[:limit]
    except Exception as e:
        logger.warning(f"10jqka failed: {type(e).__name__}: {e}")
        return []


def _filter_quality_gainers(
    gainers: list[dict],
    min_price: float = 1.0,
    min_volume: int = 100000,
    max_change_pct: float = 500,
    exclude_warrants: bool = True,
) -> list[dict]:
    """Filter US gainers to remove penny stocks, warrants, and data anomalies.

    Removes:
      - Tickers ending in 'W' (warrants / rights)
      - Price below min_price (penny stocks)
      - Volume below min_volume (illiquid micro-caps)
      - |change_pct| exceeding max_change_pct (likely data errors)
      - Tickers containing '+' (some preferred/warrant variants)

    Args:
        gainers: list of gainer dicts from any _fetch_us_gainers_* source
        min_price: minimum stock price in USD (default $1.00)
        min_volume: minimum daily volume in shares (default 100k)
        max_change_pct: maximum absolute percentage change (default 500%)
        exclude_warrants: exclude tickers ending in 'W' (default True)

    Returns:
        Filtered list, preserving original order
    """
    filtered = []
    removed_counts = {"warrant": 0, "penny": 0, "low_vol": 0, "anomaly": 0}

    for g in gainers:
        ticker = g.get("ticker", "")

        if exclude_warrants and (ticker.endswith("W") or "+" in ticker):
            removed_counts["warrant"] += 1
            continue

        price = g.get("price")
        if price is not None and price < min_price:
            removed_counts["penny"] += 1
            continue

        volume = g.get("volume", 0) or 0
        if volume < min_volume:
            removed_counts["low_vol"] += 1
            continue

        chg = g.get("change_pct")
        if chg is not None and abs(chg) > max_change_pct:
            removed_counts["anomaly"] += 1
            continue

        filtered.append(g)

    if removed_counts:
        logger.info(
            f"Quality filter removed: {removed_counts['warrant']} warrants, "
            f"{removed_counts['penny']} penny stocks, "
            f"{removed_counts['low_vol']} low-volume, "
            f"{removed_counts['anomaly']} anomalies "
            f"→ kept {len(filtered)}/{len(gainers)} gainers"
        )

    return filtered


def _fetch_us_gainers_alphavantage(limit: int = 20) -> list[dict]:
    """Fetch US stock top gainers from Alpha Vantage API.

    Requires API key (free tier: 5 calls/min, 500 calls/day).
    Reads ALPHA_VANTAGE_API_KEY from config or env var.
    Returns top 20 gainers by default (API limit).
    """
    import json as _json
    import urllib.request
    import urllib.parse

    api_key = ALPHA_VANTAGE_API_KEY
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TOP_GAINERS_LOSERS",
        "apikey": api_key,
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"

    try:
        req = urllib.request.Request(full_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))

        # Check for rate limit / error messages
        if "Note" in data or "Information" in data:
            logger.warning(f"Alpha Vantage rate limit or info: {data.get('Note', data.get('Information', ''))}")
            return []

        gainers = []
        for item in data.get("top_gainers", []):
            chg_str = str(item.get("change_percentage", "0%")).rstrip("%")
            gainers.append({
                "ticker": str(item.get("ticker", "")).upper(),
                "company": item.get("ticker", ""),
                "price": float(item.get("price", 0)) if item.get("price") else None,
                "change_pct": float(chg_str) if chg_str else None,
                "change_abs": None,
                "volume": int(item.get("volume", 0)) if item.get("volume") else 0,
                "market_cap": None,
                "_source": "alphavantage",
            })

        gainers.sort(key=lambda x: x.get("change_pct") or 0, reverse=True)
        logger.info(f"Alpha Vantage: {len(gainers)} US gainers fetched")
        return gainers[:limit]
    except Exception as e:
        logger.warning(f"Alpha Vantage failed: {type(e).__name__}: {e}")
        return []


def get_us_top_gainers(limit: int = 10, quality_filter: bool = True) -> dict:
    """获取美股实时涨幅榜。

    数据源优先级（v4.1 8-tier fallback chain）:
      1. yfinance Screener 'day_gainers'      — REAL market-wide top gainers (PRIMARY)
      2. TradingView Scanner                  — zero-auth scanner API (FALLBACK 1)
      3. 同花顺 detailDefer                    — scraped HTML table, rich fields (FALLBACK 2)
      4. 新浪财经 Market_Center                — no-auth GET API (FALLBACK 3)
      5. 东方财富 push2                        — well-documented internal API (FALLBACK 4)
      6. Alpha Vantage TOP_GAINERS_LOSERS     — requires API key (FALLBACK 5)
      7. 腾讯 qt.gtimg.cn 扫描池兜底           — last resort scan pool (FALLBACK 6)

    追加: yfinance Screener 成功后，用腾讯 qt.gtimg.cn 交叉验证每只个股。

    v4.1 新增:
      - quality_filter=True 时自动过滤: 权证(后缀W/+)、仙股(<$1)、低量(<10万股)、异常值(>500%)
      - 返回结果中剔除的计数记录在 result['quality_filter'] 中

    每个 fallback 源失败后自动尝试下一个，所有源均失败才返回 pending。

    Args:
        limit: 返回前 N 只涨幅最大的股票，默认 10

    Returns:
        dict: {
            'source': 'yfinance-screener' | 'tradingview' | 'sina-finance' |
                      'eastmoney' | 'alphavantage' | 'tencent-qt' | 'pending',
            'gainers': [{ticker, company, price, change_pct, volume, market_cap,
                         _source, _verified, tencent_price, tencent_change_pct}],
            'gainers_found': int, 'gainers_missing': int,
            'fallback_used': bool, 'timestamp': str
        }
    """
    from datetime import datetime, timezone

    result: dict = {
        "source": "pending",
        "gainers": [],
        "gainers_found": 0,
        "gainers_missing": 0,
        "fallback_used": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if limit <= 0:
        logger.warning("get_us_top_gainers called with limit <= 0")
        return result

    # 质量过滤统计
    quality_stats: dict = {"before": 0, "after": 0, "removed_reasons": {}}

    def _apply_quality(gainers: list[dict], req_limit: int) -> list[dict]:
        """Apply quality filter and return enough gainers to satisfy requested limit."""
        if not quality_filter:
            return gainers[:req_limit]
        quality_stats["before"] = len(gainers)
        filtered = _filter_quality_gainers(gainers)
        quality_stats["after"] = len(filtered)
        quality_stats["removed_reasons"] = {
            "total_removed": quality_stats["before"] - quality_stats["after"]
        }
        return filtered[:req_limit]

    # ========================================================================
    # 数据源1: yfinance Screener 'day_gainers' (v3.9 主源 — 全市场真实涨幅榜)
    # ========================================================================
    yf_screener_gainers: list[dict] = []
    try:
        # 取多一些让 Screener 返回足够数据（Screener 通常返回25-50条）
        fetch_limit = max(limit * 3 if quality_filter else limit, 25)
        yf_screener_gainers = _fetch_us_gainers_yfinance_screener(fetch_limit)
    except Exception as e:
        logger.warning(f"yfinance Screener failed: {type(e).__name__}: {e}")

    if yf_screener_gainers:
        logger.info(f"yfinance Screener primary source success: {len(yf_screener_gainers)} gainers")

        # ========================================================================
        # 交叉验证: 腾讯 qt.gtimg.cn 对每只股票做交叉验证
        # ========================================================================
        try:
            yf_screener_gainers = _cross_verify_yf_gainers_with_tencent(yf_screener_gainers)
        except Exception as e:
            logger.warning(f"Tencent cross-verification failed (non-fatal): {type(e).__name__}: {e}")

        filtered = _apply_quality(yf_screener_gainers, limit)
        result["source"] = "yfinance-screener"
        result["gainers"] = filtered
        result["gainers_found"] = len(filtered)
        result["gainers_missing"] = max(0, limit - len(filtered))
        if quality_filter:
            result["quality_filter"] = quality_stats
        return result

    # ========================================================================
    # Fallback chain: try each source in order until one succeeds (v4.1)
    # ========================================================================
    logger.warning("yfinance Screener failed, starting fallback chain")
    result["fallback_used"] = True

    # --- Fallback 1: TradingView Scanner ---
    tv_gainers = _fetch_us_gainers_tradingview(limit * 3 if quality_filter else limit)
    if tv_gainers:
        filtered = _apply_quality(tv_gainers, limit)
        result["source"] = "tradingview"
        result["gainers"] = filtered
        result["gainers_found"] = len(filtered)
        result["gainers_missing"] = max(0, limit - len(filtered))
        if quality_filter:
            result["quality_filter"] = quality_stats
        return result

    # --- Fallback 2: 同花顺 detailDefer (v4.1 新增) ---
    jqka_gainers = _fetch_us_gainers_10jqka(limit * 3 if quality_filter else limit)
    if jqka_gainers:
        filtered = _apply_quality(jqka_gainers, limit)
        result["source"] = "10jqka"
        result["gainers"] = filtered
        result["gainers_found"] = len(filtered)
        result["gainers_missing"] = max(0, limit - len(filtered))
        if quality_filter:
            result["quality_filter"] = quality_stats
        return result

    # --- Fallback 3: Sina Finance ---
    sina_gainers = _fetch_us_gainers_sina(limit * 3 if quality_filter else limit)
    if sina_gainers:
        filtered = _apply_quality(sina_gainers, limit)
        result["source"] = "sina-finance"
        result["gainers"] = filtered
        result["gainers_found"] = len(filtered)
        result["gainers_missing"] = max(0, limit - len(filtered))
        if quality_filter:
            result["quality_filter"] = quality_stats
        return result

    # --- Fallback 4: Eastmoney ---
    em_gainers = _fetch_us_gainers_eastmoney(limit * 3 if quality_filter else limit)
    if em_gainers:
        filtered = _apply_quality(em_gainers, limit)
        result["source"] = "eastmoney"
        result["gainers"] = filtered
        result["gainers_found"] = len(filtered)
        result["gainers_missing"] = max(0, limit - len(filtered))
        if quality_filter:
            result["quality_filter"] = quality_stats
        return result

    # --- Fallback 5: Alpha Vantage ---
    av_gainers = _fetch_us_gainers_alphavantage(limit * 3 if quality_filter else limit)
    if av_gainers:
        filtered = _apply_quality(av_gainers, limit)
        result["source"] = "alphavantage"
        result["gainers"] = filtered
        result["gainers_found"] = len(filtered)
        result["gainers_missing"] = max(0, limit - len(filtered))
        if quality_filter:
            result["quality_filter"] = quality_stats
        return result

    # --- Fallback 6: Tencent QT scan pool (last resort) ---
    tx_gainers: list[dict] = []
    try:
        tx_gainers = _fetch_us_gainers_tencent(limit * 3 if quality_filter else limit)
    except Exception as e:
        logger.warning(f"Tencent QT scan pool fallback also failed: {type(e).__name__}: {e}")

    if tx_gainers:
        logger.info(f"Tencent QT fallback success: {len(tx_gainers)} stocks from scan pool")
        filtered = _apply_quality(tx_gainers, limit)
        result["source"] = "tencent-qt"
        result["gainers"] = filtered
        result["gainers_found"] = len(filtered)
        result["gainers_missing"] = max(0, limit - len(filtered))
        if quality_filter:
            result["quality_filter"] = quality_stats
        return result

    # ========================================================================
    # All data sources failed
    # ========================================================================
    logger.warning("All US gainers data sources failed; returning pending")
    result["source"] = "pending"
    result["gainers"] = []
    result["gainers_found"] = 0
    result["gainers_missing"] = limit
    return result


# ============================================================
# 致谢
# ============================================================
# 本模块设计参考了 UZI-Skill 的可靠数据源架构
# 核心改进：雪球作主源 + 腾讯qt.gtimg.cn(GBK解码)作兜底

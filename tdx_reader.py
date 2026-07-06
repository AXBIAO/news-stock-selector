# -*- coding: utf-8 -*-
"""通达信 (TDX) 本地数据读取器 — v5.1

读取通达信本地 vipdoc 目录下的日线数据(.day文件)和板块数据(.blk文件)。
无需网络，直接从本地文件解析全市场 A 股股票。

.day 文件格式（每条记录32字节）：
    [0:4]   date (int32, YYYYMMDD)
    [4:8]   open (int32, 元×100)
    [8:12]  high (int32)
    [12:16] low (int32)
    [16:20] close (int32)
    [20:24] amount (float32, 成交额/元)
    [24:28] volume (int32, 成交量)
    [28:32] reserved

用法:
    from tdx_reader import TDXReader
    reader = TDXReader(tdx_path)
    stocks = reader.scan_all_codes()        # 获取全市场5000+股票列表+最新价
    blocks = reader.read_block_file(name)   # 读取板块股票列表
"""

import os
import struct
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DailyBar:
    """单条日线数据"""
    date: int           # YYYYMMDD
    open: float
    high: float
    low: float
    close: float
    amount: float       # 成交额 (元)
    volume: int         # 成交量

    @property
    def change_pct(self) -> float:
        """当日涨跌幅 %"""
        prev_close = self.close - (self.high - self.low) * 0  # unused
        return 0.0


@dataclass
class StockSnapshot:
    """单只股票快照"""
    code: str
    name: str = ""
    market: str = ""        # sh / sz / bj
    latest_date: int = 0
    latest_close: float = 0.0
    latest_open: float = 0.0
    latest_high: float = 0.0
    latest_low: float = 0.0
    latest_amount: float = 0.0
    latest_volume: int = 0
    prev_close: float = 0.0
    change_pct: float = 0.0
    sector: str = ""        # 板块（从.blk文件名推断或由scanner填充）

    @property
    def price(self) -> float:
        return self.latest_close


class TDXReader:
    """通达信本地数据读取器"""

    _RECORD_SIZE = 32
    _RECORD_FMT = '<IIIIIfI'  # date, open, high, low, close, amount, volume + 4 reserved

    # 股票代码范围（排除指数）
    _STOCK_RANGES = {
        'sh': lambda c: (c.startswith(('600', '601', '603', '605')) or c.startswith(('688', '689'))),
        'sz': lambda c: (c.startswith(('000', '001', '002', '003', '004')) or c.startswith(('300', '301'))),
        'bj': lambda c: c.startswith(('8', '9')) and not c.startswith('899'),
    }

    def __init__(self, tdx_path: str):
        self.tdx_path = tdx_path
        self._vipdoc = os.path.join(tdx_path, 'vipdoc')
        self._block_dir = os.path.join(tdx_path, 'T0002', 'blocknew')
        self._name_cache: dict[str, str] = {}
        self._load_name_cache()

    # ── 全市场代码扫描 ──

    def scan_all_codes(self, markets: tuple = ('sh', 'sz', 'bj')) -> dict[str, StockSnapshot]:
        """扫描全市场股票代码，返回 {code: StockSnapshot} 字典。

        自动过滤指数（如000001上证指数），仅返回实际A股标的。
        """
        snapshots: dict[str, StockSnapshot] = {}
        for mkt in markets:
            lday_dir = os.path.join(self._vipdoc, mkt, 'lday')
            if not os.path.isdir(lday_dir):
                continue
            is_stock = self._STOCK_RANGES.get(mkt, lambda c: True)
            for fname in os.listdir(lday_dir):
                if not fname.endswith('.day'):
                    continue
                code = fname[2:8]  # skip market prefix
                if not code.isdigit() or len(code) != 6:
                    continue
                if not is_stock(code):
                    continue  # skip indices
                ss = self._read_latest_snapshot(mkt, code)
                if ss is not None:
                    ss.name = self._name_cache.get(code, '')
                    snapshots[code] = ss
        return snapshots

    def get_last_n_bars(self, market: str, code: str, n: int = 5) -> list[DailyBar]:
        """获取最近 N 条日线"""
        fpath = os.path.join(self._vipdoc, market, 'lday', f'{market}{code}.day')
        if not os.path.isfile(fpath):
            return []
        bars: list[DailyBar] = []
        with open(fpath, 'rb') as f:
            fsize = os.path.getsize(fpath)
            total = fsize // self._RECORD_SIZE
            start = max(0, total - n)
            f.seek(start * self._RECORD_SIZE)
            for _ in range(start, total):
                raw = f.read(self._RECORD_SIZE)
                if len(raw) < self._RECORD_SIZE:
                    break
                date, o, h, l, c = struct.unpack_from('<IIIII', raw, 0)
                amt, vol = struct.unpack_from('<fI', raw, 20)
                bars.append(DailyBar(
                    date=date, open=o / 100.0, high=h / 100.0,
                    low=l / 100.0, close=c / 100.0, amount=amt, volume=vol,
                ))
        return bars

    # ── 板块文件读取 ──

    def read_block_file(self, block_name: str) -> list[str]:
        """读取 .blk 板块文件，返回6位A股代码列表。

        TDX .blk 格式: 每行一个7位代码（首位=市场: 0=深, 1=沪），\r\n分隔。
        首行通常为板块内股票总数，自动跳过。
        """
        fpath = os.path.join(self._block_dir, block_name if block_name.endswith('.blk') else f'{block_name}.blk')
        if not os.path.isfile(fpath):
            return []
        codes = []
        with open(fpath, 'r', encoding='gbk', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.isdigit():
                    # 7位TDX格式: 0xxxxxx (深) 或 1xxxxxx (沪)
                    if len(line) == 7 and line[0] in ('0', '1'):
                        codes.append(line[1:])  # 去掉首位市场标识
                    elif len(line) == 6:
                        codes.append(line)
                    # 其他长度的数字行可能是数量头，跳过
        return codes

    def list_block_files(self) -> list[str]:
        """列出所有可用的板块文件"""
        if not os.path.isdir(self._block_dir):
            return []
        return sorted([f for f in os.listdir(self._block_dir) if f.endswith('.blk')])

    def get_block_info(self) -> dict[str, list[str]]:
        """读取所有板块 → {板块名: [代码列表]}"""
        blocks = {}
        for fname in self.list_block_files():
            name = fname.replace('.blk', '')
            codes = self.read_block_file(fname)
            if codes:
                blocks[name] = codes
        return blocks

    # ── 内部方法 ──

    def _read_latest_snapshot(self, market: str, code: str) -> Optional[StockSnapshot]:
        """读取单只股票的最新快照（最后2条记录用于计算涨跌幅）"""
        fpath = os.path.join(self._vipdoc, market, 'lday', f'{market}{code}.day')
        if not os.path.isfile(fpath):
            return None
        try:
            with open(fpath, 'rb') as f:
                fsize = os.path.getsize(fpath)
                if fsize < self._RECORD_SIZE * 2:
                    f.seek(0)
                    raw = f.read(self._RECORD_SIZE)
                    date, o, h, l, c = struct.unpack_from('<IIIII', raw, 0)
                    return StockSnapshot(code=code, market=market, latest_date=date,
                                         latest_open=o/100, latest_high=h/100,
                                         latest_low=l/100, latest_close=c/100)

                # 读最后两条
                f.seek(-self._RECORD_SIZE * 2, 2)
                prev_raw = f.read(self._RECORD_SIZE)
                curr_raw = f.read(self._RECORD_SIZE)

                p_date, p_o, p_h, p_l, p_c = struct.unpack_from('<IIIII', prev_raw, 0)
                c_date, c_o, c_h, c_l, c_c = struct.unpack_from('<IIIII', curr_raw, 0)
                c_amt, c_vol = struct.unpack_from('<fI', curr_raw, 20)

                p_close = p_c / 100.0
                c_close = c_c / 100.0
                chg_pct = round((c_close - p_close) / p_close * 100, 2) if p_close > 0 else 0.0

                return StockSnapshot(
                    code=code, market=market,
                    latest_date=c_date,
                    latest_open=c_o / 100.0, latest_high=c_h / 100.0,
                    latest_low=c_l / 100.0, latest_close=c_close,
                    latest_amount=c_amt, latest_volume=c_vol,
                    prev_close=p_close, change_pct=chg_pct,
                )
        except Exception:
            return None

    def _load_name_cache(self):
        """从多个来源加载股票名称缓存"""
        # 源1: T0002/hq_cache/code2name.ini
        ini_path = os.path.join(self.tdx_path, 'T0002', 'hq_cache', 'code2name.ini')
        if os.path.isfile(ini_path):
            try:
                with open(ini_path, 'r', encoding='gbk', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        # 格式: 代码,名称,市场,...
                        parts = line.split(',')
                        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0].isdigit():
                            self._name_cache[parts[0]] = parts[1]
            except Exception:
                pass

        # 源2: T0002/cloud_cfg XML
        cfg_path = os.path.join(self.tdx_path, 'T0002', 'cloud_cfg')
        if os.path.isdir(cfg_path):
            for fname in os.listdir(cfg_path):
                if fname.endswith('.xml') and 'BK' in fname:
                    try:
                        self._parse_xml_for_names(os.path.join(cfg_path, fname))
                    except Exception:
                        pass

        # 源3: T0002/hq_cache/base.dbf or base.map
        dbf_path = os.path.join(self.tdx_path, 'T0002', 'hq_cache', 'base.dbf')
        if os.path.isfile(dbf_path):
            try:
                with open(dbf_path, 'rb') as f:
                    content = f.read()
                # DBF格式: 在固定偏移处有名称字段
                # 简单解析: 搜索GBK编码的名称模式
                import re
                # 尝试解析DBF记录
                for m in re.finditer(rb'(\d{6})\s+([\x80-\xff]{4,16})', content):
                    try:
                        code = m.group(1).decode('ascii')
                        name = m.group(2).decode('gbk', errors='ignore').strip()
                        if code.isdigit() and len(code) == 6:
                            self._name_cache[code] = name
                    except Exception:
                        pass
            except Exception:
                pass

    def _parse_xml_for_names(self, xml_path: str):
        """从通达信XML配置中解析股票名称"""
        try:
            with open(xml_path, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read()
            # 简单正则解析 code="xxx" name="xxx"
            import re
            for m in re.finditer(r'code="(\d{6})".*?name="([^"]+)"', content):
                self._name_cache[m.group(1)] = m.group(2)
        except Exception:
            pass


# ── 便捷函数 ──

def create_reader(tdx_path: Optional[str] = None) -> Optional[TDXReader]:
    """自动查找通达信目录并创建 reader"""
    if tdx_path and os.path.isdir(tdx_path):
        return TDXReader(tdx_path)
    # 自动搜索
    candidates = [
        r'D:\BaiduNetdiskDownload\通达信zd_zyb_V7.73_20260117原汁原味版',
        r'C:\new_tdx', r'D:\new_tdx',
        os.path.expandvars(r'%APPDATA%\tdx'),
    ]
    for c in candidates:
        vipdoc = os.path.join(c, 'vipdoc')
        if os.path.isdir(vipdoc):
            return TDXReader(c)
    return None

# -*- coding: utf-8 -*-
"""通达信全市场扫描引擎 — v5.1

基于 tdx_reader.py 的全市场数据，提供多维度筛选和排序能力。
从5000+全市场 → 板块/行业筛选 → 多因子粗筛 → 候选池输出。

用法:
    from tdx_scanner import TDXScanner
    scanner = TDXScanner(tdx_path)
    candidates = scanner.scan_by_sectors(['半导体', '芯片', '光模块'])  # 200-500 stocks
    top50 = scanner.rank_by_momentum(candidates, top_n=50)             # 50 stocks
"""

import os
from datetime import date
from typing import Optional
from tdx_reader import TDXReader, StockSnapshot, create_reader


# ═══════════════════════════════════════════════════════════════
# 行业/概念板块关键词映射
# 搜新闻得到的关键词 → 股票名称/板块中匹配
# ═══════════════════════════════════════════════════════════════

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "半导体": ["半导体", "芯片", "晶圆", "封测", "光刻", "刻蚀", "硅片", "存储", "集成电路", "MCU", "FPGA", "GPU", "DRAM", "NAND"],
    "AI算力": ["算力", "AI", "人工智能", "大模型", "数据中心", "服务器", "IDC", "云计算", "智算"],
    "光通信": ["光模块", "光通信", "光纤", "CPO", "光器件", "光芯片", "800G", "1.6T", "光互联"],
    "机器人": ["机器人", "人形", "伺服", "减速器", "传感器", "工控", "自动化", "机器视觉"],
    "光伏": ["光伏", "硅料", "硅片", "电池片", "组件", "逆变器", "光伏玻璃", "多晶硅", "单晶硅"],
    "锂电/新能源": ["锂电池", "锂电", "碳酸锂", "正极", "负极", "电解液", "隔膜", "固态电池", "钠电池"],
    "新能源汽车": ["新能源车", "整车", "自动驾驶", "智能驾驶", "域控", "激光雷达", "热管理", "一体化压铸"],
    "医药": ["创新药", "CXO", "生物医药", "医疗器械", "疫苗", "中药", "化学药", "医疗"],
    "消费电子": ["消费电子", "手机", "AR", "VR", "MR", "可穿戴", "PC", "笔电", "面板"],
    "钢铁": ["钢铁", "普钢", "特钢", "螺纹钢", "热轧"],
    "水泥建材": ["水泥", "建材", "玻璃", "玻纤", "瓷砖", "防水"],
    "煤炭": ["煤炭", "焦煤", "焦炭", "动力煤", "煤化工"],
    "有色金属": ["铜", "铝", "金", "银", "稀土", "钨", "钼", "锂矿", "钴", "镍", "有色", "金属"],
    "电力": ["电力", "发电", "电网", "特高压", "储能", "风电", "核电", "火电", "水电"],
    "军工": ["军工", "航天", "航空", "导弹", "雷达", "卫星", "无人机", "舰船"],
    "金融": ["银行", "券商", "保险", "非银", "金融科技"],
    "地产": ["地产", "房地产", "物业", "园区"],
    "消费": ["白酒", "食品", "饮料", "家电", "服装", "化妆品", "旅游", "酒店", "餐饮"],
    "通信/5G": ["5G", "6G", "通信", "天线", "射频", "基站", "物联网"],
    "软件": ["软件", "SAAS", "ERP", "信创", "操作系统", "数据库", "中间件", "办公"],
}

# 停止词 (出现在名称中但不是股票关键字的词)
_STOP_WORDS = {"股份", "集团", "科技", "有限", "公司", "股份有限", "技术", "股份公司"}


class TDXScanner:
    """全市场扫描引擎"""

    # 板块 → 典型代码前缀（精简版，只保留最相关的）
    SECTOR_CODE_PREFIX: dict[str, list[str]] = {
        "半导体": ["688"],      # 科创板半导体最多
        "AI算力": ["688"],      # 科创板AI
        "机器人": ["688", "300"],
        "软件": ["300"],
        "军工": ["600"],        # 军工央企多在沪市
    }

    def __init__(self, tdx_path: Optional[str] = None):
        reader = create_reader(tdx_path)
        if reader is None:
            raise FileNotFoundError("Cannot find TDX installation. Specify tdx_path.")
        self.reader = reader
        self._all_stocks_cache: Optional[dict[str, StockSnapshot]] = None

    @property
    def all_stocks(self) -> dict[str, StockSnapshot]:
        """全市场股票缓存（延迟加载）"""
        if self._all_stocks_cache is None:
            self._all_stocks_cache = self.reader.scan_all_codes(('sh', 'sz', 'bj'))
        return self._all_stocks_cache

    def scan_all(self) -> dict[str, StockSnapshot]:
        """扫描全市场A股（已过滤指数）"""
        return self.all_stocks

    def scan_by_sectors(self, keywords: list[str], top_per_sector: int = 0) -> dict[str, StockSnapshot]:
        """按行业/概念关键词筛选全市场股票。

        双通道匹配：
        1. 名称匹配（如果有名称缓存）→ 精确
        2. 代码前缀 + SECTOR_CODE_PREFIX 映射（兜底）→ 宽泛但覆盖面大
        """
        matched: dict[str, StockSnapshot] = {}
        all_stocks = self.all_stocks

        for kw in keywords:
            category = self._find_category(kw)
            match_words = self._expand_keyword(kw)

            if category:
                # 方式1: 代码前缀快速过滤
                prefixes = self.SECTOR_CODE_PREFIX.get(category, [])
                if prefixes:
                    for code, snap in all_stocks.items():
                        if any(code.startswith(pf) for pf in prefixes):
                            if code not in matched:
                                matched[code] = snap
                    continue

            # 方式2: 名称匹配（如果有名称）
            if self.reader._name_cache:
                for code, snap in all_stocks.items():
                    if code in matched:
                        continue
                    name = snap.name or self.reader._name_cache.get(code, '')
                    if not name:
                        continue
                    score = self._match_score(code, name, match_words)
                    if score > 0:
                        matched[code] = snap
                        if top_per_sector > 0 and len(matched) >= top_per_sector * len(keywords):
                            break

        return matched

    def scan_by_sectors_named(
        self, keywords: list[str], names_lookup: dict[str, str]
    ) -> dict[str, StockSnapshot]:
        """按关键词筛选，使用外部名称查找表进行精确匹配。

        Args:
            keywords: 行业关键词
            names_lookup: {code: name} 字典（可从 tencent-qt 批量获取）
        """
        matched: dict[str, StockSnapshot] = {}
        for kw in keywords:
            match_words = self._expand_keyword(kw)
            for code, snap in self.all_stocks.items():
                if code in matched:
                    continue
                name = names_lookup.get(code, snap.name)
                if not name:
                    continue
                score = self._match_score(code, name, match_words)
                if score > 0:
                    matched[code] = snap
        return matched

    def scan_by_block(self, block_name: str) -> dict[str, StockSnapshot]:
        """从.blk板块文件获取所有股票"""
        codes = self.reader.read_block_file(block_name)
        return {c: self.all_stocks[c] for c in codes if c in self.all_stocks}

    def filter_by_conditions(
        self,
        stocks: dict[str, StockSnapshot],
        min_price: float = 2.0,
        max_price: float = 9999.0,
        min_chg: float = -20.0,
        max_chg: float = 20.0,
        exclude_st: bool = True,
    ) -> dict[str, StockSnapshot]:
        """按基础条件筛选。

        Args:
            min_price/max_price: 价格范围
            min_chg/max_chg: 涨跌幅范围
            exclude_st: 排除ST股（名称含ST）
        """
        result: dict[str, StockSnapshot] = {}
        for code, snap in stocks.items():
            if snap.latest_close < min_price or snap.latest_close > max_price:
                continue
            if snap.change_pct < min_chg or snap.change_pct > max_chg:
                continue
            if exclude_st and ('ST' in snap.name.upper() or '*ST' in snap.name):
                continue
            result[code] = snap
        return result

    def rank_by_momentum(
        self, stocks: dict[str, StockSnapshot], top_n: int = 30
    ) -> list[tuple[str, StockSnapshot, float]]:
        """按动量（涨跌幅）排序，返回TopN"""
        ranked = [(code, snap, snap.change_pct) for code, snap in stocks.items()]
        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked[:top_n]

    def rank_by_composite(
        self, stocks: dict[str, StockSnapshot], top_n: int = 30
    ) -> list[tuple[str, StockSnapshot, float]]:
        """复合排序：涨跌幅 + 成交额 + 日期新鲜度"""
        # 计算最大成交额用于归一化
        max_amount = max((s.latest_amount for s in stocks.values()), default=1e8)
        ranked = []
        for code, snap in stocks.items():
            chg_score = snap.change_pct / 20.0  # normalize to ~[-1, 1]
            amt_score = min(snap.latest_amount / max(max_amount, 1), 1.0)
            freshness = 1.0 if snap.latest_date >= int(date.today().strftime('%Y%m%d')) - 3 else 0.5
            composite = chg_score * 0.5 + amt_score * 0.3 + freshness * 0.2
            ranked.append((code, snap, round(composite, 4)))
        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked[:top_n]

    def get_block_stocks(self, block_name: str) -> list[str]:
        """从.blk板块文件获取股票代码列表"""
        return self.reader.read_block_file(block_name)

    def scan_top_gainers(self, top_n: int = 30, min_amount: float = 5e7) -> list[tuple[str, StockSnapshot, float]]:
        """全市场涨幅Top N（排除成交量过低的股票）"""
        all_stocks = self.scan_all()
        filtered = {
            c: s for c, s in all_stocks.items()
            if s.latest_amount >= min_amount and s.latest_close >= 3.0
        }
        return self.rank_by_momentum(filtered, top_n=top_n)

    def scan_limit_up_stocks(self, threshold: float = 9.5) -> list[tuple[str, StockSnapshot, float]]:
        """扫描全市场涨停股"""
        all_stocks = self.scan_all()
        up_stocks = {c: s for c, s in all_stocks.items() if s.change_pct >= threshold}
        ranked = self.rank_by_momentum(up_stocks, top_n=len(up_stocks))
        return ranked

    # ── 内部 ──

    def _find_category(self, kw: str) -> Optional[str]:
        """查找关键词对应的行业分类"""
        kw_lower = kw.lower()
        for category, words in SECTOR_KEYWORDS.items():
            if kw in category or kw_lower in (w.lower() for w in words):
                return category
        # 也检查代码前缀映射
        for category in self.SECTOR_CODE_PREFIX:
            if kw in category:
                return category
        return None

    def _expand_keyword(self, kw: str) -> list[str]:
        """扩展关键词：若kw匹配SECTOR_KEYWORDS，返回对应的扩展词列表"""
        kw_lower = kw.lower()
        for category, words in SECTOR_KEYWORDS.items():
            if kw_lower in (w.lower() for w in words) or kw in category:
                return [kw] + [w for w in words if w != kw]
        return [kw]

    def _match_score(self, code: str, name: str, match_words: list[str]) -> float:
        """计算股票与关键词的匹配度分数"""
        if not name:
            return 0.0
        score = 0.0
        name_lower = name.lower()
        for word in match_words:
            word_lower = word.lower()
            if word_lower == name_lower:
                score += 5.0  # 精确名称匹配
            elif word_lower in name_lower:
                score += 3.0  # 名称包含关键词
            # 关键词在股票名中模糊匹配
            elif len(word) >= 2 and all(ch in name_lower for ch in word_lower):
                score += 1.0
        return score


def quick_scan(tdx_path: Optional[str] = None, sectors: Optional[list[str]] = None) -> dict:
    """快捷全市场扫描，返回结构化结果。

    Returns:
        dict with keys: total, stocks (code->snapshot), sectors_used
    """
    scanner = TDXScanner(tdx_path)
    if sectors:
        stocks = scanner.scan_by_sectors(sectors)
    else:
        stocks = scanner.scan_all()
    return {
        "total": len(stocks),
        "stocks": stocks,
        "sectors_used": sectors or ["全市场"],
    }

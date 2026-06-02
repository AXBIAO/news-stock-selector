# config.py — news-stock-selector 外置配置
# 把敏感凭据和环境相关配置从 skill.md 和 data_sources.py 中抽出。

import os
from types import MappingProxyType

# TuShare Pro API — token 和 URL 必须通过环境变量提供
# 未配置时 data_sources.py 的 TuShare Pro 层自动降级跳过
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
TUSHARE_HTTP_URL = os.environ.get("TUSHARE_HTTP_URL", "")
TUSHARE_ENABLED = True

REPORT_DIR = os.environ.get("NEWS_STOCK_REPORT_DIR", os.path.join(os.path.expanduser("~"), "新闻选股报告"))
AUTO_OPEN_REPORT = os.environ.get("NEWS_STOCK_AUTO_OPEN", "1") == "1"

# fallback 链命名 — 与 skill.md 描述保持对齐 (v3.2 实时优先)
PROVIDER_LABELS = (
    "xueqiu_quote",
    "tencent_quote",
    "sina_quote",
    "eastmoney_quote",
    "tushare_quote",
    "tushare_pro_daily",
    "mcp_quote",
    "pending",
)

# 社交热榜平台权重
HOT_PLATFORM_WEIGHTS = MappingProxyType({
    "weibo": 1.2,
    "zhihu": 1.0,
    "baidu": 0.9,
    "douyin": 1.3,
    "toutiao": 1.0,
    "bilibili": 0.8,
})

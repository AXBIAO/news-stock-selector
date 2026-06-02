# tests/test_contracts.py
import pytest
from contracts import (
    FieldStatus,
    StockResult,
    QuoteSnapshot,
    FallbackRecord,
    SelectionResult,
    SentimentLevel,
    CatalystType,
)


def test_stock_result_defaults():
    sr = StockResult()
    assert sr.code_status == FieldStatus.PENDING
    assert sr.quote_status == FieldStatus.PENDING
    assert sr.sector_status == FieldStatus.SKIPPED
    assert sr.sentiment_score == SentimentLevel.NEUTRAL
    assert sr.confidence == 0.0


def test_selection_result_empty():
    sel = SelectionResult()
    assert sel.stock_count == 0
    assert sel.stocks == []


def test_field_status_values():
    assert FieldStatus.CONFIRMED == "confirmed"
    assert FieldStatus.PENDING == "pending_confirmation"
    assert FieldStatus.FAILED == "failed"
    assert FieldStatus.SKIPPED == "skipped"
    assert FieldStatus.NOT_AVAILABLE == "not_available"


def test_catalyst_types_count():
    assert len(list(CatalystType)) == 9


def test_sentiment_levels():
    assert SentimentLevel.STRONG_BULLISH == 5
    assert SentimentLevel.STRONG_BEARISH == 1


def test_fallback_record_tracking():
    record = FallbackRecord(provider_label="xueqiu_quote")
    record.attempted_sources.append("tushare_quote")
    record.attempted_sources.append("xueqiu_quote")
    record.final_source = "xueqiu_quote"
    assert len(record.attempted_sources) == 2
    assert record.final_source == "xueqiu_quote"


def test_quote_snapshot_pending_default():
    q = QuoteSnapshot()
    assert q.status == FieldStatus.PENDING
    assert q.source == "pending"
    assert q.price is None

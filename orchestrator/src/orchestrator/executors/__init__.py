"""Executors: outbound calls to external systems (broker, market data, fundamentals)."""

from .alpaca import AlpacaExecutionError, AlpacaExecutor, ExecutionResult
from .fundamentals import (
    EdgarFundamentalsProvider,
    FundamentalsProvider,
    MockFundamentalsProvider,
)
from .market_data import MarketDataError, get_mock_quote, get_quote
from .sec_edgar import SECEdgarClient, SECEdgarError, normalize_company_facts

__all__ = [
    "AlpacaExecutor",
    "AlpacaExecutionError",
    "ExecutionResult",
    "EdgarFundamentalsProvider",
    "FundamentalsProvider",
    "MockFundamentalsProvider",
    "MarketDataError",
    "get_mock_quote",
    "get_quote",
    "SECEdgarClient",
    "SECEdgarError",
    "normalize_company_facts",
]

"""Tests for the synchronous deterministic equity-analysis endpoint."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.orchestrator import server
from src.orchestrator.state import PreloadDeclinedError


def test_analyze_equity_happy_path():
    research = {"ticker": "AAPL", "assessment": {"ticker": "AAPL", "valuation_verdict": "undervalued"}}
    suitability = {"recommendation": {"ticker": "AAPL", "direction": "buy", "disclaimers": ["not advice"]}}

    with (
        patch("src.orchestrator.server.preload_for_equity_research", return_value=research) as p1,
        patch("src.orchestrator.server.preload_for_suitability", return_value=suitability) as p2,
    ):
        with TestClient(server.app) as client:
            r = client.post("/v1/analysis/equity", json={"ticker": "aapl", "user_id": "u1"})

    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["assessment"]["valuation_verdict"] == "undervalued"
    assert body["recommendation"]["direction"] == "buy"
    p1.assert_called_once()
    p2.assert_called_once()
    # suitability is fed the assessment produced by equity-research
    assert p2.call_args.kwargs["assessment"] == research["assessment"]


def test_analyze_equity_declined_returns_422():
    with patch("src.orchestrator.server.preload_for_equity_research", side_effect=PreloadDeclinedError("unknown symbol")):
        with TestClient(server.app) as client:
            r = client.post("/v1/analysis/equity", json={"ticker": "ZZZZ"})

    assert r.status_code == 422
    assert "unknown symbol" in r.json()["detail"]


def test_analyze_equity_missing_ticker_returns_400():
    with TestClient(server.app) as client:
        r = client.post("/v1/analysis/equity", json={"ticker": "   "})
    assert r.status_code == 400

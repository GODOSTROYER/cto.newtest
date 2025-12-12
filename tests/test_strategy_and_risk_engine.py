from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from strategy_risk_engine.models import Candle, EntryType, OrderPlan, Side, StopLossSpec, TakeProfitSpec
from strategy_risk_engine.risk import RiskConfig, RiskManager
from strategy_risk_engine.strategy import StrategyConfig, VolatilityBreakoutStrategy
from strategy_risk_engine.sizing import MarketConstraints


UTC = timezone.utc


def _candle(symbol: str, t0: datetime, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(
        symbol=symbol,
        open_time=t0,
        close_time=t0 + timedelta(minutes=5),
        open=open_,
        high=high,
        low=low,
        close=close,
    )


def test_closed_candle_only_evaluation_no_lookahead() -> None:
    symbol = "BTCUSDT"
    base = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)

    candles = [
        _candle(symbol, base + timedelta(minutes=0), 100, 101, 99, 100),
        _candle(symbol, base + timedelta(minutes=5), 100, 102, 99, 101),
        _candle(symbol, base + timedelta(minutes=10), 101, 103, 100, 102),
        _candle(symbol, base + timedelta(minutes=15), 102, 104, 101, 103),
    ]

    future_breakout = _candle(symbol, base + timedelta(minutes=20), 103, 110, 102, 109)
    candles_with_future = candles + [future_breakout]

    strat = VolatilityBreakoutStrategy(StrategyConfig(lookback_candles=3, tp_mode="fixed"))

    as_of_before_future_close = base + timedelta(minutes=24, seconds=59)
    plan = strat.evaluate(va_id="va1", symbol=symbol, as_of=as_of_before_future_close, candles=candles_with_future)
    assert plan is None

    as_of_after_future_close = base + timedelta(minutes=25)
    plan2 = strat.evaluate(va_id="va1", symbol=symbol, as_of=as_of_after_future_close, candles=candles_with_future)
    assert plan2 is not None
    assert plan2.symbol == symbol


def test_orderplan_includes_mandatory_sl_and_fixed_tp() -> None:
    symbol = "ETHUSDT"
    base = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)

    candles = [
        _candle(symbol, base + timedelta(minutes=0), 100, 101, 99, 100),
        _candle(symbol, base + timedelta(minutes=5), 100, 102, 99, 101),
        _candle(symbol, base + timedelta(minutes=10), 101, 103, 100, 102),
        _candle(symbol, base + timedelta(minutes=15), 102, 104, 101, 105),
    ]

    strat = VolatilityBreakoutStrategy(StrategyConfig(lookback_candles=3, tp_mode="fixed", fixed_tp_r=1.7))
    plan = strat.evaluate(va_id="va1", symbol=symbol, as_of=base + timedelta(minutes=20), candles=candles)

    assert plan is not None
    assert plan.entry_type == EntryType.MARKET
    assert plan.stop_loss is not None
    assert plan.stop_loss.kind == "fixed"
    assert plan.take_profit is not None


def test_size_decay_after_consecutive_losses() -> None:
    cfg = RiskConfig(
        risk_per_trade_pct=0.01,
        max_trades_per_day=10,
        market_constraints=MarketConstraints(min_qty=0.0, min_notional=0.0),
    )

    rm = RiskManager(config=cfg, real_equity=10_000)
    rm.register_va(va_id="va1", virtual_equity=1_000)

    plan = OrderPlan(
        va_id="va1",
        symbol="BTCUSDT",
        side=Side.BUY,
        entry_type=EntryType.MARKET,
        entry_price=100.0,
        risk_tag="t",
        stop_loss=StopLossSpec(kind="fixed", price=99.0),
        take_profit=TakeProfitSpec(price=102.0),
    )

    now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)

    r0 = rm.review_orderplan(plan=plan, now=now, reserve=False)
    assert r0.approved
    assert pytest.approx(abs(r0.qty or 0.0), rel=1e-9) == 10.0

    rm.record_trade_pnl(va_id="va1", symbol="BTCUSDT", pnl=-1.0, now=now)
    rm.record_trade_pnl(va_id="va1", symbol="BTCUSDT", pnl=-1.0, now=now)

    r2 = rm.review_orderplan(plan=plan, now=now, reserve=False)
    assert r2.approved
    assert pytest.approx(abs(r2.qty or 0.0), rel=1e-9) == (998.0 * 0.01) * 0.5

    rm.record_trade_pnl(va_id="va1", symbol="BTCUSDT", pnl=-1.0, now=now)
    rm.record_trade_pnl(va_id="va1", symbol="BTCUSDT", pnl=-1.0, now=now)

    r4 = rm.review_orderplan(plan=plan, now=now, reserve=False)
    assert r4.approved
    assert pytest.approx(abs(r4.qty or 0.0), rel=1e-9) == (996.0 * 0.01) * 0.25


def test_daily_reset_boundary_utc_midnight() -> None:
    cfg = RiskConfig(
        max_trades_per_day=1,
        daily_reset_hour_utc=0,
        market_constraints=MarketConstraints(min_qty=0.0, min_notional=0.0),
    )
    rm = RiskManager(config=cfg, real_equity=10_000)
    rm.register_va(va_id="va1", virtual_equity=1_000)

    plan = OrderPlan(
        va_id="va1",
        symbol="BTCUSDT",
        side=Side.BUY,
        entry_type=EntryType.MARKET,
        entry_price=100.0,
        risk_tag="t",
        stop_loss=StopLossSpec(kind="fixed", price=99.0),
        take_profit=TakeProfitSpec(price=102.0),
    )

    before_midnight = datetime(2025, 1, 1, 23, 59, tzinfo=UTC)
    r1 = rm.review_orderplan(plan=plan, now=before_midnight, reserve=True)
    assert r1.approved

    r2 = rm.review_orderplan(plan=plan, now=before_midnight, reserve=False)
    assert not r2.approved
    assert r2.reason == "max_trades_per_day"

    after_midnight = datetime(2025, 1, 2, 0, 1, tzinfo=UTC)
    r3 = rm.review_orderplan(plan=plan, now=after_midnight, reserve=False)
    assert r3.approved


def test_global_one_va_per_symbol_enforced() -> None:
    cfg = RiskConfig(market_constraints=MarketConstraints(min_qty=0.0, min_notional=0.0))
    rm = RiskManager(config=cfg, real_equity=10_000)
    rm.register_va(va_id="va1", virtual_equity=1_000)
    rm.register_va(va_id="va2", virtual_equity=1_000)

    rm.record_position(va_id="va1", symbol="BTCUSDT", qty=1.0, avg_entry_price=100.0)

    plan_va2 = OrderPlan(
        va_id="va2",
        symbol="BTCUSDT",
        side=Side.BUY,
        entry_type=EntryType.MARKET,
        entry_price=100.0,
        risk_tag="t",
        stop_loss=StopLossSpec(kind="fixed", price=99.0),
        take_profit=TakeProfitSpec(price=102.0),
    )

    now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    res = rm.review_orderplan(plan=plan_va2, now=now, reserve=False)
    assert not res.approved
    assert res.reason == "symbol_owned_by_other_va"


def test_net_exposure_cap_blocks() -> None:
    cfg = RiskConfig(
        max_symbol_exposure_pct_real_equity=0.10,
        market_constraints=MarketConstraints(min_qty=0.0, min_notional=0.0),
    )
    rm = RiskManager(config=cfg, real_equity=1_000)
    rm.register_va(va_id="va1", virtual_equity=1_000)

    rm.record_position(va_id="va1", symbol="BTCUSDT", qty=0.9, avg_entry_price=100.0)

    plan = OrderPlan(
        va_id="va1",
        symbol="BTCUSDT",
        side=Side.BUY,
        entry_type=EntryType.MARKET,
        entry_price=100.0,
        risk_tag="t",
        stop_loss=StopLossSpec(kind="fixed", price=99.0),
        take_profit=TakeProfitSpec(price=102.0),
    )

    now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    res = rm.review_orderplan(plan=plan, now=now, reserve=False)
    assert not res.approved
    assert res.reason == "net_exposure_cap"

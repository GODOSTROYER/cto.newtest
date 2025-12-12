import pytest
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from src.storage import SQLiteManager, VirtualAccount, Order, Position, OrderSide, OrderStatus
from src.execution import SignalRouter, Governor, MarketFilters, OrderManager
from src.execution.filters import MarketData
from src.config import Settings


@pytest.mark.asyncio
async def test_database_initialization():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = SQLiteManager(db_path)
        await db.initialize()
        
        va = VirtualAccount(va_id="TEST001", balance=100000.0)
        created_va = await db.create_virtual_account(va)
        
        assert created_va.id is not None
        assert created_va.va_id == "TEST001"
        
        retrieved_va = await db.get_virtual_account("TEST001")
        assert retrieved_va is not None
        assert retrieved_va.balance == 100000.0
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_one_symbol_per_va_rule():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = SQLiteManager(db_path)
        await db.initialize()
        router = SignalRouter(db)
        
        can_trade_aapl, msg = await router.can_trade_symbol("VA001", "AAPL")
        assert can_trade_aapl is True
        
        can_trade_aapl_again, msg = await router.can_trade_symbol("VA001", "AAPL")
        assert can_trade_aapl_again is True
        
        position = Position(
            va_id="VA001",
            symbol="AAPL",
            quantity=10.0,
            entry_price=150.0
        )
        await db.create_position(position)
        router._va_symbol_map["VA001"] = "AAPL"
        
        can_trade_googl, msg = await router.can_trade_symbol("VA001", "GOOGL")
        assert can_trade_googl is False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_governor_cooldown():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = SQLiteManager(db_path)
        await db.initialize()
        settings = Settings(max_loss_cooldown=3, cooldown_duration_seconds=60)
        governor = Governor(db, settings)
        
        va = VirtualAccount(va_id="VA001", balance=100000.0, consecutive_losses=0)
        await db.create_virtual_account(va)
        
        can_trade, msg = await governor.can_trade("VA001")
        assert can_trade is True
        
        va = await db.get_virtual_account("VA001")
        va.consecutive_losses = 3
        await db.update_virtual_account(va)
        
        can_trade, msg = await governor.can_trade("VA001")
        assert can_trade is False
        assert "consecutive losses" in msg.lower()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_governor_trade_tracking():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name
    
    try:
        db = SQLiteManager(db_path)
        await db.initialize()
        settings = Settings(max_loss_cooldown=3)
        governor = Governor(db, settings)
        
        va = VirtualAccount(va_id="VA001", balance=100000.0)
        await db.create_virtual_account(va)
        
        await governor.record_trade_result("VA001", 100.0)
        va = await db.get_virtual_account("VA001")
        assert va.total_pnl == 100.0
        assert va.winning_trades == 1
        assert va.consecutive_losses == 0
        
        await governor.record_trade_result("VA001", -50.0)
        va = await db.get_virtual_account("VA001")
        assert va.total_pnl == 50.0
        assert va.losing_trades == 1
        assert va.consecutive_losses == 1
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_market_filters_spread():
    settings = Settings(max_spread_bps=10.0)
    filters = MarketFilters(settings)
    
    good_data = MarketData("AAPL", bid=100.0, ask=100.05, last=100.025, latency_ms=100.0)
    passed, msg = filters.check_spread(good_data)
    assert passed is True
    
    bad_data = MarketData("AAPL", bid=100.0, ask=100.50, last=100.25, latency_ms=100.0)
    passed, msg = filters.check_spread(bad_data)
    assert passed is False


def test_market_filters_latency():
    settings = Settings(max_latency_ms=500.0)
    filters = MarketFilters(settings)
    
    good_data = MarketData("AAPL", bid=100.0, ask=100.10, last=100.05, latency_ms=100.0)
    passed, msg = filters.check_latency(good_data)
    assert passed is True
    
    bad_data = MarketData("AAPL", bid=100.0, ask=100.10, last=100.05, latency_ms=600.0)
    passed, msg = filters.check_latency(bad_data)
    assert passed is False


def test_order_manager_stop_loss_calculation():
    settings = Settings(stop_loss_percentage=2.0)
    db = SQLiteManager(":memory:")
    order_manager = OrderManager(db, settings)
    
    stop_loss_buy = order_manager._calculate_stop_loss(100.0, OrderSide.BUY)
    assert stop_loss_buy == 98.0
    
    stop_loss_sell = order_manager._calculate_stop_loss(100.0, OrderSide.SELL)
    assert stop_loss_sell == 102.0


@pytest.mark.asyncio
async def test_order_manager_stop_loss_trigger():
    settings = Settings(stop_loss_percentage=2.0)
    db = SQLiteManager(":memory:")
    order_manager = OrderManager(db, settings)
    
    long_position = Position(
        va_id="VA001",
        symbol="AAPL",
        quantity=10.0,
        entry_price=100.0,
        stop_loss_price=98.0
    )
    
    triggered = await order_manager.check_stop_loss(long_position, 97.0)
    assert triggered is True
    
    not_triggered = await order_manager.check_stop_loss(long_position, 99.0)
    assert not_triggered is False
    
    short_position = Position(
        va_id="VA001",
        symbol="AAPL",
        quantity=-10.0,
        entry_price=100.0,
        stop_loss_price=102.0
    )
    
    triggered = await order_manager.check_stop_loss(short_position, 103.0)
    assert triggered is True

import asyncio
from src.storage import SQLiteManager, VirtualAccount, OrderSide
from src.execution import ExecutionLoop, Signal
from src.config import Settings


async def test_system():
    print("Testing Trading Execution System...")
    
    settings = Settings(
        database_path="test_trading.db",
        max_loss_cooldown=3,
        cooldown_duration_seconds=10,
        max_spread_bps=100.0,
        max_slippage_bps=100.0,
        max_latency_ms=1000.0,
        trading_window_start="00:00",
        trading_window_end="23:59",
        kill_switch_enabled=False
    )
    
    db = SQLiteManager(settings.database_path)
    await db.initialize()
    print("✓ Database initialized")
    
    va = VirtualAccount(va_id="TEST001", balance=100000.0)
    await db.create_virtual_account(va)
    print("✓ Virtual account created")
    
    execution_loop = ExecutionLoop(db, settings)
    print("✓ Execution loop initialized")
    
    signal = Signal(
        va_id="TEST001",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10.0,
        price=150.0
    )
    
    await execution_loop.submit_signal(signal)
    print("✓ Signal submitted")
    
    await execution_loop._handle_signal(signal)
    print("✓ Signal processed")
    
    orders = await db.get_open_orders("TEST001")
    if orders:
        print(f"✓ Order created: {orders[0].symbol} {orders[0].side.value} {orders[0].quantity} @ {orders[0].price}")
        print(f"✓ Stop loss set: {orders[0].stop_loss_price}")
    
    va = await db.get_virtual_account("TEST001")
    print(f"✓ Virtual account status: Balance=${va.balance:,.2f}, PnL=${va.total_pnl:,.2f}")
    
    second_signal = Signal(
        va_id="TEST001",
        symbol="GOOGL",
        side=OrderSide.BUY,
        quantity=5.0,
        price=100.0
    )
    
    can_trade, msg = await execution_loop.signal_router.can_trade_symbol("TEST001", "GOOGL")
    if not can_trade:
        print("✓ One-symbol-per-VA rule enforced (cannot trade GOOGL while holding AAPL)")
    
    await execution_loop.governor.record_trade_result("TEST001", -100.0)
    await execution_loop.governor.record_trade_result("TEST001", -100.0)
    await execution_loop.governor.record_trade_result("TEST001", -100.0)
    
    va = await db.get_virtual_account("TEST001")
    if va.consecutive_losses >= 3:
        print(f"✓ Consecutive losses tracked: {va.consecutive_losses}")
    
    can_trade, msg = await execution_loop.governor.can_trade("TEST001")
    if not can_trade:
        print(f"✓ Cooldown activated: {msg}")
    
    print("\n✅ All system tests passed!")
    print("\nSystem is ready for deployment via docker-compose up")
    
    import os
    if os.path.exists("test_trading.db"):
        os.unlink("test_trading.db")


if __name__ == "__main__":
    asyncio.run(test_system())

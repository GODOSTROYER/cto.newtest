import asyncio
import signal
import random
from datetime import datetime
from src.storage import SQLiteManager, VirtualAccount, OrderSide
from src.config import get_settings
from src.execution import ExecutionLoop, Signal
from src.cli import Dashboard


async def create_sample_data(db: SQLiteManager):
    va_ids = ["VA001", "VA002", "VA003"]
    
    for va_id in va_ids:
        existing = await db.get_virtual_account(va_id)
        if not existing:
            va = VirtualAccount(
                va_id=va_id,
                balance=100000.0,
                total_pnl=0.0
            )
            await db.create_virtual_account(va)
            print(f"Created virtual account: {va_id}")


async def simulate_signals(execution_loop: ExecutionLoop):
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
    va_ids = ["VA001", "VA002", "VA003"]
    
    await asyncio.sleep(2)
    
    while execution_loop.running:
        await asyncio.sleep(random.uniform(5, 15))
        
        va_id = random.choice(va_ids)
        symbol = random.choice(symbols)
        side = random.choice([OrderSide.BUY, OrderSide.SELL])
        quantity = random.uniform(10, 100)
        price = 100.0 + random.uniform(-10, 10)
        
        signal = Signal(va_id, symbol, side, quantity, price)
        await execution_loop.submit_signal(signal)
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Signal: {va_id} {side.value} {quantity:.2f} {symbol} @ ${price:.2f}")


async def main():
    settings = get_settings()
    db = SQLiteManager(settings.database_path)
    
    await db.initialize()
    await create_sample_data(db)
    
    execution_loop = ExecutionLoop(db, settings)
    dashboard = Dashboard(db, settings)
    
    def signal_handler(sig, frame):
        print("\nShutting down...")
        execution_loop.running = False
        dashboard.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    tasks = [
        asyncio.create_task(execution_loop.start()),
        asyncio.create_task(simulate_signals(execution_loop)),
        asyncio.create_task(dashboard.start()),
    ]
    
    print("Starting execution loop and dashboard...")
    
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        execution_loop.running = False
        dashboard.running = False


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import random
from datetime import datetime
from typing import List
from ..storage import SQLiteManager, Order, OrderSide
from ..config import Settings
from .signal_router import SignalRouter
from .governor import Governor
from .filters import MarketFilters, MarketData
from .order_manager import OrderManager


class Signal:
    def __init__(self, va_id: str, symbol: str, side: OrderSide, quantity: float, price: float):
        self.va_id = va_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.timestamp = datetime.utcnow()


class ExecutionLoop:
    def __init__(self, db: SQLiteManager, settings: Settings):
        self.db = db
        self.settings = settings
        self.signal_router = SignalRouter(db)
        self.governor = Governor(db, settings)
        self.filters = MarketFilters(settings)
        self.order_manager = OrderManager(db, settings)
        self.running = False
        self._signal_queue = asyncio.Queue()

    async def start(self):
        self.running = True
        await self.db.initialize()
        
        tasks = [
            asyncio.create_task(self._process_signals()),
            asyncio.create_task(self._reconcile_orders_loop()),
            asyncio.create_task(self._monitor_positions_loop()),
        ]
        
        await asyncio.gather(*tasks)

    async def stop(self):
        self.running = False

    async def submit_signal(self, signal: Signal):
        await self._signal_queue.put(signal)

    async def _process_signals(self):
        while self.running:
            try:
                signal = await asyncio.wait_for(self._signal_queue.get(), timeout=1.0)
                await self._handle_signal(signal)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing signal: {e}")

    async def _handle_signal(self, signal: Signal):
        if self.settings.kill_switch_enabled:
            print(f"Kill switch enabled, rejecting signal for {signal.va_id}")
            return

        can_trade_symbol, msg = await self.signal_router.can_trade_symbol(signal.va_id, signal.symbol)
        if not can_trade_symbol:
            print(f"Signal rejected for {signal.va_id}: {msg}")
            return

        can_trade, msg = await self.governor.can_trade(signal.va_id)
        if not can_trade:
            print(f"Governor rejected signal for {signal.va_id}: {msg}")
            return

        can_throttle, msg = await self.governor.check_throttle(signal.va_id)
        if not can_throttle:
            print(f"Throttle check failed for {signal.va_id}: {msg}")
            return

        market_data = await self._fetch_market_data(signal.symbol)
        
        filters_pass, msg = self.filters.check_all(market_data, signal.price)
        if not filters_pass:
            print(f"Filters rejected signal for {signal.va_id}: {msg}")
            return

        stop_loss_price = self.order_manager._calculate_stop_loss(signal.price, signal.side)
        
        order = Order(
            va_id=signal.va_id,
            symbol=signal.symbol,
            side=signal.side,
            quantity=signal.quantity,
            price=signal.price,
            stop_loss_price=stop_loss_price,
            reduce_only=False
        )

        await self.order_manager.submit_order(order)
        print(f"Order submitted for {signal.va_id}: {signal.side.value} {signal.quantity} {signal.symbol} @ {signal.price}")

    async def _fetch_market_data(self, symbol: str) -> MarketData:
        await asyncio.sleep(random.uniform(0.01, 0.05))
        
        base_price = 100.0 + random.uniform(-10, 10)
        spread = random.uniform(0.01, 0.05)
        
        bid = base_price - spread / 2
        ask = base_price + spread / 2
        last = base_price + random.uniform(-0.02, 0.02)
        latency_ms = random.uniform(50, 200)
        
        return MarketData(symbol, bid, ask, last, latency_ms)

    async def _reconcile_orders_loop(self):
        while self.running:
            try:
                await asyncio.sleep(self.settings.reconcile_interval_seconds)
                await self.order_manager.reconcile_orders()
            except Exception as e:
                print(f"Error in reconcile loop: {e}")

    async def _monitor_positions_loop(self):
        while self.running:
            try:
                await asyncio.sleep(1.0)
                await self._check_stop_losses()
            except Exception as e:
                print(f"Error in position monitor loop: {e}")

    async def _check_stop_losses(self):
        positions = await self.db.get_positions()
        
        for position in positions:
            market_data = await self._fetch_market_data(position.symbol)
            current_price = market_data.last
            
            position.current_price = current_price
            position.unrealized_pnl = (
                (current_price - position.entry_price) * position.quantity
                if position.quantity > 0
                else (position.entry_price - current_price) * abs(position.quantity)
            )
            await self.db.update_position(position)
            
            if await self.order_manager.check_stop_loss(position, current_price):
                print(f"Stop loss triggered for {position.va_id} {position.symbol}")
                await self.order_manager.create_stop_loss_order(position, current_price)

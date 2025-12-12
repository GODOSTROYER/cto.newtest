import asyncio
import random
from typing import Optional
from datetime import datetime
from ..storage import SQLiteManager, Order, Position, Trade, OrderStatus, OrderSide
from ..config import Settings


class OrderManager:
    def __init__(self, db: SQLiteManager, settings: Settings):
        self.db = db
        self.settings = settings

    async def submit_order(self, order: Order) -> Order:
        order.status = OrderStatus.SUBMITTED
        order.order_ref = f"ORD-{order.va_id}-{datetime.utcnow().timestamp()}"
        await self.db.create_order(order)
        
        asyncio.create_task(self._simulate_fill(order))
        
        return order

    async def _simulate_fill(self, order: Order):
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        db_order = await self.db.get_order(order.id)
        if not db_order or db_order.status not in [OrderStatus.SUBMITTED, OrderStatus.PENDING]:
            return

        db_order.status = OrderStatus.FILLED
        db_order.filled_quantity = db_order.quantity
        await self.db.update_order(db_order)

        await self._process_fill(db_order)

    async def _process_fill(self, order: Order):
        position = await self.db.get_position(order.va_id, order.symbol)
        
        if order.reduce_only or (position and self._is_closing_order(order, position)):
            await self._close_position(order, position)
        else:
            await self._open_or_add_position(order, position)

    def _is_closing_order(self, order: Order, position: Position) -> bool:
        if order.side == OrderSide.SELL and position.quantity > 0:
            return True
        if order.side == OrderSide.BUY and position.quantity < 0:
            return True
        return False

    async def _open_or_add_position(self, order: Order, existing_position: Optional[Position]):
        quantity = order.filled_quantity if order.side == OrderSide.BUY else -order.filled_quantity
        
        if existing_position:
            total_cost = (existing_position.entry_price * abs(existing_position.quantity)) + (order.price * order.filled_quantity)
            total_quantity = abs(existing_position.quantity) + order.filled_quantity
            new_entry_price = total_cost / total_quantity
            
            existing_position.quantity = existing_position.quantity + quantity
            existing_position.entry_price = new_entry_price
            existing_position.current_price = order.price
            
            if order.stop_loss_price:
                existing_position.stop_loss_price = order.stop_loss_price
            
            await self.db.update_position(existing_position)
        else:
            stop_loss_price = order.stop_loss_price
            if not stop_loss_price:
                stop_loss_price = self._calculate_stop_loss(order.price, order.side)
            
            position = Position(
                va_id=order.va_id,
                symbol=order.symbol,
                quantity=quantity,
                entry_price=order.price,
                current_price=order.price,
                stop_loss_price=stop_loss_price
            )
            await self.db.create_position(position)

        trade = Trade(
            va_id=order.va_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.filled_quantity,
            price=order.price,
            pnl=0.0,
            order_id=order.id
        )
        await self.db.create_trade(trade)

    async def _close_position(self, order: Order, position: Position):
        close_quantity = min(order.filled_quantity, abs(position.quantity))
        
        if position.quantity > 0:
            pnl = (order.price - position.entry_price) * close_quantity
        else:
            pnl = (position.entry_price - order.price) * close_quantity
        
        trade = Trade(
            va_id=order.va_id,
            symbol=order.symbol,
            side=order.side,
            quantity=close_quantity,
            price=order.price,
            pnl=pnl,
            order_id=order.id
        )
        await self.db.create_trade(trade)
        
        position.quantity = position.quantity + (close_quantity if order.side == OrderSide.BUY else -close_quantity)
        position.realized_pnl += pnl
        
        if abs(position.quantity) < 0.0001:
            await self.db.delete_position(order.va_id, order.symbol)
        else:
            await self.db.update_position(position)

        from .governor import Governor
        governor = Governor(self.db, self.settings)
        await governor.record_trade_result(order.va_id, pnl)

    def _calculate_stop_loss(self, entry_price: float, side: OrderSide) -> float:
        if side == OrderSide.BUY:
            return entry_price * (1 - self.settings.stop_loss_percentage / 100)
        else:
            return entry_price * (1 + self.settings.stop_loss_percentage / 100)

    async def check_stop_loss(self, position: Position, current_price: float) -> bool:
        if not position.stop_loss_price:
            return False
        
        if position.quantity > 0 and current_price <= position.stop_loss_price:
            return True
        
        if position.quantity < 0 and current_price >= position.stop_loss_price:
            return True
        
        return False

    async def create_stop_loss_order(self, position: Position, current_price: float) -> Order:
        side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        
        order = Order(
            va_id=position.va_id,
            symbol=position.symbol,
            side=side,
            quantity=abs(position.quantity),
            price=current_price,
            reduce_only=True,
            stop_loss_price=None
        )
        
        return await self.submit_order(order)

    async def reconcile_orders(self):
        open_orders = await self.db.get_open_orders()
        
        for order in open_orders:
            if (datetime.utcnow() - order.created_at).total_seconds() > 30:
                order.status = OrderStatus.CANCELLED
                await self.db.update_order(order)

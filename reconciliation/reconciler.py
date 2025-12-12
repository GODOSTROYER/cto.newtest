from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from exchange.bybit_client import BybitClient
from exchange.models import ExchangePosition
from storage.database import Database


class OrderReconciler:
    """Reconciles exchange orders with database records."""

    def __init__(self, client: BybitClient, db: Database):
        self.client = client
        self.db = db

    def reconcile_orders(self) -> None:
        """Fetch open orders from exchange and reconcile with DB."""
        # Fetch from exchange
        exchange_orders = self.client.get_open_orders()

        # For each exchange order, update DB
        for xch_order in exchange_orders:
            db_order = self.db.get_order(xch_order.order_id)
            if db_order:
                self.db.update_order_status(
                    xch_order.order_id,
                    xch_order.status,
                    xch_order.filled_qty,
                )


class PositionReconciler:
    """Reconciles exchange positions with database records and enforces SL/TP attachment."""

    def __init__(self, client: BybitClient, db: Database):
        self.client = client
        self.db = db
        self.panic_close_timeout_sec = 30

    def reconcile_positions(self) -> None:
        """
        Fetch positions from exchange, reconcile with DB, and enforce SL attachment.
        If SL is missing, attempt to attach; if that fails, panic-close.
        """
        exchange_positions = self.client.get_positions()

        for xch_pos in exchange_positions:
            # Find corresponding entry order
            va_pos = self.db.get_position(va_id="unknown", symbol=xch_pos.symbol)
            if not va_pos:
                continue

            # Check if SL is attached
            if xch_pos.stop_loss_price is None:
                self._enforce_sl_attachment(xch_pos)

    def _enforce_sl_attachment(self, position: ExchangePosition) -> None:
        """
        Ensure SL is attached to a position.
        If it fails, panic-close the position.
        """
        # Get entry orders for this position
        # (In a real implementation, we'd track the entry order ID)
        # For now, assume we have the position and can compute a reasonable SL

        # Try to attach SL - this is simplified
        # In reality, we'd fetch the entry order from DB and use its SL spec
        try:
            # Attempt to find open orders for this symbol
            orders = self.client.get_open_orders(symbol=position.symbol)
            entry_orders = [o for o in orders if not o.reduce_only and o.status in ("New", "PartiallyFilled")]

            if entry_orders:
                entry_order = entry_orders[0]
                # Try to attach a default SL (e.g., 2% from entry)
                sl_price = entry_order.price * 0.98 if position.side == "Buy" else entry_order.price * 1.02
                success = self.client.attach_stop_loss(
                    symbol=position.symbol,
                    order_id=entry_order.order_id,
                    stop_price=sl_price,
                )
                if success:
                    return

        except Exception:
            pass

        # If attachment failed, panic-close
        self._panic_close(position)

    def _panic_close(self, position: ExchangePosition) -> None:
        """Market reduce-only close of a position and log incident."""
        try:
            close_order = self.client.panic_close_position(
                symbol=position.symbol,
                side=position.side,
                qty=position.qty,
            )

            # Log incident
            self.db.create_incident(
                incident_id=str(uuid.uuid4()),
                incident_type="panic_close",
                severity="high",
                description=f"Panic-closed position {position.symbol} {position.side} {position.qty}",
                symbol=position.symbol,
                order_id=close_order.order_id,
                metadata={
                    "position_qty": position.qty,
                    "position_side": position.side,
                    "close_order_id": close_order.order_id,
                },
            )
        except Exception as e:
            # Log the panic-close failure
            self.db.create_incident(
                incident_id=str(uuid.uuid4()),
                incident_type="panic_close_failed",
                severity="critical",
                description=f"Failed to panic-close position {position.symbol}: {str(e)}",
                symbol=position.symbol,
                metadata={"error": str(e)},
            )

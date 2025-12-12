from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ExchangeOrder:
    order_id: str
    client_order_id: str
    symbol: str
    side: str  # 'Buy' or 'Sell'
    order_type: str  # 'Market', 'Limit', etc.
    price: float
    qty: float
    reduce_only: bool
    status: str  # 'New', 'PartiallyFilled', 'Filled', 'Cancelled', etc.
    filled_qty: float
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ExchangeFill:
    fill_id: str
    order_id: str
    symbol: str
    side: str  # 'Buy' or 'Sell'
    qty: float
    price: float
    fee: float
    fee_asset: str
    created_at: datetime


@dataclass(frozen=True)
class ExchangePosition:
    symbol: str
    side: str  # 'Buy' or 'Sell'
    qty: float
    avg_entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: float
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

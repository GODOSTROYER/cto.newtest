from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class EntryType(str, Enum):
    MARKET = "MARKET"
    STOP = "STOP"
    LIMIT = "LIMIT"


@dataclass(frozen=True)
class Candle:
    symbol: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float


StopLossKind = Literal["fixed", "trailing"]


@dataclass(frozen=True)
class StopLossSpec:
    kind: StopLossKind
    price: Optional[float] = None
    trail_by: Optional[float] = None

    def resolved_stop_price(self, *, entry_price: float, side: Side) -> float:
        if self.kind == "fixed":
            if self.price is None:
                raise ValueError("fixed stop-loss requires price")
            return float(self.price)

        if self.trail_by is None:
            raise ValueError("trailing stop-loss requires trail_by")

        if side == Side.BUY:
            return float(entry_price - self.trail_by)
        return float(entry_price + self.trail_by)


@dataclass(frozen=True)
class TakeProfitSpec:
    price: float


@dataclass(frozen=True)
class OrderPlan:
    va_id: str
    symbol: str
    side: Side
    entry_type: EntryType
    entry_price: float
    risk_tag: str
    stop_loss: StopLossSpec
    take_profit: Optional[TakeProfitSpec] = None


@dataclass
class Position:
    va_id: str
    symbol: str
    qty: float
    avg_entry_price: float

    @property
    def notional(self) -> float:
        return abs(self.qty) * self.avg_entry_price

    @property
    def side(self) -> Optional[Side]:
        if self.qty > 0:
            return Side.BUY
        if self.qty < 0:
            return Side.SELL
        return None


@dataclass(frozen=True)
class ReviewResult:
    approved: bool
    reason: Optional[str] = None
    qty: Optional[float] = None

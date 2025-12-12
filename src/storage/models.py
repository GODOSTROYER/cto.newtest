from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Order(BaseModel):
    id: Optional[int] = None
    va_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    filled_quantity: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    reduce_only: bool = False
    order_ref: Optional[str] = None


class Position(BaseModel):
    id: Optional[int] = None
    va_id: str
    symbol: str
    quantity: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss_price: Optional[float] = None
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Trade(BaseModel):
    id: Optional[int] = None
    va_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    pnl: float = 0.0
    order_id: Optional[int] = None
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class VirtualAccount(BaseModel):
    id: Optional[int] = None
    va_id: str
    balance: float = 100000.0
    total_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    consecutive_losses: int = 0
    in_cooldown: bool = False
    cooldown_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class VirtualAccountRecord(Base):
    __tablename__ = "virtual_accounts"

    id = Column(String(50), primary_key=True)
    allocation = Column(Float, nullable=False)
    status = Column(String(50), default="active")
    kill_switch = Column(Boolean, default=False)
    blocked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("OrderRecord", back_populates="va")
    positions = relationship("PositionRecord", back_populates="va")
    equity_snapshots = relationship("EquitySnapshotRecord", back_populates="va")
    daily_pnls = relationship("DailyPnLRecord", back_populates="va")
    trade_stats = relationship("TradeStatsRecord", back_populates="va")


class OrderRecord(Base):
    __tablename__ = "orders"

    id = Column(String(100), primary_key=True)
    va_id = Column(String(50), ForeignKey("virtual_accounts.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False)
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    reduce_only = Column(Boolean, default=False)
    client_order_id = Column(String(100), unique=True, nullable=True)
    status = Column(String(50), nullable=False)
    filled_qty = Column(Float, default=0.0)
    sl_plan_id = Column(String(100), nullable=True)
    tp_plan_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    va = relationship("VirtualAccountRecord", back_populates="orders")


class FillRecord(Base):
    __tablename__ = "fills"

    id = Column(String(100), primary_key=True)
    order_id = Column(String(100), ForeignKey("orders.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    fee_asset = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PositionRecord(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("va_id", "symbol", name="uq_va_symbol"),)

    id = Column(String(100), primary_key=True)
    va_id = Column(String(50), ForeignKey("virtual_accounts.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    qty = Column(Float, nullable=False)
    avg_entry_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    va = relationship("VirtualAccountRecord", back_populates="positions")


class EquitySnapshotRecord(Base):
    __tablename__ = "equity_snapshots"

    id = Column(String(100), primary_key=True)
    va_id = Column(String(50), ForeignKey("virtual_accounts.id"), nullable=False)
    virtual_equity = Column(Float, nullable=False)
    peak_equity = Column(Float, nullable=False)
    daily_pnl = Column(Float, nullable=False)
    snapshot_at = Column(DateTime, default=datetime.utcnow)

    va = relationship("VirtualAccountRecord", back_populates="equity_snapshots")


class DailyPnLRecord(Base):
    __tablename__ = "daily_pnl"
    __table_args__ = (UniqueConstraint("va_id", "date", name="uq_va_date"),)

    id = Column(String(100), primary_key=True)
    va_id = Column(String(50), ForeignKey("virtual_accounts.id"), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    pnl = Column(Float, nullable=False)
    trades_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    va = relationship("VirtualAccountRecord", back_populates="daily_pnls")


class IncidentRecord(Base):
    __tablename__ = "incidents"

    id = Column(String(100), primary_key=True)
    incident_type = Column(String(50), nullable=False)
    va_id = Column(String(50), nullable=True)
    symbol = Column(String(20), nullable=True)
    order_id = Column(String(100), nullable=True)
    severity = Column(String(20), nullable=False)
    description = Column(String(500), nullable=False)
    incident_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GovernorEventRecord(Base):
    __tablename__ = "governor_events"

    id = Column(String(100), primary_key=True)
    va_id = Column(String(50), nullable=True)
    symbol = Column(String(20), nullable=True)
    event_type = Column(String(50), nullable=False)
    description = Column(String(500), nullable=False)
    cooldown_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TradeStatsRecord(Base):
    __tablename__ = "trade_stats"

    id = Column(String(100), primary_key=True)
    va_id = Column(String(50), ForeignKey("virtual_accounts.id"), nullable=False)
    consecutive_wins = Column(Integer, default=0)
    consecutive_losses = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    largest_win = Column(Float, nullable=True)
    largest_loss = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    va = relationship("VirtualAccountRecord", back_populates="trade_stats")

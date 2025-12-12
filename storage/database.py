from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Base,
    DailyPnLRecord,
    EquitySnapshotRecord,
    FillRecord,
    GovernorEventRecord,
    IncidentRecord,
    OrderRecord,
    PositionRecord,
    TradeStatsRecord,
    VirtualAccountRecord,
)


class Database:
    def __init__(self, db_url: str = "sqlite:///trading.db"):
        self.engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init_db(self) -> None:
        """Initialize all tables in the database."""
        Base.metadata.create_all(self.engine)

    def create_session(self) -> Session:
        """Create a new database session."""
        return self.SessionLocal()

    # Virtual Account operations
    def create_or_update_va(self, va_id: str, allocation: float, status: str = "active") -> VirtualAccountRecord:
        """Create or update a virtual account."""
        session = self.create_session()
        try:
            va = session.query(VirtualAccountRecord).filter_by(id=va_id).first()
            if va is None:
                va = VirtualAccountRecord(id=va_id, allocation=allocation, status=status)
                session.add(va)
            else:
                va.allocation = allocation
                va.status = status
                va.updated_at = datetime.utcnow()
            session.commit()
            return va
        finally:
            session.close()

    def get_va(self, va_id: str) -> Optional[VirtualAccountRecord]:
        """Get a virtual account by ID."""
        session = self.create_session()
        try:
            return session.query(VirtualAccountRecord).filter_by(id=va_id).first()
        finally:
            session.close()

    def set_va_kill_switch(self, va_id: str, kill_switch: bool) -> None:
        """Set kill switch for a VA."""
        session = self.create_session()
        try:
            va = session.query(VirtualAccountRecord).filter_by(id=va_id).first()
            if va:
                va.kill_switch = kill_switch
                va.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def set_va_blocked_until(self, va_id: str, blocked_until: Optional[datetime]) -> None:
        """Set blocked_until timestamp for a VA."""
        session = self.create_session()
        try:
            va = session.query(VirtualAccountRecord).filter_by(id=va_id).first()
            if va:
                va.blocked_until = blocked_until
                va.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    # Order operations
    def create_order(
        self,
        order_id: str,
        va_id: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        price: float,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> OrderRecord:
        """Create an order record."""
        session = self.create_session()
        try:
            order = OrderRecord(
                id=order_id,
                va_id=va_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                qty=qty,
                price=price,
                reduce_only=reduce_only,
                client_order_id=client_order_id,
                status="New",
            )
            session.add(order)
            session.commit()
            return order
        finally:
            session.close()

    def update_order_status(self, order_id: str, status: str, filled_qty: float = 0.0) -> Optional[OrderRecord]:
        """Update order status and filled quantity."""
        session = self.create_session()
        try:
            order = session.query(OrderRecord).filter_by(id=order_id).first()
            if order:
                order.status = status
                order.filled_qty = filled_qty
                order.updated_at = datetime.utcnow()
                session.commit()
            return order
        finally:
            session.close()

    def link_sl_to_entry(self, entry_order_id: str, sl_order_id: str) -> None:
        """Link a stop-loss order to an entry order."""
        session = self.create_session()
        try:
            order = session.query(OrderRecord).filter_by(id=entry_order_id).first()
            if order:
                order.sl_plan_id = sl_order_id
                order.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def link_tp_to_entry(self, entry_order_id: str, tp_order_id: str) -> None:
        """Link a take-profit order to an entry order."""
        session = self.create_session()
        try:
            order = session.query(OrderRecord).filter_by(id=entry_order_id).first()
            if order:
                order.tp_plan_id = tp_order_id
                order.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()

    def get_order(self, order_id: str) -> Optional[OrderRecord]:
        """Get an order by ID."""
        session = self.create_session()
        try:
            return session.query(OrderRecord).filter_by(id=order_id).first()
        finally:
            session.close()

    def get_orders_by_va(self, va_id: str) -> List[OrderRecord]:
        """Get all orders for a VA."""
        session = self.create_session()
        try:
            return session.query(OrderRecord).filter_by(va_id=va_id).all()
        finally:
            session.close()

    # Fill operations
    def create_fill(
        self,
        fill_id: str,
        order_id: str,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        fee: float,
        fee_asset: str,
    ) -> FillRecord:
        """Create a fill record."""
        session = self.create_session()
        try:
            fill = FillRecord(
                id=fill_id,
                order_id=order_id,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                fee=fee,
                fee_asset=fee_asset,
            )
            session.add(fill)
            session.commit()
            return fill
        finally:
            session.close()

    def get_fills_by_symbol(self, symbol: str) -> List[FillRecord]:
        """Get all fills for a symbol."""
        session = self.create_session()
        try:
            return session.query(FillRecord).filter_by(symbol=symbol).all()
        finally:
            session.close()

    # Position operations
    def create_or_update_position(
        self,
        position_id: str,
        va_id: str,
        symbol: str,
        qty: float,
        avg_entry_price: float,
    ) -> PositionRecord:
        """Create or update a position record."""
        session = self.create_session()
        try:
            pos = session.query(PositionRecord).filter_by(id=position_id).first()
            if pos is None:
                pos = PositionRecord(
                    id=position_id,
                    va_id=va_id,
                    symbol=symbol,
                    qty=qty,
                    avg_entry_price=avg_entry_price,
                )
                session.add(pos)
            else:
                pos.qty = qty
                pos.avg_entry_price = avg_entry_price
                pos.updated_at = datetime.utcnow()
            session.commit()
            return pos
        finally:
            session.close()

    def get_position(self, va_id: str, symbol: str) -> Optional[PositionRecord]:
        """Get a position for a VA and symbol."""
        session = self.create_session()
        try:
            return session.query(PositionRecord).filter_by(va_id=va_id, symbol=symbol).first()
        finally:
            session.close()

    def get_positions_by_symbol(self, symbol: str) -> List[PositionRecord]:
        """Get all positions for a symbol (one VA per symbol)."""
        session = self.create_session()
        try:
            return session.query(PositionRecord).filter_by(symbol=symbol).all()
        finally:
            session.close()

    def get_positions_by_va(self, va_id: str) -> List[PositionRecord]:
        """Get all positions for a VA."""
        session = self.create_session()
        try:
            return session.query(PositionRecord).filter_by(va_id=va_id).all()
        finally:
            session.close()

    # Equity operations
    def create_equity_snapshot(
        self,
        snapshot_id: str,
        va_id: str,
        virtual_equity: float,
        peak_equity: float,
        daily_pnl: float,
    ) -> EquitySnapshotRecord:
        """Create an equity snapshot."""
        session = self.create_session()
        try:
            snapshot = EquitySnapshotRecord(
                id=snapshot_id,
                va_id=va_id,
                virtual_equity=virtual_equity,
                peak_equity=peak_equity,
                daily_pnl=daily_pnl,
            )
            session.add(snapshot)
            session.commit()
            return snapshot
        finally:
            session.close()

    # Daily PnL operations
    def create_or_update_daily_pnl(
        self,
        pnl_id: str,
        va_id: str,
        date: str,
        pnl: float,
        trades_count: int = 0,
    ) -> DailyPnLRecord:
        """Create or update a daily PnL record."""
        session = self.create_session()
        try:
            record = session.query(DailyPnLRecord).filter_by(va_id=va_id, date=date).first()
            if record is None:
                record = DailyPnLRecord(
                    id=pnl_id,
                    va_id=va_id,
                    date=date,
                    pnl=pnl,
                    trades_count=trades_count,
                )
                session.add(record)
            else:
                record.pnl = pnl
                record.trades_count = trades_count
                record.updated_at = datetime.utcnow()
            session.commit()
            return record
        finally:
            session.close()

    # Incident operations
    def create_incident(
        self,
        incident_id: str,
        incident_type: str,
        severity: str,
        description: str,
        va_id: Optional[str] = None,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> IncidentRecord:
        """Create an incident record."""
        session = self.create_session()
        try:
            incident = IncidentRecord(
                id=incident_id,
                incident_type=incident_type,
                severity=severity,
                description=description,
                va_id=va_id,
                symbol=symbol,
                order_id=order_id,
                incident_metadata=metadata,
            )
            session.add(incident)
            session.commit()
            return incident
        finally:
            session.close()

    def get_incidents(self, incident_type: Optional[str] = None) -> List[IncidentRecord]:
        """Get all incidents, optionally filtered by type."""
        session = self.create_session()
        try:
            query = session.query(IncidentRecord)
            if incident_type:
                query = query.filter_by(incident_type=incident_type)
            return query.all()
        finally:
            session.close()

    # Governor event operations
    def create_governor_event(
        self,
        event_id: str,
        event_type: str,
        description: str,
        cooldown_ms: int,
        va_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> GovernorEventRecord:
        """Create a governor event record."""
        session = self.create_session()
        try:
            event = GovernorEventRecord(
                id=event_id,
                event_type=event_type,
                description=description,
                cooldown_ms=cooldown_ms,
                va_id=va_id,
                symbol=symbol,
            )
            session.add(event)
            session.commit()
            return event
        finally:
            session.close()

    # Trade stats operations
    def create_or_update_trade_stats(
        self,
        stats_id: str,
        va_id: str,
        consecutive_wins: int = 0,
        consecutive_losses: int = 0,
        total_trades: int = 0,
        winning_trades: int = 0,
        losing_trades: int = 0,
        win_rate: float = 0.0,
        largest_win: Optional[float] = None,
        largest_loss: Optional[float] = None,
    ) -> TradeStatsRecord:
        """Create or update trade stats record."""
        session = self.create_session()
        try:
            stats = session.query(TradeStatsRecord).filter_by(va_id=va_id).first()
            if stats is None:
                stats = TradeStatsRecord(
                    id=stats_id,
                    va_id=va_id,
                    consecutive_wins=consecutive_wins,
                    consecutive_losses=consecutive_losses,
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=losing_trades,
                    win_rate=win_rate,
                    largest_win=largest_win,
                    largest_loss=largest_loss,
                )
                session.add(stats)
            else:
                stats.consecutive_wins = consecutive_wins
                stats.consecutive_losses = consecutive_losses
                stats.total_trades = total_trades
                stats.winning_trades = winning_trades
                stats.losing_trades = losing_trades
                stats.win_rate = win_rate
                stats.largest_win = largest_win
                stats.largest_loss = largest_loss
                stats.updated_at = datetime.utcnow()
            session.commit()
            return stats
        finally:
            session.close()

    def get_trade_stats(self, va_id: str) -> Optional[TradeStatsRecord]:
        """Get trade stats for a VA."""
        session = self.create_session()
        try:
            return session.query(TradeStatsRecord).filter_by(va_id=va_id).first()
        finally:
            session.close()

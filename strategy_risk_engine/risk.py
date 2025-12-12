from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from .models import OrderPlan, Position, ReviewResult, Side
from .sizing import MarketConstraints, SizeCalculator


@dataclass(frozen=True)
class RiskConfig:
    max_daily_loss: float = 0.0
    max_drawdown_pct: float = 0.30
    max_trades_per_day: int = 10
    risk_per_trade_pct: float = 0.01
    default_leverage: float = 3.0
    max_leverage: float = 5.0
    daily_reset_hour_utc: int = 0
    max_symbol_exposure_pct_real_equity: float = 1.0
    market_constraints: MarketConstraints = field(default_factory=MarketConstraints)


@dataclass
class VaState:
    virtual_equity: float
    peak_virtual_equity: float
    daily_pnl: float = 0.0
    daily_trades: int = 0
    day_id: Optional[str] = None
    consecutive_losses: int = 0
    kill_switch: bool = False


class RiskManager:
    def __init__(self, *, config: RiskConfig, real_equity: float):
        self.config = config
        self.real_equity = real_equity

        self._va: Dict[str, VaState] = {}
        self._positions: Dict[Tuple[str, str], Position] = {}
        self._symbol_owner: Dict[str, str] = {}
        self._blocked_until: Dict[Tuple[str, str], datetime] = {}

        self._sizer = SizeCalculator(
            risk_per_trade_pct=config.risk_per_trade_pct,
            default_leverage=config.default_leverage,
            max_leverage=config.max_leverage,
            market_constraints=config.market_constraints,
        )

    def register_va(self, *, va_id: str, virtual_equity: float) -> None:
        self._va[va_id] = VaState(
            virtual_equity=virtual_equity,
            peak_virtual_equity=virtual_equity,
            day_id=None,
        )

    def apply_governor_breach(
        self,
        *,
        va_id: str,
        symbol: str,
        now: datetime,
        cooldown: timedelta,
    ) -> None:
        self._blocked_until[(va_id, symbol)] = now + cooldown

    def record_trade_pnl(self, *, va_id: str, symbol: str, pnl: float, now: datetime) -> None:
        st = self._require_va(va_id)
        self._roll_day(st, now)

        st.virtual_equity += pnl
        st.daily_pnl += pnl

        if pnl < 0:
            st.consecutive_losses += 1
        else:
            st.consecutive_losses = 0

        st.peak_virtual_equity = max(st.peak_virtual_equity, st.virtual_equity)
        if st.peak_virtual_equity > 0:
            dd = 1.0 - (st.virtual_equity / st.peak_virtual_equity)
            if dd >= self.config.max_drawdown_pct:
                st.kill_switch = True

        if st.virtual_equity <= 0:
            st.kill_switch = True

    def record_position(self, *, va_id: str, symbol: str, qty: float, avg_entry_price: float) -> None:
        key = (va_id, symbol)
        if qty == 0:
            self._positions.pop(key, None)
            if self._symbol_owner.get(symbol) == va_id and not self._any_position_for_symbol(symbol):
                self._symbol_owner.pop(symbol, None)
            return

        self._positions[key] = Position(va_id=va_id, symbol=symbol, qty=qty, avg_entry_price=avg_entry_price)
        self._symbol_owner[symbol] = va_id

    def review_orderplan(self, *, plan: OrderPlan, now: datetime, reserve: bool = True) -> ReviewResult:
        st = self._require_va(plan.va_id)
        self._roll_day(st, now)

        if st.kill_switch:
            return ReviewResult(approved=False, reason="kill_switch")

        if plan.stop_loss is None:
            return ReviewResult(approved=False, reason="stop_loss_required")

        if plan.stop_loss.kind == "fixed" and plan.take_profit is None:
            return ReviewResult(approved=False, reason="take_profit_required_for_fixed")

        blocked_until = self._blocked_until.get((plan.va_id, plan.symbol))
        if blocked_until is not None and now < blocked_until:
            return ReviewResult(approved=False, reason="cooldown_active")

        if self.config.max_daily_loss > 0 and -st.daily_pnl >= self.config.max_daily_loss:
            return ReviewResult(approved=False, reason="max_daily_loss")

        if st.daily_trades >= self.config.max_trades_per_day:
            return ReviewResult(approved=False, reason="max_trades_per_day")

        owner = self._symbol_owner.get(plan.symbol)
        if owner is not None and owner != plan.va_id:
            return ReviewResult(approved=False, reason="symbol_owned_by_other_va")

        existing_pos = self._positions.get((plan.va_id, plan.symbol))
        if existing_pos and existing_pos.side and existing_pos.side != plan.side:
            return ReviewResult(approved=False, reason="opposing_exposure_not_allowed")

        size = self._sizer.calculate_qty(
            plan=plan,
            virtual_equity=st.virtual_equity,
            consecutive_losses=st.consecutive_losses,
        )
        if size.qty == 0.0:
            return ReviewResult(approved=False, reason=size.reason)

        if self._would_breach_symbol_exposure_cap(symbol=plan.symbol, add_notional=abs(size.qty) * plan.entry_price):
            return ReviewResult(approved=False, reason="net_exposure_cap")

        if reserve:
            st.daily_trades += 1
            self._symbol_owner.setdefault(plan.symbol, plan.va_id)

        return ReviewResult(approved=True, qty=size.qty)

    def _would_breach_symbol_exposure_cap(self, *, symbol: str, add_notional: float) -> bool:
        if self.config.max_symbol_exposure_pct_real_equity <= 0:
            return True

        cap = self.real_equity * self.config.max_symbol_exposure_pct_real_equity
        if cap <= 0:
            return True

        existing = sum(pos.notional for pos in self._positions.values() if pos.symbol == symbol)
        return (existing + add_notional) > cap

    def _any_position_for_symbol(self, symbol: str) -> bool:
        return any(pos.symbol == symbol and pos.qty != 0 for pos in self._positions.values())

    def _require_va(self, va_id: str) -> VaState:
        if va_id not in self._va:
            raise KeyError(f"VA not registered: {va_id}")
        return self._va[va_id]

    def _day_id(self, now: datetime) -> str:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        shift = timedelta(hours=self.config.daily_reset_hour_utc)
        shifted = now - shift
        return shifted.date().isoformat()

    def _roll_day(self, st: VaState, now: datetime) -> None:
        day_id = self._day_id(now.astimezone(timezone.utc))
        if st.day_id is None:
            st.day_id = day_id
            return
        if day_id != st.day_id:
            st.day_id = day_id
            st.daily_pnl = 0.0
            st.daily_trades = 0

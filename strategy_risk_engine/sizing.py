from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import OrderPlan, Side


@dataclass(frozen=True)
class MarketConstraints:
    min_qty: float = 0.0
    min_notional: float = 0.0


@dataclass(frozen=True)
class SizeResult:
    qty: float
    reason: Optional[str] = None


class SizeCalculator:
    def __init__(
        self,
        *,
        risk_per_trade_pct: float,
        default_leverage: float,
        max_leverage: float,
        market_constraints: MarketConstraints,
    ):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.default_leverage = default_leverage
        self.max_leverage = max_leverage
        self.market_constraints = market_constraints

    def calculate_qty(
        self,
        *,
        plan: OrderPlan,
        virtual_equity: float,
        consecutive_losses: int,
        leverage: Optional[float] = None,
    ) -> SizeResult:
        if virtual_equity <= 0:
            return SizeResult(qty=0.0, reason="virtual_equity_non_positive")

        lev = self.default_leverage if leverage is None else float(leverage)
        lev = min(lev, self.max_leverage)
        if lev <= 0:
            return SizeResult(qty=0.0, reason="leverage_non_positive")

        resolved_sl = plan.stop_loss.resolved_stop_price(entry_price=plan.entry_price, side=plan.side)
        per_unit_risk = abs(plan.entry_price - resolved_sl)
        if per_unit_risk <= 0:
            return SizeResult(qty=0.0, reason="stop_loss_distance_zero")

        risk_budget = virtual_equity * self.risk_per_trade_pct
        raw_qty = risk_budget / per_unit_risk

        max_notional = virtual_equity * lev
        qty_cap = max_notional / plan.entry_price

        qty = min(raw_qty, qty_cap)

        decay = 1.0
        if consecutive_losses >= 4:
            decay = 0.25
        elif consecutive_losses >= 2:
            decay = 0.5

        qty *= decay

        min_qty = self.market_constraints.min_qty
        min_notional = self.market_constraints.min_notional
        if qty < min_qty:
            return SizeResult(qty=0.0, reason="below_min_qty")

        if qty * plan.entry_price < min_notional:
            return SizeResult(qty=0.0, reason="below_min_notional")

        if plan.side == Side.SELL:
            qty = -qty

        return SizeResult(qty=qty)

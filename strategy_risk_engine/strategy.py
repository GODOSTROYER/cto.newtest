from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Sequence

from .models import Candle, EntryType, OrderPlan, Side, StopLossSpec, TakeProfitSpec


TpMode = Literal["fixed", "trailing"]


@dataclass(frozen=True)
class StrategyConfig:
    lookback_candles: int = 20
    tp_mode: TpMode = "fixed"
    fixed_tp_r: float = 1.8
    sl_range_mult: float = 1.0
    min_stop_distance: float = 0.0
    risk_tag: str = "vol_breakout_5m_closed"


class VolatilityBreakoutStrategy:
    def __init__(self, config: StrategyConfig):
        self.config = config

    def evaluate(
        self,
        *,
        va_id: str,
        symbol: str,
        as_of: datetime,
        candles: Sequence[Candle],
    ) -> Optional[OrderPlan]:
        closed = [c for c in candles if c.symbol == symbol and c.close_time <= as_of]
        if len(closed) < self.config.lookback_candles + 1:
            return None

        window = closed[-(self.config.lookback_candles + 1) :]
        trigger = window[-1]
        reference = window[:-1]

        prev_high = max(c.high for c in reference)
        prev_low = min(c.low for c in reference)

        if trigger.close > prev_high:
            side = Side.BUY
        elif trigger.close < prev_low:
            side = Side.SELL
        else:
            return None

        avg_range = sum((c.high - c.low) for c in reference) / len(reference)
        stop_distance = max(self.config.min_stop_distance, avg_range * self.config.sl_range_mult)

        entry_price = float(trigger.close)

        if side == Side.BUY:
            sl_price = entry_price - stop_distance
            tp_price = entry_price + self.config.fixed_tp_r * stop_distance
        else:
            sl_price = entry_price + stop_distance
            tp_price = entry_price - self.config.fixed_tp_r * stop_distance

        if self.config.tp_mode == "fixed":
            stop_loss = StopLossSpec(kind="fixed", price=sl_price)
            take_profit = TakeProfitSpec(price=tp_price)
        else:
            stop_loss = StopLossSpec(kind="trailing", trail_by=stop_distance)
            take_profit = None

        return OrderPlan(
            va_id=va_id,
            symbol=symbol,
            side=side,
            entry_type=EntryType.MARKET,
            entry_price=entry_price,
            risk_tag=self.config.risk_tag,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

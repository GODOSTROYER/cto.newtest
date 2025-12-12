from datetime import datetime, time
from typing import Optional
from ..config import Settings


class MarketData:
    def __init__(self, symbol: str, bid: float, ask: float, last: float, latency_ms: float):
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.last = last
        self.latency_ms = latency_ms
        self.timestamp = datetime.utcnow()

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_bps(self) -> float:
        mid = (self.bid + self.ask) / 2
        if mid == 0:
            return 0
        return (self.spread / mid) * 10000


class MarketFilters:
    def __init__(self, settings: Settings):
        self.settings = settings

    def check_spread(self, market_data: MarketData) -> tuple[bool, str]:
        if market_data.spread_bps > self.settings.max_spread_bps:
            return False, f"Spread {market_data.spread_bps:.2f}bps exceeds max {self.settings.max_spread_bps}bps"
        return True, "OK"

    def check_slippage(self, expected_price: float, market_data: MarketData) -> tuple[bool, str]:
        actual_price = market_data.last
        slippage = abs(actual_price - expected_price) / expected_price * 10000
        
        if slippage > self.settings.max_slippage_bps:
            return False, f"Slippage {slippage:.2f}bps exceeds max {self.settings.max_slippage_bps}bps"
        return True, "OK"

    def check_latency(self, market_data: MarketData) -> tuple[bool, str]:
        if market_data.latency_ms > self.settings.max_latency_ms:
            return False, f"Latency {market_data.latency_ms:.1f}ms exceeds max {self.settings.max_latency_ms}ms"
        return True, "OK"

    def check_trading_window(self) -> tuple[bool, str]:
        now = datetime.utcnow().time()
        
        start = datetime.strptime(self.settings.trading_window_start, "%H:%M").time()
        end = datetime.strptime(self.settings.trading_window_end, "%H:%M").time()
        
        if start <= now <= end:
            return True, "OK"
        return False, f"Outside trading window {self.settings.trading_window_start}-{self.settings.trading_window_end}"

    def check_all(self, market_data: MarketData, expected_price: Optional[float] = None) -> tuple[bool, str]:
        checks = [
            self.check_spread(market_data),
            self.check_latency(market_data),
            self.check_trading_window(),
        ]
        
        if expected_price is not None:
            checks.append(self.check_slippage(expected_price, market_data))
        
        for passed, message in checks:
            if not passed:
                return False, message
        
        return True, "OK"

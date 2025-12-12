# Trading System: Volatility Breakout Strategy with Risk Management

A comprehensive trading system featuring a volatility breakout strategy for 5-minute closed candles, integrated with Bybit testnet, advanced risk management, and SQLite-based persistence.

## Features

### Strategy Engine
- **Volatility Breakout Strategy**: 5-minute closed candle analysis
  - No lookahead bias: only uses closed candles up to evaluation time
  - Dynamic breakout detection based on recent highs/lows
  - Configurable lookback periods and risk ratios

### Risk Management
- **Per-VA Rules**:
  - Maximum daily loss limits
  - 30% drawdown kill-switch
  - Mandatory stop-loss enforcement
  - Max trades per day
  - Size decay: 2 consecutive losses → 0.5×, 4 losses → 0.25×
  
- **Global Rules**:
  - One VA owns a symbol at a time (system-wide)
  - No opposing exposures allowed across VAs
  - Net exposure guard (configurable % of real equity)
  - Breach cooldown policy for governor events

### Exchange Integration
- **Bybit Testnet Client**:
  - Official SDK wrapper with testnet URLs
  - Rate limiting and retry logic with jitter
  - Time sync handling
  - Idempotency helpers and standardized errors

- **Stop-Loss Hard Enforcement**:
  - Immediate SL/TP placement on entry fill
  - Panic-close (market reduce-only) if SL fails
  - Continuous reconciliation and verification
  - Incident logging for all SL failures

### Size Calculator
- Uses VA virtual equity allocation
- Respects leverage caps (3× default, 5× max)
- Enforces min order qty/notional constraints
- Configurable safety floors

### Storage Layer
SQLite with SQLAlchemy ORM supporting:
- Virtual accounts with allocations and kill flags
- Orders with VA attribution and SL/TP linkage
- Fills for reconciliation
- Positions (one active owner per symbol)
- Equity snapshots (per VA + real)
- Daily PnL tracking (per VA + real)
- Incident logging (SL failures, panic-closes, latency breaches)
- Governor events and trade statistics

## Project Structure

```
.
├── strategy_risk_engine/          # Core strategy and risk logic
│   ├── __init__.py
│   ├── models.py                  # Data models (Candle, OrderPlan, etc.)
│   ├── strategy.py                # VolatilityBreakoutStrategy
│   ├── risk.py                    # RiskManager with per-VA and global rules
│   └── sizing.py                  # SizeCalculator
├── exchange/                      # Exchange client and models
│   ├── __init__.py
│   ├── models.py                  # ExchangeOrder, ExchangeFill, ExchangePosition
│   └── bybit_client.py            # BybitClient wrapper
├── storage/                       # Database layer
│   ├── __init__.py
│   ├── models.py                  # SQLAlchemy ORM models
│   └── database.py                # Database class with CRUD operations
├── reconciliation/                # Order and position reconciliation
│   ├── __init__.py
│   └── reconciler.py              # OrderReconciler and PositionReconciler
├── tests/                         # Comprehensive test suite
│   ├── test_strategy_and_risk_engine.py
│   └── test_exchange_and_storage.py
├── requirements.txt
├── pytest.ini
└── README.md
```

## Usage

### Setup

```bash
pip install -r requirements.txt
```

### Initialize Database

```python
from storage import Database

db = Database("sqlite:///trading.db")
db.init_db()
```

### Create Strategy and Risk Manager

```python
from datetime import datetime, timezone
from strategy_risk_engine import (
    StrategyConfig, VolatilityBreakoutStrategy,
    RiskConfig, RiskManager,
    MarketConstraints
)

# Configure strategy
strat_config = StrategyConfig(
    lookback_candles=20,
    tp_mode="fixed",
    fixed_tp_r=1.8,
    sl_range_mult=1.0,
)
strategy = VolatilityBreakoutStrategy(strat_config)

# Configure risk manager
risk_config = RiskConfig(
    max_daily_loss=100.0,
    max_drawdown_pct=0.30,
    max_trades_per_day=10,
    risk_per_trade_pct=0.01,
    default_leverage=3.0,
    max_leverage=5.0,
    market_constraints=MarketConstraints(
        min_qty=0.001,
        min_notional=10.0
    )
)
risk_manager = RiskManager(config=risk_config, real_equity=100_000)
risk_manager.register_va(va_id="va1", virtual_equity=10_000)
```

### Evaluate Strategy and Get OrderPlan

```python
from strategy_risk_engine import Candle

# Prepare candles (5-minute bars)
candles = [...]  # List of Candle objects

# Evaluate strategy
order_plan = strategy.evaluate(
    va_id="va1",
    symbol="BTCUSDT",
    as_of=datetime.now(timezone.utc),
    candles=candles
)

if order_plan:
    # Review with risk manager
    review = risk_manager.review_orderplan(
        plan=order_plan,
        now=datetime.now(timezone.utc),
        reserve=True
    )
    if review.approved:
        print(f"Order approved: {review.qty} units")
```

### Bybit Integration

```python
from exchange import BybitClient, BybitClientConfig

config = BybitClientConfig(
    testnet=True,
    api_key="your_api_key",
    api_secret="your_api_secret",
)
client = BybitClient(config)

# Place entry order
entry = client.place_market_order(
    symbol="BTCUSDT",
    side="Buy",
    qty=1.0,
)

# Place stop-loss
sl = client.place_stop_loss(
    symbol="BTCUSDT",
    side="Buy",
    stop_price=99.0,
    qty=1.0,
)

# Record in database
db.create_order(
    order_id=entry.order_id,
    va_id="va1",
    symbol="BTCUSDT",
    side="Buy",
    order_type="Market",
    qty=1.0,
    price=entry.price,
)
db.link_sl_to_entry(entry.order_id, sl.order_id)
```

## Testing

Run all tests:

```bash
pytest tests/ -v
```

Run specific test class:

```bash
pytest tests/test_strategy_and_risk_engine.py::test_closed_candle_only_evaluation_no_lookahead -v
```

Run with coverage:

```bash
pytest tests/ --cov=strategy_risk_engine --cov=exchange --cov=storage
```

## Test Coverage

### Strategy Engine Tests
- ✅ Closed-candle-only evaluation (no lookahead)
- ✅ OrderPlan includes mandatory SL (and TP if fixed mode)
- ✅ Size decay triggers after consecutive losses
- ✅ Daily reset boundary (UTC midnight)
- ✅ Global one-VA-per-symbol enforcement
- ✅ Net exposure cap blocks trades when exceeded

### Risk Management Tests
- ✅ Per-VA kill-switch and daily loss limits
- ✅ Consecutive loss tracking and decay
- ✅ Leverage capping and sizing
- ✅ Daily trade count enforcement
- ✅ Symbol ownership rules

### Exchange Integration Tests
- ✅ Bybit client initialization and time sync
- ✅ Market order placement
- ✅ Stop-loss and take-profit placement
- ✅ Position fetching
- ✅ Panic-close mechanism

### Storage Layer Tests
- ✅ Virtual account CRUD operations
- ✅ Order creation and status updates
- ✅ SL/TP linkage to entry orders
- ✅ Position management with one-VA-per-symbol constraint
- ✅ Fill tracking
- ✅ Equity snapshots and daily PnL
- ✅ Incident logging
- ✅ Trade statistics tracking

## Key Design Decisions

1. **Closed-Candle-Only Evaluation**: The strategy strictly uses `close_time <= as_of` to prevent lookahead bias.

2. **Risk Manager State**: All risk state (daily PnL, consecutive losses, kill switch) is tracked in memory during execution and persisted to DB for audit/recovery.

3. **SL Hard Enforcement**: SL placement is mandatory. If it fails, the system immediately panic-closes the position and logs an incident.

4. **One-VA-Per-Symbol**: Enforced at the database level (unique constraint) and in RiskManager logic to prevent conflicting exposures.

5. **Leverage Capping**: Calculated as `qty = min(risk_budget / per_unit_risk, max_notional / entry_price)` where `max_notional = virtual_equity * leverage`.

6. **Size Decay**: Multiplicative factors ensure aggressive position reduction after losses.

## Configuration

### Strategy Config
```python
StrategyConfig(
    lookback_candles=20,      # Number of candles for ATR/volatility
    tp_mode="fixed",          # "fixed" or "trailing"
    fixed_tp_r=1.8,           # Multiples of risk (SL distance)
    sl_range_mult=1.0,        # ATR multiplier for SL distance
    min_stop_distance=0.0,    # Absolute minimum SL distance
    risk_tag="vol_breakout_5m_closed",
)
```

### Risk Config
```python
RiskConfig(
    max_daily_loss=100.0,
    max_drawdown_pct=0.30,
    max_trades_per_day=10,
    risk_per_trade_pct=0.01,  # 1% risk per trade
    default_leverage=3.0,
    max_leverage=5.0,
    daily_reset_hour_utc=0,   # Midnight UTC
    max_symbol_exposure_pct_real_equity=1.0,  # Up to 100% of real equity
    market_constraints=MarketConstraints(...)
)
```

## License

MIT

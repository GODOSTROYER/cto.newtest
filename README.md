# Trading System: Volatility Breakout Strategy with Risk Management

A comprehensive trading system featuring a volatility breakout strategy for 5-minute closed candles, integrated with Bybit testnet, advanced risk management, and SQLite-based persistence.

**What's in the box.** Four Python packages — a strategy + risk + sizing engine, a Bybit v5 REST client, a SQLAlchemy storage layer, and a reconciliation module tying the last two together — plus 34 tests covering all of it. It is a library, not a daemon: there is no CLI or execution loop on `main`, so you drive the pieces from your own code (see [Usage](#usage)). Everything points at Bybit **testnet** and a local SQLite file. Read [Limitations](#limitations) before pointing it at anything real.

## Features

### Strategy Engine
- **Volatility Breakout Strategy**: 5-minute closed candle analysis
  - No lookahead bias: only uses closed candles up to evaluation time
  - Dynamic breakout detection based on recent highs/lows
  - Configurable lookback periods and risk ratios

The signal, concretely: take the last `lookback_candles + 1` candles whose `close_time <= as_of`. The final one is the trigger, the rest are the reference window. If the trigger closes **above the highest high** of the window, go long; **below the lowest low**, go short; otherwise no plan. Stop distance is the window's mean candle range (`high - low`) × `sl_range_mult`, floored at `min_stop_distance`. In `fixed` TP mode the target sits `fixed_tp_r` × stop distance away; in `trailing` mode the stop trails by that distance and no TP is emitted. The result is an `OrderPlan` — a proposal. Nothing is sized or sent until `RiskManager.review_orderplan` approves it.

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
  - `requests`-based wrapper over the Bybit v5 REST API, pointed at `api-testnet.bybit.com` (or `api.bybit.com` with `testnet=False`)
  - Retry logic with jitter, plus a `urllib3` retry adapter for 429/5xx
  - Time sync handling via `/v5/market/time`
  - Idempotency helpers (`orderLinkId` client order IDs) and standardized errors — non-zero `retCode` is raised as a `RuntimeError`

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
├── requirements.txt               # Pinned runtime deps
├── pyproject.toml                 # Package metadata, dev extras, black/isort/mypy config
├── pytest.ini
└── README.md
```

## Stack

Python 3.9+, no framework. [SQLAlchemy](https://www.sqlalchemy.org/) 2.x ORM over SQLite for persistence, [requests](https://requests.readthedocs.io/) + `urllib3` for the Bybit v5 REST client, [pytest](https://docs.pytest.org/) for tests. The strategy, risk and sizing engines are plain frozen dataclasses and pure functions with no I/O — which is what makes them cheap to test.

## Usage

### Setup

Requires Python 3.9 or newer.

```bash
git clone https://github.com/GODOSTROYER/cto.newtest.git
cd cto.newtest

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt                 # runtime deps
pip install pytest-cov black isort mypy flake8  # optional dev tools
```

Run everything from the repository root — the packages are imported by their top-level names (`strategy_risk_engine`, `exchange`, `storage`, `reconciliation`) and are not installed onto the path. See [Limitations](#limitations) for why `pip install -e .` does not work yet.

No configuration files, environment variables or migrations are needed to run the engines or the tests — the strategy, risk and sizing packages are pure, and the test suite uses an in-memory SQLite database. Only the Bybit client reaches the network, and only when you construct one.

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

Credentials are passed straight into `BybitClientConfig` — nothing in the package reads the environment or a config file, so load them from wherever you keep secrets (e.g. `BYBIT_API_KEY` / `BYBIT_API_SECRET` in your environment) and keep them out of source control. `.env` is already gitignored.

```python
import os
from exchange import BybitClient, BybitClientConfig

config = BybitClientConfig(
    testnet=True,
    api_key=os.environ["BYBIT_API_KEY"],
    api_secret=os.environ["BYBIT_API_SECRET"],
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

34 tests across two files; the whole suite runs in about two seconds with no network and no database file — exchange calls are mocked with `unittest.mock.patch` and storage runs on `sqlite:///:memory:`.

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
    lookback_candles=20,      # Reference window for the breakout level and mean range
    tp_mode="fixed",          # "fixed" or "trailing"
    fixed_tp_r=1.8,           # Multiples of risk (SL distance)
    sl_range_mult=1.0,        # Multiplier on the window's mean candle range
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

## Limitations

Known gaps, so nobody is surprised by them:

- **The Bybit client does not sign requests.** `api_key` and `api_secret` are accepted by `BybitClientConfig` but never used to build the `X-BAPI-*` HMAC auth headers Bybit v5 requires. Public endpoints such as `/v5/market/time` work; the private ones (`order/create`, `order/amend`, `order/cancel`, `position/list`, `execution/list`) will be rejected until signing is added. The tests pass because every exchange call is mocked.
- **No execution loop on `main`.** There is no CLI, scheduler or entrypoint that polls candles, calls the strategy, routes approved plans to the exchange and runs the reconcilers on a timer. The components are here and the tests wire them up by hand; the runner is not.
- **Risk state is in-memory.** `RiskManager` holds daily PnL, trade counts, consecutive losses and the kill switch in a dict and has no database handle. The tables for snapshots, daily PnL and trade stats exist in `storage/`, but persisting and rehydrating that state is the caller's job — restart the process and the risk state resets.
- **`PositionReconciler` is a sketch.** `reconcile_positions` looks positions up under a literal `va_id="unknown"`, and `_enforce_sl_attachment` falls back to a hardcoded 2% stop rather than the plan's own `StopLossSpec`. Both are flagged as simplified in the source.
- **Nothing has been run against the live testnet.** Every exchange test uses `unittest.mock`; there is no recorded run, no fill log and no backtest or performance numbers in this repository. Treat the strategy parameters as defaults, not as tuned values.
- **`datetime.utcnow()` is used throughout `storage/`**, which emits deprecation warnings on Python 3.12+ and stores naive timestamps, while the strategy and risk engines require timezone-aware datetimes.
- **`pip install -e .` fails.** `pyproject.toml` declares the project but sets no `[tool.setuptools] packages`, so setuptools' flat-layout auto-discovery sees four top-level packages plus `tests/` and refuses to guess. Until that is configured, work from the repository root and rely on `requirements.txt`.
- **MIT is declared** here and in `pyproject.toml`, but no `LICENSE` file is checked in.

## Author

**Arnav Bule**

- Portfolio: [www.arnavbule.in](https://www.arnavbule.in)
- GitHub: [@GODOSTROYER](https://github.com/GODOSTROYER)

## License

MIT

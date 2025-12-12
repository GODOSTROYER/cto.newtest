# Trading Execution Loop

A comprehensive trading execution system with governance rules, risk management, and real-time monitoring.

## Features

- **Signal Router**: Enforces one-symbol-per-virtual-account (VA) rule
- **Governor**: Implements throttling and automatic cooldown after N consecutive losses
- **Market Filters**: 
  - Spread/slippage validation
  - Latency checks
  - Trading window constraints
- **Execution Loop**: 
  - Async order processing
  - Market entries and reduce-only exits
  - Partial fill handling
  - Order reconciliation every 5-10 seconds
  - SQLite persistence
- **Safety Features**:
  - Automatic stop-loss on every order
  - Trades abort on spread/latency breaches
  - Kill-switch capability
- **CLI Dashboard**: Live display of:
  - Per-VA PnL and drawdown
  - Open positions
  - Kill-switch state
  - Real-time updates

## Architecture

```
/src
  /config       - Settings and configuration
  /storage      - SQLite database and models
  /execution    - Core execution components
    - signal_router.py   - One-symbol-per-VA enforcement
    - governor.py        - Throttling and cooldown logic
    - filters.py         - Market filters (spread, latency, trading window)
    - order_manager.py   - Order lifecycle and stop-loss management
    - execution_loop.py  - Main execution loop
  /cli          - Dashboard and monitoring
```

## Quick Start

### Using Docker Compose (Recommended)

1. Build and start the container:
```bash
docker-compose up --build
```

2. View logs:
```bash
docker-compose logs -f
```

3. Stop the service:
```bash
docker-compose down
```

### Manual Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment (optional):
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Run the execution loop:
```bash
python main.py
```

## Configuration

Configure the system via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `trading.db` | SQLite database file path |
| `MAX_LOSS_COOLDOWN` | `3` | Number of consecutive losses before cooldown |
| `COOLDOWN_DURATION_SECONDS` | `300` | Cooldown duration (seconds) |
| `MAX_SPREAD_BPS` | `10.0` | Maximum allowed spread (basis points) |
| `MAX_SLIPPAGE_BPS` | `5.0` | Maximum allowed slippage (basis points) |
| `MAX_LATENCY_MS` | `500.0` | Maximum allowed latency (milliseconds) |
| `TRADING_WINDOW_START` | `09:30` | Trading window start time (HH:MM) |
| `TRADING_WINDOW_END` | `16:00` | Trading window end time (HH:MM) |
| `RECONCILE_INTERVAL_SECONDS` | `5` | Order reconciliation interval |
| `KILL_SWITCH_ENABLED` | `false` | Global kill switch |
| `MAX_POSITION_SIZE` | `10000.0` | Maximum position size per VA |
| `MAX_OPEN_POSITIONS_PER_VA` | `5` | Maximum open positions per VA |
| `STOP_LOSS_PERCENTAGE` | `2.0` | Stop loss percentage from entry |

## Governance Rules

### Signal Router
- Enforces one symbol per virtual account at a time
- Blocks signals for different symbols until current position is closed
- Automatically releases symbol when position is closed

### Governor
- **Cooldown Mechanism**: After N consecutive losses (default: 3), VA enters cooldown
- **Cooldown Duration**: Configurable period (default: 5 minutes)
- **Throttling**: Limits maximum open positions per VA
- **Trade Tracking**: Records PnL, win/loss ratio, and drawdown

### Market Filters
- **Spread Filter**: Rejects trades with excessive spread
- **Slippage Filter**: Validates expected vs. actual price
- **Latency Filter**: Ensures market data freshness
- **Trading Window**: Only trades during specified hours

### Order Management
- **Automatic Stop-Loss**: Every order includes a stop-loss
- **Position Monitoring**: Continuous check for stop-loss triggers
- **Reconciliation**: Periodic order status reconciliation
- **Partial Fills**: Proper handling of partially filled orders

## CLI Dashboard

The dashboard provides real-time monitoring:

**Virtual Accounts Panel:**
- Account ID
- Current balance
- Total PnL (profit/loss)
- Trade statistics (wins/losses)
- Maximum drawdown
- Status (active/cooldown)

**Open Positions Panel:**
- VA ID and symbol
- Position size (quantity)
- Entry and current price
- Unrealized PnL
- Stop-loss price

**Footer:**
- Kill-switch status
- System configuration
- Filter thresholds

## Testing

Run the test suite:

```bash
# All tests
pytest

# With coverage
pytest --cov=src tests/

# Specific test file
pytest tests/unit/test_governor.py

# Integration tests
pytest tests/integration/
```

## Development

### Project Structure

- `main.py` - Application entry point with signal simulation
- `src/config/` - Settings management
- `src/storage/` - Database models and SQLite manager
- `src/execution/` - Core execution logic
- `src/cli/` - Dashboard UI
- `tests/` - Unit and integration tests

### Adding New Features

1. Create feature module in appropriate `src/` subdirectory
2. Add models to `src/storage/models.py` if needed
3. Update database schema in `src/storage/sqlite_manager.py`
4. Write tests in `tests/unit/` or `tests/integration/`
5. Update configuration in `src/config/settings.py`
6. Document in README

## Docker Commands

```bash
# Build image
docker-compose build

# Start service
docker-compose up

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop service
docker-compose stop

# Remove containers and volumes
docker-compose down -v

# Restart service
docker-compose restart

# Execute commands in container
docker-compose exec trading-engine bash
```

## Troubleshooting

### Container won't start
- Check logs: `docker-compose logs trading-engine`
- Verify environment variables in `docker-compose.yml`
- Ensure port 8080 is available

### Database issues
- Remove volume: `docker-compose down -v`
- Check database path configuration
- Verify write permissions

### Dashboard not updating
- Ensure container is running: `docker-compose ps`
- Check reconciliation interval setting
- Verify terminal supports rich output

## License

MIT

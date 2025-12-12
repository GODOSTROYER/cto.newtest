# Quick Start Guide

This guide will help you get the Trading Execution Loop running in under 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- OR Python 3.11+ and pip

## Option 1: Docker (Recommended)

This is the fastest way to get started:

```bash
# Clone the repository (if not already done)
cd /path/to/project

# Build and start the system
docker-compose up --build
```

That's it! The system will:
1. Build the Docker image
2. Create a persistent database volume
3. Start the execution loop
4. Display the live CLI dashboard

### What You'll See

The dashboard shows:
- **Virtual Accounts Panel**: 3 demo accounts (VA001, VA002, VA003) with PnL, trades, and cooldown status
- **Open Positions Panel**: Active trades with real-time PnL updates
- **Status Footer**: System configuration and kill-switch state

### Stop the System

Press `Ctrl+C` or run:
```bash
docker-compose down
```

## Option 2: Manual Setup

If you prefer to run without Docker:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Configure settings
cp .env.example .env
# Edit .env if needed

# 3. Run the system
python main.py
```

## Testing the System

Run the test suite to validate all governance rules:

```bash
# Install test dependencies (if not already installed)
pip install -r requirements.txt

# Run tests
pytest tests/test_basic_functionality.py -v

# Run with coverage
pytest tests/test_basic_functionality.py --cov=src --cov-report=term-missing
```

### Expected Test Results

All 8 tests should pass:
- ✅ Database initialization
- ✅ One-symbol-per-VA rule
- ✅ Governor cooldown
- ✅ Trade tracking
- ✅ Market filters (spread)
- ✅ Market filters (latency)
- ✅ Stop-loss calculation
- ✅ Stop-loss trigger

## System Validation

Run the validation script to ensure all components are present:

```bash
./validate_system.sh
```

Expected output: `Checks passed: 24/24`

## Understanding the System

### Signal Flow

```
Signal Generated
    ↓
Signal Router (One-symbol-per-VA check)
    ↓
Governor (Cooldown & throttle check)
    ↓
Market Filters (Spread, latency, window check)
    ↓
Order Manager (Create order with stop-loss)
    ↓
Execution Loop (Submit to exchange simulation)
    ↓
Position Management (Track & update)
```

### Demo Behavior

The system runs with simulated signals:
- Generates random buy/sell signals every 5-15 seconds
- Distributes across 3 virtual accounts
- Trades 5 symbols: AAPL, GOOGL, MSFT, TSLA, AMZN
- Simulates order fills after 0.5-2 seconds
- Monitors positions for stop-loss triggers

### Key Features in Action

1. **One-Symbol-Per-VA**: Each VA can only trade one symbol at a time
2. **Cooldown**: After 3 consecutive losses, VA enters 5-minute cooldown
3. **Stop-Loss**: Every order gets a 2% stop-loss automatically
4. **Filters**: Orders rejected if spread/latency/window constraints fail
5. **Reconciliation**: Orders reconciled every 5 seconds

## Configuration

All settings can be customized via environment variables:

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_LOSS_COOLDOWN` | 3 | Losses before cooldown |
| `COOLDOWN_DURATION_SECONDS` | 300 | Cooldown period (5 min) |
| `MAX_SPREAD_BPS` | 10.0 | Max spread (10 bps) |
| `MAX_LATENCY_MS` | 500.0 | Max latency (500ms) |
| `STOP_LOSS_PERCENTAGE` | 2.0 | Stop-loss (2%) |
| `KILL_SWITCH_ENABLED` | false | Emergency stop |

See `.env.example` for all available settings.

## Troubleshooting

### Docker Issues

**Container won't start:**
```bash
# Check logs
docker-compose logs trading-engine

# Rebuild from scratch
docker-compose down -v
docker-compose up --build
```

**Port conflicts:**
- The system doesn't expose ports by default
- It runs entirely in the container with CLI output

### Python Issues

**Import errors:**
```bash
# Ensure you're in the project root
cd /path/to/project

# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

**Database locked:**
```bash
# Remove the database file
rm trading.db

# Restart the system
python main.py
```

## Next Steps

1. **Customize Configuration**: Edit `.env` to adjust governance rules
2. **Connect Real Exchange**: Replace simulated fills with actual exchange API
3. **Add Strategies**: Integrate your trading strategy signals
4. **Enhance Dashboard**: Add charts, alerts, or web interface
5. **Production Deploy**: Set up proper logging, monitoring, and alerting

## Support

- See `README.md` for full documentation
- See `IMPLEMENTATION.md` for technical details
- Check `tests/test_basic_functionality.py` for usage examples

## Success Criteria ✅

You've successfully deployed if:
- Dashboard shows 3 virtual accounts
- Signals are being generated and logged
- Orders appear in the console
- No error messages in the output
- Tests pass with `pytest tests/test_basic_functionality.py -v`

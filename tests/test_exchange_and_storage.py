from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from exchange import BybitClient, BybitClientConfig
from exchange.models import ExchangeFill, ExchangeOrder, ExchangePosition
from storage import Database
from storage.models import OrderRecord, PositionRecord, VirtualAccountRecord

UTC = timezone.utc


# ===== Fixture Setup =====


@pytest.fixture
def db_memory():
    """In-memory SQLite database for testing."""
    db = Database("sqlite:///:memory:")
    db.init_db()
    return db


@pytest.fixture
def bybit_config():
    """Bybit client configuration for testnet."""
    return BybitClientConfig(
        testnet=True,
        api_key="test_key",
        api_secret="test_secret",
        max_retries=2,
        retry_delay_ms=50,
    )


# ===== Storage Layer Tests =====


class TestDatabaseVAOperations:
    """Test virtual account database operations."""

    def test_create_va(self, db_memory):
        """Test creating a virtual account."""
        va = db_memory.create_or_update_va(va_id="va1", allocation=1000.0, status="active")
        assert va.id == "va1"
        assert va.allocation == 1000.0
        assert va.status == "active"
        assert va.kill_switch is False

    def test_get_va(self, db_memory):
        """Test retrieving a virtual account."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        va = db_memory.get_va("va1")
        assert va is not None
        assert va.id == "va1"
        assert va.allocation == 1000.0

    def test_set_va_kill_switch(self, db_memory):
        """Test setting kill switch on VA."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.set_va_kill_switch("va1", True)
        va = db_memory.get_va("va1")
        assert va.kill_switch is True

    def test_update_va_allocation(self, db_memory):
        """Test updating VA allocation."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_or_update_va(va_id="va1", allocation=2000.0)
        va = db_memory.get_va("va1")
        assert va.allocation == 2000.0


class TestDatabaseOrderOperations:
    """Test order database operations."""

    def test_create_order(self, db_memory):
        """Test creating an order."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        order = db_memory.create_order(
            order_id="order1",
            va_id="va1",
            symbol="BTCUSDT",
            side="Buy",
            order_type="Market",
            qty=1.0,
            price=100.0,
            reduce_only=False,
            client_order_id="client_order1",
        )
        assert order.id == "order1"
        assert order.va_id == "va1"
        assert order.symbol == "BTCUSDT"
        assert order.status == "New"

    def test_update_order_status(self, db_memory):
        """Test updating order status."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_order(
            order_id="order1",
            va_id="va1",
            symbol="BTCUSDT",
            side="Buy",
            order_type="Market",
            qty=1.0,
            price=100.0,
        )
        db_memory.update_order_status("order1", "Filled", 1.0)
        order = db_memory.get_order("order1")
        assert order.status == "Filled"
        assert order.filled_qty == 1.0

    def test_link_sl_to_entry(self, db_memory):
        """Test linking stop-loss to entry order."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_order(
            order_id="entry1",
            va_id="va1",
            symbol="BTCUSDT",
            side="Buy",
            order_type="Market",
            qty=1.0,
            price=100.0,
        )
        db_memory.create_order(
            order_id="sl1",
            va_id="va1",
            symbol="BTCUSDT",
            side="Sell",
            order_type="Stop",
            qty=1.0,
            price=99.0,
            reduce_only=True,
        )
        db_memory.link_sl_to_entry("entry1", "sl1")
        order = db_memory.get_order("entry1")
        assert order.sl_plan_id == "sl1"

    def test_get_orders_by_va(self, db_memory):
        """Test retrieving orders for a VA."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_order(
            order_id="order1",
            va_id="va1",
            symbol="BTCUSDT",
            side="Buy",
            order_type="Market",
            qty=1.0,
            price=100.0,
        )
        db_memory.create_order(
            order_id="order2",
            va_id="va1",
            symbol="ETHUSDT",
            side="Buy",
            order_type="Market",
            qty=10.0,
            price=10.0,
        )
        orders = db_memory.get_orders_by_va("va1")
        assert len(orders) == 2


class TestDatabasePositionOperations:
    """Test position database operations."""

    def test_create_position(self, db_memory):
        """Test creating a position."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        pos = db_memory.create_or_update_position(
            position_id="pos1",
            va_id="va1",
            symbol="BTCUSDT",
            qty=1.0,
            avg_entry_price=100.0,
        )
        assert pos.va_id == "va1"
        assert pos.symbol == "BTCUSDT"
        assert pos.qty == 1.0

    def test_get_position(self, db_memory):
        """Test retrieving a position."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_or_update_position(
            position_id="pos1",
            va_id="va1",
            symbol="BTCUSDT",
            qty=1.0,
            avg_entry_price=100.0,
        )
        pos = db_memory.get_position("va1", "BTCUSDT")
        assert pos is not None
        assert pos.qty == 1.0

    def test_update_position(self, db_memory):
        """Test updating a position."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_or_update_position(
            position_id="pos1",
            va_id="va1",
            symbol="BTCUSDT",
            qty=1.0,
            avg_entry_price=100.0,
        )
        db_memory.create_or_update_position(
            position_id="pos1",
            va_id="va1",
            symbol="BTCUSDT",
            qty=2.0,
            avg_entry_price=101.0,
        )
        pos = db_memory.get_position("va1", "BTCUSDT")
        assert pos.qty == 2.0
        assert pos.avg_entry_price == 101.0

    def test_get_positions_by_symbol(self, db_memory):
        """Test one VA owns a symbol at a time."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_or_update_va(va_id="va2", allocation=1000.0)
        db_memory.create_or_update_position(
            position_id="pos1",
            va_id="va1",
            symbol="BTCUSDT",
            qty=1.0,
            avg_entry_price=100.0,
        )
        positions = db_memory.get_positions_by_symbol("BTCUSDT")
        assert len(positions) == 1
        assert positions[0].va_id == "va1"


class TestDatabaseFillOperations:
    """Test fill database operations."""

    def test_create_fill(self, db_memory):
        """Test creating a fill record."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_order(
            order_id="order1",
            va_id="va1",
            symbol="BTCUSDT",
            side="Buy",
            order_type="Market",
            qty=1.0,
            price=100.0,
        )
        fill = db_memory.create_fill(
            fill_id="fill1",
            order_id="order1",
            symbol="BTCUSDT",
            side="Buy",
            qty=1.0,
            price=100.0,
            fee=0.1,
            fee_asset="USDT",
        )
        assert fill.id == "fill1"
        assert fill.qty == 1.0


class TestDatabaseIncidentOperations:
    """Test incident database operations."""

    def test_create_incident(self, db_memory):
        """Test creating an incident."""
        incident = db_memory.create_incident(
            incident_id="inc1",
            incident_type="sl_failed",
            severity="high",
            description="SL placement failed for BTCUSDT",
            symbol="BTCUSDT",
        )
        assert incident.incident_type == "sl_failed"
        assert incident.severity == "high"

    def test_get_incidents(self, db_memory):
        """Test retrieving incidents."""
        db_memory.create_incident(
            incident_id="inc1",
            incident_type="sl_failed",
            severity="high",
            description="SL placement failed",
            symbol="BTCUSDT",
        )
        db_memory.create_incident(
            incident_id="inc2",
            incident_type="panic_close",
            severity="high",
            description="Position panic-closed",
            symbol="ETHUSDT",
        )
        incidents = db_memory.get_incidents(incident_type="sl_failed")
        assert len(incidents) == 1
        assert incidents[0].incident_type == "sl_failed"


class TestDatabaseEquitySnapshot:
    """Test equity snapshot database operations."""

    def test_create_equity_snapshot(self, db_memory):
        """Test creating an equity snapshot."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        snapshot = db_memory.create_equity_snapshot(
            snapshot_id="snap1",
            va_id="va1",
            virtual_equity=1000.0,
            peak_equity=1000.0,
            daily_pnl=0.0,
        )
        assert snapshot.va_id == "va1"
        assert snapshot.virtual_equity == 1000.0


class TestDatabaseDailyPnL:
    """Test daily PnL database operations."""

    def test_create_daily_pnl(self, db_memory):
        """Test creating a daily PnL record."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        record = db_memory.create_or_update_daily_pnl(
            pnl_id="pnl1",
            va_id="va1",
            date="2025-01-01",
            pnl=50.0,
            trades_count=2,
        )
        assert record.va_id == "va1"
        assert record.pnl == 50.0

    def test_update_daily_pnl(self, db_memory):
        """Test updating a daily PnL record."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_or_update_daily_pnl(
            pnl_id="pnl1",
            va_id="va1",
            date="2025-01-01",
            pnl=50.0,
        )
        db_memory.create_or_update_daily_pnl(
            pnl_id="pnl1",
            va_id="va1",
            date="2025-01-01",
            pnl=100.0,
            trades_count=3,
        )
        # Re-query to verify
        from sqlalchemy import text
        session = db_memory.create_session()
        try:
            result = session.execute(text("SELECT pnl FROM daily_pnl WHERE va_id = 'va1'")).fetchone()
            assert result[0] == 100.0
        finally:
            session.close()


# ===== Exchange Client Tests =====


class TestBybitClientMock:
    """Test Bybit client with mocked HTTP responses."""

    @patch("exchange.bybit_client.requests.Session.get")
    def test_get_server_time(self, mock_get, bybit_config):
        """Test getting server time."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "retCode": 0,
            "result": {"timeSecond": "1700000000"},
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = BybitClient(bybit_config)
        server_time = client.get_server_time()

        assert isinstance(server_time, datetime)
        assert server_time.tzinfo == UTC

    @patch("exchange.bybit_client.requests.Session.post")
    def test_place_market_order(self, mock_post, bybit_config):
        """Test placing a market order."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "retCode": 0,
            "result": {"orderId": "order123"},
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = BybitClient(bybit_config)
        order = client.place_market_order(
            symbol="BTCUSDT",
            side="Buy",
            qty=1.0,
        )

        assert order.order_id == "order123"
        assert order.symbol == "BTCUSDT"
        assert order.side == "Buy"
        assert order.qty == 1.0

    @patch("exchange.bybit_client.requests.Session.post")
    def test_place_stop_loss(self, mock_post, bybit_config):
        """Test placing a stop-loss order."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "retCode": 0,
            "result": {"orderId": "sl_order123"},
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = BybitClient(bybit_config)
        order = client.place_stop_loss(
            symbol="BTCUSDT",
            side="Buy",
            stop_price=99.0,
            qty=1.0,
        )

        assert order.order_id == "sl_order123"
        assert order.reduce_only is True

    @patch("exchange.bybit_client.requests.Session.get")
    def test_get_positions(self, mock_get, bybit_config):
        """Test fetching positions."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "side": "Buy",
                        "size": "1.0",
                        "avgPrice": "100.0",
                        "markPrice": "101.0",
                        "unrealisedPnl": "1.0",
                        "leverage": "3.0",
                        "stopLoss": None,
                        "takeProfit": None,
                    }
                ]
            },
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = BybitClient(bybit_config)
        positions = client.get_positions()

        assert len(positions) == 1
        assert positions[0].symbol == "BTCUSDT"
        assert positions[0].qty == 1.0

    @patch("exchange.bybit_client.requests.Session.post")
    def test_panic_close_position(self, mock_post, bybit_config):
        """Test panic-closing a position."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "retCode": 0,
            "result": {"orderId": "close_order123"},
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = BybitClient(bybit_config)
        order = client.panic_close_position(
            symbol="BTCUSDT",
            side="Buy",
            qty=1.0,
        )

        assert order.order_id == "close_order123"
        assert order.reduce_only is True


# ===== Integration Tests =====


class TestSLAttachmentAndPanicClose:
    """Test stop-loss attachment and panic-close mechanisms."""

    def test_entry_and_sl_linkage(self, db_memory):
        """Test that entry orders are linked to SL orders in DB."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)

        # Create entry order
        entry = db_memory.create_order(
            order_id="entry1",
            va_id="va1",
            symbol="BTCUSDT",
            side="Buy",
            order_type="Market",
            qty=1.0,
            price=100.0,
        )

        # Create SL order
        sl = db_memory.create_order(
            order_id="sl1",
            va_id="va1",
            symbol="BTCUSDT",
            side="Sell",
            order_type="Stop",
            qty=1.0,
            price=99.0,
            reduce_only=True,
        )

        # Link them
        db_memory.link_sl_to_entry("entry1", "sl1")

        # Verify linkage
        entry_retrieved = db_memory.get_order("entry1")
        assert entry_retrieved.sl_plan_id == "sl1"


class TestOneVAPerSymbolEnforcement:
    """Test that one VA owns a symbol at a time."""

    def test_one_va_owns_symbol(self, db_memory):
        """Test one-VA-per-symbol constraint in DB."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)
        db_memory.create_or_update_va(va_id="va2", allocation=1000.0)

        # VA1 takes position
        db_memory.create_or_update_position(
            position_id="pos1",
            va_id="va1",
            symbol="BTCUSDT",
            qty=1.0,
            avg_entry_price=100.0,
        )

        # Only VA1 should have a position in BTCUSDT
        positions = db_memory.get_positions_by_symbol("BTCUSDT")
        assert len(positions) == 1
        assert positions[0].va_id == "va1"

        # Can't have VA2 take BTCUSDT at same time (in app logic, not DB constraint)
        # This is enforced by RiskManager


class TestNetExposureCap:
    """Test net exposure cap enforcement."""

    def test_positions_notional_calculation(self, db_memory):
        """Test calculating total notional exposure."""
        db_memory.create_or_update_va(va_id="va1", allocation=1000.0)

        # Create two positions
        db_memory.create_or_update_position(
            position_id="pos1",
            va_id="va1",
            symbol="BTCUSDT",
            qty=0.5,
            avg_entry_price=100.0,
        )

        db_memory.create_or_update_position(
            position_id="pos2",
            va_id="va1",
            symbol="ETHUSDT",
            qty=10.0,
            avg_entry_price=50.0,
        )

        # Get all positions for VA
        positions = db_memory.get_positions_by_va("va1")
        assert len(positions) == 2

        # Calculate notional
        total_notional = sum(abs(pos.qty) * pos.avg_entry_price for pos in positions)
        assert total_notional == (0.5 * 100.0) + (10.0 * 50.0)


class TestIncidentLogging:
    """Test incident logging for SL failures and panic-closes."""

    def test_sl_failed_incident(self, db_memory):
        """Test logging SL attachment failure."""
        incident = db_memory.create_incident(
            incident_id="inc1",
            incident_type="sl_failed",
            severity="high",
            description="Failed to attach SL to order order1",
            symbol="BTCUSDT",
            order_id="order1",
        )

        incidents = db_memory.get_incidents(incident_type="sl_failed")
        assert len(incidents) == 1
        assert incidents[0].order_id == "order1"

    def test_panic_close_incident(self, db_memory):
        """Test logging panic-close."""
        incident = db_memory.create_incident(
            incident_id="inc2",
            incident_type="panic_close",
            severity="high",
            description="Panic-closed position BTCUSDT",
            symbol="BTCUSDT",
        )

        incidents = db_memory.get_incidents(incident_type="panic_close")
        assert len(incidents) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

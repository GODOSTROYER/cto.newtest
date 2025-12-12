from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import ExchangeFill, ExchangeOrder, ExchangePosition


@dataclass(frozen=True)
class BybitClientConfig:
    testnet: bool = True
    api_key: str = ""
    api_secret: str = ""
    recv_window: int = 5000
    max_retries: int = 3
    retry_delay_ms: int = 100
    timeout_sec: int = 10


class BybitClient:
    """Bybit Testnet client wrapper with rate limiting, retries, and time sync handling."""

    def __init__(self, config: BybitClientConfig):
        self.config = config
        self.base_url = "https://api-testnet.bybit.com" if config.testnet else "https://api.bybit.com"
        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a session with retry strategy and jitter."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def get_server_time(self) -> datetime:
        """Get server time and handle time sync."""
        try:
            resp = self._session.get(f"{self.base_url}/v5/market/time", timeout=self.config.timeout_sec)
            resp.raise_for_status()
            data = resp.json()
            if data.get("retCode") != 0:
                raise RuntimeError(f"Bybit error: {data}")
            timestamp_ms = int(data["result"]["timeSecond"]) * 1000
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        except Exception as e:
            raise RuntimeError(f"Failed to get server time: {e}")

    def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> ExchangeOrder:
        """Place a market entry order."""
        payload = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
            "reduceOnly": reduce_only,
        }
        if client_order_id:
            payload["orderLinkId"] = client_order_id

        data = self._request("POST", "/v5/order/create", payload)
        order_id = data["orderId"]
        return ExchangeOrder(
            order_id=order_id,
            client_order_id=client_order_id or order_id,
            symbol=symbol,
            side=side,
            order_type="Market",
            price=0.0,
            qty=qty,
            reduce_only=reduce_only,
            status="New",
            filled_qty=0.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def place_stop_loss(
        self,
        *,
        symbol: str,
        side: str,
        stop_price: float,
        qty: float,
        client_order_id: Optional[str] = None,
    ) -> ExchangeOrder:
        """Place a stop-loss order (reduce-only)."""
        opposite_side = "Sell" if side == "Buy" else "Buy"
        payload = {
            "category": "linear",
            "symbol": symbol,
            "side": opposite_side,
            "orderType": "Market",
            "stopLoss": str(stop_price),
            "qty": str(qty),
            "reduceOnly": True,
        }
        if client_order_id:
            payload["orderLinkId"] = client_order_id

        data = self._request("POST", "/v5/order/create", payload)
        order_id = data["orderId"]
        return ExchangeOrder(
            order_id=order_id,
            client_order_id=client_order_id or order_id,
            symbol=symbol,
            side=opposite_side,
            order_type="Market",
            price=stop_price,
            qty=qty,
            reduce_only=True,
            status="New",
            filled_qty=0.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def place_take_profit(
        self,
        *,
        symbol: str,
        side: str,
        take_profit_price: float,
        qty: float,
        client_order_id: Optional[str] = None,
    ) -> ExchangeOrder:
        """Place a take-profit order (reduce-only)."""
        opposite_side = "Sell" if side == "Buy" else "Buy"
        payload = {
            "category": "linear",
            "symbol": symbol,
            "side": opposite_side,
            "orderType": "Limit",
            "price": str(take_profit_price),
            "takeProfit": str(take_profit_price),
            "qty": str(qty),
            "reduceOnly": True,
        }
        if client_order_id:
            payload["orderLinkId"] = client_order_id

        data = self._request("POST", "/v5/order/create", payload)
        order_id = data["orderId"]
        return ExchangeOrder(
            order_id=order_id,
            client_order_id=client_order_id or order_id,
            symbol=symbol,
            side=opposite_side,
            order_type="Limit",
            price=take_profit_price,
            qty=qty,
            reduce_only=True,
            status="New",
            filled_qty=0.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def cancel_order(self, *, symbol: str, order_id: str) -> bool:
        """Cancel an order."""
        payload = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id,
        }
        try:
            self._request("POST", "/v5/order/cancel", payload)
            return True
        except Exception:
            return False

    def cancel_replace_order(
        self,
        *,
        symbol: str,
        order_id: str,
        new_qty: Optional[float] = None,
        new_price: Optional[float] = None,
    ) -> ExchangeOrder:
        """Cancel and replace an order atomically."""
        payload = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id,
        }
        if new_qty is not None:
            payload["newQty"] = str(new_qty)
        if new_price is not None:
            payload["newPrice"] = str(new_price)

        data = self._request("POST", "/v5/order/amend", payload)
        order_id = data["orderId"]
        return ExchangeOrder(
            order_id=order_id,
            client_order_id=order_id,
            symbol=symbol,
            side="",
            order_type="",
            price=new_price or 0.0,
            qty=new_qty or 0.0,
            reduce_only=False,
            status="New",
            filled_qty=0.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def get_positions(self) -> List[ExchangePosition]:
        """Fetch all open positions."""
        data = self._request("GET", "/v5/position/list", {"category": "linear"})
        positions = []
        for item in data.get("list", []):
            if float(item["size"]) == 0:
                continue
            positions.append(
                ExchangePosition(
                    symbol=item["symbol"],
                    side=item["side"],
                    qty=float(item["size"]),
                    avg_entry_price=float(item["avgPrice"]),
                    mark_price=float(item["markPrice"]),
                    unrealized_pnl=float(item["unrealisedPnl"]),
                    leverage=float(item.get("leverage", 1.0)),
                    stop_loss_price=float(item["stopLoss"]) if item.get("stopLoss") else None,
                    take_profit_price=float(item["takeProfit"]) if item.get("takeProfit") else None,
                )
            )
        return positions

    def get_open_orders(self, *, symbol: Optional[str] = None) -> List[ExchangeOrder]:
        """Fetch open orders."""
        payload = {"category": "linear", "settleCoin": "USDT"}
        if symbol:
            payload["symbol"] = symbol

        data = self._request("GET", "/v5/order/realtime", payload)
        orders = []
        for item in data.get("list", []):
            orders.append(
                ExchangeOrder(
                    order_id=item["orderId"],
                    client_order_id=item.get("orderLinkId", item["orderId"]),
                    symbol=item["symbol"],
                    side=item["side"],
                    order_type=item["orderType"],
                    price=float(item["price"]),
                    qty=float(item["qty"]),
                    reduce_only=item.get("reduceOnly", False),
                    status=item["orderStatus"],
                    filled_qty=float(item.get("cumExecQty", 0)),
                    created_at=datetime.fromtimestamp(int(item["createdTime"]) / 1000, tz=timezone.utc),
                    updated_at=datetime.fromtimestamp(int(item["updatedTime"]) / 1000, tz=timezone.utc),
                )
            )
        return orders

    def get_fills(self, *, symbol: Optional[str] = None, limit: int = 50) -> List[ExchangeFill]:
        """Fetch trade fills."""
        payload = {"category": "linear", "limit": limit}
        if symbol:
            payload["symbol"] = symbol

        data = self._request("GET", "/v5/execution/list", payload)
        fills = []
        for item in data.get("list", []):
            fills.append(
                ExchangeFill(
                    fill_id=item["execId"],
                    order_id=item["orderId"],
                    symbol=item["symbol"],
                    side=item["side"],
                    qty=float(item["execQty"]),
                    price=float(item["execPrice"]),
                    fee=float(item.get("execFee", 0)),
                    fee_asset=item.get("feeCurrency", "USDT"),
                    created_at=datetime.fromtimestamp(int(item["execTime"]) / 1000, tz=timezone.utc),
                )
            )
        return fills

    def attach_stop_loss(
        self,
        *,
        symbol: str,
        order_id: str,
        stop_price: float,
    ) -> bool:
        """Attach a stop-loss to an existing order."""
        payload = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id,
            "stopLoss": str(stop_price),
        }
        try:
            self._request("POST", "/v5/order/amend", payload)
            return True
        except Exception:
            return False

    def panic_close_position(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
    ) -> ExchangeOrder:
        """Market reduce-only order to close position immediately."""
        opposite_side = "Sell" if side == "Buy" else "Buy"
        payload = {
            "category": "linear",
            "symbol": symbol,
            "side": opposite_side,
            "orderType": "Market",
            "qty": str(qty),
            "reduceOnly": True,
        }
        data = self._request("POST", "/v5/order/create", payload)
        order_id = data["orderId"]
        return ExchangeOrder(
            order_id=order_id,
            client_order_id=order_id,
            symbol=symbol,
            side=opposite_side,
            order_type="Market",
            price=0.0,
            qty=qty,
            reduce_only=True,
            status="New",
            filled_qty=0.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def _request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request with retries and jitter."""
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.config.max_retries):
            try:
                if method == "GET":
                    resp = self._session.get(url, params=payload, timeout=self.config.timeout_sec)
                elif method == "POST":
                    resp = self._session.post(url, json=payload, timeout=self.config.timeout_sec)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                resp.raise_for_status()
                data = resp.json()

                if data.get("retCode") != 0:
                    raise RuntimeError(f"Bybit API error: {data.get('retMsg', 'Unknown error')}")

                return data.get("result", {})
            except requests.exceptions.RequestException as e:
                if attempt < self.config.max_retries - 1:
                    jitter_ms = random.randint(0, self.config.retry_delay_ms)
                    time.sleep((self.config.retry_delay_ms + jitter_ms) / 1000.0)
                else:
                    raise RuntimeError(f"Request failed after {self.config.max_retries} attempts: {e}")

        raise RuntimeError("Unexpected error in _request")

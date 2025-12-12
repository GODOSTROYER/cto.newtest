import aiosqlite
from datetime import datetime
from typing import List, Optional
from .models import Order, Position, Trade, VirtualAccount, OrderStatus, OrderSide


class SQLiteManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS virtual_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    va_id TEXT UNIQUE NOT NULL,
                    balance REAL NOT NULL,
                    total_pnl REAL DEFAULT 0.0,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    max_drawdown REAL DEFAULT 0.0,
                    current_drawdown REAL DEFAULT 0.0,
                    consecutive_losses INTEGER DEFAULT 0,
                    in_cooldown BOOLEAN DEFAULT 0,
                    cooldown_until TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    va_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL,
                    stop_loss_price REAL,
                    filled_quantity REAL DEFAULT 0.0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reduce_only BOOLEAN DEFAULT 0,
                    order_ref TEXT,
                    FOREIGN KEY (va_id) REFERENCES virtual_accounts(va_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    va_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL DEFAULT 0.0,
                    unrealized_pnl REAL DEFAULT 0.0,
                    realized_pnl REAL DEFAULT 0.0,
                    stop_loss_price REAL,
                    opened_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(va_id, symbol),
                    FOREIGN KEY (va_id) REFERENCES virtual_accounts(va_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    va_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    pnl REAL DEFAULT 0.0,
                    order_id INTEGER,
                    executed_at TEXT NOT NULL,
                    FOREIGN KEY (va_id) REFERENCES virtual_accounts(va_id),
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            """)
            
            await db.commit()

    async def create_virtual_account(self, va: VirtualAccount) -> VirtualAccount:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO virtual_accounts (
                    va_id, balance, total_pnl, total_trades, winning_trades, 
                    losing_trades, max_drawdown, current_drawdown, consecutive_losses,
                    in_cooldown, cooldown_until, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                va.va_id, va.balance, va.total_pnl, va.total_trades, va.winning_trades,
                va.losing_trades, va.max_drawdown, va.current_drawdown, va.consecutive_losses,
                va.in_cooldown, va.cooldown_until.isoformat() if va.cooldown_until else None,
                va.created_at.isoformat(), va.updated_at.isoformat()
            ))
            await db.commit()
            va.id = cursor.lastrowid
            return va

    async def get_virtual_account(self, va_id: str) -> Optional[VirtualAccount]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM virtual_accounts WHERE va_id = ?", (va_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return VirtualAccount(
                        id=row["id"],
                        va_id=row["va_id"],
                        balance=row["balance"],
                        total_pnl=row["total_pnl"],
                        total_trades=row["total_trades"],
                        winning_trades=row["winning_trades"],
                        losing_trades=row["losing_trades"],
                        max_drawdown=row["max_drawdown"],
                        current_drawdown=row["current_drawdown"],
                        consecutive_losses=row["consecutive_losses"],
                        in_cooldown=bool(row["in_cooldown"]),
                        cooldown_until=datetime.fromisoformat(row["cooldown_until"]) if row["cooldown_until"] else None,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"])
                    )
                return None

    async def update_virtual_account(self, va: VirtualAccount):
        va.updated_at = datetime.utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE virtual_accounts SET
                    balance = ?, total_pnl = ?, total_trades = ?, winning_trades = ?,
                    losing_trades = ?, max_drawdown = ?, current_drawdown = ?,
                    consecutive_losses = ?, in_cooldown = ?, cooldown_until = ?,
                    updated_at = ?
                WHERE va_id = ?
            """, (
                va.balance, va.total_pnl, va.total_trades, va.winning_trades,
                va.losing_trades, va.max_drawdown, va.current_drawdown,
                va.consecutive_losses, va.in_cooldown,
                va.cooldown_until.isoformat() if va.cooldown_until else None,
                va.updated_at.isoformat(), va.va_id
            ))
            await db.commit()

    async def list_virtual_accounts(self) -> List[VirtualAccount]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM virtual_accounts") as cursor:
                rows = await cursor.fetchall()
                return [
                    VirtualAccount(
                        id=row["id"],
                        va_id=row["va_id"],
                        balance=row["balance"],
                        total_pnl=row["total_pnl"],
                        total_trades=row["total_trades"],
                        winning_trades=row["winning_trades"],
                        losing_trades=row["losing_trades"],
                        max_drawdown=row["max_drawdown"],
                        current_drawdown=row["current_drawdown"],
                        consecutive_losses=row["consecutive_losses"],
                        in_cooldown=bool(row["in_cooldown"]),
                        cooldown_until=datetime.fromisoformat(row["cooldown_until"]) if row["cooldown_until"] else None,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"])
                    )
                    for row in rows
                ]

    async def create_order(self, order: Order) -> Order:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO orders (
                    va_id, symbol, side, quantity, price, stop_loss_price,
                    filled_quantity, status, created_at, updated_at, reduce_only, order_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.va_id, order.symbol, order.side.value, order.quantity, order.price,
                order.stop_loss_price, order.filled_quantity, order.status.value,
                order.created_at.isoformat(), order.updated_at.isoformat(),
                order.reduce_only, order.order_ref
            ))
            await db.commit()
            order.id = cursor.lastrowid
            return order

    async def get_order(self, order_id: int) -> Optional[Order]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Order(
                        id=row["id"],
                        va_id=row["va_id"],
                        symbol=row["symbol"],
                        side=OrderSide(row["side"]),
                        quantity=row["quantity"],
                        price=row["price"],
                        stop_loss_price=row["stop_loss_price"],
                        filled_quantity=row["filled_quantity"],
                        status=OrderStatus(row["status"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        reduce_only=bool(row["reduce_only"]),
                        order_ref=row["order_ref"]
                    )
                return None

    async def update_order(self, order: Order):
        order.updated_at = datetime.utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE orders SET
                    filled_quantity = ?, status = ?, updated_at = ?, order_ref = ?
                WHERE id = ?
            """, (
                order.filled_quantity, order.status.value,
                order.updated_at.isoformat(), order.order_ref, order.id
            ))
            await db.commit()

    async def get_open_orders(self, va_id: Optional[str] = None) -> List[Order]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if va_id:
                query = "SELECT * FROM orders WHERE va_id = ? AND status IN (?, ?)"
                params = (va_id, OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value)
            else:
                query = "SELECT * FROM orders WHERE status IN (?, ?)"
                params = (OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [
                    Order(
                        id=row["id"],
                        va_id=row["va_id"],
                        symbol=row["symbol"],
                        side=OrderSide(row["side"]),
                        quantity=row["quantity"],
                        price=row["price"],
                        stop_loss_price=row["stop_loss_price"],
                        filled_quantity=row["filled_quantity"],
                        status=OrderStatus(row["status"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        reduce_only=bool(row["reduce_only"]),
                        order_ref=row["order_ref"]
                    )
                    for row in rows
                ]

    async def create_position(self, position: Position) -> Position:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT OR REPLACE INTO positions (
                    va_id, symbol, quantity, entry_price, current_price,
                    unrealized_pnl, realized_pnl, stop_loss_price, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.va_id, position.symbol, position.quantity, position.entry_price,
                position.current_price, position.unrealized_pnl, position.realized_pnl,
                position.stop_loss_price, position.opened_at.isoformat(),
                position.updated_at.isoformat()
            ))
            await db.commit()
            position.id = cursor.lastrowid
            return position

    async def get_position(self, va_id: str, symbol: str) -> Optional[Position]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM positions WHERE va_id = ? AND symbol = ?",
                (va_id, symbol)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Position(
                        id=row["id"],
                        va_id=row["va_id"],
                        symbol=row["symbol"],
                        quantity=row["quantity"],
                        entry_price=row["entry_price"],
                        current_price=row["current_price"],
                        unrealized_pnl=row["unrealized_pnl"],
                        realized_pnl=row["realized_pnl"],
                        stop_loss_price=row["stop_loss_price"],
                        opened_at=datetime.fromisoformat(row["opened_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"])
                    )
                return None

    async def update_position(self, position: Position):
        position.updated_at = datetime.utcnow()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE positions SET
                    quantity = ?, current_price = ?, unrealized_pnl = ?,
                    realized_pnl = ?, stop_loss_price = ?, updated_at = ?
                WHERE va_id = ? AND symbol = ?
            """, (
                position.quantity, position.current_price, position.unrealized_pnl,
                position.realized_pnl, position.stop_loss_price,
                position.updated_at.isoformat(), position.va_id, position.symbol
            ))
            await db.commit()

    async def delete_position(self, va_id: str, symbol: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM positions WHERE va_id = ? AND symbol = ?", (va_id, symbol))
            await db.commit()

    async def get_positions(self, va_id: Optional[str] = None) -> List[Position]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if va_id:
                query = "SELECT * FROM positions WHERE va_id = ?"
                params = (va_id,)
            else:
                query = "SELECT * FROM positions"
                params = ()
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [
                    Position(
                        id=row["id"],
                        va_id=row["va_id"],
                        symbol=row["symbol"],
                        quantity=row["quantity"],
                        entry_price=row["entry_price"],
                        current_price=row["current_price"],
                        unrealized_pnl=row["unrealized_pnl"],
                        realized_pnl=row["realized_pnl"],
                        stop_loss_price=row["stop_loss_price"],
                        opened_at=datetime.fromisoformat(row["opened_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"])
                    )
                    for row in rows
                ]

    async def create_trade(self, trade: Trade) -> Trade:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO trades (
                    va_id, symbol, side, quantity, price, pnl, order_id, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.va_id, trade.symbol, trade.side.value, trade.quantity,
                trade.price, trade.pnl, trade.order_id, trade.executed_at.isoformat()
            ))
            await db.commit()
            trade.id = cursor.lastrowid
            return trade

    async def get_trades(self, va_id: Optional[str] = None, limit: int = 100) -> List[Trade]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if va_id:
                query = "SELECT * FROM trades WHERE va_id = ? ORDER BY executed_at DESC LIMIT ?"
                params = (va_id, limit)
            else:
                query = "SELECT * FROM trades ORDER BY executed_at DESC LIMIT ?"
                params = (limit,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [
                    Trade(
                        id=row["id"],
                        va_id=row["va_id"],
                        symbol=row["symbol"],
                        side=OrderSide(row["side"]),
                        quantity=row["quantity"],
                        price=row["price"],
                        pnl=row["pnl"],
                        order_id=row["order_id"],
                        executed_at=datetime.fromisoformat(row["executed_at"])
                    )
                    for row in rows
                ]

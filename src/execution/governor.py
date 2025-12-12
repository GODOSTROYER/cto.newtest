from datetime import datetime, timedelta
from ..storage import SQLiteManager, VirtualAccount
from ..config import Settings


class Governor:
    def __init__(self, db: SQLiteManager, settings: Settings):
        self.db = db
        self.settings = settings

    async def can_trade(self, va_id: str) -> tuple[bool, str]:
        va = await self.db.get_virtual_account(va_id)
        if not va:
            return False, f"Virtual account {va_id} not found"

        if va.in_cooldown and va.cooldown_until:
            if datetime.utcnow() < va.cooldown_until:
                remaining = (va.cooldown_until - datetime.utcnow()).total_seconds()
                return False, f"In cooldown for {remaining:.0f}s due to consecutive losses"
            else:
                va.in_cooldown = False
                va.cooldown_until = None
                va.consecutive_losses = 0
                await self.db.update_virtual_account(va)

        if va.consecutive_losses >= self.settings.max_loss_cooldown:
            await self._activate_cooldown(va)
            return False, f"Cooldown activated: {self.settings.max_loss_cooldown} consecutive losses"

        return True, "OK"

    async def _activate_cooldown(self, va: VirtualAccount):
        va.in_cooldown = True
        va.cooldown_until = datetime.utcnow() + timedelta(seconds=self.settings.cooldown_duration_seconds)
        await self.db.update_virtual_account(va)

    async def record_trade_result(self, va_id: str, pnl: float):
        va = await self.db.get_virtual_account(va_id)
        if not va:
            return

        va.total_trades += 1
        va.total_pnl += pnl
        va.balance += pnl

        if pnl > 0:
            va.winning_trades += 1
            va.consecutive_losses = 0
            if va.current_drawdown < 0:
                va.current_drawdown = 0
        else:
            va.losing_trades += 1
            va.consecutive_losses += 1
            va.current_drawdown += pnl
            if va.current_drawdown < va.max_drawdown:
                va.max_drawdown = va.current_drawdown

        await self.db.update_virtual_account(va)

    async def check_throttle(self, va_id: str) -> tuple[bool, str]:
        positions = await self.db.get_positions(va_id)
        open_orders = await self.db.get_open_orders(va_id)

        if len(positions) >= self.settings.max_open_positions_per_va:
            return False, f"Max positions ({self.settings.max_open_positions_per_va}) reached"

        return True, "OK"

from typing import Dict, Optional
from ..storage import SQLiteManager


class SignalRouter:
    def __init__(self, db: SQLiteManager):
        self.db = db
        self._va_symbol_map: Dict[str, str] = {}

    async def can_trade_symbol(self, va_id: str, symbol: str) -> tuple[bool, str]:
        current_symbol = self._va_symbol_map.get(va_id)
        
        if current_symbol is None:
            positions = await self.db.get_positions(va_id)
            if positions:
                current_symbol = positions[0].symbol
                self._va_symbol_map[va_id] = current_symbol
        
        if current_symbol is None:
            self._va_symbol_map[va_id] = symbol
            return True, "OK"
        
        if current_symbol == symbol:
            return True, "OK"
        else:
            return False, f"VA already trading {current_symbol}, cannot trade {symbol}"

    async def release_symbol(self, va_id: str):
        if va_id in self._va_symbol_map:
            del self._va_symbol_map[va_id]

    def get_active_symbol(self, va_id: str) -> Optional[str]:
        return self._va_symbol_map.get(va_id)

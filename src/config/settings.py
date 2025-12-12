from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_path: str = Field(default="trading.db", description="Path to SQLite database")
    
    max_loss_cooldown: int = Field(default=3, description="Number of losses before cooldown")
    cooldown_duration_seconds: int = Field(default=300, description="Cooldown duration in seconds")
    
    max_spread_bps: float = Field(default=10.0, description="Max spread in basis points")
    max_slippage_bps: float = Field(default=5.0, description="Max slippage in basis points")
    max_latency_ms: float = Field(default=500.0, description="Max latency in milliseconds")
    
    trading_window_start: str = Field(default="09:30", description="Trading window start time (HH:MM)")
    trading_window_end: str = Field(default="16:00", description="Trading window end time (HH:MM)")
    
    reconcile_interval_seconds: int = Field(default=5, description="Order reconciliation interval")
    
    kill_switch_enabled: bool = Field(default=False, description="Global kill switch")
    
    max_position_size: float = Field(default=10000.0, description="Max position size per VA")
    max_open_positions_per_va: int = Field(default=5, description="Max open positions per VA")
    
    stop_loss_percentage: float = Field(default=2.0, description="Stop loss percentage")


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

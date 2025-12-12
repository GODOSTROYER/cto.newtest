import asyncio
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from ..storage import SQLiteManager
from ..config import Settings


class Dashboard:
    def __init__(self, db: SQLiteManager, settings: Settings):
        self.db = db
        self.settings = settings
        self.console = Console()
        self.running = False

    async def start(self):
        self.running = True
        
        with Live(self._generate_layout(), refresh_per_second=1, console=self.console) as live:
            while self.running:
                live.update(self._generate_layout())
                await asyncio.sleep(1)

    async def stop(self):
        self.running = False

    def _generate_layout(self) -> Layout:
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        
        layout["header"].update(
            Panel(
                f"[bold cyan]Trading Execution Dashboard[/bold cyan] - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                style="bold white on blue"
            )
        )
        
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        
        layout["left"].update(self._create_va_table())
        layout["right"].update(self._create_positions_table())
        
        kill_switch_status = "[red]ENABLED[/red]" if self.settings.kill_switch_enabled else "[green]DISABLED[/green]"
        layout["footer"].update(
            Panel(
                f"Kill Switch: {kill_switch_status} | Reconcile Interval: {self.settings.reconcile_interval_seconds}s | "
                f"Max Spread: {self.settings.max_spread_bps}bps | Max Latency: {self.settings.max_latency_ms}ms",
                style="bold white on black"
            )
        )
        
        return layout

    def _create_va_table(self) -> Table:
        table = Table(title="Virtual Accounts", show_header=True, header_style="bold magenta")
        table.add_column("VA ID", style="cyan")
        table.add_column("Balance", justify="right", style="green")
        table.add_column("PnL", justify="right")
        table.add_column("Trades", justify="right")
        table.add_column("W/L", justify="right")
        table.add_column("Max DD", justify="right", style="red")
        table.add_column("Status")
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return table
            
            vas = loop.run_until_complete(self.db.list_virtual_accounts())
            
            for va in vas:
                win_rate = (va.winning_trades / va.total_trades * 100) if va.total_trades > 0 else 0
                pnl_color = "green" if va.total_pnl >= 0 else "red"
                
                status = "🔴 COOLDOWN" if va.in_cooldown else "🟢 ACTIVE"
                if va.in_cooldown and va.cooldown_until:
                    remaining = (va.cooldown_until - datetime.utcnow()).total_seconds()
                    status = f"🔴 COOLDOWN ({remaining:.0f}s)"
                
                table.add_row(
                    va.va_id,
                    f"${va.balance:,.2f}",
                    f"[{pnl_color}]${va.total_pnl:,.2f}[/{pnl_color}]",
                    str(va.total_trades),
                    f"{va.winning_trades}/{va.losing_trades} ({win_rate:.1f}%)",
                    f"${va.max_drawdown:,.2f}",
                    status
                )
        except Exception as e:
            pass
        
        return table

    def _create_positions_table(self) -> Table:
        table = Table(title="Open Positions", show_header=True, header_style="bold magenta")
        table.add_column("VA ID", style="cyan")
        table.add_column("Symbol", style="yellow")
        table.add_column("Qty", justify="right")
        table.add_column("Entry", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("PnL", justify="right")
        table.add_column("Stop Loss", justify="right", style="red")
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return table
            
            positions = loop.run_until_complete(self.db.get_positions())
            
            for pos in positions:
                pnl = pos.unrealized_pnl + pos.realized_pnl
                pnl_color = "green" if pnl >= 0 else "red"
                qty_color = "green" if pos.quantity > 0 else "red"
                
                table.add_row(
                    pos.va_id,
                    pos.symbol,
                    f"[{qty_color}]{pos.quantity:+.2f}[/{qty_color}]",
                    f"${pos.entry_price:.2f}",
                    f"${pos.current_price:.2f}",
                    f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]",
                    f"${pos.stop_loss_price:.2f}" if pos.stop_loss_price else "N/A"
                )
        except Exception as e:
            pass
        
        return table

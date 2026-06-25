# portfolio_risk.py
import numpy as np


class PortfolioRiskManager:
    def __init__(self, max_open_positions=0, max_drawdown_pct=0.0,
                 cooldown_bars=0, max_sector_exposure=0.0, sector_map=None):
        self.max_open_positions = max_open_positions
        self.max_drawdown_pct = max_drawdown_pct
        self.cooldown_bars = cooldown_bars
        self.max_sector_exposure = max_sector_exposure
        self.sector_map = sector_map or {}

        self._halted = False
        self._halt_bar = -1
        self._stats = {
            'blocked_positions': 0,
            'blocked_drawdown': 0,
            'blocked_sector': 0,
            'drawdown_halts': 0,
        }

    @property
    def stats(self):
        return dict(self._stats)

    def reset_stats(self):
        self._halted = False
        self._halt_bar = -1
        self._stats = {
            'blocked_positions': 0,
            'blocked_drawdown': 0,
            'blocked_sector': 0,
            'drawdown_halts': 0,
        }

    def can_open(self, ticker, current_positions, portfolio_equity,
                 peak_equity, current_bar, position_values=None):
        if not self.enabled:
            return True, ''

        reason = ''

        if self.max_open_positions > 0 and len(current_positions) >= self.max_open_positions:
            self._stats['blocked_positions'] += 1
            reason = f'лимит позиций ({len(current_positions)}/{self.max_open_positions})'

        if not reason and self.max_drawdown_pct > 0:
            dd = (peak_equity - portfolio_equity) / peak_equity * 100 if peak_equity > 0 else 0
            if dd >= self.max_drawdown_pct:
                if not self._halted:
                    self._halted = True
                    self._halt_bar = current_bar
                    self._stats['drawdown_halts'] += 1
            else:
                if self._halted:
                    self._halted = False

            if self._halted:
                bars_in_cooldown = current_bar - self._halt_bar
                if self.cooldown_bars > 0 and bars_in_cooldown >= self.cooldown_bars:
                    self._halted = False
                else:
                    self._stats['blocked_drawdown'] += 1
                    reason = f'стоп-просадка ({dd:.1f}%>={self.max_drawdown_pct}%)'

        if not reason and self.max_sector_exposure > 0 and position_values is not None:
            sector = self.sector_map.get(ticker.upper(), 'Прочее')
            total_capital = portfolio_equity
            if total_capital > 0:
                sector_value = 0.0
                for pos in current_positions:
                    pos_ticker = pos.get('ticker', '')
                    pos_sector = self.sector_map.get(pos_ticker.upper(), 'Прочее')
                    if pos_sector == sector:
                        sector_value += position_values.get(pos_ticker, 0)
                exposure = sector_value / total_capital
                if exposure >= self.max_sector_exposure:
                    self._stats['blocked_sector'] += 1
                    reason = f'секторная концентрация {sector} ({exposure:.0%}>={self.max_sector_exposure:.0%})'

        return reason == '', reason

    @property
    def enabled(self):
        return (self.max_open_positions > 0 or self.max_drawdown_pct > 0
                or self.max_sector_exposure > 0)

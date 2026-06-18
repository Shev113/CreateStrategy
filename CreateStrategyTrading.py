# CreateStrategyTrading.py
# -*- coding: utf-8 -*-
import json
import logging
import os
import threading
from datetime import datetime, timedelta

import pandas as pd
import requests
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox as mb
try:
    import sv_ttk
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False

from backtest.engine import BacktestEngine, export_results as _export_results, candles_to_df
from screening.levels_strength import DEFAULT_LAST_CANDLES, calculate_level_strength, get_best_level_signal
from screening.reporter import generate_report
from screening.scanner import Scanner
from screening.smart_scanner import SmartScanner
from screening.sectors import SectorDB
from strategy.bounce import check_bounce
from strategy.indicators import calc_atr
from strategy.levels import find_strong_zones
from visual import StockAppVisual, ScannerUI, SmartScannerUI, DiaryUI, StrategyGuideUI, _add_copy_menu
from diary.journal import DiaryStorage, DiaryEntry, calc_position_qty, calc_position_volume
from intraday.visual import IntradayUI
from utils import normalize_numeric_params, migrate_ticker_settings, load_favorites, toggle_favorite, sort_tickers_by_favorites

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('CreateStrategyTrading.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Константы
MAX_DATA_FETCH_INTERVAL = timedelta(days=365 * 2)
DEFAULT_START_DATE = "2020-01-01"
DEFAULT_END_DATE = datetime.now().strftime("%Y-%m-%d")
MIN_CANDLES_FOR_BACKTEST = 30
INITIAL_CAPITAL = 1_000_000
DEFAULT_MIN_REPEATS = 5
SESSION_STATE_PATH = os.path.join('results', 'session_state.json')


class StrategyAppState:
    """Хранение состояния приложения"""
    def __init__(self):
        self.stock_data = None
        self.current_step = 0
        self.strong_zones = []
        self.df = None


class CreateStrategyApp:
    """Основное приложение для анализа и backtesting стратегий"""
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.state = StrategyAppState()
        self.app = None
        self.scanner_ui = None
        self.diary_ui = None
        self.sector_db = SectorDB()
        self._last_scan_results = []
        self._last_scan_params = {}
        self._last_smart_results = []
        self._last_smart_params = {}
        self._last_capital = 1_000_000
        self._last_trades = None
        self._last_metrics = None
        self._last_export_stock = None
        self._favorites = load_favorites()
        self.diary_storage = DiaryStorage()
        migrate_ticker_settings(os.path.join('results', 'ticker_settings.json'))
        self.setup_ui()
        self._load_session_state()
        self._start_auto_load_tickers()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self.bind_events()
        self.root.after(1000, self._auto_check_positions)

    def candles_to_df_custom(self, candles_list: list) -> pd.DataFrame | None:
        """Конвертация списка свечей в DataFrame"""
        valid = [c for c in candles_list if c is not None and len(c) > 6]
        if not valid:
            return None
        return pd.DataFrame(
            valid,
            columns=['Open', 'Close', 'High', 'Low', 'Volume', 'Value', 'Begin', 'End'],
            index=pd.to_datetime([c[6] for c in valid], format='mixed')
        )

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> list | str:
        """Получение исторических данных по акции"""
        try:
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{symbol}/candles.json"
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            all_candles = []
            current_start = start_dt

            while current_start < end_dt:
                current_end = min(current_start + MAX_DATA_FETCH_INTERVAL, end_dt)
                params = {
                    "start": 0,
                    "till": current_end.strftime("%Y-%m-%d"),
                    "from": current_start.strftime("%Y-%m-%d"),
                    "interval": 24
                }
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                if "candles" in data and "data" in data["candles"]:
                    all_candles.extend(data["candles"]["data"])
                current_start += MAX_DATA_FETCH_INTERVAL
            return all_candles if all_candles else "Нет данных за указанный период"
        except requests.exceptions.HTTPError as e:
            logging.error(f"Ошибка HTTP: {e}")
            return f"Ошибка HTTP: {e}"
        except Exception as e:
            logging.error(f"Ошибка получения данных: {e}")
            return f"Ошибка получения данных: {e}"

    DARK_TEXT_BG = '#1e1e1e'
    DARK_TEXT_FG = '#d4d4d4'
    LIGHT_TEXT_BG = '#ffffff'
    LIGHT_TEXT_FG = '#000000'

    def setup_ui(self) -> None:
        """Настройка GUI"""
        self.root.title("CreateStrategy — Технический анализ MOEX")
        self.root.geometry("1250x800")

        self._current_theme = 'light'
        if HAS_SV_TTK:
            sv_ttk.set_theme(self._current_theme)

        top_bar = ttk.Frame(self.root)
        top_bar.pack(fill=tk.X, padx=5, pady=(5, 0))
        ttk.Label(top_bar, text="CreateStrategy", font=('', 12, 'bold')).pack(side=tk.LEFT)
        if HAS_SV_TTK:
            self._theme_btn = ttk.Button(top_bar, text='🌙 Тёмная', width=12, command=self._toggle_theme)
            self._theme_btn.pack(side=tk.RIGHT)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=1)

        tab_analysis = ttk.Frame(notebook)
        tab_scanner = ttk.Frame(notebook)
        tab_smart_scanner = ttk.Frame(notebook)
        tab_diary = ttk.Frame(notebook)
        notebook.add(tab_analysis, text='Анализ')
        notebook.add(tab_scanner, text='Сканер')
        notebook.add(tab_smart_scanner, text='Умный сканер')
        notebook.add(tab_diary, text='Дневник сделок')

        tab_guide = ttk.Frame(notebook)
        notebook.add(tab_guide, text='Справочник стратегий')

        tab_intraday = ttk.Frame(notebook)
        notebook.add(tab_intraday, text='Интрадей')

        intraday_notebook = ttk.Notebook(tab_intraday)
        intraday_notebook.pack(fill='both', expand=1)

        tab_intra_backtest = ttk.Frame(intraday_notebook)
        tab_intra_scanner = ttk.Frame(intraday_notebook)
        intraday_notebook.add(tab_intra_backtest, text='Backtest')
        intraday_notebook.add(tab_intra_scanner, text='Умный сканер')

        self.app = StockAppVisual(
            tab_analysis, self.on_select, self.on_export_button,
            self.get_moex_tickers, self.on_backtest,
            on_diary=self.on_add_to_diary_analysis,
            on_show_settings=self.on_show_ticker_settings,
            on_save_results=self._on_save_results,
            on_optimize=self.on_optimize,
            on_portfolio=self.on_portfolio,
            favorites=self._favorites,
            on_toggle_favorite=self._on_toggle_favorite,
            sector_db=self.sector_db
        )

        all_sectors = self.sector_db.get_all_sectors()
        total_tickers = len(self.sector_db.get_tickers(all_sectors))
        self.scanner_ui = ScannerUI(
            tab_scanner, sectors=all_sectors,
            on_scan=self.on_scanner, on_legend=self.on_show_legend,
            on_excel=self.on_export_excel, on_diary=self.on_add_to_diary,
            on_show_settings=self.on_show_ticker_settings,
            total_tickers=total_tickers
        )

        self.smart_scanner_ui = SmartScannerUI(
            tab_smart_scanner, sectors=all_sectors,
            on_scan=self.on_smart_scanner,
            on_excel=self.on_smart_export_excel,
            on_diary=self.on_add_to_diary,
            total_tickers=total_tickers
        )

        self.diary_ui = DiaryUI(
            tab_diary, storage=self.diary_storage,
            on_check_positions=self.on_check_positions,
            on_show_analysis=self.on_show_analysis
        )

        self.guide_ui = StrategyGuideUI(tab_guide)

        from intraday.strategies import SOLABUTO_REGISTRY
        intraday_tickers = self.sector_db.get_tickers(self.sector_db.get_all_sectors())
        self.intraday_ui = IntradayUI(
            tab_intra_backtest,
            on_diary_entry=self._on_intraday_diary_entry,
            fetch_fn=None
        )
        self.intraday_ui.set_tickers(intraday_tickers)

        from intraday.visual import IntradaySmartScannerUI
        self.intraday_smart_ui = IntradaySmartScannerUI(
            tab_intra_scanner,
            on_scan=self._on_intraday_smart_scan,
            on_excel=self._on_intraday_smart_excel,
            on_diary=self._on_intraday_smart_diary,
        )
        self.intraday_smart_ui.set_tickers(intraday_tickers)

    def _on_intraday_diary_entry(self, ticker, signal, params):
        side_map = {'BUY': 'LONG', 'SELL': 'SHORT'}
        entry_price = signal.get('entry_price', 0) or signal.get('level', 0)
        sl_price = signal.get('sl_price', 0)
        tp_price = signal.get('tp_price', 0)
        capital = params.get('capital', 1_000_000)
        risk_per_trade = params.get('risk_per_trade', 0.02)
        qty = calc_position_qty(capital, risk_per_trade, entry_price, sl_price)
        volume = calc_position_volume(capital, risk_per_trade, entry_price, sl_price)
        entry = DiaryEntry(
            date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            ticker=ticker,
            side=side_map.get(signal['action'], signal['action']),
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            volume=volume,
            qty=qty,
            max_hold=params.get('max_hold', 20),
            status='open'
        )
        self.diary_storage.add_entries([entry])
        if self.diary_ui:
            self.diary_ui.refresh()
        mb.showinfo('В дневник', f'{ticker} (H1) добавлен в дневник.')

    def _on_intraday_smart_scan(self) -> None:
        from intraday.smart_scanner import IntradaySmartScanner
        params = self.intraday_smart_ui.get_backtest_params()
        if params is None:
            self.intraday_smart_ui.show_results([])
            return
        date_from = self.intraday_smart_ui.date_from.get()
        date_to = self.intraday_smart_ui.date_to.get()
        tickers = self.intraday_smart_ui.get_scan_tickers()
        if not tickers or not date_from or not date_to:
            self.intraday_smart_ui.show_results([])
            return
        min_trades = 10
        self._last_intra_smart_params = params
        def run():
            try:
                scanner = IntradaySmartScanner()
                results = scanner.scan(
                    tickers=tickers,
                    date_from=date_from,
                    date_to=date_to,
                    base_params=params,
                    min_trades=min_trades,
                    progress_fn=lambda c, t, tk, sn: self.intraday_smart_ui.update_progress(c, t, tk, sn),
                )
                self._last_intra_smart_results = results
                self.root.after(0, lambda: self.intraday_smart_ui.show_results(results))
            except Exception as e:
                self.root.after(0, lambda: self.intraday_smart_ui.status_var.set(f'Ошибка: {str(e)}'))
            finally:
                self.root.after(0, lambda: self.intraday_smart_ui.set_running(False))
        self.intraday_smart_ui.set_running(True)
        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _on_intraday_smart_excel(self) -> None:
        results = getattr(self, '_last_intra_smart_results', [])
        if not results:
            self.intraday_smart_ui.status_var.set('Ошибка: сначала запустите сканер.')
            return
        import os
        os.makedirs('results', exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fpath = f'results/intraday_smart_scanner_{ts}.xlsx'
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            names = {k: v['name'] for k, v in __import__('intraday.strategies', fromlist=['SOLABUTO_REGISTRY']).SOLABUTO_REGISTRY.items()}
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Intraday Smart Scan'
            headers = ['№', 'Тикер', 'Лучшая стратегия', 'Score', 'Доходность',
                       'Sharpe', 'Сделок', 'WinRate', 'Profit Factor', 'Сигнал']
            for ci, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=ci, value=h)
                cell.font = Font(bold=True)
            for ri, r in enumerate(results, 2):
                sid = r.get('best_strategy', '')
                m = r.get('best_metrics', {})
                sig = r.get('best_signal', {})
                ws.cell(row=ri, column=1, value=ri - 1)
                ws.cell(row=ri, column=2, value=r['ticker'])
                ws.cell(row=ri, column=3, value=names.get(sid, sid))
                ws.cell(row=ri, column=4, value=round(r.get('best_score', -1), 2))
                ws.cell(row=ri, column=5, value=round(m.get('total_return', 0), 2))
                ws.cell(row=ri, column=6, value=round(m.get('sharpe', 0), 2))
                ws.cell(row=ri, column=7, value=m.get('total_trades', 0))
                ws.cell(row=ri, column=8, value=round(m.get('win_rate', 0), 1))
                ws.cell(row=ri, column=9, value=round(m.get('profit_factor', 0), 2))
                ws.cell(row=ri, column=10, value=sig.get('action', 'NONE'))
            ws.column_dimensions['A'].width = 5
            ws.column_dimensions['B'].width = 10
            ws.column_dimensions['C'].width = 22
            ws.column_dimensions['D'].width = 8
            ws.column_dimensions['E'].width = 12
            ws.column_dimensions['F'].width = 8
            ws.column_dimensions['G'].width = 8
            ws.column_dimensions['H'].width = 8
            ws.column_dimensions['I'].width = 10
            ws.column_dimensions['J'].width = 8
            wb.save(fpath)
            self.intraday_smart_ui.status_var.set(f'Excel сохранён: {fpath}')
        except ImportError:
            self.intraday_smart_ui.status_var.set('Ошибка: установите openpyxl (pip install openpyxl)')
        except Exception as e:
            self.intraday_smart_ui.status_var.set(f'Ошибка экспорта: {str(e)}')

    def _on_intraday_smart_diary(self) -> None:
        results = getattr(self, '_last_intra_smart_results', [])
        if not results:
            self.intraday_smart_ui.status_var.set('Ошибка: сначала запустите сканер.')
            return
        params = getattr(self, '_last_intra_smart_params', {})
        capital = params.get('capital', 1_000_000)
        risk_per_trade = params.get('risk_per_trade', 0.02)
        max_hold = params.get('max_hold', 20)
        actionable = [r for r in results if r.get('best_signal', {}).get('action') in ('BUY', 'SELL')]
        if not actionable:
            self.intraday_smart_ui.status_var.set('Нет сигналов BUY/SELL для добавления.')
            return
        win = tk.Toplevel(self.root)
        win.title('Добавить в дневник (H1 Smart Scan)')
        win.geometry('750x500')
        win.transient(self.root)
        win.grab_set()
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=10)
        vars_map = {}
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=1)
        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scrollable, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Label(scrollable, text='', font=('', 9, 'bold')).grid(row=0, column=0, sticky='w', padx=2)
        ttk.Label(scrollable, text='Тикер', font=('', 9, 'bold')).grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(scrollable, text='Сигнал', font=('', 9, 'bold')).grid(row=0, column=2, sticky='w', padx=5)
        ttk.Label(scrollable, text='Цена', font=('', 9, 'bold')).grid(row=0, column=3, sticky='w', padx=5)
        ttk.Label(scrollable, text='SL', font=('', 9, 'bold')).grid(row=0, column=4, sticky='w', padx=5)
        ttk.Label(scrollable, text='TP', font=('', 9, 'bold')).grid(row=0, column=5, sticky='w', padx=5)
        ttk.Label(scrollable, text='Объём (₽)', font=('', 9, 'bold')).grid(row=0, column=6, sticky='w', padx=5)
        for idx, r in enumerate(actionable, 1):
            sig = r['best_signal']
            ticker = r['ticker']
            action = sig['action']
            entry_price = sig.get('last_price') or sig.get('level') or 0
            sl_price = sig.get('sl_price', 0)
            tp_price = sig.get('tp_price', 0)
            qty = calc_position_qty(capital, risk_per_trade, entry_price, sl_price)
            volume = calc_position_volume(capital, risk_per_trade, entry_price, sl_price)
            var = tk.BooleanVar(value=False)
            vars_map[ticker] = {
                'var': var, 'ticker': ticker, 'action': action,
                'entry_price': entry_price, 'sl_price': sl_price, 'tp_price': tp_price,
                'qty': qty, 'volume': volume,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            }
            ttk.Checkbutton(scrollable, variable=var).grid(row=idx, column=0, padx=2, pady=1)
            ttk.Label(scrollable, text=ticker).grid(row=idx, column=1, sticky='w', padx=5)
            ttk.Label(scrollable, text=action).grid(row=idx, column=2, sticky='w', padx=5)
            ttk.Label(scrollable, text=f'{entry_price:.2f}').grid(row=idx, column=3, sticky='w', padx=5)
            ttk.Label(scrollable, text=f'{sl_price:.2f}' if sl_price else '-').grid(row=idx, column=4, sticky='w', padx=5)
            ttk.Label(scrollable, text=f'{tp_price:.2f}' if tp_price else '-').grid(row=idx, column=5, sticky='w', padx=5)
            ttk.Label(scrollable, text=f'{volume:,.0f}').grid(row=idx, column=6, sticky='w', padx=5)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        def add_selected():
            entries = []
            for info in vars_map.values():
                if info['var'].get():
                    side_map = {'BUY': 'LONG', 'SELL': 'SHORT'}
                    entries.append(DiaryEntry(
                        date=info['date'], ticker=info['ticker'],
                        side=side_map.get(info['action'], info['action']),
                        entry_price=info['entry_price'], sl_price=info['sl_price'],
                        tp_price=info['tp_price'], volume=info['volume'], qty=info['qty'],
                        max_hold=max_hold, status='open',
                    ))
            if entries:
                self.diary_storage.add_entries(entries)
                if self.diary_ui:
                    self.diary_ui.refresh()
                win.destroy()
                self.intraday_smart_ui.status_var.set(f'Добавлено в дневник: {len(entries)} сделок.')
            else:
                mb.showwarning('Нет выбора', 'Не выбрано ни одной сделки.')
        ttk.Button(btn_frame, text='Добавить выбранные', command=add_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Отмена', command=win.destroy).pack(side=tk.LEFT, padx=5)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', _on_mousewheel)
        win.protocol('WM_DELETE_WINDOW', lambda: (canvas.unbind_all('<MouseWheel>'), win.destroy()))

    def bind_events(self) -> None:
        """Привязка событий"""
        pass

    def _save_session_state(self) -> None:
        import json
        os.makedirs('results', exist_ok=True)
        state = {
            'last_ticker': self.app.get_selected_ticker(),
            'last_capital': self._last_capital,
            'theme': self._current_theme,
        }
        try:
            with open(SESSION_STATE_PATH, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_session_state(self) -> None:
        import json
        if not os.path.exists(SESSION_STATE_PATH):
            return
        try:
            with open(SESSION_STATE_PATH, 'r', encoding='utf-8') as f:
                state = json.load(f)
            if 'last_ticker' in state and state['last_ticker']:
                self.app.stock_combobox.set(state['last_ticker'])
                self.app._load_ticker_settings()
            if 'last_capital' in state:
                self._last_capital = state['last_capital']
            if 'theme' in state and state['theme'] == 'dark':
                self._toggle_theme()
        except Exception:
            pass

    def _toggle_theme(self):
        if not HAS_SV_TTK:
            return
        self._current_theme = 'dark' if self._current_theme == 'light' else 'light'
        sv_ttk.set_theme(self._current_theme)
        self._apply_text_theme()
        if self._theme_btn:
            self._theme_btn.config(text='☀️ Светлая' if self._current_theme == 'dark' else '🌙 Тёмная')

    def _apply_text_theme(self):
        is_dark = self._current_theme == 'dark'
        bg = self.DARK_TEXT_BG if is_dark else self.LIGHT_TEXT_BG
        fg = self.DARK_TEXT_FG if is_dark else self.LIGHT_TEXT_FG
        for w in (self.app.result_text, self.app.backtest_text):
            w.config(bg=bg, fg=fg, insertbackground=fg)
        if hasattr(self.scanner_ui, 'scanner_result_text'):
            self.scanner_ui.scanner_result_text.config(bg=bg, fg=fg, insertbackground=fg)
        if hasattr(self.scanner_ui, '_legend_text_widget'):
            self.scanner_ui._legend_text_widget.config(bg=bg, fg=fg)
        import matplotlib.pyplot as plt
        plt.style.use('dark_background' if is_dark else 'default')

    def _on_sectors_loaded(self, all_tickers, ticker_to_sector, sector_to_tickers):
        if ticker_to_sector is None:
            self.app.set_tickers_loading(False)
            self.app.result_text.insert(tk.END, "Ошибка загрузки эмитентов (MOEX API недоступен)\n")
            return
        old_count = len(self.sector_db.get_all_tickers())
        self.sector_db.apply_dynamic_data(ticker_to_sector, sector_to_tickers)
        sector_map = self.sector_db.get_ticker_to_sector_map()
        self.app.update_ticker_list(all_tickers, sector_map)
        total = len(self.sector_db.get_tickers(self.sector_db.get_all_sectors()))
        self.scanner_ui.update_total_count(total)
        if hasattr(self, 'smart_scanner_ui'):
            self.smart_scanner_ui._total_tickers = total
            self.smart_scanner_ui._total_count_label.config(text=f"Всего эмитентов: {total}")
            self.smart_scanner_ui.status_var.set(f"Готов к сканированию ({total} эмитентов)")
        added = total - old_count
        self.app.result_text.insert(
            tk.END,
            f"Загружено {total} эмитентов (+{added} из MOEX индексов)\n")

    def _start_auto_load_tickers(self):
        self.app.set_tickers_loading(True)
        self.sector_db.load_dynamic_async(on_complete=self._on_sectors_loaded)

    def _on_toggle_favorite(self, ticker):
        from utils import save_favorites
        self._favorites = toggle_favorite(list(self._favorites), ticker)
        save_favorites(self._favorites)
        return self._favorites

    def _on_close(self) -> None:
        try:
            self._save_session_state()
        except Exception:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def get_moex_tickers(self) -> list[str]:
        """Получение списка тикеров MOEX"""
        try:
            url = "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "securities" in data and "data" in data["securities"]:
                return [security[0] for security in data["securities"]["data"]]
            logging.error("Отсутствует securities.data")
            return []
        except Exception as e:
            logging.error(f"Ошибка получения списка акций: {e}")
            return []

    def validate_date(self, date_str: str) -> bool:
        """Проверка формата даты"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def export_data_to_txt(self, data: dict, filename: str) -> bool:
        """Экспорт данных в текстовый файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"Ошибка экспорта данных: {e}")
            return False

    def _process_stock_data(self, stock_data, start_date, end_date):
        """Обработка загруженных данных (вызывается в главном потоке)"""
        if isinstance(stock_data, str):
            self.app.result_text.delete(1.0, tk.END)
            self.app.result_text.insert(tk.END, f"Ошибка: {stock_data}")
            self.app.get_data_button.config(state='normal', text='1. Получить данные')
            return
        if not isinstance(stock_data, list) or len(stock_data) == 0:
            self.app.result_text.delete(1.0, tk.END)
            self.app.result_text.insert(tk.END, "Ошибка: данные не получены")
            self.app.get_data_button.config(state='normal', text='1. Получить данные')
            return

        self.state.stock_data = stock_data
        self.state.df = self.candles_to_df_custom(stock_data)
        self.app.result_text.delete(1.0, tk.END)

        params = self.app.get_backtest_params()
        min_hits = params.get('min_hits', DEFAULT_MIN_REPEATS) if params else DEFAULT_MIN_REPEATS
        if min_hits < 1:
            min_hits = 1

        self.state.strong_zones = []
        if self.state.df is not None and len(stock_data) > 0:
            atr_series = calc_atr(self.state.df, 14)
            avg_atr = atr_series.mean()
            if not pd.isna(avg_atr) and avg_atr > 0:
                self.state.strong_zones = find_strong_zones(
                    stock_data, atr_value=avg_atr, min_hits=min_hits, max_zones=6)
                for price, count in self.state.strong_zones:
                    self.app.result_text.insert(
                        tk.END, f"Зона: {price:.2f}, касаний: {count}\n")
            else:
                self.app.result_text.insert(tk.END, "Недостаточно данных для ATR\n")

        self.state.current_step = 0
        self.app.get_data_button.config(state='normal', text='1. Получить данные')

        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        total_days = (end_dt - start_dt).days
        self.app.result_text.insert(tk.END, f"\nСвечей: {len(stock_data)}, период: ~{total_days} дн.")
        self._save_session_state()
        self.app.update_chart(self.state.df, strong_zones=self.state.strong_zones)

    def on_select(self) -> None:
        """Обработка выбора акции и дат (асинхронная загрузка)"""
        selected_stock = self.app.get_selected_ticker()
        start_date = self.app.start_date_entry.get()
        end_date = self.app.end_date_entry.get()

        if not self.validate_date(start_date):
            self.app.result_text.delete(1.0, tk.END)
            self.app.result_text.insert(tk.END, "Ошибка: неверный формат начальной даты")
            return
        if not self.validate_date(end_date):
            self.app.result_text.delete(1.0, tk.END)
            self.app.result_text.insert(tk.END, "Ошибка: неверный формат конечной даты")
            return

        self.app.get_data_button.config(state='disabled', text='Загрузка...')
        self.app.result_text.delete(1.0, tk.END)
        self.app.result_text.insert(tk.END, "Загрузка данных с MOEX...")

        def fetch_task():
            try:
                data = self.get_stock_data(selected_stock, start_date, end_date)
                self.root.after(0, lambda: self._process_stock_data(
                    data, start_date, end_date))
            except Exception as e:
                self.root.after(0, lambda: self._on_select_error(str(e)))

        t = threading.Thread(target=fetch_task, daemon=True)
        t.start()

    def _on_select_error(self, error_msg):
        self.app.result_text.delete(1.0, tk.END)
        self.app.result_text.insert(tk.END, f"Ошибка: {error_msg}")
        self.app.get_data_button.config(state='normal', text='1. Получить данные')

    def on_export_button(self) -> None:
        """Экспорт данных в текстовый файл"""
        if self.state.stock_data is None:
            print("Ошибка: данные по акции не загружены")
            return
        selected_stock = self.app.get_selected_ticker()
        if isinstance(self.state.stock_data, list):
            filename = f"{selected_stock}_data.txt"
            if self.export_data_to_txt(self.state.stock_data, filename):
                print(f"Data exported to {filename}")
            else:
                print("Failed to export data.")

    def _run_backtest_task(self, params):
        try:
            engine = BacktestEngine(**params)
            trades, metrics = engine.run(self.state.stock_data)
            selected_stock = self.app.get_selected_ticker()
            self._last_trades = trades
            self._last_metrics = metrics
            self._last_export_stock = selected_stock

            signal = None
            stock_data = self.state.stock_data
            if trades and stock_data:
                last_price = float(stock_data[-1][1])
                df = candles_to_df(stock_data)
                if df is not None and len(df) > 0:
                    atr_series = calc_atr(df, params.get('atr_period', 14))
                    if not atr_series.empty and not atr_series.isna().iloc[-1]:
                        atr_value = atr_series.iloc[-1]
                        last_candles = DEFAULT_LAST_CANDLES
                        levels_strength = calculate_level_strength(trades, last_candles=last_candles)
                        if levels_strength and last_price and atr_value:
                            atr_sl_val = params.get('atr_sl', 1.0)
                            atr_tp_val = params.get('atr_tp', 2.0)
                            signal = get_best_level_signal(
                                levels_strength, last_price, atr_value,
                                atr_sl=atr_sl_val, atr_tp=atr_tp_val)
                            if signal and signal['action'] == 'NONE':
                                signal = get_best_level_signal(
                                    levels_strength, last_price, atr_value,
                                    threshold_mult=1.0, atr_sl=atr_sl_val, atr_tp=atr_tp_val)
                            if signal:
                                signal['last_price'] = last_price
                                signal['atr'] = atr_value

            self.root.after(0, lambda e=engine: self._on_backtest_complete(
                trades, metrics, selected_stock, signal, params, engine=e))
        except Exception as e:
            self.root.after(0, lambda: self._on_backtest_error(str(e)))

    def _on_backtest_complete(self, trades, metrics,
                              selected_stock, signal=None, params=None, engine=None):
        self.app.backtest_button.config(state='normal', text='2. Запустить Backtest')
        self.app.display_backtest_results(metrics, params)
        self.app.enable_save_results_button()
        if params and 'capital' in params:
            self._last_capital = params['capital']
        if signal:
            self.app.display_recommendation(signal, params)
            self.app.set_last_analysis(signal, params)
        engine_levels = engine.last_levels if engine else []
        if signal:
            sl_price = signal.get('sl_price')
            tp_price = signal.get('tp_price')
        else:
            sl_price = tp_price = None
        self.app.add_post_backtest_lines(
            engine_levels=engine_levels,
            sl_price=sl_price,
            tp_price=tp_price)

    def _on_backtest_error(self, error_msg):
        self.app.add_backtest_result(f"Ошибка backtest: {error_msg}")
        self.app.backtest_button.config(state='normal', text='2. Запустить Backtest')
        logging.exception("Backtest error")

    def _on_save_results(self):
        if not self._last_trades and not self._last_metrics:
            return
        stock = self._last_export_stock or self.app.get_selected_ticker()
        csv_path, json_path = _export_results(
            self._last_trades or [], self._last_metrics or {}, stock)
        self.app.backtest_text.insert(tk.END, f"\n\nФайлы:\n  {csv_path}\n  {json_path}")

    def on_backtest(self) -> None:
        """Запуск backtesting стратегии (асинхронно)"""
        if self.state.stock_data is None or not isinstance(self.state.stock_data, list):
            self.app.add_backtest_result("Ошибка: сначала загрузите данные (кнопка 1)")
            return
        if len(self.state.stock_data) < MIN_CANDLES_FOR_BACKTEST:
            self.app.add_backtest_result("Ошибка: слишком мало данных (нужно >= 30 свечей)")
            return

        params = self.app.get_backtest_params()
        if params is None:
            self.app.add_backtest_result("Ошибка: проверьте числовые параметры.")
            return

        self.app.backtest_button.config(state='disabled', text='Backtest запущен...')

        t = threading.Thread(
            target=self._run_backtest_task,
            args=(params,),
            daemon=True
        )
        t.start()

    def on_optimize(self) -> None:
        """Запуск оптимизации параметров стратегии (асинхронно)"""
        if self.state.stock_data is None or not isinstance(self.state.stock_data, list):
            self.app.add_backtest_result("Ошибка: сначала загрузите данные (кнопка 1)")
            return
        if len(self.state.stock_data) < MIN_CANDLES_FOR_BACKTEST:
            self.app.add_backtest_result("Ошибка: слишком мало данных (нужно >= 30 свечей)")
            return

        params = self.app.get_backtest_params()
        if params is None:
            self.app.add_backtest_result("Ошибка: проверьте числовые параметры.")
            return

        strategy_id = params.pop('strategy', 'bounce')

        self.app.optimize_button.config(state='disabled', text='Оптимизация...')

        def run():
            try:
                from optimization.grid import optimize
                results, total = optimize(
                    strategy_id,
                    self.state.stock_data,
                    default_params=params,
                    progress_fn=lambda c, t: None
                )
                self.root.after(0, lambda: self._on_optimize_complete(results, total, strategy_id))
            except Exception as e:
                self.root.after(0, lambda: self._on_optimize_error(str(e)))

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _on_optimize_complete(self, results, total, strategy_id):
        self.app.optimize_button.config(state='normal', text='3. Оптимизация параметров')
        from strategy.config import STRATEGY_REGISTRY
        strat_name = STRATEGY_REGISTRY.get(strategy_id, {}).get('name', strategy_id)

        txt = self.app.backtest_text
        txt.delete(1.0, tk.END)
        txt.insert(tk.END, (
            f"========== ОПТИМИЗАЦИЯ: {strat_name} ==========\n"
            f"Проверено комбинаций: {total}\n"
            f"Лучших результатов: {len(results)}\n\n"
        ))

        if results:
            best = results[0]
            txt.insert(tk.END, "── Лучшие параметры ──\n")
            for k, v in best['params'].items():
                txt.insert(tk.END, f"  {k}: {v}\n")
            txt.insert(tk.END, "\n")
            txt.insert(tk.END, (
                f"  Sharpe:       {best['sharpe']:.2f}\n"
                f"  Profit Factor:{best['profit_factor']:.2f}\n"
                f"  Доходность:   {best['total_return']:+.2f}%\n"
                f"  Max Drawdown: -{best['max_drawdown']:.2f}%\n"
                f"  Сделок:       {best['total_trades']}\n"
                f"  Win Rate:     {best['win_rate']:.1f}%\n\n"
            ))
            txt.insert(tk.END, "── Топ-5 комбинаций (нажмите [Применить]) ──\n")
            for rank, r in enumerate(results[:5], 1):
                param_str = ", ".join(f"{k}={v}" for k, v in r['params'].items())
                txt.insert(tk.END, f"  {rank}. ")
                tag_name = f"apply_{rank - 1}"
                txt.insert(tk.END, "[Применить] ", (tag_name,))
                txt.insert(tk.END, (
                    f"Sharpe={r['sharpe']:.2f} PF={r['profit_factor']:.2f} "
                    f"Ret={r['total_return']:+.1f}% | {param_str}\n"
                ))
                txt.tag_config(tag_name, foreground='blue', underline=1)
                txt.tag_bind(tag_name, '<Button-1>',
                             lambda e, idx=rank - 1: self._apply_optimized_params(results[idx]['params']))
                txt.tag_bind(tag_name, '<Enter>',
                             lambda e, tn=tag_name: txt.tag_config(tn, foreground='#0066ff'))
                txt.tag_bind(tag_name, '<Leave>',
                             lambda e, tn=tag_name: txt.tag_config(tn, foreground='blue'))
        else:
            txt.insert(tk.END, "Не найдено комбинаций с достаточным числом сделок (>=5).\n")
        txt.insert(tk.END, "=" * 50)

    def _apply_optimized_params(self, params_dict):
        """Применить параметры из оптимизации к текущим настройкам бумаги."""
        app = self.app
        txt = app.backtest_text

        try:
            app._rebuild_params()
            for key, value in params_dict.items():
                entry = app._param_entries.get(key)
                if entry is None:
                    continue
                if isinstance(entry, ttk.Combobox):
                    try:
                        entry.current(int(value))
                    except (ValueError, TypeError):
                        pass
                else:
                    entry.delete(0, tk.END)
                    entry.insert(0, str(value))

            app._save_current_settings()
            self.root.update_idletasks()

            ticker = app._extract_ticker(app.stock_combobox.get())
            txt.delete(1.0, tk.END)
            txt.insert(tk.END, (
                f"Параметры применены к бумаге {ticker}.\n"
                "Настройки сохранены в ticker_settings.json.\n\n"
                "Применённые параметры:\n"
            ))
            for k, v in params_dict.items():
                txt.insert(tk.END, f"  {k}: {v}\n")
        except Exception as e:
            txt.delete(1.0, tk.END)
            txt.insert(tk.END, f"Ошибка при применении параметров: {e}")
            raise

    def _on_optimize_error(self, error_msg):
        self.app.add_backtest_result(f"Ошибка оптимизации: {error_msg}")
        self.app.optimize_button.config(state='normal', text='3. Оптимизация параметров')

    def on_portfolio(self) -> None:
        """Запуск портфельного бэктеста по нескольким тикерам."""
        raw = self.app.portfolio_entry.get().strip()
        if not raw:
            self.app.add_backtest_result("Ошибка: введите тикеры через запятую или пробел.")
            return

        tickers = [t.strip().upper() for t in raw.replace(',', ' ').split() if t.strip()]
        if not tickers:
            self.app.add_backtest_result("Ошибка: не указаны тикеры.")
            return
        if len(tickers) < 2:
            self.app.add_backtest_result("Ошибка: для портфеля нужно минимум 2 тикера.")
            return

        params = self.app.get_backtest_params()
        if params is None:
            self.app.add_backtest_result("Ошибка: проверьте числовые параметры.")
            return
        strategy_id = params.pop('strategy', 'bounce')

        start_date = self.app.start_date_entry.get()
        end_date = self.app.end_date_entry.get()

        self.app.portfolio_button.config(state='disabled', text='Портфель...')
        txt = self.app.backtest_text
        txt.delete(1.0, tk.END)
        txt.insert(tk.END, f"Загрузка данных для {len(tickers)} тикеров: {', '.join(tickers)}\n")
        self.root.update_idletasks()

        def fetch_and_run():
            try:
                portfolio_data = {}
                errors = []
                for t in tickers:
                    data = self.get_stock_data(t, start_date, end_date)
                    if isinstance(data, str):
                        errors.append(f"{t}: {data}")
                    elif len(data) < MIN_CANDLES_FOR_BACKTEST:
                        errors.append(f"{t}: недостаточно данных ({len(data)} свечей)")
                    else:
                        portfolio_data[t] = data

                if not portfolio_data:
                    self.root.after(0, lambda: self._on_portfolio_error("Нет данных ни по одному тикеру."))
                    return

                from backtest.portfolio import run_portfolio
                result = run_portfolio(portfolio_data, capital=params.get('capital', 1_000_000), **params)

                self.root.after(0, lambda: self._on_portfolio_complete(result, strategy_id, errors))
            except Exception as e:
                self.root.after(0, lambda: self._on_portfolio_error(str(e)))

        t = threading.Thread(target=fetch_and_run, daemon=True)
        t.start()

    def _on_portfolio_complete(self, result, strategy_id, errors):
        self.app.portfolio_button.config(state='normal', text='4. Портфельный бэктест')
        pm = result['portfolio_metrics']
        txt = self.app.backtest_text
        txt.delete(1.0, tk.END)

        from strategy.config import STRATEGY_REGISTRY
        strat_name = STRATEGY_REGISTRY.get(strategy_id, {}).get('name', strategy_id)

        lines = [
            f"========== ПОРТФЕЛЬНЫЙ БЭКТЕСТ ==========",
            f"Стратегия: {strat_name}",
            f"Тикеров: {len(result['ticker_results'])}",
            "",
            f"Начальный капитал: {pm['initial_capital']:,.0f} руб",
            f"Конечный капитал:   {pm['final_capital']:,.0f} руб",
            f"Чистая прибыль:     {pm['net_profit']:+,.0f} руб",
            f"Общая доходность:   {pm['total_return']:+.2f} %",
            "",
            f"Всего сделок:       {pm['total_trades']}",
            f"Win Rate:           {pm['win_rate']:.1f} %",
            f"Profit Factor:      {pm['profit_factor']}",
            f"Max Drawdown:       -{pm['max_drawdown']:.2f} %",
            f"Sharpe Ratio:       {pm['sharpe']}",
            "",
            "── По тикерам ──",
        ]
        for ticker, tr in sorted(result['ticker_results'].items()):
            m = tr['metrics']
            lines.append(
                f"  {ticker}: {m.get('total_return', 0):+.2f}% | "
                f"сделок={m.get('total_trades', 0)} | "
                f"Sharpe={m.get('sharpe', 0)} | "
                f"DD=-{m.get('max_drawdown', 0):.1f}%"
            )

        if errors:
            lines.append("")
            lines.append("── Ошибки ──")
            for e in errors:
                lines.append(f"  {e}")

        lines.append("=" * 50)
        txt.insert(tk.END, '\n'.join(lines))

    def _on_portfolio_error(self, error_msg):
        self.app.add_backtest_result(f"Ошибка портфельного бэктеста: {error_msg}")
        self.app.portfolio_button.config(state='normal', text='4. Портфельный бэктест')

    def on_scanner(self) -> None:
        """Запуск сканера по секторам"""
        selected = self.scanner_ui.get_selected_sectors()
        if not selected:
            self.scanner_ui.show_report("Ошибка: выберите хотя бы один сектор.")
            return

        params = self.scanner_ui.get_backtest_params()
        if params is None:
            self.scanner_ui.show_report("Ошибка: проверьте числовые параметры.")
            return

        date_from = self.scanner_ui.scanner_date_from.get()
        date_to = self.scanner_ui.scanner_date_to.get()
        if not self.validate_date(date_from) or not self.validate_date(date_to):
            self.scanner_ui.show_report("Ошибка: проверьте формат дат (гггг-мм-дд).")
            return

        self._last_scan_params = params

        def run_scan():
            try:
                scanner = Scanner(sector_db=self.sector_db, fetch_fn=self.get_stock_data)
                ticker_settings_path = os.path.join('results', 'ticker_settings.json')
                results = scanner.scan(
                    sectors=selected,
                    date_from=date_from,
                    date_to=date_to,
                    backtest_params=params,
                    ticker_settings_path=ticker_settings_path,
                    progress_fn=lambda c, t, tick, sec: self.scanner_ui.update_progress(c, t, tick, sec)
                )
                self._last_scan_results = results
                n_custom = len(scanner.ticker_overrides_used)
                report = generate_report(results, top_n=5, params=params)
                if n_custom:
                    report += f"\n  Бумаг с индивид. настройками: {n_custom}"
                self.root.after(0, lambda: self.scanner_ui.show_report(report))
            except Exception as e:
                self.root.after(0, lambda: self.scanner_ui.show_report(f"Ошибка: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.scanner_ui.set_running(False))

        self.scanner_ui.set_running(True)
        t = threading.Thread(target=run_scan, daemon=True)
        t.start()

    def on_export_excel(self) -> None:
        """Экспорт результатов сканера в Excel"""
        if not self._last_scan_results:
            self.scanner_ui.show_report("Ошибка: сначала запустите сканер.")
            return
        from screening.reporter import export_to_excel
        os.makedirs('results', exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fpath = f'results/scanner_{ts}.xlsx'
        try:
            export_to_excel(self._last_scan_results, self._last_scan_params, fpath)
            self.scanner_ui.scanner_result_text.insert(tk.END, f"\n\nExcel сохранён: {fpath}")
        except ImportError:
            self.scanner_ui.show_report("Ошибка: установите openpyxl (pip install openpyxl)")
        except Exception as e:
            self.scanner_ui.show_report(f"Ошибка экспорта: {str(e)}")

    def on_smart_scanner(self) -> None:
        """Запуск умного сканера (все стратегии на каждом тикере)"""
        selected = self.smart_scanner_ui.get_selected_sectors()
        if not selected:
            self.smart_scanner_ui.show_results([])
            return

        params = self.smart_scanner_ui.get_backtest_params()
        if params is None:
            self.smart_scanner_ui.show_results([])
            return

        date_from = self.smart_scanner_ui.smart_date_from.get()
        date_to = self.smart_scanner_ui.smart_date_to.get()
        if not self.validate_date(date_from) or not self.validate_date(date_to):
            self.smart_scanner_ui.show_results([])
            return

        min_trades = params.pop('min_trades', 30)
        self._last_smart_params = params

        def run_scan():
            try:
                scanner = SmartScanner(sector_db=self.sector_db, fetch_fn=self.get_stock_data)
                results = scanner.scan(
                    sectors=selected,
                    date_from=date_from,
                    date_to=date_to,
                    base_params=params,
                    min_trades=min_trades,
                    progress_fn=lambda c, t, tick, sid_name: self.smart_scanner_ui.update_progress(c, t, tick, sid_name)
                )
                self._last_smart_results = results
                self.root.after(0, lambda: self.smart_scanner_ui.show_results(results))
            except Exception as e:
                self.root.after(0, lambda: self.smart_scanner_ui.status_var.set(f"Ошибка: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.smart_scanner_ui.set_running(False))

        self.smart_scanner_ui.set_running(True)
        t = threading.Thread(target=run_scan, daemon=True)
        t.start()

    def on_smart_export_excel(self) -> None:
        """Экспорт результатов умного сканера в Excel"""
        if not self._last_smart_results:
            self.smart_scanner_ui.status_var.set("Ошибка: сначала запустите умный сканер.")
            return
        from screening.reporter import export_smart_scan_excel
        os.makedirs('results', exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fpath = f'results/smart_scanner_{ts}.xlsx'
        try:
            export_smart_scan_excel(self._last_smart_results, self._last_smart_params, fpath)
            self.smart_scanner_ui.status_var.set(f"Excel сохранён: {fpath}")
        except ImportError:
            self.smart_scanner_ui.status_var.set("Ошибка: установите openpyxl (pip install openpyxl)")
        except Exception as e:
            self.smart_scanner_ui.status_var.set(f"Ошибка экспорта: {str(e)}")

    def on_add_to_diary(self) -> None:
        """Добавить выбранные сигналы в торговый дневник"""
        results = self._last_scan_results
        if not results:
            self.scanner_ui.show_report("Ошибка: сначала запустите сканер.")
            return

        actionable = [r for r in results if r['signal']['action'] in ('BUY', 'SELL')]
        if not actionable:
            self.scanner_ui.show_report("Нет сигналов BUY/SELL для добавления.")
            return

        params = self._last_scan_params
        capital = params.get('capital', 1_000_000)
        risk_per_trade = params.get('risk_per_trade', 0.02)
        max_hold = params.get('max_hold', 20)

        win = tk.Toplevel(self.root)
        win.title("Добавить в дневник")
        win.geometry("750x500")
        win.transient(self.root)
        win.grab_set()

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=10)

        vars_map = {}

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=1)

        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scrollable, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(scrollable, text='',
                  font=('', 9, 'bold')).grid(row=0, column=0, sticky='w', padx=2)
        ttk.Label(scrollable, text='Тикер', font=('', 9, 'bold')).grid(
            row=0, column=1, sticky='w', padx=5)
        ttk.Label(scrollable, text='Сигнал', font=('', 9, 'bold')).grid(
            row=0, column=2, sticky='w', padx=5)
        ttk.Label(scrollable, text='Цена', font=('', 9, 'bold')).grid(
            row=0, column=3, sticky='w', padx=5)
        ttk.Label(scrollable, text='SL', font=('', 9, 'bold')).grid(
            row=0, column=4, sticky='w', padx=5)
        ttk.Label(scrollable, text='TP', font=('', 9, 'bold')).grid(
            row=0, column=5, sticky='w', padx=5)
        ttk.Label(scrollable, text='Объём (₽)', font=('', 9, 'bold')).grid(
            row=0, column=6, sticky='w', padx=5)

        for idx, r in enumerate(actionable, 1):
            sig = r['signal']
            ticker = r['ticker']
            action = sig['action']
            entry_price = r.get('last_price') or sig['level'] or 0
            sl_price = sig.get('sl_price', 0)
            tp_price = sig.get('tp_price', 0)
            qty = calc_position_qty(capital, risk_per_trade, entry_price, sl_price)
            volume = calc_position_volume(capital, risk_per_trade, entry_price, sl_price)

            var = tk.BooleanVar(value=False)
            vars_map[ticker] = {
                'var': var,
                'ticker': ticker,
                'action': action,
                'entry_price': entry_price,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'qty': qty,
                'volume': volume,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            }

            cb = ttk.Checkbutton(scrollable, variable=var)
            cb.grid(row=idx, column=0, padx=2, pady=1)

            ttk.Label(scrollable, text=ticker).grid(
                row=idx, column=1, sticky='w', padx=5)
            ttk.Label(scrollable, text=action).grid(
                row=idx, column=2, sticky='w', padx=5)
            ttk.Label(scrollable, text=f'{entry_price:.2f}').grid(
                row=idx, column=3, sticky='w', padx=5)
            ttk.Label(scrollable, text=f'{sl_price:.2f}' if sl_price else '-').grid(
                row=idx, column=4, sticky='w', padx=5)
            ttk.Label(scrollable, text=f'{tp_price:.2f}' if tp_price else '-').grid(
                row=idx, column=5, sticky='w', padx=5)
            ttk.Label(scrollable, text=f'{volume:,.0f}').grid(
                row=idx, column=6, sticky='w', padx=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        def add_selected():
            entries = []
            for info in vars_map.values():
                if info['var'].get():
                    side_map = {'BUY': 'LONG', 'SELL': 'SHORT'}
                    entries.append(DiaryEntry(
                        date=info['date'],
                        ticker=info['ticker'],
                        side=side_map.get(info['action'], info['action']),
                        entry_price=info['entry_price'],
                        sl_price=info['sl_price'],
                        tp_price=info['tp_price'],
                        volume=info['volume'],
                        qty=info['qty'],
                        max_hold=max_hold,
                        status='open'
                    ))
            if entries:
                self.diary_storage.add_entries(entries)
                if self.diary_ui:
                    self.diary_ui.refresh()
                win.destroy()
                self.scanner_ui.show_report(
                    f"Добавлено в дневник: {len(entries)} сделок.")
            else:
                from tkinter import messagebox as mb
                mb.showwarning('Нет выбора', 'Не выбрано ни одной сделки.')

        ttk.Button(btn_frame, text='Добавить выбранные',
                   command=add_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Отмена',
                   command=win.destroy).pack(side=tk.LEFT, padx=5)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        canvas.bind_all('<MouseWheel>', _on_mousewheel)
        win.protocol('WM_DELETE_WINDOW', lambda: (
            canvas.unbind_all('<MouseWheel>'), win.destroy()
        ))

    def on_add_to_diary_analysis(self) -> None:
        """Добавить текущий сигнал из вкладки Анализа в дневник"""
        signal = self.app._last_signal
        params = self.app._last_params
        if not signal or signal.get('action') not in ('BUY', 'SELL'):
            mb.showinfo('В дневник', 'Нет активного сигнала BUY/SELL.')
            return
        if not params:
            mb.showinfo('В дневник', 'Нет параметров. Запустите backtest.')
            return

        ticker = self.app.get_selected_ticker()
        if not ticker:
            return

        confirm = mb.askyesno(
            'Подтверждение',
            f'Добавить {ticker} в торговый дневник?\n\n'
            f'Сигнал: {signal["action"]}\n'
            f'Цена входа: {signal.get("last_price", 0):.2f}\n'
            f'SL: {signal.get("sl_price", 0):.2f} | TP: {signal.get("tp_price", 0):.2f}'
        )
        if not confirm:
            return

        capital = params.get('capital', 1_000_000)
        risk_per_trade = params.get('risk_per_trade', 0.02)
        entry_price = signal.get('last_price') or signal.get('level', 0)
        sl_price = signal.get('sl_price', 0)
        tp_price = signal.get('tp_price', 0)
        qty = calc_position_qty(capital, risk_per_trade, entry_price, sl_price)
        volume = calc_position_volume(capital, risk_per_trade, entry_price, sl_price)
        side_map = {'BUY': 'LONG', 'SELL': 'SHORT'}

        entry = DiaryEntry(
            date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            ticker=ticker,
            side=side_map.get(signal['action'], signal['action']),
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            volume=volume,
            qty=qty,
            max_hold=params.get('max_hold', 20),
            status='open'
        )
        self.diary_storage.add_entries([entry])
        if self.diary_ui:
            self.diary_ui.refresh()
        mb.showinfo('В дневник', f'{ticker} добавлен в дневник.')

    def on_show_ticker_settings(self) -> None:
        """Показать индивидуальные настройки для каждой бумаги"""
        path = os.path.join('results', 'ticker_settings.json')
        if not os.path.exists(path):
            mb.showinfo('Индивид. настройки', 'Нет сохранённых настроек.')
            return
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            mb.showinfo('Индивид. настройки', 'Нет сохранённых настроек.')
            return

        from strategy.config import get_strategy_names
        name_map = dict(get_strategy_names())

        win = tk.Toplevel(self.root)
        win.title('Индивидуальные настройки бумаг')
        win.geometry('700x550')

        text_frame = ttk.Frame(win)
        text_frame.pack(fill=tk.BOTH, expand=1, padx=5, pady=(5, 0))

        text = tk.Text(text_frame, wrap=tk.NONE, font=('Consolas', 10))
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll_y = tk.Scrollbar(text_frame, orient='vertical', command=text.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        text.configure(yscrollcommand=scroll_y.set)

        content = []
        for ticker in sorted(data):
            entry = data[ticker]
            sid = entry.get('strategy', '?')
            sname = name_map.get(sid, sid)
            content.append(f' {ticker}  ({sname})')
            for k, v in entry.get('params', {}).items():
                content.append(f'   {k}: {v}')
            content.append('')
        text.insert('1.0', '\n'.join(content))
        text.configure(state='disabled')

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text='Экспорт JSON',
                   command=lambda: self._export_ticker_settings(data, win)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Импорт JSON',
                   command=lambda: self._import_ticker_settings(data, win, name_map)).pack(side=tk.LEFT, padx=2)

    def _export_ticker_settings(self, data, win):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON', '*.json')],
            title='Экспорт настроек бумаг'
        )
        if not path:
            return
        try:
            import json
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            mb.showinfo('Экспорт', f'Настройки сохранены:\n{path}')
        except Exception as e:
            mb.showerror('Ошибка', f'Не удалось экспортировать:\n{e}')

    def _import_ticker_settings(self, current_data, win, name_map):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            defaultextension='.json',
            filetypes=[('JSON', '*.json')],
            title='Импорт настроек бумаг'
        )
        if not path:
            return
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            if not isinstance(imported, dict):
                mb.showerror('Ошибка', 'Неверный формат файла.')
                return
            merged = dict(current_data)
            merged.update(imported)
            settings_path = os.path.join('results', 'ticker_settings.json')
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            mb.showinfo('Импорт',
                        f'Импортировано настроек: {len(imported)} бумаг.\n'
                        'Закройте и откройте окно заново для просмотра.')
        except Exception as e:
            mb.showerror('Ошибка', f'Не удалось импортировать:\n{e}')

    def on_check_positions(self) -> None:
        """Проверить открытые позиции — закрыть по SL/TP"""
        if not self.diary_ui:
            return

        def task():
            try:
                updated = self.diary_storage.check_positions(self.get_stock_data)
                self.root.after(0, lambda: self._on_check_positions_done(updated))
            except Exception as e:
                self.root.after(0, lambda: self.diary_ui.refresh())
                logging.exception('Check positions error')

        self.diary_ui.refresh()
        t = threading.Thread(target=task, daemon=True)
        t.start()

    def _auto_check_positions(self):
        open_entries = self.diary_storage.get_open_entries()
        if not open_entries:
            return

        def task():
            try:
                updated = self.diary_storage.check_positions(self.get_stock_data)
                if updated:
                    self.root.after(0, lambda: self.diary_ui.refresh())
                    self.root.after(0, lambda: mb.showinfo(
                        'Автопроверка',
                        f'Закрыто по SL/TP/TIMEOUT: {updated} сделок.'))
            except Exception:
                logging.exception('Auto check positions error')

        t = threading.Thread(target=task, daemon=True)
        t.start()

    def _on_check_positions_done(self, updated):
        self.diary_ui.refresh()
        import tkinter.messagebox as mb
        if updated:
            mb.showinfo('Проверка позиций',
                        f'Закрыто по SL/TP: {updated} сделок.')
        else:
            mb.showinfo('Проверка позиций',
                        'Открытые позиции без изменений.')

    def on_show_analysis(self) -> None:
        """Показать окно анализа сделок с equity curve"""
        entries = self.diary_storage.load()
        closed = [e for e in entries if e.status == 'closed' and e.pnl is not None]
        if not closed:
            import tkinter.messagebox as mb
            mb.showwarning('Анализ', 'Нет закрытых сделок для анализа.')
            return

        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        win = tk.Toplevel(self.root)
        win.title("Анализ сделок")
        win.geometry("900x600")

        capital = self._last_capital
        equity = [capital]
        dates = [closed[0].date[:10]]
        running = capital

        cumulative_pnl = 0
        wins = 0
        losses = 0

        for e in closed:
            running += (e.pnl or 0)
            equity.append(running)
            dates.append(e.exit_date[:10] if e.exit_date else e.date[:10])
            cumulative_pnl += (e.pnl or 0)
            if (e.pnl or 0) > 0:
                wins += 1
            else:
                losses += 1

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), gridspec_kw={'height_ratios': [3, 1]})

        ax1.plot(dates, equity, 'b-', linewidth=1.5, label='Капитал')
        ax1.fill_between(dates, capital, equity, alpha=0.1, color='blue')
        ax1.axhline(y=capital, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_ylabel('Капитал (₽)')
        ax1.set_title('Кривая капитала')
        ax1.legend()
        ax1.tick_params(axis='x', rotation=45)
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))

        total_pnl = sum(e.pnl for e in closed)
        total_trades = len(closed)
        win_rate = (wins / total_trades * 100) if total_trades else 0

        stats_text = (
            f'Сделок: {total_trades} | '
            f'Win Rate: {win_rate:.1f}% | '
            f'Прибыль: {total_pnl:+,.0f} ₽ | '
            f'Текущий капитал: {running:,.0f} ₽'
        )

        ax2.axis('off')
        ax2.text(0.5, 0.5, stats_text, ha='center', va='center',
                 fontsize=12, fontfamily='monospace',
                 bbox=dict(boxstyle='round,pad=0.8', facecolor='lightgray'))

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)

        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)

    def on_show_legend(self) -> None:
        """Показать окно с легендой сигналов"""
        from screening.reporter import get_legend_text
        legend_win = tk.Toplevel(self.root)
        legend_win.title("Легенда сигналов")
        legend_win.geometry("550x500")
        text_w = tk.Text(legend_win, wrap=tk.WORD, font=('Consolas', 10))
        text_w.pack(fill=tk.BOTH, expand=1, padx=10, pady=10)
        text_w.insert(tk.END, get_legend_text())
        text_w.config(state=tk.DISABLED)
        _add_copy_menu(text_w)


if __name__ == "__main__":
    def main():
        """Точка входа приложения"""
        root = tk.Tk()
        app = CreateStrategyApp(root)
        try:
            root.mainloop()
        except KeyboardInterrupt:
            app._on_close()

    main()

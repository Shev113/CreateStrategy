# visual.py
# -*- coding: utf-8 -*-
import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime

import pandas as pd

from utils import normalize_numeric_params, sort_tickers_by_favorites



def _add_copy_menu(text_widget):
    menu = tk.Menu(text_widget, tearoff=0)
    menu.add_command(label='Копировать', command=lambda: _copy_selection(text_widget))

    def _copy_selection(w):
        try:
            text = w.selection_get()
        except tk.TclError:
            text = w.get('1.0', 'end-1c')
        w.clipboard_clear()
        w.clipboard_append(text)

    def show_menu(event):
        menu.tk_popup(event.x_root, event.y_root)

    text_widget.bind('<Button-3>', show_menu)
    text_widget.bind('<Control-c>', lambda e: _copy_selection(text_widget))
    text_widget.bind('<Control-C>', lambda e: _copy_selection(text_widget))


class StockAppVisual:
    def __init__(self, parent, on_select, on_export_button,
                 get_moex_tickers, on_backtest, on_diary=None,
                 on_show_settings=None, on_save_results=None,
                 on_optimize=None, on_portfolio=None, on_walkforward=None,
                 favorites=None, on_toggle_favorite=None,
                 sector_db=None):
        self.root = parent.winfo_toplevel()
        self._last_signal = None
        self._last_params = None
        self._favorites = favorites or []
        self._on_toggle_favorite = on_toggle_favorite
        self._sector_db = sector_db

        # Разделяем вкладку на левую панель (управление) и правую (график)
        parent.grid_columnconfigure(0, weight=0, minsize=480)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        left_frame = ttk.Frame(parent)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        left_frame.grid_rowconfigure(8, weight=1)

        chart_frame = ttk.Frame(parent)
        chart_frame.grid(row=0, column=1, sticky='nsew')
        self._chart_frame = chart_frame

        self._chart_placeholder = ttk.Label(
            chart_frame, text="Загрузите данные для отображения графика",
            anchor='center', font=('', 11))
        self._chart_placeholder.pack(fill=tk.BOTH, expand=1)

        self._chart_figure = None
        self._chart_canvas = None
        self._chart_toolbar = None
        self._chart_ax = None
        self._chart_lines = []

        # Все дальнейшие виджеты идут в левую панель
        parent = left_frame
        self.parent = parent

        all_tickers = get_moex_tickers()
        sector_map = self._sector_db.get_ticker_to_sector_map() if self._sector_db else {}
        self._all_tickers = sort_tickers_by_favorites(
            self._build_display_list(all_tickers, sector_map), self._favorites)

        label_stock = ttk.Label(parent, text="Тикер:")
        label_stock.grid(row=0, column=0, padx=5, pady=5, sticky='e')
        ticker_frame = ttk.Frame(parent)
        ticker_frame.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        self.stock_combobox = ttk.Combobox(ticker_frame, values=self._all_tickers, width=25)
        self.stock_combobox.pack(side=tk.LEFT)
        if all_tickers:
            self.stock_combobox.set(all_tickers[0] if self._all_tickers else all_tickers[0])

        self._star_btn = ttk.Button(ticker_frame, text='★', width=3,
                                    command=self._toggle_current_favorite)
        self._star_btn.pack(side=tk.LEFT, padx=(4, 0))
        self._ticker_status_var = tk.StringVar()
        self._ticker_status_label = ttk.Label(ticker_frame, textvariable=self._ticker_status_var, foreground='gray')
        self._ticker_status_label.pack(side=tk.LEFT, padx=(8, 0))
        self._update_star_button()
        self.stock_combobox.bind('<<ComboboxSelected>>', lambda e: (self._restore_ticker_list(), self._load_ticker_settings(), self._update_star_button()))

        self._autocomplete_hit = False
        self.stock_combobox.bind('<KeyRelease>', self._on_ticker_keyrelease)

        label_start = ttk.Label(parent, text="Начальная дата (гггг-мм-дд):")
        label_start.grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.start_date_entry = ttk.Entry(parent)
        self.start_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        self.start_date_entry.insert(0, "2015-01-01")

        label_end = ttk.Label(parent, text="Конечная дата (гггг-мм-дд):")
        label_end.grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.end_date_entry = ttk.Entry(parent)
        self.end_date_entry.grid(row=2, column=1, padx=5, pady=5, sticky='w')
        self.end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        parent.grid_rowconfigure(8, weight=1)

        self.result_text = tk.Text(parent, height=6, width=55)
        self.result_text.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        _add_copy_menu(self.result_text)

        # Стратегия
        from strategy.config import get_strategy_names
        self._strategy_names = get_strategy_names()
        self._strategy_id_map = {name: sid for sid, name in self._strategy_names}

        ttk.Label(parent, text="Стратегия:",
                  font=('', 10, 'bold')).grid(row=4, column=0, padx=5, pady=(5, 0), sticky='w')
        self._strategy_combo = ttk.Combobox(parent, state='readonly', width=35)
        display_names = [name for sid, name in self._strategy_names]
        self._strategy_combo['values'] = display_names
        if display_names:
            self._strategy_combo.current(0)
        self._strategy_combo.grid(row=4, column=1, padx=5, pady=(5, 0), sticky='w')
        self._strategy_combo.bind('<<ComboboxSelected>>', lambda e: self._rebuild_params())

        self._params_frame = ttk.Frame(parent)
        self._params_frame.grid(row=5, column=0, columnspan=2, sticky='ew', padx=5, pady=1)

        self._param_entries = {}
        self._rebuild_params()

        # Action buttons in 2 rows
        action_frame = ttk.Frame(parent)
        action_frame.grid(row=6, column=0, columnspan=2, pady=1)

        self.get_data_button = ttk.Button(
            action_frame, text="1. Получить данные", command=on_select)
        self.get_data_button.grid(row=0, column=0, padx=2, pady=1)

        self.backtest_button = ttk.Button(
            action_frame, text="2. Backtest", command=on_backtest)
        self.backtest_button.grid(row=0, column=1, padx=2, pady=1)

        self.optimize_button = ttk.Button(
            action_frame, text="3. Оптимизация", command=lambda: on_optimize() if on_optimize else None)
        self.optimize_button.grid(row=0, column=2, padx=2, pady=1)

        self.portfolio_button = ttk.Button(
            action_frame, text="4. Портфель", command=lambda: on_portfolio() if on_portfolio else None)
        self.portfolio_button.grid(row=1, column=0, padx=2, pady=1)

        self.walkforward_button = ttk.Button(
            action_frame, text="5. Walk-fwd", command=lambda: on_walkforward() if on_walkforward else None)
        self.walkforward_button.grid(row=1, column=1, padx=2, pady=1)

        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)
        action_frame.grid_columnconfigure(2, weight=1)
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)

        # Second btn row: Настройки, В дневник, Индивид., Сохранить
        btn_row = ttk.Frame(parent)
        btn_row.grid(row=7, column=0, columnspan=2, pady=1)

        self.save_settings_btn = ttk.Button(
            btn_row, text="Настройки", width=10,
            command=lambda: self._save_current_settings())
        self.save_settings_btn.pack(side=tk.LEFT, padx=2)

        self.diary_btn = ttk.Button(
            btn_row, text="В дневник", width=9,
            command=lambda: on_diary() if on_diary else None)
        self.diary_btn.pack(side=tk.LEFT, padx=2)
        self.diary_btn.config(state='disabled')

        self._on_show_settings = on_show_settings
        self._settings_btn = ttk.Button(
            btn_row, text="Индивид.", width=9,
            command=lambda: self._show_settings())
        self._settings_btn.pack(side=tk.LEFT, padx=2)

        self._save_results_btn = ttk.Button(
            btn_row, text="Сохранить", width=9,
            command=lambda: on_save_results() if on_save_results else None)
        self._save_results_btn.pack(side=tk.LEFT, padx=2)
        self._save_results_btn.config(state='disabled')

        self.backtest_text = tk.Text(parent, height=8, width=55)
        self.backtest_text.grid(row=8, column=0, columnspan=2, padx=5, pady=5, sticky='nsew')
        _add_copy_menu(self.backtest_text)

    def enable_save_results_button(self):
        self._save_results_btn.config(state='normal')

    def disable_save_results_button(self):
        self._save_results_btn.config(state='disabled')

    def _on_ticker_keyrelease(self, event):
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape'):
            return
        if self._autocomplete_hit:
            self._autocomplete_hit = False
            return
        pattern = self.stock_combobox.get().strip()
        if not pattern:
            self.stock_combobox['values'] = self._all_tickers
            return
        filtered = [t for t in self._all_tickers if pattern.upper() in t]
        if filtered:
            self.stock_combobox['values'] = filtered
            self.stock_combobox.event_generate('<Down>')
            self._autocomplete_hit = True

    def _restore_ticker_list(self):
        self.stock_combobox['values'] = self._all_tickers

    def _is_favorite(self, ticker):
        return ticker in self._favorites

    def _update_star_button(self):
        ticker = self._extract_ticker(self.stock_combobox.get())
        self._star_btn.config(text='★' if self._is_favorite(ticker) else '☆')

    def _toggle_current_favorite(self):
        ticker = self._extract_ticker(self.stock_combobox.get())
        if not ticker or not self._on_toggle_favorite:
            return
        self._favorites = self._on_toggle_favorite(ticker)
        self._all_tickers = sort_tickers_by_favorites(self._all_tickers, self._favorites)
        current = self.stock_combobox.get()
        self.stock_combobox['values'] = self._all_tickers
        if current in self._all_tickers:
            self.stock_combobox.set(current)
        self._update_star_button()

    @staticmethod
    def _build_display_list(tickers, sector_map):
        result = []
        for t in tickers:
            sector = sector_map.get(t, '')
            if not sector:
                sector = 'Прочее'
            result.append(f'[{sector}] {t}')

        def sort_key(display):
            if display.startswith('[') and '] ' in display:
                sector = display.split('] ', 1)[0][1:]
                if sector in ('Прочее', 'Без сектора'):
                    return (1, display)
                return (0, sector + display)
            return (1, display)

        result.sort(key=sort_key)
        return result

    @staticmethod
    def _extract_ticker(display):
        if display.startswith('[') and '] ' in display:
            return display.split('] ', 1)[1]
        return display

    def get_selected_ticker(self):
        return self._extract_ticker(self.stock_combobox.get())

    def update_ticker_list(self, all_tickers, sector_map):
        new_display = sort_tickers_by_favorites(
            self._build_display_list(all_tickers, sector_map), self._favorites)
        self._all_tickers = new_display
        current = self.stock_combobox.get()
        self.stock_combobox['values'] = new_display
        if current in new_display:
            self.stock_combobox.set(current)
        self.set_tickers_loading(False)
        self._ticker_status_var.set(f'Загружено {len(all_tickers)} эмитентов')

    def set_tickers_loading(self, loading):
        if loading:
            self.stock_combobox.config(state='disabled')
            self._star_btn.config(state='disabled')
            self._ticker_status_var.set('Загрузка списка эмитентов...')
        else:
            self.stock_combobox.config(state='normal')
            self._star_btn.config(state='normal')

    def _prepare_df_for_chart(self, df):
        if df is None or df.empty:
            return None
        cols = {'Open', 'High', 'Low', 'Close', 'Volume'}
        if not cols.issubset(set(df.columns)):
            return None
        chart_df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        chart_df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        chart_df.index = pd.to_datetime(df.index)
        return chart_df

    def update_chart(self, df, strong_zones=None, engine_levels=None):
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
        import mplfinance as mpf
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        chart_df = self._prepare_df_for_chart(df)
        if chart_df is None or chart_df.empty:
            return

        for w in self._chart_frame.winfo_children():
            w.destroy()
        if self._chart_figure is not None:
            import matplotlib.pyplot as plt
            plt.close(self._chart_figure)
        self._chart_lines.clear()
        self._chart_figure = None
        self._chart_canvas = None
        self._chart_toolbar = None
        self._chart_ax = None

        n_points = len(chart_df)
        fig, axes = mpf.plot(
            chart_df, type='candle', style='charles',
            volume=True,
            returnfig=True,
            figsize=(8, 6),
            figscale=1.0,
            warn_too_much_data=n_points + 1
        )

        ax = axes[0]
        if strong_zones:
            for price, count in strong_zones:
                ax.axhline(y=price, color='#1565C0', linestyle='-', linewidth=2.0, alpha=0.8)
                ax.annotate(f'зона {price:.2f} ({count})', xy=(0, price),
                            xytext=(5, 0), textcoords='offset points',
                            fontsize=8, color='#1565C0', fontweight='bold',
                            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))

        if engine_levels:
            for price in engine_levels:
                ax.axhline(y=price, color='red', linestyle='--', linewidth=0.8, alpha=0.7)
                ax.annotate(f'ур. {price:.2f}', xy=(0, price),
                            xytext=(5, 0), textcoords='offset points',
                            fontsize=7, color='red',
                            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))

        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='This figure includes Axes that are not compatible')
            try:
                fig.tight_layout()
            except UserWarning:
                pass

        canvas = FigureCanvasTkAgg(fig, master=self._chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)

        toolbar = NavigationToolbar2Tk(canvas, self._chart_frame)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        self._chart_figure = fig
        self._chart_canvas = canvas
        self._chart_toolbar = toolbar
        self._chart_ax = ax

    def add_post_backtest_lines(self, engine_levels=None, sl_price=None, tp_price=None):
        if self._chart_ax is None:
            return
        ax = self._chart_ax
        for line in self._chart_lines:
            try:
                line.remove()
            except Exception:
                pass
        self._chart_lines.clear()

        if engine_levels:
            for price in engine_levels:
                line = ax.axhline(y=price, color='red', linestyle='--', linewidth=0.8, alpha=0.7)
                self._chart_lines.append(line)
                ann = ax.annotate(f'ур. {price:.2f}', xy=(0, price),
                                  xytext=(5, 0), textcoords='offset points',
                                  fontsize=7, color='red',
                                  bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))
                self._chart_lines.append(ann)

        if sl_price is not None:
            line = ax.axhline(y=sl_price, color='orange', linestyle=':', linewidth=1.5, alpha=0.9)
            self._chart_lines.append(line)
            ann = ax.annotate(f'SL {sl_price:.2f}', xy=(0, sl_price),
                              xytext=(5, 0), textcoords='offset points',
                              fontsize=8, color='orange', fontweight='bold',
                              bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))
            self._chart_lines.append(ann)

        if tp_price is not None:
            line = ax.axhline(y=tp_price, color='green', linestyle=':', linewidth=1.5, alpha=0.9)
            self._chart_lines.append(line)
            ann = ax.annotate(f'TP {tp_price:.2f}', xy=(0, tp_price),
                              xytext=(5, 0), textcoords='offset points',
                              fontsize=8, color='green', fontweight='bold',
                              bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))
            self._chart_lines.append(ann)

        if self._chart_canvas:
            self._chart_canvas.draw_idle()
        self._chart_ax = ax

    def clear_chart(self):
        for w in self._chart_frame.winfo_children():
            w.destroy()
        self._chart_placeholder = ttk.Label(
            self._chart_frame, text="Загрузите данные для отображения графика",
            anchor='center', font=('', 11))
        self._chart_placeholder.pack(fill=tk.BOTH, expand=1)
        self._chart_figure = None
        self._chart_canvas = None
        self._chart_toolbar = None
        self._chart_ax = None
        self._chart_lines = []

    def add_backtest_result(self, text):
        self.backtest_text.delete(1.0, tk.END)
        self.backtest_text.insert(tk.END, text)

    def display_backtest_results(self, metrics, params=None):
        lines = [
            "========== РЕЗУЛЬТАТЫ BACKTEST ==========",
            f"Начальный капитал: {metrics['initial_capital']:,.0f} руб",
            f"Конечный капитал:   {metrics['final_capital']:,.0f} руб",
            f"Чистая прибыль:     {metrics['net_profit']:+,.0f} руб",
            f"Общая доходность:   {metrics['total_return']:+.2f} %",
            "",
            f"Всего сделок:       {metrics['total_trades']}",
            f"Win Rate:           {metrics['win_rate']:.1f} %",
            f"Profit Factor:      {metrics['profit_factor']}",
            f"Max Drawdown:       -{metrics['max_drawdown']:.2f} %",
            f"Sharpe Ratio:       {metrics['sharpe']}",
            "",
            f"Средняя прибыль:    {metrics['avg_win']:+.2f} руб" if metrics.get('avg_win') else "",
            f"Средний убыток:     {metrics['avg_loss']:+.2f} руб" if metrics.get('avg_loss') else "",
        ]
        if params:
            capital = params.get('capital', 1_000_000)
            risk = params.get('risk_per_trade', 0.02)
            risk_amount = capital * risk
            lines.append(f"Риск на сделку:     {risk_amount:,.0f} руб")
        lines.append("==========================================")
        self.add_backtest_result('\n'.join(lines))

    def _show_settings(self):
        if self._on_show_settings:
            self._on_show_settings()

    def set_last_analysis(self, signal, params):
        self._last_signal = signal
        self._last_params = params
        if signal and signal.get('action') in ('BUY', 'SELL'):
            self.diary_btn.config(state='normal')
        else:
            self.diary_btn.config(state='disabled')

    def display_recommendation(self, signal, params=None):
        action = signal.get('action', 'NONE')
        if action == 'NONE':
            self.backtest_text.insert(tk.END, '\n\n========== РЕКОМЕНДАЦИЯ ==========\nНет сигнала\n====================================')
            return

        symbols = {'BUY': '⬆', 'SELL': '⬇', 'WAIT': '➡'}
        labels = {'BUY': 'ПОКУПКА', 'SELL': 'ПРОДАЖА', 'WAIT': 'ОЖИДАНИЕ'}
        level = signal.get('level', 0)
        stars = signal.get('strength', {}).get('stars', '')
        last_price = signal.get('last_price', 0)
        atr_val = signal.get('atr', 0)
        dist = signal.get('distance', 0) * atr_val if atr_val else 0
        sl = signal.get('sl_price', 0)
        tp = signal.get('tp_price', 0)

        lines = [
            '',
            '========== РЕКОМЕНДАЦИЯ ==========',
            f'{symbols.get(action, "➡")} {labels.get(action, action)} от {level:.2f}',
            f'Уровень: {level:.2f} {stars}  (дист. {dist:.2f})',
            f'Посл. цена: {last_price:.2f}',
            f'SL: {sl:.2f} | TP: {tp:.2f}',
        ]
        if params and level and sl:
            capital = params.get('capital', 1_000_000)
            risk = params.get('risk_per_trade', 0.02)
            risk_amount = capital * risk
            sl_dist = abs(float(level) - float(sl)) / float(level)
            if sl_dist > 0:
                lines.append(f'Объём позиции: {risk_amount / sl_dist:,.0f} руб')
        lines.append('====================================')
        self.backtest_text.insert(tk.END, '\n'.join(lines))

    def _get_strategy_id(self):
        display = self._strategy_combo.get()
        return self._strategy_id_map.get(display, 'bounce')

    def _rebuild_params(self):
        for w in self._params_frame.winfo_children():
            w.destroy()
        self._param_entries.clear()

        from strategy.config import get_strategy_params
        strategy_id = self._get_strategy_id()
        params_config = get_strategy_params(strategy_id)

        for i, pcfg in enumerate(params_config):
            col = (i % 3) * 2
            row_num = i // 3
            ttk.Label(self._params_frame, text=pcfg['label'] + ':',
                      font=('', 8)).grid(row=row_num, column=col, padx=(0, 1), sticky='w')
            if pcfg['key'] == 'entry_type':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=22, font=('', 8),
                    values=['По рынку (open след. свечи)', 'По цене сигнала (лимитный)'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'trailing_sl':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=14, font=('', 8),
                    values=['Выкл', 'Фикс. отступ', 'По MA'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'partial_tp':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=10, font=('', 8),
                    values=['Выкл', 'Вкл'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'use_mtf_filter':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=10, font=('', 8),
                    values=['Выкл', 'Вкл'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'use_pivot_levels':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=10, font=('', 8),
                    values=['Частотный', 'Pivot'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'vote_method':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=14, font=('', 8),
                    values=['Большинство (>50%)', 'Любой сигнал', 'Консенсус'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'position_sizing':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=14, font=('', 8),
                    values=['Фикс. риск', 'Kelly', 'ATR-зависимый'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            else:
                entry = ttk.Entry(self._params_frame, width=8, font=('', 8))
                entry.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                entry.insert(0, str(pcfg['default']))
                self._param_entries[pcfg['key']] = entry

    def get_backtest_params(self):
        try:
            from strategy.config import get_strategy_params
            strategy_id = self._get_strategy_id()
            params = {'strategy': strategy_id}

            cfg_list = get_strategy_params(strategy_id)
            for key, entry in self._param_entries.items():
                if isinstance(entry, ttk.Combobox):
                    params[key] = entry.current()
                    continue
                raw = entry.get().strip()
                cfg = next((c for c in cfg_list if c['key'] == key), None)
                if cfg and cfg['type'] == int:
                    params[key] = int(raw)
                elif cfg and cfg['type'] == str:
                    params[key] = raw
                else:
                    params[key] = float(raw)

            if 'risk_per_trade' in params:
                params['risk_per_trade'] = params['risk_per_trade'] / 100.0
            if 'commission' in params:
                params['commission'] = params['commission'] / 100.0

            return params
        except (ValueError, TypeError):
            print(f"Ошибка преобразования параметра {key}: {raw}")
            return None

    def _save_current_settings(self):
        ticker = self._extract_ticker(self.stock_combobox.get())
        if not ticker:
            return
        import json
        from strategy.config import get_strategy_params
        data = {}
        if os.path.exists(self._settings_path()):
            with open(self._settings_path(), 'r', encoding='utf-8') as f:
                data = json.load(f)
        strategy_id = self._get_strategy_id()
        data[ticker] = {
            'strategy': strategy_id,
            'params': {}
        }
        cfg_list = get_strategy_params(strategy_id)
        for key, entry in self._param_entries.items():
            if isinstance(entry, ttk.Combobox):
                data[ticker]['params'][key] = entry.current()
                continue
            raw = entry.get().strip()
            cfg = next((c for c in cfg_list if c['key'] == key), None)
            if cfg and cfg['type'] == int:
                data[ticker]['params'][key] = int(raw)
            elif cfg and cfg['type'] == str:
                data[ticker]['params'][key] = raw
            else:
                data[ticker]['params'][key] = float(raw)
        with open(self._settings_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_ticker_settings(self):
        ticker = self._extract_ticker(self.stock_combobox.get())
        if not ticker:
            return
        import json
        if not os.path.exists(self._settings_path()):
            return
        with open(self._settings_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        saved = data.get(ticker)
        if not saved:
            return

        strategy_id = saved.get('strategy', 'bounce')
        display_name = self._strategy_id_map.get(strategy_id)
        if display_name:
            self._strategy_combo.set(display_name)
        self._rebuild_params()

        saved_params = normalize_numeric_params(saved.get('params', {}))
        for key, entry in self._param_entries.items():
            if key in saved_params:
                if isinstance(entry, ttk.Combobox):
                    entry.current(int(saved_params[key]))
                else:
                    entry.delete(0, tk.END)
                    entry.insert(0, str(saved_params[key]))


class ScannerUI:
    def __init__(self, parent, sectors, on_scan, on_legend=None, on_excel=None, on_diary=None,
                 on_show_settings=None, total_tickers=0):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self._on_legend = on_legend
        self._on_excel = on_excel
        self._on_diary = on_diary
        self._on_show_settings = on_show_settings
        self._strategy_id_map = {}
        self._strategy_names = []
        self._total_tickers = total_tickers

        from strategy.config import get_strategy_names
        self._strategy_names = get_strategy_names()
        self._strategy_id_map = {name: sid for sid, name in self._strategy_names}

        row = 0
        ttk.Label(parent, text="Сектора для сканирования:",
                  font=('', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(5, 2))
        row += 1

        self.sector_vars = {}
        sector_frame = ttk.Frame(parent)
        sector_frame.grid(row=row, column=0, columnspan=2, sticky='w', padx=5)
        row += 1

        for i, sector in enumerate(sorted(sectors)):
            var = tk.BooleanVar(value=True)
            self.sector_vars[sector] = var
            cb = ttk.Checkbutton(sector_frame, text=sector, variable=var)
            cb.grid(row=i // 2, column=i % 2, sticky='w', padx=5, pady=1)

        self._total_count_label = ttk.Label(
            parent, text=f"Всего эмитентов: {total_tickers}",
            font=('', 8), foreground='gray')
        self._total_count_label.grid(
            row=row, column=0, columnspan=2, sticky='w', padx=8, pady=(0, 2))
        row += 1

        ttk.Separator(parent, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', pady=3)
        row += 1

        ttk.Label(parent, text="Стратегия:",
                  font=('', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', padx=5, pady=(5, 0))
        row += 1

        self._strategy_combo = ttk.Combobox(parent, state='readonly', width=35)
        display_names = [name for sid, name in self._strategy_names]
        self._strategy_combo['values'] = display_names
        if display_names:
            self._strategy_combo.current(0)
        self._strategy_combo.grid(row=row, column=0, columnspan=2, sticky='w', padx=5, pady=1)
        self._strategy_combo.bind('<<ComboboxSelected>>', lambda e: self._rebuild_params())
        row += 1

        self._params_frame = ttk.Frame(parent)
        self._params_frame.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        row += 1

        self._param_entries = {}
        self._rebuild_params()

        date_frame = ttk.Frame(parent)
        date_frame.grid(row=row, column=0, columnspan=2, pady=2)
        row += 1

        ttk.Label(date_frame, text="От:").pack(side=tk.LEFT, padx=2)
        self.scanner_date_from = ttk.Entry(date_frame, width=12)
        self.scanner_date_from.pack(side=tk.LEFT, padx=2)
        self.scanner_date_from.insert(0, "2015-01-01")

        ttk.Label(date_frame, text="До:").pack(side=tk.LEFT, padx=2)
        self.scanner_date_to = ttk.Entry(date_frame, width=12)
        self.scanner_date_to.pack(side=tk.LEFT, padx=2)
        self.scanner_date_to.insert(0, datetime.now().strftime("%Y-%m-%d"))

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        self.scan_button = ttk.Button(
            btn_frame, text="Запустить сканер", command=on_scan)
        self.scan_button.pack(side=tk.LEFT, padx=5)

        self.legend_button = ttk.Button(
            btn_frame, text="Скрыть легенду",
            command=lambda: self._toggle_legend())
        self.legend_button.pack(side=tk.LEFT, padx=5)

        self.export_excel_button = ttk.Button(
            btn_frame, text="Экспорт в Excel",
            command=lambda: self._request_excel())
        self.export_excel_button.pack(side=tk.LEFT, padx=5)
        self.export_excel_button.config(state='disabled')

        self.diary_button = ttk.Button(
            btn_frame, text="В дневник",
            command=lambda: self._request_diary())
        self.diary_button.pack(side=tk.LEFT, padx=5)
        self.diary_button.config(state='disabled')

        self.settings_button = ttk.Button(
            btn_frame, text="Индивид. настройки",
            command=lambda: self._request_show_settings())
        self.settings_button.pack(side=tk.LEFT, padx=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            parent, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=2)
        row += 1

        self.status_var = tk.StringVar(value=f"Готов к сканированию ({total_tickers} эмитентов)" if total_tickers else "Готов к сканированию")
        self.status_label = ttk.Label(parent, textvariable=self.status_var, foreground='gray')
        self.status_label.grid(row=row, column=0, columnspan=2, pady=2)
        row += 1

        ttk.Separator(parent, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', pady=3)
        row += 1

        bottom_frame = ttk.Frame(parent)
        bottom_frame.grid(row=row, column=0, columnspan=2, sticky='nsew', padx=5, pady=5)
        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        bottom_frame.grid_columnconfigure(0, weight=2)
        bottom_frame.grid_columnconfigure(1, weight=1)
        bottom_frame.grid_rowconfigure(0, weight=1)

        left_inner = ttk.Frame(bottom_frame)
        left_inner.grid(row=0, column=0, sticky='nsew')
        left_inner.grid_rowconfigure(0, weight=1)
        left_inner.grid_columnconfigure(0, weight=1)

        self.scanner_result_text = tk.Text(left_inner, height=22, width=75, wrap=tk.WORD)
        self.scanner_result_text.grid(row=0, column=0, sticky='nsew')
        _add_copy_menu(self.scanner_result_text)

        self._legend_frame = ttk.Frame(bottom_frame)
        self._legend_frame.grid(row=0, column=1, sticky='nsew')
        self._legend_frame.grid_rowconfigure(1, weight=1)
        self._legend_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(self._legend_frame, text="Легенда сигналов",
                  font=('', 9, 'bold')).grid(row=0, column=0, pady=(0, 2))
        self._legend_text_widget = tk.Text(self._legend_frame, height=22, width=42,
                                           wrap=tk.WORD, font=('Consolas', 9))
        self._legend_text_widget.grid(row=1, column=0, sticky='nsew')
        self._legend_text_widget.insert(tk.END, self._get_legend_text())
        self._legend_text_widget.config(state=tk.DISABLED)
        _add_copy_menu(self._legend_text_widget)

    def _get_legend_text(self):
        try:
            from screening.reporter import get_legend_text
            return get_legend_text()
        except ImportError:
            return "Легенда недоступна."

    def _get_strategy_id(self):
        display = self._strategy_combo.get()
        return self._strategy_id_map.get(display, 'bounce')

    def _rebuild_params(self):
        for w in self._params_frame.winfo_children():
            w.destroy()
        self._param_entries.clear()

        from strategy.config import get_strategy_params
        strategy_id = self._get_strategy_id()
        params_config = get_strategy_params(strategy_id)

        for i, pcfg in enumerate(params_config):
            col = (i % 3) * 2
            row_num = i // 3
            ttk.Label(self._params_frame, text=pcfg['label'] + ':',
                      font=('', 8)).grid(row=row_num, column=col, padx=(0, 1), sticky='w')
            if pcfg['key'] == 'entry_type':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=22, font=('', 8),
                    values=['По рынку (open след. свечи)', 'По цене сигнала (лимитный)'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'trailing_sl':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=14, font=('', 8),
                    values=['Выкл', 'Фикс. отступ', 'По MA'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'partial_tp':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=10, font=('', 8),
                    values=['Выкл', 'Вкл'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'use_mtf_filter':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=10, font=('', 8),
                    values=['Выкл', 'Вкл'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'use_pivot_levels':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=10, font=('', 8),
                    values=['Частотный', 'Pivot'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'vote_method':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=14, font=('', 8),
                    values=['Большинство (>50%)', 'Любой сигнал', 'Консенсус'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            elif pcfg['key'] == 'position_sizing':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=14, font=('', 8),
                    values=['Фикс. риск', 'Kelly', 'ATR-зависимый'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
            else:
                entry = ttk.Entry(self._params_frame, width=8, font=('', 8))
                entry.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                entry.insert(0, str(pcfg['default']))
                self._param_entries[pcfg['key']] = entry

    def _toggle_legend(self):
        if self._legend_frame.winfo_viewable():
            self._legend_frame.grid_remove()
            self.legend_button.config(text="Показать легенду")
        else:
            self._legend_frame.grid()
            self.legend_button.config(text="Скрыть легенду")

    def _request_legend(self):
        if self._on_legend:
            self._on_legend()

    def _request_excel(self):
        if self._on_excel:
            self._on_excel()

    def _request_diary(self):
        if self._on_diary:
            self._on_diary()

    def _request_show_settings(self):
        if self._on_show_settings:
            self._on_show_settings()

    def get_selected_sectors(self):
        return [s for s, v in self.sector_vars.items() if v.get()]

    def get_backtest_params(self):
        try:
            from strategy.config import get_strategy_params
            strategy_id = self._get_strategy_id()
            params = {'strategy': strategy_id}

            cfg_list = get_strategy_params(strategy_id)
            for key, entry in self._param_entries.items():
                if isinstance(entry, ttk.Combobox):
                    params[key] = entry.current()
                    continue
                raw = entry.get().strip()
                cfg = next((c for c in cfg_list if c['key'] == key), None)
                if cfg and cfg['type'] == int:
                    params[key] = int(raw)
                elif cfg and cfg['type'] == str:
                    params[key] = raw
                else:
                    params[key] = float(raw)

            if 'risk_per_trade' in params:
                params['risk_per_trade'] = params['risk_per_trade'] / 100.0
            if 'commission' in params:
                params['commission'] = params['commission'] / 100.0

            return params
        except (ValueError, TypeError):
            return None

    def show_report(self, report_text):
        self.scanner_result_text.delete(1.0, tk.END)
        self.scanner_result_text.insert(tk.END, report_text)

    def update_progress(self, current, total, ticker, sector):
        pct = (current / max(total, 1)) * 100
        self.progress_var.set(pct)
        self.status_var.set(f"Сканирование: {current}/{total} — {ticker} ({sector})")
        self.parent.update_idletasks()

    def set_running(self, running):
        if running:
            self.scan_button.config(state='disabled', text='Сканирование...')
            self.progress_var.set(0)
            self.status_var.set('Запуск...')
        else:
            self.scan_button.config(state='normal', text='Запустить сканер')
            self.export_excel_button.config(state='normal')
            self.diary_button.config(state='normal')
            self.status_var.set(f'Завершено ({self._total_tickers} эмитентов)')

    def update_total_count(self, total):
        self._total_tickers = total
        self._total_count_label.config(text=f"Всего эмитентов: {total}")
        self.status_var.set(f"Готов к сканированию ({total} эмитентов)")


class SmartScannerUI:
    COLUMNS = ('rank', 'ticker', 'sector', 'best_strategy', 'total_return', 'sharpe', 'trades', 'signal_action')
    HEADERS = {
        'rank': '№', 'ticker': 'Тикер', 'sector': 'Сектор',
        'best_strategy': 'Лучшая стратегия',
        'total_return': 'Доходность',
        'sharpe': 'Sharpe',
        'trades': 'Сделок',
        'signal_action': 'Сигнал',
    }
    WIDTHS = {
        'rank': 35, 'ticker': 70, 'sector': 170,
        'best_strategy': 140,
        'total_return': 90,
        'sharpe': 70,
        'trades': 65,
        'signal_action': 90,
    }

    def __init__(self, parent, sectors, on_scan=None, on_excel=None, on_diary=None, total_tickers=0):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self._on_scan = on_scan
        self._on_excel = on_excel
        self._on_diary = on_diary
        self._strategy_id_map = {}
        self._total_tickers = total_tickers

        from strategy.config import get_strategy_names
        self._strategy_names = get_strategy_names()
        self._strategy_id_map = {name: sid for sid, name in self._strategy_names}

        self._all_results = []

        row = 0
        ttk.Label(parent, text="Сектора для сканирования:",
                  font=('', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(5, 2))
        row += 1

        self.sector_vars = {}
        sector_frame = ttk.Frame(parent)
        sector_frame.grid(row=row, column=0, columnspan=2, sticky='w', padx=5)
        row += 1

        for i, sector in enumerate(sorted(sectors)):
            var = tk.BooleanVar(value=True)
            self.sector_vars[sector] = var
            cb = ttk.Checkbutton(sector_frame, text=sector, variable=var)
            cb.grid(row=i // 2, column=i % 2, sticky='w', padx=5, pady=1)

        self._total_count_label = ttk.Label(
            parent, text=f"Всего эмитентов: {total_tickers}",
            font=('', 8), foreground='gray')
        self._total_count_label.grid(
            row=row, column=0, columnspan=2, sticky='w', padx=8, pady=(0, 2))
        row += 1

        ttk.Separator(parent, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', pady=3)
        row += 1

        ttk.Label(parent, text="Параметры (единые для всех стратегий):",
                  font=('', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', padx=5, pady=(5, 0))
        row += 1

        param_frame = ttk.Frame(parent)
        param_frame.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        row += 1

        self._param_entries = {}
        base_params_config = [
            {'key': 'capital', 'label': 'Капитал', 'default': '1000000', 'width': 10},
            {'key': 'risk_per_trade', 'label': 'Риск%', 'default': '2.0', 'width': 6},
            {'key': 'atr_sl', 'label': 'ATR SL', 'default': '1.0', 'width': 6},
            {'key': 'atr_tp', 'label': 'ATR TP', 'default': '2.0', 'width': 6},
            {'key': 'min_hits', 'label': 'Мин.повт.', 'default': '5', 'width': 6},
            {'key': 'max_hold', 'label': 'Макс.св.', 'default': '20', 'width': 6},
            {'key': 'commission', 'label': 'Комис.%', 'default': '0.05', 'width': 6},
            {'key': 'min_trades', 'label': 'Мин.сд.', 'default': '30', 'width': 6},
        ]
        for i, pcfg in enumerate(base_params_config):
            lbl = ttk.Label(param_frame, text=pcfg['label'] + ':', font=('', 8))
            lbl.grid(row=0, column=i * 2, padx=(0, 1), sticky='w')
            ent = ttk.Entry(param_frame, width=pcfg['width'], font=('', 8))
            ent.grid(row=0, column=i * 2 + 1, padx=(0, 4), sticky='w')
            ent.insert(0, pcfg['default'])
            self._param_entries[pcfg['key']] = ent

        ttk.Label(parent, text="Тип входа:").grid(
            row=row, column=0, sticky='w', padx=5)
        self._entry_type_combo = ttk.Combobox(
            parent, state='readonly', width=28, font=('', 8),
            values=['По рынку (open след. свечи)', 'По цене сигнала (лимитный)'])
        self._entry_type_combo.current(0)
        self._entry_type_combo.grid(row=row, column=1, sticky='w', padx=5)
        row += 1

        n_strategies = len(self._strategy_names)
        ttk.Label(parent, text=f"Внимание: тестируются {n_strategies} стратегий для каждого тикера",
                  font=('', 8, 'italic'), foreground='gray').grid(
            row=row, column=0, columnspan=2, sticky='w', padx=5, pady=(0, 2))
        row += 1

        date_frame = ttk.Frame(parent)
        date_frame.grid(row=row, column=0, columnspan=2, pady=2)
        row += 1

        ttk.Label(date_frame, text="От:").pack(side=tk.LEFT, padx=2)
        self.smart_date_from = ttk.Entry(date_frame, width=12)
        self.smart_date_from.pack(side=tk.LEFT, padx=2)
        self.smart_date_from.insert(0, "2015-01-01")

        ttk.Label(date_frame, text="До:").pack(side=tk.LEFT, padx=2)
        self.smart_date_to = ttk.Entry(date_frame, width=12)
        self.smart_date_to.pack(side=tk.LEFT, padx=2)
        self.smart_date_to.insert(0, datetime.now().strftime("%Y-%m-%d"))

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        self.scan_button = ttk.Button(
            btn_frame, text="Запустить умный сканер", command=self._request_scan)
        self.scan_button.pack(side=tk.LEFT, padx=5)

        self.export_excel_button = ttk.Button(
            btn_frame, text="Экспорт в Excel",
            command=self._request_excel)
        self.export_excel_button.pack(side=tk.LEFT, padx=5)
        self.export_excel_button.config(state='disabled')

        self.diary_button = ttk.Button(
            btn_frame, text="В дневник",
            command=self._request_diary)
        self.diary_button.pack(side=tk.LEFT, padx=5)
        self.diary_button.config(state='disabled')

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            parent, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=2)
        row += 1

        self.status_var = tk.StringVar(value="Готов к сканированию" if not total_tickers else f"Готов к сканированию ({total_tickers} эмитентов)")
        self.status_label = ttk.Label(parent, textvariable=self.status_var, foreground='gray')
        self.status_label.grid(row=row, column=0, columnspan=2, pady=2)
        row += 1

        ttk.Separator(parent, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', pady=3)
        row += 1

        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=row, column=0, columnspan=2, sticky='nsew', padx=5, pady=5)
        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame, columns=self.COLUMNS, show='headings',
            height=22, selectmode='browse'
        )
        for col in self.COLUMNS:
            self.tree.heading(col, text=self.HEADERS[col])
            self.tree.column(col, width=self.WIDTHS[col], anchor='center')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        scroll_y = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<Double-1>', self._on_double_click)

    def _request_scan(self):
        if self._on_scan:
            self._on_scan()

    def _request_excel(self):
        if self._on_excel:
            self._on_excel()

    def _request_diary(self):
        if self._on_diary:
            self._on_diary()

    def get_backtest_params(self):
        try:
            params = {}
            for key, entry in self._param_entries.items():
                raw = entry.get().strip()
                if key == 'min_trades':
                    params[key] = int(raw)
                elif key in ('min_hits', 'max_hold'):
                    params[key] = int(raw)
                else:
                    params[key] = float(raw)
            params['entry_type'] = self._entry_type_combo.current()

            if 'risk_per_trade' in params:
                params['risk_per_trade'] = params['risk_per_trade'] / 100.0
            if 'commission' in params:
                params['commission'] = params['commission'] / 100.0

            return params
        except (ValueError, TypeError):
            return None

    def get_selected_sectors(self):
        return [s for s, v in self.sector_vars.items() if v.get()]

    def set_running(self, running):
        if running:
            self.scan_button.config(state='disabled', text='Сканирование...')
            self.progress_var.set(0)
            self.status_var.set('Запуск...')
        else:
            self.scan_button.config(state='normal', text='Запустить умный сканер')
            self.export_excel_button.config(state='normal')
            self.status_var.set('Завершено')

    def update_progress(self, current, total, ticker, strategy_name):
        pct = (current / max(total, 1)) * 100
        self.progress_var.set(pct)
        self.status_var.set(f"{ticker} — тестирование {strategy_name} ({current}/{total})")
        self.parent.update_idletasks()

    def show_results(self, results):
        self._all_results = results
        for item in self.tree.get_children():
            self.tree.delete(item)

        strategy_reverse = {sid: name for sid, name in self._strategy_names}

        for rank, r in enumerate(results, 1):
            best_sid = r.get('best_strategy')
            best_name = strategy_reverse.get(best_sid, best_sid or '—')
            metrics = r.get('best_metrics', {})
            sig = r.get('best_signal', {})
            action = sig.get('action', 'NONE')
            action_short = {'BUY': '⬆', 'SELL': '⬇', 'WAIT': '➡', 'NONE': '—'}.get(action, action)
            ret = metrics.get('total_return', 0)
            sh = metrics.get('sharpe', 0)
            trades = metrics.get('total_trades', 0)

            if not best_sid:
                best_name = '—'

            ret_str = f"{ret:+.1f}%" if isinstance(ret, (int, float)) else "—"
            sh_str = f"{sh:.2f}" if isinstance(sh, (int, float)) else "—"
            trades_str = str(trades) if trades else "—"

            values = (rank, r['ticker'], r['sector'], best_name, ret_str, sh_str, trades_str, action_short)
            tags = ()
            if isinstance(ret, (int, float)):
                tags = ('positive',) if ret > 0 else ('negative',)
            self.tree.insert('', 'end', values=values, tags=tags)

        self.tree.tag_configure('positive', foreground='green')
        self.tree.tag_configure('negative', foreground='red')

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if idx < 0 or idx >= len(self._all_results):
            return
        result = self._all_results[idx]
        self._show_detail_window(result)

    def _show_detail_window(self, result):
        from strategy.config import get_strategy_names
        strategy_reverse = {sid: name for sid, name in get_strategy_names()}

        win = tk.Toplevel(self.parent)
        win.title(f"{result['ticker']} — все стратегии")
        win.geometry("700x400")
        win.transient(self.parent)
        win.grab_set()

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=10)

        text = tk.Text(frame, wrap=tk.WORD, font=('Consolas', 10))
        text.pack(fill=tk.BOTH, expand=1)

        lines = [
            f"Тикер: {result['ticker']}",
            f"Сектор: {result['sector']}",
            "",
            "────── Результаты по всем стратегиям ──────",
            "",
        ]
        strategies = result.get('strategies', {})
        for sid, sdata in strategies.items():
            name = strategy_reverse.get(sid, sid)
            metrics = sdata.get('metrics', {})
            score = sdata.get('score', -1)
            sig = sdata.get('signal', {})
            action = sig.get('action', 'NONE')

            ret = metrics.get('total_return', 0)
            sh = metrics.get('sharpe', 0)
            tr = metrics.get('total_trades', 0)
            wr = metrics.get('win_rate', 0)
            pf = metrics.get('profit_factor', 0)

            ret_s = f"{ret:+.1f}%" if isinstance(ret, (int, float)) else "—"
            sh_s = f"{sh:.2f}" if isinstance(sh, (int, float)) else "—"

            star = '★ ' if sid == result.get('best_strategy') else '  '
            lines.append(
                f"{star}{name:<20s} Score:{score:>5.2f}  "
                f"Ret:{ret_s:>7s}  Sharpe:{sh_s:>5s}  "
                f"Сд:{tr:>3d}  WR:{wr:.0f}%  PF:{pf:.1f}  "
                f"Сигнал:{action}"
            )

        if not strategies:
            lines.append("  Нет данных.")

        text.insert(tk.END, '\n'.join(lines))
        text.config(state=tk.DISABLED)
        _add_copy_menu(text)


class DiaryUI:
    COLUMNS = ('date', 'ticker', 'side', 'entry_price', 'sl_price',
               'tp_price', 'volume', 'qty', 'max_hold', 'status', 'exit_price',
               'exit_reason', 'pnl')

    HEADERS = {
        'date': 'Дата', 'ticker': 'Тикер', 'side': 'Напр.',
        'entry_price': 'Цена входа', 'sl_price': 'SL', 'tp_price': 'TP',
        'volume': 'Объём (₽)', 'qty': 'Кол-во', 'max_hold': 'Макс.дней',
        'status': 'Статус',
        'exit_price': 'Цена выхода', 'exit_reason': 'Причина', 'pnl': 'P&L'
    }

    WIDTHS = {
        'date': 130, 'ticker': 65, 'side': 55, 'entry_price': 80,
        'sl_price': 70, 'tp_price': 70, 'volume': 90, 'qty': 70,
        'max_hold': 70,
        'status': 60, 'exit_price': 80, 'exit_reason': 70, 'pnl': 70
    }

    def __init__(self, parent, storage, on_close_entry=None,
                 on_check_positions=None, on_show_analysis=None):
        self.parent = parent
        self.storage = storage
        self._on_close_entry = on_close_entry
        self._on_check_positions = on_check_positions
        self._on_show_analysis = on_show_analysis

        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        tree_frame = ttk.Frame(top_frame)
        tree_frame.pack(fill=tk.BOTH, expand=1)

        self.tree = ttk.Treeview(
            tree_frame, columns=self.COLUMNS, show='headings',
            height=20, selectmode='browse'
        )

        for col in self.COLUMNS:
            self.tree.heading(col, text=self.HEADERS[col])
            self.tree.column(col, width=self.WIDTHS[col], anchor='center')

        scroll_y = ttk.Scrollbar(tree_frame, orient='vertical',
                                 command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(btn_frame, text='Проверить позиции',
                   command=self._check_positions).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Анализ сделок',
                   command=self._show_analysis).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Закрыть сделку',
                   command=self._close_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Экспорт CSV',
                   command=self._export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Экспорт JSON',
                   command=self._export_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Импорт JSON',
                   command=self._import_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Обновить',
                   command=self.refresh).pack(side=tk.LEFT, padx=2)

        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        entries = self.storage.load()
        for e in entries:
            values = (
                e.date, e.ticker, e.side, e.entry_price,
                e.sl_price, e.tp_price, e.volume, e.qty,
                e.max_hold,
                e.status, e.exit_price_display, e.exit_reason or '', e.pnl_text
            )
            tags = ()
            if e.is_open:
                tags = ('open',)
            elif e.pnl is not None and e.pnl > 0:
                tags = ('win',)
            elif e.pnl is not None and e.pnl <= 0:
                tags = ('loss',)
            item = self.tree.insert('', 'end', values=values, tags=tags)

        self.tree.tag_configure('win', foreground='green')
        self.tree.tag_configure('loss', foreground='red')
        self.tree.tag_configure('open', foreground='blue')

    def _check_positions(self):
        if self._on_check_positions:
            self._on_check_positions()

    def _show_analysis(self):
        if self._on_show_analysis:
            self._on_show_analysis()

    def _close_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self.storage.close_entry(idx)
        self.refresh()
        if self._on_close_entry:
            self._on_close_entry(idx)

    def _export_csv(self):
        import csv
        from datetime import datetime
        os.makedirs('results', exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = f'results/diary_{ts}.csv'
        entries = self.storage.load()
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(list(self.HEADERS.values()))
            for e in entries:
                writer.writerow([
                    e.date, e.ticker, e.side, e.entry_price,
                    e.sl_price, e.tp_price, e.volume, e.qty, e.status,
                    e.exit_price_display, e.exit_reason or '', e.pnl_text
                ])
        import tkinter.messagebox as mb
        mb.showinfo('Экспорт', f'Дневник сохранён:\n{path}')

    def _export_json(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON', '*.json')],
            title='Экспорт дневника'
        )
        if not path:
            return
        try:
            self.storage.export_json(path)
            import tkinter.messagebox as mb
            mb.showinfo('Экспорт', f'Дневник экспортирован:\n{path}')
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror('Ошибка', f'Не удалось экспортировать:\n{e}')

    def _import_json(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            defaultextension='.json',
            filetypes=[('JSON', '*.json')],
            title='Импорт дневника'
        )
        if not path:
            return
        try:
            added = self.storage.import_json(path, merge=True)
            self.refresh()
            import tkinter.messagebox as mb
            if added:
                mb.showinfo('Импорт', f'Добавлено записей: {added}')
            else:
                mb.showinfo('Импорт', 'Новых записей не найдено.')
        except Exception as e:
            import tkinter.messagebox as mb
            mb.showerror('Ошибка', f'Не удалось импортировать:\n{e}')


class StrategyGuideUI:
    COLUMNS = ('name',)
    HEADERS = {'name': 'Стратегия'}

    def __init__(self, parent):
        self.parent = parent
        self.root = parent.winfo_toplevel()

        parent.grid_columnconfigure(0, weight=0, minsize=240)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        left_frame = ttk.Frame(parent)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        left_frame.grid_rowconfigure(1, weight=1)

        ttk.Label(left_frame, text="Стратегии", font=('', 10, 'bold')).pack(fill=tk.X, padx=5, pady=(5, 2))

        from strategy.config import get_strategy_names
        from intraday.strategies import SOLABUTO_REGISTRY

        daily_names = get_strategy_names()
        intra_names = [(k, v['name']) for k, v in SOLABUTO_REGISTRY.items()]

        self.tree = ttk.Treeview(left_frame, columns=self.COLUMNS, show='tree', height=30)
        self.tree.column('#0', width=220, minwidth=180)

        parent_daily = self.tree.insert('', 'end', iid='_daily', text='Дневные стратегии', open=True)
        for sid, sname in daily_names:
            self.tree.insert(parent_daily, 'end', iid=sid, text=sname)

        parent_intra = self.tree.insert('', 'end', iid='_intra', text='Внутридневные стратегии', open=True)
        for sid, sname in intra_names:
            self.tree.insert(parent_intra, 'end', iid=sid, text=sname)

        self.tree.pack(fill='both', expand=1, padx=5, pady=2)

        right_frame = ttk.Frame(parent)
        right_frame.grid(row=0, column=1, sticky='nsew')
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self.text = tk.Text(right_frame, wrap='word', state='disabled',
                            font=('Consolas', 10), padx=10, pady=10)
        self.text.grid(row=0, column=0, sticky='nsew')

        scroll_y = ttk.Scrollbar(right_frame, orient='vertical', command=self.text.yview)
        scroll_y.grid(row=0, column=1, sticky='ns')
        self.text.configure(yscrollcommand=scroll_y.set)

        _add_copy_menu(self.text)

        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        if daily_names:
            first_id = daily_names[0][0]
            self.tree.selection_set(first_id)
            self._show_guide(first_id)

    def _on_select(self, event):
        sel = self.tree.selection()
        if sel:
            self._show_guide(sel[0])

    def _show_guide(self, strategy_id):
        from strategy.config import STRATEGY_REGISTRY, get_strategy_params
        from strategy.guide import get_guide
        from intraday.strategies import SOLABUTO_REGISTRY as SOLABUTO
        from intraday.guide import get_solabuto_guide

        entry = STRATEGY_REGISTRY.get(strategy_id)
        solabuto_entry = SOLABUTO.get(strategy_id) if not entry else None
        if not entry and not solabuto_entry:
            return

        guide = get_guide(strategy_id) or (get_solabuto_guide(strategy_id) or {})
        entry = entry or solabuto_entry

        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"  {entry['name']}")
        lines.append(f"{'='*60}")
        lines.append("")

        author = guide.get('author', '—')
        source = guide.get('source', '—')
        lines.append(f"  Автор:     {author}")
        lines.append(f"  Источник:  {source}")
        lines.append(f"  ID:        {strategy_id}")
        lines.append("")

        lines.append(f"{'─'*60}")
        lines.append(f"  ОПИСАНИЕ")
        lines.append(f"{'─'*60}")
        lines.append("")
        lines.append(f"  {entry['description']}")
        lines.append("")

        logic = guide.get('logic', '')
        if logic:
            lines.append(f"{'─'*60}")
            lines.append(f"  ЛОГИКА ВХОДА")
            lines.append(f"{'─'*60}")
            lines.append("")
            lines.append(f"  {logic}")
            lines.append("")

        example = guide.get('example_params', '')
        if example:
            lines.append(f"{'─'*60}")
            lines.append(f"  ПРИМЕР ПАРАМЕТРОВ")
            lines.append(f"{'─'*60}")
            lines.append("")
            lines.append(f"  {example}")
            lines.append("")

        params = get_strategy_params(strategy_id) or (list(solabuto_entry.get('params', [])) if solabuto_entry else [])
        if params:
            lines.append(f"{'─'*60}")
            lines.append(f"  ПАРАМЕТРЫ")
            lines.append(f"{'─'*60}")
            lines.append("")
            lines.append(f"  {'Параметр':<25} {'По умолч.':<12} {'Описание'}")
            lines.append(f"  {'─'*25} {'─'*12} {'─'*30}")
            for p in params:
                k = p['key']
                lbl = p.get('label', '')
                default = str(p.get('default', ''))
                hint = p.get('hint', '')
                if hint:
                    lines.append(f"  {k:<25} {default:<12} {hint}")
                else:
                    lines.append(f"  {k:<25} {default:<12} {lbl}")

        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', '\n'.join(lines))
        self.text.configure(state='disabled')
        self.text.see('1.0')


class AppGuideUI:
    """Вкладка описания программы: возможности, параметры, сокращения."""

    def __init__(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=1)

        text = tk.Text(frame, wrap='word', state='disabled',
                       font=('Consolas', 10), padx=15, pady=15)
        text.pack(fill='both', expand=1, side=tk.LEFT)

        scroll = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
        scroll.pack(side=tk.RIGHT, fill='y')
        text.configure(yscrollcommand=scroll.set)

        _add_copy_menu(text)

        lines = [
            "╔" + "═" * 58 + "╗",
            "║  CreateStrategy — система тестирования и оптимизации         ║",
            "║  торговых стратегий на данных MOEX                          ║",
            "╚" + "═" * 58 + "╝",
            "",
            "",
            "1. ВКЛАДКА «АНАЛИЗ»",
            "─" * 60,
            "",
            "  Кнопка 1 «Получить данные» — загружает исторические свечи",
            "  выбранного тикера с MOEX за указанный период.",
            "",
            "  Кнопка 2 «Запустить Backtest» — запускает выбранную стратегию",
            "  с текущими параметрами. Результат: количество сделок, доходность,",
            "  Sharpe, Profit Factor, просадка.",
            "",
            "  Кнопка 3 «Оптимизация» — grid search по сетке параметров.",
            "  Топ-5 комбинаций выводятся с кликабельным [Применить].",
            "  При нажатии параметры заполняются в UI и сохраняются в ticker_settings.json.",
            "",
            "  Кнопка 4 «Портфельный бэктест» — запуск backtest на всех тикерах",
            "  из торгового дневника. Капитал делится поровну. Выводятся общие",
            "  метрики портфеля и разбивка по тикерам.",
            "",
            "  Кнопка 5 «Walk-forward» — проверка стабильности параметров.",
            "  Данные делятся на окна (IS/OOS), оптимизация на IS, тест на OOS.",
            "  Если среднее OOS/IS < 30% — стратегия нестабильна.",
            "",
            "",
            "2. ПАРАМЕТРЫ СТРАТЕГИИ",
            "─" * 60,
            "",
            "  capital           — стартовый капитал в рублях",
            "  risk_per_trade    — риск на сделку в % от капитала",
            "  atr_sl            — множитель ATR для стоп-лосса",
            "  atr_tp            — множитель ATR для тейк-профита",
            "  min_hits          — минимальное число касаний уровня для входа",
            "  max_hold          — максимальное количество свечей удержания",
            "  commission        — комиссия брокера в %",
            "  entry_type        — 0: вход по open, 1: лимитный по цене сигнала",
            "",
            "  risk_per_trade и commission задаются в % (например 2.0 = 2%).",
            "  Внутри расчёта они делятся на 100.",
            "",
            "",
            "3. УПРАВЛЕНИЕ РИСКОМ И ВЫХОДОМ",
            "─" * 60,
            "",
            "  Трейлинг-стоп:",
            "    0 — выключен",
            "    1 — фиксированный отступ от максимума (в ATR)",
            "    2 — по скользящей средней (MA от close)",
            "    trailing_activation — при какой прибыли в ATR активировать",
            "    trailing_offset — отступ от экстремума в ATR",
            "    trailing_ma_period — период MA для режима 2",
            "",
            "  Частичное фиксирование:",
            "    partial_tp — 0: выкл, 1: вкл",
            "    partial_tp_ratio1 — первый тейк (в ATR)",
            "    partial_tp_ratio2 — второй тейк (в ATR)",
            "    partial_tp_size1 — доля позиции для TP1",
            "",
            "  Pivot-уровни:",
            "    use_pivot_levels — 0: частотный метод, 1: pivot detection",
            "    pivot_lookback — свечей с каждой стороны для пивота",
            "",
            "  MTF-фильтр (Multi-Timeframe):",
            "    use_mtf_filter  — 0: выкл, 1: вкл",
            "    mtf_ma_period   — период MA на недельных свечах",
            "    BUY только когда weekly close > weekly MA,",
            "    SELL только когда weekly close < weekly MA.",
            "",
            "  Размер позиции:",
            "    0 — фиксированный риск (как было)",
            "    1 — Kelly Criterion (доля от капитала = f*)",
            "    2 — ATR-зависимый (обратно пропорционально волатильности)",
            "    kelly_fraction — доля от Kelly (0.0–1.0)",
            "    atr_sizing_mult — множитель ATR для режима 2",
            "",
            "",
            "4. АНСАМБЛЬ СТРАТЕГИЙ",
            "─" * 60,
            "",
            "  Объединяет несколько стратегий голосованием.",
            "  sub_strategies — ID через запятую (bounce,fisher,trend,...)",
            "  vote_method:",
            "    0 — большинство (>50% голосов за BUY/SELL)",
            "    1 — любой сигнал (первое совпадение)",
            "    2 — консенсус (все стратегии должны согласиться)",
            "",
            "  SL/TP консервативные: худший SL (самый узкий) и худший TP",
            "  (дальний для BUY, ближний для SELL).",
            "",
            "",
            "5. СОКРАЩЕНИЯ",
            "─" * 60,
            "",
            "  ATR    Average True Range",
            "  SL     Stop Loss",
            "  TP     Take Profit",
            "  MA     Moving Average",
            "  SMA    Simple Moving Average",
            "  EMA    Exponential Moving Average",
            "  MTF    Multi-Timeframe",
            "  DD     Drawdown (максимальная просадка)",
            "  PF     Profit Factor (валовая прибыль / валовый убыток)",
            "  IS     In-Sample (обучающий период)",
            "  OOS    Out-Of-Sample (тестовый период)",
            "  RSI    Relative Strength Index",
            "  ROC    Rate of Change",
            "  TSI    True Strength Index",
            "  ECO    Ehlers Cyber Cycle",
            "  COG    Center of Gravity",
            "  TCF    Time Cycle Factor",
            "  HV     Historical Volatility",
            "  BB     Bollinger Bands",
            "  MACD   Moving Average Convergence Divergence",
            "  DMI    Directional Movement Index",
            "  ADX    Average Directional Index",
            "",
            "",
            "6. ВКЛАДКА «СКАНЕР»",
            "─" * 60,
            "",
            "  Сканирует все тикеры выбранных секторов MOEX.",
            "  Для каждого тикера запускается backtest с текущей стратегией.",
            "  Отбираются лучшие сигналы. Возможен экспорт в Excel",
            "  и добавление в торговый дневник.",
            "",
            "",
            "7. ВКЛАДКА «УМНЫЙ СКАНЕР»",
            "─" * 60,
            "",
            "  Multi-timeframe сканер: сигналы на H1 с подтверждением по D1.",
            "  Использует внутридневные стратегии Solabuto.",
            "",
            "",
            "8. ВКЛАДКА «ДНЕВНИК СДЕЛОК»",
            "─" * 60,
            "",
            "  Таблица открытых/закрытых позиций. Автоматическая проверка",
            "  стоп-лоссов и тейк-профитов по текущим рыночным данным.",
            "  Экспорт/импорт в JSON, группировка по статусу.",
            "",
            "",
            "9. ВКЛАДКА «ИНТРАДЕЙ»",
            "─" * 60,
            "",
            "  Бэктестинг и сканирование на часовых (H1) данных.",
            "  Стратегии Solabuto для внутридневной торговли.",
        ]

        text.configure(state='normal')
        text.insert('1.0', '\n'.join(lines))
        text.configure(state='disabled')
        text.see('1.0')

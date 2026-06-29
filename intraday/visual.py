import tkinter as tk
from tkinter import ttk, messagebox as mb
import threading
import logging
from datetime import datetime, timedelta

from utils import tree_batch_insert
import urllib3
import numpy as np
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import pandas as pd

from visual import _add_copy_menu
from intraday.strategies import (
    SOLABUTO_REGISTRY, get_solabuto_params, get_solabuto_defaults,
    get_solabuto_strategy
)
from intraday.engine import IntradayEngine

H1_INTERVAL = 60
H1_DAYS_LIMIT = 30


class IntradayUI:
    def __init__(self, parent, on_diary_entry=None, fetch_fn=None):
        self.parent = parent
        self._on_diary_entry = on_diary_entry
        self._fetch_fn = fetch_fn
        self._stock_data = None
        self._last_trades = None
        self._last_metrics = None
        self._last_signal = None
        self._last_params = None
        self._last_ticker = None

        self._build_ui()

    def _build_ui(self):
        self.parent.grid_columnconfigure(0, weight=0, minsize=480)
        self.parent.grid_columnconfigure(1, weight=1)
        self.parent.grid_rowconfigure(0, weight=1)

        left = ttk.Frame(self.parent)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        left.grid_rowconfigure(3, weight=1)

        chart_frame = ttk.Frame(self.parent)
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

        parent = left

        top = ttk.Frame(parent)
        top.pack(fill=tk.X)

        ttk.Label(top, text='Тикер:').pack(side=tk.LEFT)
        self.ticker_var = tk.StringVar()
        self.ticker_combo = ttk.Combobox(top, textvariable=self.ticker_var, width=12, state='normal')
        self.ticker_combo.pack(side=tk.LEFT, padx=2)

        ttk.Label(top, text='Начало:').pack(side=tk.LEFT, padx=(10, 0))
        self.start_var = tk.StringVar(value='2015-01-01')
        ttk.Entry(top, textvariable=self.start_var, width=12).pack(side=tk.LEFT, padx=2)

        ttk.Label(top, text='Конец:').pack(side=tk.LEFT, padx=(5, 0))
        self.end_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(top, textvariable=self.end_var, width=12).pack(side=tk.LEFT, padx=2)

        self.load_btn = ttk.Button(top, text='Загрузить H1', command=self._load_data)
        self.load_btn.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(top, text='', foreground='gray')
        self.status_label.pack(side=tk.LEFT, padx=5)

        mid = ttk.Frame(parent)
        mid.pack(fill=tk.X, pady=5)

        ttk.Label(mid, text='Стратегия:').pack(side=tk.LEFT)
        strategy_ids = list(SOLABUTO_REGISTRY.keys())
        strategy_names = [f'{sid} — {SOLABUTO_REGISTRY[sid]["name"]}' for sid in strategy_ids]
        self.strategy_var = tk.StringVar(value=strategy_names[0] if strategy_names else '')
        self.strategy_combo = ttk.Combobox(mid, textvariable=self.strategy_var,
                                            values=strategy_names, width=50, state='readonly')
        self.strategy_combo.pack(side=tk.LEFT, padx=2)
        self.strategy_combo.bind('<<ComboboxSelected>>', self._on_strategy_change)

        self.run_btn = ttk.Button(mid, text='Запустить Backtest', command=self._run_backtest, state='disabled')
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.diary_btn = ttk.Button(mid, text='В дневник', command=self._save_to_diary, state='disabled')
        self.diary_btn.pack(side=tk.LEFT, padx=5)

        params_frame = ttk.LabelFrame(parent, text='Параметры')
        params_frame.pack(fill=tk.X, pady=5)

        self._params_widgets = {}
        self._current_strategy = None
        self._param_frame = params_frame

        res_frame = ttk.LabelFrame(parent, text='Результаты')
        res_frame.pack(fill=tk.BOTH, expand=1, pady=5)

        self.results_text = tk.Text(res_frame, height=10, wrap=tk.WORD, state='disabled')
        self.results_text.pack(fill=tk.BOTH, expand=1, side=tk.LEFT)

        scroll = ttk.Scrollbar(res_frame, command=self.results_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_text.config(yscrollcommand=scroll.set)
        _add_copy_menu(self.results_text)

        self._strategy_ids = strategy_ids
        self._rebuild_params()

    def set_tickers(self, tickers):
        self.ticker_combo['values'] = tickers
        if tickers and not self.ticker_var.get():
            self.ticker_combo.current(0)

    def _get_strategy_id(self):
        raw = self.strategy_var.get()
        for sid in self._strategy_ids:
            if raw.startswith(sid):
                return sid
        return self._strategy_ids[0] if self._strategy_ids else None

    def _on_strategy_change(self, event=None):
        self._rebuild_params()

    def _rebuild_params(self):
        for w in self._params_widgets.values():
            try:
                w[0].destroy()
            except Exception:
                pass
        self._params_widgets.clear()
        if hasattr(self, '_base_frame') and self._base_frame:
            try:
                self._base_frame.destroy()
            except Exception:
                pass
            self._base_frame = None
        sid = self._get_strategy_id()
        if not sid:
            return
        params = get_solabuto_params(sid)
        defaults = get_solabuto_defaults(sid)
        self._current_strategy = sid
        row = 0
        col = 0
        for p in params:
            key = p['key']
            if key in ('capital', 'risk_per_trade', 'atr_sl', 'atr_tp', 'commission', 'max_hold', 'level_proximity'):
                continue
            frame = ttk.Frame(self._param_frame)
            frame.grid(row=row, column=col, sticky='w', padx=3, pady=1)
            hint = p.get('hint', '')
            label_text = p['label']
            if hint:
                label_text += '?'
            lbl = ttk.Label(frame, text=label_text, width=16, anchor='w')
            lbl.pack(side=tk.LEFT)
            if hint:
                self._create_tooltip(lbl, hint)
            var = tk.StringVar(value=str(defaults.get(key, p['default'])))
            ent = ttk.Entry(frame, textvariable=var, width=10)
            ent.pack(side=tk.LEFT, padx=2)
            self._params_widgets[key] = (frame, lbl, ent, var)
            col += 1
            if col >= 3:
                col = 0
                row += 1
        self._base_frame = ttk.LabelFrame(self._param_frame, text='Базовые')
        self._base_frame.grid(row=row + 1, column=0, columnspan=3, sticky='ew', pady=5)
        self._base_widgets = {}
        base_keys = ['capital', 'risk_per_trade', 'atr_sl', 'atr_tp', 'max_hold', 'level_proximity', 'commission']
        base_labels = {
            'capital': 'Капитал', 'risk_per_trade': 'Риск %', 'atr_sl': 'SL (ATR)',
            'atr_tp': 'TP (ATR)', 'max_hold': 'Макс. баров', 'level_proximity': 'Дист. ATR',
            'commission': 'Комиссия %'
        }
        for i, k in enumerate(base_keys):
            lbl = ttk.Label(self._base_frame, text=base_labels[k])
            lbl.grid(row=0, column=i * 2, padx=2, sticky='w')
            var = tk.StringVar(value=str(defaults.get(k, '')))
            ent = ttk.Entry(self._base_frame, textvariable=var, width=10)
            ent.grid(row=0, column=i * 2 + 1, padx=2)
            self._base_widgets[k] = var

        ttk.Label(self._base_frame, text='Тип входа:').grid(row=1, column=0, padx=2, sticky='w')
        self._entry_type_var = tk.StringVar(value='По рынку (open)')
        self._entry_type_combo = ttk.Combobox(
            self._base_frame, textvariable=self._entry_type_var, state='readonly', width=22,
            values=['По рынку (open)', 'По цене сигнала (лимитный)'])
        self._entry_type_combo.grid(row=1, column=1, columnspan=3, sticky='w', padx=2)

    def _create_tooltip(self, widget, text):
        tw = None
        def show(event):
            nonlocal tw
            if tw:
                return
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f'+{event.x_root + 10}+{event.y_root + 10}')
            lbl = ttk.Label(tw, text=text, background='lightyellow', foreground='black', relief='solid', padding=3)
            lbl.pack()
        def hide(event):
            nonlocal tw
            if tw:
                tw.destroy()
                tw = None
        widget.bind('<Enter>', show)
        widget.bind('<Leave>', hide)

    def _get_params(self):
        sid = self._get_strategy_id()
        if not sid:
            return None
        defaults = get_solabuto_defaults(sid)
        params = dict(defaults)
        for key, var in self._params_widgets.items():
            try:
                val = var[3].get()
                ptype = float
                for p in get_solabuto_params(sid):
                    if p['key'] == key:
                        ptype = p['type']
                        break
                params[key] = ptype(val)
            except (ValueError, KeyError):
                return None
        for key, var in self._base_widgets.items():
            try:
                params[key] = float(var.get())
            except (ValueError, KeyError):
                return None
        if 'risk_per_trade' in params:
            params['risk_per_trade'] = params['risk_per_trade'] / 100.0
        if 'commission' in params:
            params['commission'] = params['commission'] / 100.0
        params['entry_type'] = 1 if self._entry_type_var.get().startswith('По цене сигнала') else 0
        params['strategy'] = sid
        return params

    def _load_data(self):
        ticker = self.ticker_var.get().strip().upper()
        if not ticker:
            mb.showwarning('Данные', 'Введите тикер.')
            return
        start = self.start_var.get().strip()
        end = self.end_var.get().strip()
        self.status_label.config(text='Загрузка...')
        self.load_btn.config(state='disabled')
        def task():
            try:
                import requests
                from datetime import timedelta
                url = (f'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR'
                       f'/securities/{ticker}/candles.json')
                start_dt = datetime.strptime(start, '%Y-%m-%d')
                end_dt = datetime.strptime(end, '%Y-%m-%d')
                all_candles = []
                step = timedelta(days=H1_DAYS_LIMIT)
                cur = start_dt
                while cur < end_dt:
                    nxt = min(cur + step, end_dt)
                    params = {'from': cur.strftime('%Y-%m-%d'), 'till': nxt.strftime('%Y-%m-%d'), 'interval': H1_INTERVAL}
                    resp = requests.get(url, params=params, timeout=15, verify=False)
                    resp.raise_for_status()
                    data = resp.json()
                    if 'candles' in data and 'data' in data['candles']:
                        all_candles.extend(data['candles']['data'])
                    cur = nxt
                self._stock_data = all_candles if all_candles else f'Нет данных за {start}..{end}'
                self._last_ticker = ticker
                self.parent.after(0, self._on_data_loaded)
            except Exception as e:
                logging.error(f'Intraday load error: {e}')
                self.parent.after(0, lambda: self._on_data_error(str(e)))
        t = threading.Thread(target=task, daemon=True)
        t.start()

    def _on_data_loaded(self):
        cnt = len(self._stock_data) if isinstance(self._stock_data, list) else 0
        self.status_label.config(text=f'Загружено {cnt} H1 свечей')
        self.load_btn.config(state='normal')
        self.run_btn.config(state='normal' if cnt > 0 else 'disabled')
        if cnt > 0:
            self._last_trades = None
            self._last_metrics = None
            self._last_signal = None
            self._update_chart()

    def _on_data_error(self, msg):
        self.status_label.config(text=f'Ошибка: {msg}')
        self.load_btn.config(state='normal')

    def _run_backtest(self):
        if not isinstance(self._stock_data, list) or len(self._stock_data) < 10:
            mb.showwarning('Backtest', 'Сначала загрузите H1 данные.')
            return
        params = self._get_params()
        if params is None:
            mb.showwarning('Backtest', 'Проверьте числовые параметры.')
            return
        self._last_params = params
        self.run_btn.config(state='disabled', text='Запущен...')
        data = list(self._stock_data)
        def task():
            try:
                strategy_id = params.pop('strategy')
                engine = IntradayEngine(strategy=strategy_id, **params)
                trades, metrics = engine.run(data)
                signal = self._build_signal(trades, data, params)
                self._last_trades = trades
                self._last_metrics = metrics
                self._last_signal = signal
                self.parent.after(0, lambda: self._on_backtest_done(trades, metrics, signal, params))
            except Exception as e:
                logging.error(f'Intraday backtest error: {e}')
                self.parent.after(0, lambda: self._on_backtest_error(str(e)))
        t = threading.Thread(target=task, daemon=True)
        t.start()

    def _build_signal(self, trades, data, params):
        if not trades or not data:
            return None
        last = trades[-1] if trades else None
        if not last:
            return None
        return {
            'action': last['side'],
            'entry_price': last['entry_price'],
            'sl_price': last['sl_price'],
            'tp_price': last['tp_price'],
            'level': last.get('entry_price', 0),
            'last_price': float(data[-1][1]) if data[-1] else 0,
        }

    def _on_backtest_done(self, trades, metrics, signal, params):
        self.run_btn.config(state='normal', text='Запустить Backtest')
        self._display_results(trades, metrics, signal, params)
        if signal:
            self.diary_btn.config(state='normal')
        else:
            self.diary_btn.config(state='disabled')
        self._update_chart()

    def _on_backtest_error(self, msg):
        self.run_btn.config(state='normal', text='Запустить Backtest')
        self._set_results_text(f'Ошибка: {msg}')

    def _update_chart(self):
        data = self._stock_data
        if not isinstance(data, list) or len(data) < 10:
            return
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
        import mplfinance as mpf
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from backtest.engine import candles_to_df

        df = candles_to_df(data)
        if df is None or df.empty:
            return

        chart_df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        chart_df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        chart_df.index = pd.to_datetime(df.index)

        for w in self._chart_frame.winfo_children():
            w.destroy()
        if self._chart_figure is not None:
            plt.close(self._chart_figure)
        self._chart_figure = None
        self._chart_canvas = None
        self._chart_toolbar = None
        self._chart_ax = None

        n_points = len(chart_df)
        fig, axes = mpf.plot(
            chart_df, type='candle', style='charles',
            volume=True, returnfig=True,
            figsize=(8, 6), figscale=1.0,
            warn_too_much_data=n_points + 1,
            datetime_format='%Y-%m-%d %H:00',
            show_nontrading=False,
        )
        ax = axes[0]
        ticker = self._last_ticker or self.ticker_var.get()
        ax.set_title(f'{ticker} H1 ({n_points} свечей)', fontsize=12, fontweight='bold')
        for a in fig.axes:
            for label in a.get_xticklabels():
                label.set_rotation(45)
                label.set_ha('right')

        if self._last_trades:
            import matplotlib.dates as mdates
            idx_to_dt = {i: chart_df.index[i] for i in range(len(chart_df))}
            for t in self._last_trades:
                ei = t.get('entry_idx', 0)
                xi = t.get('exit_idx', 0)
                if ei < 0 or ei >= len(data):
                    continue
                t_entry = idx_to_dt.get(ei)
                if t_entry is None:
                    continue
                t_entry_num = mdates.date2num(t_entry)
                ep = t.get('entry_price', 0)
                xp = t.get('exit_price', 0)
                side = t.get('side', '')
                ec = 'green' if side == 'BUY' else 'red'
                lbl = f'Entry {side}' if t is self._last_trades[0] else ''
                ax.scatter(t_entry_num, ep, marker='^', color=ec, s=80, zorder=5, label=lbl)
                if xi and xi < len(data) and xp:
                    t_exit = idx_to_dt.get(xi)
                    if t_exit is not None:
                        t_exit_num = mdates.date2num(t_exit)
                        ax.scatter(t_exit_num, xp, marker='v', color='blue', s=80, zorder=5)
                    if t.get('exit_reason') in ('SL', 'TP'):
                        ax.axhline(y=t.get('sl_price', 0), color='orange', linestyle=':', linewidth=0.8, alpha=0.6)
                        ax.axhline(y=t.get('tp_price', 0), color='lime', linestyle=':', linewidth=0.8, alpha=0.6)

        if self._last_signal:
            sl = self._last_signal.get('sl_price')
            tp = self._last_signal.get('tp_price')
            if sl:
                ax.axhline(y=sl, color='red', linestyle='--', linewidth=1.2, alpha=0.8, label=f'SL {sl:.2f}')
            if tp:
                ax.axhline(y=tp, color='green', linestyle='--', linewidth=1.2, alpha=0.8, label=f'TP {tp:.2f}')

        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=8, loc='best')

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

    def _display_results(self, trades, metrics, signal=None, params=None):
        lines = [
            '========== РЕЗУЛЬТАТЫ BACKTEST ==========',
            f"Начальный капитал: {metrics.get('initial_capital', 0):,.0f} руб",
            f"Конечный капитал:   {metrics.get('final_capital', 0):,.0f} руб",
            f"Чистая прибыль:     {metrics.get('net_profit', 0):+,.0f} руб",
            f"Общая доходность:   {metrics.get('total_return', 0):+.2f} %",
            '',
            f"Всего сделок:       {metrics.get('total_trades', 0)}",
            f"Win Rate:           {metrics.get('win_rate', 0):.1f} %",
            f"Profit Factor:      {metrics.get('profit_factor', 0)}",
            f"Max Drawdown:       -{metrics.get('max_drawdown', 0):.2f} %",
            f"Sharpe Ratio:       {metrics.get('sharpe', 0)}",
            '',
        ]
        if metrics.get('avg_win'):
            lines.append(f"Средняя прибыль:    {metrics['avg_win']:+.2f} руб")
        if metrics.get('avg_loss'):
            lines.append(f"Средний убыток:     {metrics['avg_loss']:+.2f} руб")
        if params:
            capital = params.get('capital', 1_000_000)
            risk = params.get('risk_per_trade', 0.02)
            lines.append(f"Риск на сделку:     {capital * risk:,.0f} руб")
        lines.append('==========================================')
        lines.append(f'=== СДЕЛКИ ({len(trades)}) ===')
        for i, t in enumerate(trades[-10:], 1):
            side = t.get('side', '?')
            ep = t.get('entry_price', 0)
            xp = t.get('exit_price', 0)
            pnl = t.get('pnl', 0)
            reason = t.get('exit_reason', '?')
            lines.append(f'  {i}. {side} entry={ep:.2f} exit={xp:.2f} pnl={pnl:+.0f} ({reason})')
        if signal and signal.get('action', 'NONE') != 'NONE':
            symbols = {'BUY': '⬆', 'SELL': '⬇'}
            labels = {'BUY': 'ПОКУПКА', 'SELL': 'ПРОДАЖА'}
            action = signal['action']
            level = signal.get('level', 0)
            last_price = signal.get('last_price', 0)
            sl = signal.get('sl_price', 0)
            tp = signal.get('tp_price', 0)
            lines.append('')
            lines.append('========== РЕКОМЕНДАЦИЯ ==========')
            lines.append(f'{symbols.get(action, "➡")} {labels.get(action, action)} от {level:.2f}')
            lines.append(f'Посл. цена: {last_price:.2f}')
            lines.append(f'SL: {sl:.2f} | TP: {tp:.2f}')
            if params and level and sl:
                capital = params.get('capital', 1_000_000)
                risk = params.get('risk_per_trade', 0.02)
                risk_amount = capital * risk
                sl_dist = abs(float(level) - float(sl)) / float(level) if float(level) else 0
                if sl_dist > 0:
                    lines.append(f'Объём позиции: {risk_amount / sl_dist:,.0f} руб')
            lines.append('====================================')
        self._set_results_text('\n'.join(lines))

    def _set_results_text(self, text):
        self.results_text.config(state='normal')
        self.results_text.delete('1.0', tk.END)
        self.results_text.insert('1.0', text)
        self.results_text.config(state='disabled')

    def _save_to_diary(self):
        if not self._last_signal or not self._last_params:
            mb.showinfo('В дневник', 'Нет сигнала. Запустите backtest.')
            return
        ticker = self._last_ticker or self.ticker_var.get().strip().upper()
        if not ticker:
            return
        signal = self._last_signal
        params = self._last_params
        confirm = mb.askyesno(
            'Подтверждение',
            f'Добавить {ticker} (H1) в дневник?\n\n'
            f'Сигнал: {signal["action"]}\n'
            f'Цена: {signal.get("entry_price", 0):.2f}\n'
            f'SL: {signal.get("sl_price", 0):.2f} | TP: {signal.get("tp_price", 0):.2f}'
        )
        if not confirm:
            return
        if self._on_diary_entry:
            self._on_diary_entry(ticker, signal, params)
        else:
            mb.showinfo('В дневник', 'Функция сохранения не подключена.')


class IntradaySmartScannerUI:
    COLUMNS = ('rank', 'ticker', 'best_strategy', 'total_return', 'sharpe', 'trades', 'signal_action')
    HEADERS = {
        'rank': '№', 'ticker': 'Тикер',
        'best_strategy': 'Лучшая стратегия',
        'total_return': 'Доходность',
        'sharpe': 'Sharpe',
        'trades': 'Сделок',
        'signal_action': 'Сигнал',
    }
    WIDTHS = {
        'rank': 35, 'ticker': 80,
        'best_strategy': 150,
        'total_return': 90,
        'sharpe': 70,
        'trades': 65,
        'signal_action': 80,
    }

    def __init__(self, parent, on_scan=None, on_excel=None, on_diary=None):
        self.parent = parent
        self._on_scan = on_scan
        self._on_excel = on_excel
        self._on_diary = on_diary
        self._all_results = []
        self._tickers = []

        row = 0
        ttk.Label(parent, text='Умный сканер (H1) — все Solabuto стратегии',
                  font=('', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', pady=(5, 2))
        row += 1

        ttk.Label(parent, text='Тикеры:').grid(row=row, column=0, sticky='w', padx=5)
        self.ticker_combo = ttk.Combobox(parent, state='readonly', width=50)
        self.ticker_combo.grid(row=row, column=1, sticky='w', padx=5)
        row += 1

        self._select_all_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text='Сканировать все тикеры (игнорируя список)',
                        variable=self._select_all_var).grid(row=row, column=0, columnspan=2, sticky='w', padx=5)
        row += 1

        ttk.Separator(parent, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=3)
        row += 1

        ttk.Label(parent, text='Параметры (единые для всех стратегий):',
                  font=('', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', padx=5, pady=(5, 0))
        row += 1

        param_frame = ttk.Frame(parent)
        param_frame.grid(row=row, column=0, columnspan=3, sticky='ew', padx=5, pady=2)
        row += 1

        self._param_entries = {}
        base_params_config = [
            ('capital', 'Капитал', '1000000', 10),
            ('risk_per_trade', 'Риск%', '2.0', 6),
            ('atr_sl', 'ATR SL', '1.0', 6),
            ('atr_tp', 'ATR TP', '2.0', 6),
            ('level_proximity', 'Дист.ATR', '0.5', 6),
            ('max_hold', 'Макс.баров', '20', 6),
            ('commission', 'Комис.%', '0.05', 6),
        ]
        for i, (key, label, default, width) in enumerate(base_params_config):
            lbl = ttk.Label(param_frame, text=label + ':', font=('', 8))
            lbl.grid(row=0, column=i * 2, padx=(0, 1), sticky='w')
            ent = ttk.Entry(param_frame, width=width, font=('', 8))
            ent.grid(row=0, column=i * 2 + 1, padx=(0, 4), sticky='w')
            ent.insert(0, default)
            self._param_entries[key] = ent

        row2 = row
        ttk.Label(parent, text='Тип входа:').grid(row=row2, column=0, sticky='w', padx=5)
        self._entry_type_var = tk.StringVar(value='По рынку (open)')
        self._entry_type_combo = ttk.Combobox(
            parent, textvariable=self._entry_type_var, state='readonly', width=28,
            values=['По рынку (open)', 'По цене сигнала (лимитный)'])
        self._entry_type_combo.grid(row=row2, column=1, sticky='w', padx=5)
        row += 1

        n_strategies = len(SOLABUTO_REGISTRY)
        ttk.Label(parent, text=f'Тестируются {n_strategies} Solabuto стратегий для каждого тикера',
                  font=('', 8, 'italic'), foreground='gray').grid(
            row=row, column=0, columnspan=3, sticky='w', padx=5, pady=(0, 2))
        row += 1

        date_frame = ttk.Frame(parent)
        date_frame.grid(row=row, column=0, columnspan=3, pady=2)
        row += 1

        ttk.Label(date_frame, text='От:').pack(side=tk.LEFT, padx=2)
        self.date_from = ttk.Entry(date_frame, width=12)
        self.date_from.pack(side=tk.LEFT, padx=2)
        self.date_from.insert(0, (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))

        ttk.Label(date_frame, text='До:').pack(side=tk.LEFT, padx=2)
        self.date_to = ttk.Entry(date_frame, width=12)
        self.date_to.pack(side=tk.LEFT, padx=2)
        self.date_to.insert(0, datetime.now().strftime('%Y-%m-%d'))

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=5)
        row += 1

        self.scan_btn = ttk.Button(btn_frame, text='Запустить умный сканер', command=self._request_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = ttk.Button(btn_frame, text='Экспорт в Excel', command=self._request_excel, state='disabled')
        self.export_btn.pack(side=tk.LEFT, padx=5)

        self.diary_btn = ttk.Button(btn_frame, text='В дневник', command=self._request_diary, state='disabled')
        self.diary_btn.pack(side=tk.LEFT, padx=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(parent, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=row, column=0, columnspan=3, sticky='ew', padx=10, pady=2)
        row += 1

        self.status_var = tk.StringVar(value='Готов к сканированию')
        self.status_label = ttk.Label(parent, textvariable=self.status_var, foreground='gray')
        self.status_label.grid(row=row, column=0, columnspan=3, pady=2)
        row += 1

        ttk.Separator(parent, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=3)
        row += 1

        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=row, column=0, columnspan=3, sticky='nsew', padx=5, pady=5)
        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_frame, columns=self.COLUMNS, show='headings',
                                 height=22, selectmode='browse')
        for col in self.COLUMNS:
            self.tree.heading(col, text=self.HEADERS[col])
            self.tree.column(col, width=self.WIDTHS[col], anchor='center')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        scroll_y = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<Double-1>', self._on_double_click)

    def set_tickers(self, tickers):
        self._tickers = tickers
        self.ticker_combo['values'] = sorted(tickers)
        if tickers:
            self.ticker_combo.current(0)

    def _request_scan(self):
        if self._on_scan:
            self._on_scan()

    def _request_diary(self):
        if self._on_diary:
            self._on_diary()

    def _request_excel(self):
        if self._on_excel:
            self._on_excel()

    def get_scan_tickers(self):
        if self._select_all_var.get():
            return list(self._tickers)
        sel = self.ticker_combo.get()
        if sel:
            return [sel]
        return []

    def get_backtest_params(self):
        try:
            params = {}
            for key, entry in self._param_entries.items():
                raw = entry.get().strip()
                if key in ('max_hold',):
                    params[key] = int(raw)
                else:
                    params[key] = float(raw)
            if 'risk_per_trade' in params:
                params['risk_per_trade'] = params['risk_per_trade'] / 100.0
            if 'commission' in params:
                params['commission'] = params['commission'] / 100.0
            params['entry_type'] = 1 if self._entry_type_var.get().startswith('По цене сигнала') else 0
            return params
        except (ValueError, TypeError):
            return None

    def set_running(self, running):
        if running:
            self.scan_btn.config(state='disabled', text='Сканирование...')
            self.progress_var.set(0)
            self.status_var.set('Запуск...')
        else:
            self.scan_btn.config(state='normal', text='Запустить умный сканер')
            self.export_btn.config(state='normal')
            self.diary_btn.config(state='normal')
            self.status_var.set('Завершено')

    def update_progress(self, current, total, ticker, strategy_name):
        pct = (current / max(total, 1)) * 100
        self.progress_var.set(pct)
        self.status_var.set(f'{ticker} — тестирование {strategy_name} ({current}/{total})')
        self.parent.update_idletasks()

    def show_results(self, results):
        self._all_results = results

        names = {k: v['name'] for k, v in SOLABUTO_REGISTRY.items()}

        items = []
        for rank, r in enumerate(results, 1):
            best_sid = r.get('best_strategy')
            best_name = names.get(best_sid, best_sid or '—')
            metrics = r.get('best_metrics', {})
            sig = r.get('best_signal', {})
            action = sig.get('action', 'NONE')
            action_short = {'BUY': 'B', 'SELL': 'S', 'WAIT': '—', 'NONE': '—'}.get(action, action)
            ret = metrics.get('total_return', 0)
            sh = metrics.get('sharpe', 0)
            trades = metrics.get('total_trades', 0)

            if not best_sid:
                best_name = '—'

            ret_str = f'{ret:+.1f}%' if isinstance(ret, (int, float)) else '—'
            sh_str = f'{sh:.2f}' if isinstance(sh, (int, float)) else '—'
            trades_str = str(trades) if trades else '—'

            values = (rank, r['ticker'], best_name, ret_str, sh_str, trades_str, action_short)
            tags = ()
            if isinstance(ret, (int, float)):
                tags = ('positive',) if ret > 0 else ('negative',)
            items.append({'values': values, 'tags': tags})

        tree_batch_insert(self.tree, items)

        self.tree.tag_configure('positive', foreground='green')
        self.tree.tag_configure('negative', foreground='red')

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if idx < 0 or idx >= len(self._all_results):
            return
        self._show_detail_window(self._all_results[idx])

    def _show_detail_window(self, result):
        names = {k: v['name'] for k, v in SOLABUTO_REGISTRY.items()}

        win = tk.Toplevel(self.parent)
        win.title(f"{result['ticker']} — все Solabuto стратегии")
        win.geometry('700x400')
        win.transient(self.parent)
        win.grab_set()

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=10)

        text = tk.Text(frame, wrap=tk.WORD, font=('Consolas', 10))
        text.pack(fill=tk.BOTH, expand=1)

        lines = [
            f"Тикер: {result['ticker']}",
            '',
            "────── Результаты по всем Solabuto стратегиям ──────",
            '',
        ]
        strategies = result.get('strategies', {})
        for sid, sdata in strategies.items():
            name = names.get(sid, sid)
            metrics = sdata.get('metrics', {})
            score = sdata.get('score', -1)
            sig = sdata.get('signal', {})
            action = sig.get('action', 'NONE')

            ret = metrics.get('total_return', 0)
            sh = metrics.get('sharpe', 0)
            tr = metrics.get('total_trades', 0)
            wr = metrics.get('win_rate', 0)
            pf = metrics.get('profit_factor', 0)

            ret_s = f'{ret:+.1f}%' if isinstance(ret, (int, float)) else '—'
            sh_s = f'{sh:.2f}' if isinstance(sh, (int, float)) else '—'

            star = '★ ' if sid == result.get('best_strategy') else '  '
            lines.append(
                f'{star}{name:<20s} Score:{score:>5.2f}  '
                f'Ret:{ret_s:>7s}  Sharpe:{sh_s:>5s}  '
                f'Сд:{tr:>3d}  WR:{wr:.0f}%  PF:{pf:.1f}  '
                f'Сигнал:{action}'
            )

        if not strategies:
            lines.append('  Нет данных.')

        text.insert(tk.END, '\n'.join(lines))
        text.config(state=tk.DISABLED)
        _add_copy_menu(text)

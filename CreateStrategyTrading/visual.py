# visual.py
# -*- coding: utf-8 -*-
import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import mplfinance as mpf
import pandas as pd
import matplotlib.pyplot as plt


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
    def __init__(self, parent, on_select, on_plot_button, on_export_button,
                 step, get_moex_tickers, on_backtest):
        self.root = parent.winfo_toplevel()
        self.parent = parent

        all_tickers = get_moex_tickers()

        label_stock = ttk.Label(parent, text="Тикер:")
        label_stock.grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.stock_combobox = ttk.Combobox(parent, values=all_tickers, width=25)
        self.stock_combobox.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        if all_tickers:
            self.stock_combobox.set(all_tickers[0])

        label_start = ttk.Label(parent, text="Начальная дата (гггг-мм-дд):")
        label_start.grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.start_date_entry = ttk.Entry(parent)
        self.start_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        self.start_date_entry.insert(0, "2020-01-01")

        label_end = ttk.Label(parent, text="Конечная дата (гггг-мм-дд):")
        label_end.grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.end_date_entry = ttk.Entry(parent)
        self.end_date_entry.grid(row=2, column=1, padx=5, pady=5, sticky='w')
        self.end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        self.min_repeats_label = tk.Label(parent, text="Мин. повторов цены:")
        self.min_repeats_label.grid(row=3, column=0, padx=5, pady=2, sticky='e')
        self.min_repeats_entry = tk.Entry(parent, width=28)
        self.min_repeats_entry.grid(row=3, column=1, padx=5, pady=2, sticky='w')
        self.min_repeats_entry.insert(0, "5")

        self.result_text = tk.Text(parent, height=12, width=55)
        self.result_text.grid(row=4, column=0, columnspan=2, padx=5, pady=5)
        _add_copy_menu(self.result_text)

        self.get_data_button = ttk.Button(
            parent, text="1. Получить данные", command=on_select)
        self.get_data_button.grid(row=5, column=0, columnspan=2, pady=2)

        plot_button = ttk.Button(
            parent, text="2. Построить график", command=on_plot_button)
        plot_button.grid(row=6, column=0, columnspan=2, pady=2)

        export_button = ttk.Button(
            parent, text="Экспорт данных", command=on_export_button)
        export_button.grid(row=7, column=0, columnspan=2, pady=2)

        ttk.Separator(parent, orient='horizontal').grid(
            row=8, column=0, columnspan=2, sticky='ew', pady=5)

        btns_frame = ttk.Frame(parent)
        btns_frame.grid(row=9, column=0, columnspan=2, pady=2)

        ttk.Label(btns_frame, text="ATR SL:").grid(
            row=0, column=0, padx=2, sticky='e')
        self.atr_sl_entry = ttk.Entry(btns_frame, width=6)
        self.atr_sl_entry.grid(row=0, column=1, padx=2)
        self.atr_sl_entry.insert(0, "1.0")

        ttk.Label(btns_frame, text="ATR TP:").grid(
            row=0, column=2, padx=2, sticky='e')
        self.atr_tp_entry = ttk.Entry(btns_frame, width=6)
        self.atr_tp_entry.grid(row=0, column=3, padx=2)
        self.atr_tp_entry.insert(0, "2.0")

        ttk.Label(btns_frame, text="Риск %:").grid(
            row=0, column=4, padx=2, sticky='e')
        self.risk_entry = ttk.Entry(btns_frame, width=6)
        self.risk_entry.grid(row=0, column=5, padx=2)
        self.risk_entry.insert(0, "2.0")

        self.show_trades_var = tk.BooleanVar(value=True)
        self.show_trades_cb = tk.Checkbutton(
            parent, text="Показать сделки на графике",
            variable=self.show_trades_var)
        self.show_trades_cb.grid(row=10, column=0, columnspan=2, pady=2)

        self.backtest_button = ttk.Button(
            parent, text="3. Запустить Backtest", command=on_backtest)
        self.backtest_button.grid(row=11, column=0, columnspan=2, pady=5)

        self.backtest_text = tk.Text(parent, height=14, width=55)
        self.backtest_text.grid(row=12, column=0, columnspan=2, padx=5, pady=5)
        _add_copy_menu(self.backtest_text)

        graph_frame = ttk.Frame(parent)
        graph_frame.grid(row=0, column=2, rowspan=10, padx=10, pady=10, sticky='n')

        self.canvas = FigureCanvasTkAgg(plt.Figure(), master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        toolbar = NavigationToolbar2Tk(self.canvas, graph_frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        step_button = ttk.Button(graph_frame, text="Шаг", command=step)
        step_button.pack(side=tk.BOTTOM)

    def add_backtest_result(self, text):
        self.backtest_text.delete(1.0, tk.END)
        self.backtest_text.insert(tk.END, text)

    def display_backtest_results(self, metrics):
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
            "=========================================="
        ]
        self.add_backtest_result('\n'.join(lines))


class ScannerUI:
    def __init__(self, parent, sectors, on_scan, on_legend=None, on_excel=None, on_diary=None):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self._on_legend = on_legend
        self._on_excel = on_excel
        self._on_diary = on_diary
        self._strategy_id_map = {}
        self._strategy_names = []

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
        self.scanner_date_from.insert(0, "2020-01-01")

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

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            parent, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=row, column=0, columnspan=2, sticky='ew', padx=10, pady=2)
        row += 1

        self.status_var = tk.StringVar(value="Готов к сканированию")
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

    def get_selected_sectors(self):
        return [s for s, v in self.sector_vars.items() if v.get()]

    def get_backtest_params(self):
        try:
            from strategy.config import get_strategy_params
            strategy_id = self._get_strategy_id()
            params = {'strategy': strategy_id}

            cfg_list = get_strategy_params(strategy_id)
            for key, entry in self._param_entries.items():
                raw = entry.get().strip()
                cfg = next((c for c in cfg_list if c['key'] == key), None)
                if cfg and cfg['type'] == int:
                    params[key] = int(raw)
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
            self.status_var.set('Завершено')


class DiaryUI:
    COLUMNS = ('date', 'ticker', 'side', 'entry_price', 'sl_price',
               'tp_price', 'volume', 'qty', 'status')

    HEADERS = {
        'date': 'Дата', 'ticker': 'Тикер', 'side': 'Напр.',
        'entry_price': 'Цена входа', 'sl_price': 'SL', 'tp_price': 'TP',
        'volume': 'Объём (₽)', 'qty': 'Кол-во', 'status': 'Статус'
    }

    WIDTHS = {
        'date': 140, 'ticker': 70, 'side': 60, 'entry_price': 90,
        'sl_price': 80, 'tp_price': 80, 'volume': 100, 'qty': 80, 'status': 70
    }

    def __init__(self, parent, storage, on_close_entry=None):
        self.parent = parent
        self.storage = storage
        self._on_close_entry = on_close_entry

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

        ttk.Button(btn_frame, text='Экспорт CSV',
                   command=self._export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Закрыть сделку',
                   command=self._close_selected).pack(side=tk.LEFT, padx=2)
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
                e.sl_price, e.tp_price, e.volume, e.qty, e.status
            )
            self.tree.insert('', 'end', values=values)

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
                    e.sl_price, e.tp_price, e.volume, e.qty, e.status
                ])
        import tkinter.messagebox as mb
        mb.showinfo('Экспорт', f'Дневник сохранён:\n{path}')

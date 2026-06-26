import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, List, Optional

from alerts.storage import AlertStorage, PriceAlert
from utils import tree_batch_insert


class AlertUI:
    def __init__(self, parent, alert_storage: AlertStorage,
                 on_add: Callable = None, on_remove: Callable = None,
                 on_start: Callable = None, on_stop: Callable = None,
                 all_tickers: List[str] = None):
        self.parent = parent
        self._storage = alert_storage
        self._on_add = on_add
        self._on_remove = on_remove
        self._on_start = on_start
        self._on_stop = on_stop
        self._all_tickers = list(all_tickers) if all_tickers else []
        self._monitor_running = False

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(ctrl, text='Тикер:').pack(side=tk.LEFT, padx=2)
        self.ticker_combo = ttk.Combobox(ctrl, values=self._all_tickers, width=10)
        self.ticker_combo.pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl, text='Цена:').pack(side=tk.LEFT, padx=2)
        self.price_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self.price_var, width=10).pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl, text='Условие:').pack(side=tk.LEFT, padx=2)
        self.cond_var = tk.StringVar(value='above')
        cond_cb = ttk.Combobox(ctrl, textvariable=self.cond_var,
                               values=['above', 'below'], width=8, state='readonly')
        cond_cb.pack(side=tk.LEFT, padx=2)

        ttk.Button(ctrl, text='Добавить', command=self._add_alert).pack(side=tk.LEFT, padx=5)

        self.start_btn = ttk.Button(ctrl, text='Запустить', command=self._toggle_monitor)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl, text='Очистить сработавшие', command=self._clear_triggered).pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(ctrl, text='', font=('', 9))
        self.status_label.pack(side=tk.RIGHT, padx=5)

        cols = ('ticker', 'target', 'condition', 'created', 'status')
        headers = {'ticker': 'Тикер', 'target': 'Целевая цена',
                   'condition': 'Условие', 'created': 'Создан', 'status': 'Статус'}
        widths = {'ticker': 80, 'target': 100, 'condition': 80, 'created': 120, 'status': 80}

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=1)

        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings',
                                  height=10, selectmode='browse')
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c], anchor='center')

        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure('active', foreground='#0066cc')
        self.tree.tag_configure('triggered', foreground='#cc0000')

        ttk.Button(main, text='Удалить выбранное', command=self._remove_selected).pack(anchor='e', pady=(5, 0))

        self.refresh()

    def _add_alert(self):
        ticker = self.ticker_combo.get().strip().upper()
        if not ticker:
            return
        try:
            price = float(self.price_var.get().replace(',', '.'))
        except ValueError:
            messagebox.showwarning('Алерты', 'Введите корректную цену')
            return
        condition = self.cond_var.get()
        alert = self._storage.add_alert(ticker, price, condition)
        if self._on_add:
            self._on_add(alert)
        self.refresh()

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        item_vals = self.tree.item(sel[0])['values']
        if not item_vals:
            return
        ticker = str(item_vals[0])
        target = str(item_vals[1])
        cond_raw = str(item_vals[2])
        cond_map = {'Выше': 'above', 'Ниже': 'below'}
        cond = cond_map.get(cond_raw, cond_raw)
        for a in self._storage.get_all():
            if a.ticker == ticker and f'{a.target_price:.2f}' == target and a.condition == cond:
                self._storage.remove_alert(a.alert_id)
                if self._on_remove:
                    self._on_remove(a.alert_id)
                break
        self.refresh()

    def _clear_triggered(self):
        self._storage.clear_triggered()
        self.refresh()

    def _toggle_monitor(self):
        if self._monitor_running:
            if self._on_stop:
                self._on_stop()
            self._monitor_running = False
            self.start_btn.configure(text='Запустить')
        else:
            if self._on_start:
                self._on_start()
            self._monitor_running = True
            self.start_btn.configure(text='Остановить')

    def set_monitor_running(self, running: bool):
        self._monitor_running = running
        self.start_btn.configure(text='Остановить' if running else 'Запустить')

    def refresh(self, alerts: List[PriceAlert] = None):
        if alerts is None:
            alerts = self._storage.get_all()

        cond_labels = {'above': 'Выше', 'below': 'Ниже'}
        active_count = 0
        items = []
        for a in alerts:
            status = 'Сработал' if a.triggered else 'Активен'
            tag = 'triggered' if a.triggered else 'active'
            if not a.triggered:
                active_count += 1
            items.append({
                'values': (a.ticker, f'{a.target_price:.2f}',
                           cond_labels.get(a.condition, a.condition),
                           a.created, status),
                'tags': (tag,),
            })

        tree_batch_insert(self.tree, items)
        self.status_label.configure(text=f'Активных: {active_count}')

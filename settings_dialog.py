import json
import logging
import os
import tkinter as tk
from tkinter import ttk, messagebox

from utils import app_dir


class SettingsDialog:
    def __init__(self, root, scheduler=None, on_start_all=None, on_stop_all=None,
                 watchlist_ui_class=None, watchlist_callbacks=None, main_app=None):
        self.root = root
        self.scheduler = scheduler
        self.on_start_all = on_start_all
        self.on_stop_all = on_stop_all
        self.watchlist_ui_class = watchlist_ui_class
        self.watchlist_callbacks = watchlist_callbacks or {}
        self.main_app = main_app
        self._dialog = None

    def show(self):
        if self._dialog and self._dialog.winfo_exists():
            self._dialog.lift()
            self._dialog.focus_force()
            return

        self._dialog = tk.Toplevel(self.root)
        self._dialog.title('Настройки')
        self._dialog.geometry('850x700')
        self._dialog.minsize(700, 500)
        self._dialog.transient(self.root)
        self._dialog.grab_set()
        self._dialog.protocol('WM_DELETE_WINDOW', self._on_close)

        try:
            self._dialog.iconbitmap('icon.ico')
        except Exception:
            pass

        nb = ttk.Notebook(self._dialog)
        nb.pack(fill='both', expand=True, padx=5, pady=5)

        tab_watchlist = ttk.Frame(nb)
        tab_auto = ttk.Frame(nb)
        tab_cloud = ttk.Frame(nb)
        tab_strategies = ttk.Frame(nb)

        nb.add(tab_watchlist, text='Избранное')
        nb.add(tab_auto, text='Автоматизация')
        nb.add(tab_cloud, text='Облако')
        nb.add(tab_strategies, text='Стратегии')

        self._build_watchlist(tab_watchlist)
        self._build_automation(tab_auto)
        self._build_cloud(tab_cloud)
        self._build_strategies(tab_strategies)

        btn_frame = ttk.Frame(self._dialog)
        btn_frame.pack(fill='x', padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text='Закрыть', command=self._on_close).pack(side='right')

    def _on_close(self):
        if self.main_app is not None:
            self.main_app.watchlist_ui = None
        if self._dialog and self._dialog.winfo_exists():
            self._dialog.destroy()
        self._dialog = None

    def _build_watchlist(self, parent):
        if self.watchlist_ui_class and self.watchlist_callbacks:
            self._watchlist_ui = self.watchlist_ui_class(
                parent, **self.watchlist_callbacks)
            if self.main_app is not None:
                self.main_app.watchlist_ui = self._watchlist_ui
        else:
            main = ttk.Frame(parent, padding=10)
            main.pack(fill='both', expand=True)
            ttk.Label(main, text='Избранное недоступно', font=('Segoe UI', 11)).pack(pady=20)

    def _build_automation(self, parent):
        from automation.panel import AutomationPanel
        self._auto_panel = AutomationPanel(
            parent, self.scheduler,
            on_start_all=self.on_start_all,
            on_stop_all=self.on_stop_all,
        )

    def _build_cloud(self, parent):
        from cloud.ui import CloudPanel
        CloudPanel(parent, self.root)

    def _build_strategies(self, parent):
        main = ttk.Frame(parent, padding=10)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text='Сохранённые стратегии для тикеров',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 5))

        ttk.Label(main, text='Стратегии привязываются к тикеру через кнопку «Сохранить» в основном окне.\n'
                              'Здесь можно просмотреть и удалить сохранённые настройки.',
                  font=('Segoe UI', 9), foreground='gray', justify='left').pack(anchor='w', pady=(0, 10))

        cols = ('Тикер', 'Стратегия', 'Параметры')
        self._strat_tree = ttk.Treeview(main, columns=cols, show='headings', height=16)
        for c in cols:
            self._strat_tree.heading(c, text=c)
        self._strat_tree.column('Тикер', width=100, minwidth=80)
        self._strat_tree.column('Стратегия', width=200, minwidth=120)
        self._strat_tree.column('Параметры', width=380, minwidth=200)

        vsb = ttk.Scrollbar(main, orient='vertical', command=self._strat_tree.yview)
        self._strat_tree.configure(yscrollcommand=vsb.set)
        self._strat_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        btn_row = ttk.Frame(main)
        btn_row.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_row, text='Удалить выбранную', command=self._delete_strat).pack(side='left')
        ttk.Button(btn_row, text='Удалить все', command=self._delete_all_strat).pack(side='left', padx=(5, 0))
        ttk.Button(btn_row, text='Обновить', command=self._load_strategies).pack(side='right')

        self._load_strategies()

    def _load_strategies(self):
        for item in self._strat_tree.get_children():
            self._strat_tree.delete(item)

        path = os.path.join(app_dir(), 'results', 'ticker_settings.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        for ticker, cfg in sorted(data.items()):
            strategy = cfg.get('strategy', '?')
            params = cfg.get('params', {})
            param_str = ', '.join(f'{k}={v}' for k, v in params.items()) if params else '-'
            self._strat_tree.insert('', 'end', values=(ticker, strategy, param_str))

    def _delete_strat(self):
        sel = self._strat_tree.selection()
        if not sel:
            return
        item = sel[0]
        ticker = self._strat_tree.item(item, 'values')[0]

        path = os.path.join(app_dir(), 'results', 'ticker_settings.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if ticker in data:
                del data[ticker]
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f'Delete strat error: {e}')

        self._load_strategies()

    def _delete_all_strat(self):
        if not messagebox.askyesno('Удалить все', 'Удалить все сохранённые стратегии?'):
            return
        path = os.path.join(app_dir(), 'results', 'ticker_settings.json')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
        except Exception as e:
            logging.error(f'Delete all strats error: {e}')
        self._load_strategies()

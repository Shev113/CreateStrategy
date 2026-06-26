import json
import logging
import os
import tkinter as tk
from tkinter import ttk, messagebox

from utils import app_dir, load_favorites, save_favorites


class SettingsDialog:
    def __init__(self, root, scheduler=None, on_start_all=None, on_stop_all=None):
        self.root = root
        self.scheduler = scheduler
        self.on_start_all = on_start_all
        self.on_stop_all = on_stop_all
        self._auto_vars = {}
        self._auto_labels = {}
        self._auto_interval_vars = {}
        self._dialog = None

    def show(self):
        if self._dialog and self._dialog.winfo_exists():
            self._dialog.lift()
            self._dialog.focus_force()
            return

        self._dialog = tk.Toplevel(self.root)
        self._dialog.title('Настройки')
        self._dialog.geometry('720x620')
        self._dialog.minsize(600, 480)
        self._dialog.transient(self.root)
        self._dialog.grab_set()

        try:
            self._dialog.iconbitmap('icon.ico')
        except Exception:
            pass

        nb = ttk.Notebook(self._dialog)
        nb.pack(fill='both', expand=True, padx=5, pady=5)

        tab_auto = ttk.Frame(nb)
        tab_cloud = ttk.Frame(nb)
        tab_strategies = ttk.Frame(nb)
        tab_favorites = ttk.Frame(nb)

        nb.add(tab_auto, text='Автоматизация')
        nb.add(tab_cloud, text='Облако')
        nb.add(tab_strategies, text='Стратегии')
        nb.add(tab_favorites, text='Избранное')

        self._build_automation(tab_auto)
        self._build_cloud(tab_cloud)
        self._build_strategies(tab_strategies)
        self._build_favorites(tab_favorites)

        btn_frame = ttk.Frame(self._dialog)
        btn_frame.pack(fill='x', padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text='Закрыть', command=self._dialog.destroy).pack(side='right')

    def _build_automation(self, parent):
        from automation.panel import INTERVAL_OPTIONS
        main = ttk.Frame(parent, padding=10)
        main.pack(fill='both', expand=True)

        if not self.scheduler:
            ttk.Label(main, text='Автоматизация недоступна', font=('Segoe UI', 11)).pack(pady=20)
            return

        tasks = ['auto_scan', 'monitor_positions', 'refresh_watchlist', 'auto_news_scan']
        task_names = {
            'auto_scan': 'Автосканер',
            'monitor_positions': 'Мониторинг позиций',
            'refresh_watchlist': 'Обновление избранного',
            'auto_news_scan': 'Сканирование новостей',
        }

        for task_id in tasks:
            task = self.scheduler.get_task(task_id)
            if not task:
                continue

            frm = ttk.LabelFrame(main, text=task_names.get(task_id, task_id), padding=8)
            frm.pack(fill='x', pady=(0, 5))

            row = ttk.Frame(frm)
            row.pack(fill='x')

            enabled_var = tk.BooleanVar(value=task.enabled)
            self._auto_vars[task_id] = enabled_var
            ttk.Checkbutton(row, text='Включён', variable=enabled_var,
                            command=lambda tid=task_id: self._on_auto_toggle(tid)).pack(side='left')

            ttk.Label(row, text='Интервал (мин):').pack(side='left', padx=(20, 5))
            interval_var = tk.StringVar(value=str(task.interval_min))
            self._auto_interval_vars[task_id] = interval_var
            cb = ttk.Combobox(row, textvariable=interval_var, values=[str(x) for x in INTERVAL_OPTIONS],
                              width=5, state='readonly')
            cb.pack(side='left')
            cb.bind('<<ComboboxSelected>>', lambda e, tid=task_id: self._on_auto_interval(tid))

            lbl = ttk.Label(row, text=self._auto_status_text(task))
            lbl.pack(side='right')
            self._auto_labels[task_id] = lbl

        btn_row = ttk.Frame(main)
        btn_row.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_row, text='Запустить все', command=self._on_start_all_btn).pack(side='left', padx=(0, 5))
        ttk.Button(btn_row, text='Остановить все', command=self._on_stop_all_btn).pack(side='left')

    def _auto_status_text(self, task):
        if task.running:
            return 'Работает'
        elif task.enabled:
            return 'Ожидание'
        return 'Остановлен'

    def _on_auto_toggle(self, task_id):
        task = self.scheduler.get_task(task_id)
        if task:
            task.enabled = self._auto_vars[task_id].get()
            self.scheduler._save_config()
            self._auto_labels[task_id].config(text=self._auto_status_text(task))

    def _on_auto_interval(self, task_id):
        task = self.scheduler.get_task(task_id)
        if task:
            try:
                task.interval_min = int(self._auto_interval_vars[task_id].get())
                self.scheduler._save_config()
            except ValueError:
                pass

    def _on_start_all_btn(self):
        if self.on_start_all:
            self.on_start_all()

    def _on_stop_all_btn(self):
        if self.on_stop_all:
            self.on_stop_all()

    def _build_cloud(self, parent):
        from cloud.ui import CloudPanel
        CloudPanel(parent, self.root)

    def _build_strategies(self, parent):
        main = ttk.Frame(parent, padding=10)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text='Сохранённые стратегии для тикеров',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        info = ttk.Label(main, text='Управление стратегиями, сохранёнными для каждого тикера.\n'
                                     'Для изменения выберите тикер → нажмите «Удалить» или измените в основном окне.',
                         font=('Segoe UI', 9), foreground='gray')
        info.pack(anchor='w', pady=(0, 10))

        cols = ('Тикер', 'Стратегия', 'Параметры')
        self._strat_tree = ttk.Treeview(main, columns=cols, show='headings', height=18)
        for c in cols:
            self._strat_tree.heading(c, text=c)
        self._strat_tree.column('Тикер', width=100, minwidth=80)
        self._strat_tree.column('Стратегия', width=180, minwidth=120)
        self._strat_tree.column('Параметры', width=350, minwidth=200)

        vsb = ttk.Scrollbar(main, orient='vertical', command=self._strat_tree.yview)
        self._strat_tree.configure(yscrollcommand=vsb.set)
        self._strat_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        btn_row = ttk.Frame(main)
        btn_row.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_row, text='Удалить выбранную', command=self._delete_strat).pack(side='left')
        ttk.Button(btn_row, text='Удалить все', command=self._delete_all_strat).pack(side='left', padx=(5, 0))

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

    def _build_favorites(self, parent):
        main = ttk.Frame(parent, padding=10)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text='Избранные тикеры',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 10))

        info = ttk.Label(main, text='Перетаскивайте для изменения порядка. Удалите ненужные.',
                         font=('Segoe UI', 9), foreground='gray')
        info.pack(anchor='w', pady=(0, 10))

        list_frame = ttk.Frame(main)
        list_frame.pack(fill='both', expand=True)

        self._fav_listbox = tk.Listbox(list_frame, font=('Consolas', 11), selectmode='extended',
                                        bg='#2d2d2d', fg='#ffffff', selectbackground='#3d6b99')
        vsb = ttk.Scrollbar(list_frame, orient='vertical', command=self._fav_listbox.yview)
        self._fav_listbox.configure(yscrollcommand=vsb.set)
        self._fav_listbox.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        btn_row = ttk.Frame(main)
        btn_row.pack(fill='x', pady=(5, 0))

        ttk.Button(btn_row, text='Удалить выбранное', command=self._delete_fav).pack(side='left')
        ttk.Button(btn_row, text='Очистить все', command=self._clear_fav).pack(side='left', padx=(5, 0))

        self._load_favorites_list()

    def _load_favorites_list(self):
        self._fav_listbox.delete(0, 'end')
        for ticker in load_favorites():
            self._fav_listbox.insert('end', ticker)

    def _delete_fav(self):
        sel = self._fav_listbox.curselection()
        if not sel:
            return
        favorites = load_favorites()
        indices = sorted(sel, reverse=True)
        for i in indices:
            if i < len(favorites):
                del favorites[i]
        save_favorites(favorites)
        self._load_favorites_list()

    def _clear_fav(self):
        if not messagebox.askyesno('Очистить', 'Удалить все избранные тикеры?'):
            return
        save_favorites([])
        self._load_favorites_list()

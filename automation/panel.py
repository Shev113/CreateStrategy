import tkinter as tk
from tkinter import ttk
from datetime import datetime


INTERVAL_OPTIONS = [5, 10, 15, 20, 30, 60]


class AutomationPanel:
    def __init__(self, parent, scheduler, on_start_all=None, on_stop_all=None):
        self.scheduler = scheduler
        self.on_start_all = on_start_all
        self.on_stop_all = on_stop_all
        self._vars = {}
        self._labels = {}

        main = ttk.Frame(parent)
        main.pack(fill='both', expand=1, padx=10, pady=5)

        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        main.grid_rowconfigure(2, weight=1)
        main.grid_rowconfigure(3, weight=0)
        main.grid_rowconfigure(4, weight=2)
        main.grid_columnconfigure(0, weight=1)

        self._build_auto_scan(main, 0)
        self._build_monitor(main, 1)
        self._build_watchlist(main, 2)
        self._build_controls(main, 3)
        self._build_status(main, 4)

        self.scheduler.set_status_callback(self._refresh_status)

    def _build_auto_scan(self, parent, grid_row):
        frm = ttk.LabelFrame(parent, text='Автосканер')
        frm.grid(row=grid_row, column=0, sticky='nsew', pady=(0, 5))

        row1 = ttk.Frame(frm)
        row1.pack(fill='x', padx=5, pady=2)

        self._vars['auto_scan_enabled'] = tk.BooleanVar(
            value=self.scheduler.get_task('auto_scan').enabled
            if self.scheduler.get_task('auto_scan') else False)
        ttk.Checkbutton(row1, text='Включён', variable=self._vars['auto_scan_enabled'],
                        command=lambda: self._on_toggle('auto_scan')).pack(side='left')

        ttk.Label(row1, text='Интервал:').pack(side='left', padx=(15, 5))
        self._vars['auto_scan_interval'] = tk.StringVar(
            value=str(self.scheduler.get_task('auto_scan').interval_min
                      if self.scheduler.get_task('auto_scan') else 30))
        cb = ttk.Combobox(row1, textvariable=self._vars['auto_scan_interval'],
                          values=[str(x) for x in INTERVAL_OPTIONS], width=5, state='readonly')
        cb.pack(side='left')
        ttk.Label(row1, text='мин').pack(side='left', padx=2)

        ttk.Button(row1, text='Сканировать сейчас',
                   command=lambda: self.scheduler.run_task_now('auto_scan')).pack(side='right')

        row2 = ttk.Frame(frm)
        row2.pack(fill='x', padx=5, pady=2)
        self._labels['auto_scan_status'] = ttk.Label(row2, text='—')
        self._labels['auto_scan_status'].pack(side='left')

    def _build_monitor(self, parent, grid_row):
        frm = ttk.LabelFrame(parent, text='Мониторинг позиций')
        frm.grid(row=grid_row, column=0, sticky='nsew', pady=(0, 5))

        row1 = ttk.Frame(frm)
        row1.pack(fill='x', padx=5, pady=2)

        self._vars['monitor_enabled'] = tk.BooleanVar(
            value=self.scheduler.get_task('monitor_positions').enabled
            if self.scheduler.get_task('monitor_positions') else False)
        ttk.Checkbutton(row1, text='Включён', variable=self._vars['monitor_enabled'],
                        command=lambda: self._on_toggle('monitor_positions')).pack(side='left')

        ttk.Label(row1, text='Интервал:').pack(side='left', padx=(15, 5))
        self._vars['monitor_interval'] = tk.StringVar(
            value=str(self.scheduler.get_task('monitor_positions').interval_min
                      if self.scheduler.get_task('monitor_positions') else 5))
        cb = ttk.Combobox(row1, textvariable=self._vars['monitor_interval'],
                          values=[str(x) for x in [1, 2, 5, 10, 15, 30]], width=5, state='readonly')
        cb.pack(side='left')
        ttk.Label(row1, text='мин').pack(side='left', padx=2)

        ttk.Button(row1, text='Проверить сейчас',
                   command=lambda: self.scheduler.run_task_now('monitor_positions')).pack(side='right')

        row2 = ttk.Frame(frm)
        row2.pack(fill='x', padx=5, pady=2)

        self._vars['autostart'] = tk.BooleanVar(
            value=self.scheduler.get_autostart_monitor())
        ttk.Checkbutton(row2, text='Автозапуск при старте приложения',
                        variable=self._vars['autostart'],
                        command=self._on_autostart_toggle).pack(side='left')

        self._labels['monitor_status'] = ttk.Label(row2, text='—')
        self._labels['monitor_status'].pack(side='right')

    def _build_watchlist(self, parent, grid_row):
        frm = ttk.LabelFrame(parent, text='Обновление вочлиста')
        frm.grid(row=grid_row, column=0, sticky='nsew', pady=(0, 5))

        row1 = ttk.Frame(frm)
        row1.pack(fill='x', padx=5, pady=2)

        self._vars['watchlist_enabled'] = tk.BooleanVar(
            value=self.scheduler.get_task('refresh_watchlist').enabled
            if self.scheduler.get_task('refresh_watchlist') else False)
        ttk.Checkbutton(row1, text='Включён', variable=self._vars['watchlist_enabled'],
                        command=lambda: self._on_toggle('refresh_watchlist')).pack(side='left')

        ttk.Label(row1, text='Интервал:').pack(side='left', padx=(15, 5))
        self._vars['watchlist_interval'] = tk.StringVar(
            value=str(self.scheduler.get_task('refresh_watchlist').interval_min
                      if self.scheduler.get_task('refresh_watchlist') else 10))
        cb = ttk.Combobox(row1, textvariable=self._vars['watchlist_interval'],
                          values=[str(x) for x in INTERVAL_OPTIONS], width=5, state='readonly')
        cb.pack(side='left')
        ttk.Label(row1, text='мин').pack(side='left', padx=2)

        ttk.Button(row1, text='Обновить сейчас',
                   command=lambda: self.scheduler.run_task_now('refresh_watchlist')).pack(side='right')

        row2 = ttk.Frame(frm)
        row2.pack(fill='x', padx=5, pady=2)
        self._labels['watchlist_status'] = ttk.Label(row2, text='—')
        self._labels['watchlist_status'].pack(side='left')

    def _build_controls(self, parent, grid_row):
        frm = ttk.Frame(parent)
        frm.grid(row=grid_row, column=0, sticky='ew', pady=5)

        ttk.Button(frm, text='Запустить всё', command=self._on_start_all).pack(side='left', padx=5)
        ttk.Button(frm, text='Остановить всё', command=self._on_stop_all).pack(side='left', padx=5)

    def _build_status(self, parent, grid_row):
        frm = ttk.LabelFrame(parent, text='Статус')
        frm.grid(row=grid_row, column=0, sticky='nsew', pady=5)

        text_frame = ttk.Frame(frm)
        text_frame.pack(fill='both', expand=1, padx=5, pady=5)

        self._status_text = tk.Text(text_frame, height=8, font=('Consolas', 9),
                                    state='disabled', wrap='word')
        status_scroll = ttk.Scrollbar(text_frame, orient='vertical',
                                       command=self._status_text.yview)
        self._status_text.configure(yscrollcommand=status_scroll.set)
        self._status_text.pack(side='left', fill='both', expand=1)
        status_scroll.pack(side='right', fill='y')

    def _on_toggle(self, name):
        enabled = self._vars.get(f'{name}_enabled')
        if enabled is None:
            return
        is_on = enabled.get()
        interval_var = self._vars.get(f'{name.replace("monitor_positions", "monitor")}_interval')
        if name == 'monitor_positions':
            interval_var = self._vars.get('monitor_interval')
        elif name == 'auto_scan':
            interval_var = self._vars.get('auto_scan_interval')
        elif name == 'refresh_watchlist':
            interval_var = self._vars.get('watchlist_interval')

        if interval_var:
            try:
                minutes = int(interval_var.get())
                self.scheduler.set_interval(name, minutes)
            except ValueError:
                pass

        if is_on:
            self.scheduler.start_task(name)
        else:
            self.scheduler.stop_task(name)

    def _on_autostart_toggle(self):
        self.scheduler.set_autostart_monitor(self._vars['autostart'].get())

    def _on_start_all(self):
        for name in ['auto_scan', 'monitor_positions', 'refresh_watchlist']:
            var_key = f'{name}_enabled'
            if name == 'monitor_positions':
                var_key = 'monitor_enabled'
            elif name == 'refresh_watchlist':
                var_key = 'watchlist_enabled'
            v = self._vars.get(var_key)
            if v and v.get():
                self.scheduler.start_task(name)
        if self.on_start_all:
            self.on_start_all()

    def _on_stop_all(self):
        self.scheduler.stop_all()
        for key, var in self._vars.items():
            if key.endswith('_enabled'):
                var.set(False)
        if self.on_stop_all:
            self.on_stop_all()

    def _refresh_status(self):
        lines = []
        task_labels = {
            'auto_scan': 'Автосканер',
            'monitor_positions': 'Мониторинг',
            'refresh_watchlist': 'Вочлист',
        }
        for name, task in self.scheduler.get_all_tasks().items():
            label = task_labels.get(name, name)
            if task.is_running:
                status = f'Активен (каждые {task.interval_min} мин)'
                detail = f'последний: {task.last_run or "—"} | {task.last_result}'
            elif task.enabled:
                status = 'Ожидание'
                detail = ''
            else:
                status = 'Выключен'
                detail = ''
            lines.append(f'  {label}: {status}')
            if detail:
                lines.append(f'    {detail}')

        autostart = 'Да' if self.scheduler.get_autostart_monitor() else 'Нет'
        lines.append(f'\n  Автозапуск монитора: {autostart}')

        self._status_text.config(state='normal')
        self._status_text.delete('1.0', 'end')
        self._status_text.insert('end', '\n'.join(lines))
        self._status_text.config(state='disabled')

        for name, lbl in self._labels.items():
            task_name = name.replace('_status', '')
            if task_name == 'auto_scan':
                task_name = 'auto_scan'
            elif task_name == 'monitor':
                task_name = 'monitor_positions'
            elif task_name == 'watchlist':
                task_name = 'refresh_watchlist'
            task = self.scheduler.get_task(task_name)
            if task and task.is_running:
                lbl.config(text=f'Активен — след. через {task.interval_min} мин | {task.last_run or "—"}')
            elif task:
                lbl.config(text='Остановлен')

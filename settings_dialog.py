import json
import logging
import os
import tkinter as tk
from tkinter import ttk, messagebox

from news.provider import load_ai_config, save_ai_config, fetch_available_models, PROVIDER_MODELS, DEFAULT_MODELS
from utils import app_dir


class SettingsDialog:
    def __init__(self, root, scheduler=None, on_start_all=None, on_stop_all=None,
                 watchlist_ui_class=None, watchlist_callbacks=None, main_app=None,
                 on_ai_config_saved=None):
        self.root = root
        self.scheduler = scheduler
        self.on_start_all = on_start_all
        self.on_stop_all = on_stop_all
        self.watchlist_ui_class = watchlist_ui_class
        self.watchlist_callbacks = watchlist_callbacks or {}
        self.main_app = main_app
        self._on_ai_config_saved = on_ai_config_saved
        self._dialog = None
        self._nb = None
        self._strat_name_map = None
        self._strat_id_map = None

    def _ensure_strat_maps(self):
        if self._strat_name_map is not None:
            return
        from strategy.config import get_strategy_names
        names = get_strategy_names()
        self._strat_name_map = {sid: name for sid, name in names}
        self._strat_id_map = {name: sid for sid, name in names}

    def show(self, select_tab=None):
        if self._dialog and self._dialog.winfo_exists():
            if select_tab:
                for child in self._nb.tabs():
                    if self._nb.tab(child, 'text') == select_tab:
                        self._nb.select(child)
                        break
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

        self._nb = ttk.Notebook(self._dialog)
        self._nb.pack(fill='both', expand=True, padx=5, pady=5)

        tab_watchlist = ttk.Frame(self._nb)
        tab_auto = ttk.Frame(self._nb)
        tab_cloud = ttk.Frame(self._nb)
        tab_strategies = ttk.Frame(self._nb)
        tab_ai_news = ttk.Frame(self._nb)

        self._nb.add(tab_watchlist, text='Избранное')
        self._nb.add(tab_auto, text='Автоматизация')
        self._nb.add(tab_cloud, text='Облако')
        self._nb.add(tab_strategies, text='Стратегии')
        self._nb.add(tab_ai_news, text='AI Новости')

        self._scrollable_tabs = []
        self._build_watchlist(self._make_scrollable(tab_watchlist))
        self._build_automation(self._make_scrollable(tab_auto))
        self._build_cloud(self._make_scrollable(tab_cloud))
        self._build_strategies(self._make_scrollable(tab_strategies))
        self._build_ai_news(self._make_scrollable(tab_ai_news))

        if select_tab:
            for child in self._nb.tabs():
                if self._nb.tab(child, 'text') == select_tab:
                    self._nb.select(child)
                    break

        btn_frame = ttk.Frame(self._dialog)
        btn_frame.pack(fill='x', padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text='Закрыть', command=self._on_close).pack(side='right')

    def _on_close(self):
        if self.main_app is not None:
            self.main_app.watchlist_ui = None
        if self._dialog and self._dialog.winfo_exists():
            self._dialog.destroy()
        self._dialog = None

    def _make_scrollable(self, parent):
        """Wrap a tab frame in a Canvas + Scrollbar; returns inner frame for content."""
        canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0)
        vsb = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind('<Configure>',
                   lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=inner, anchor='nw', tags='inner')
        canvas.configure(yscrollcommand=vsb.set)

        def _on_canvas_resize(event):
            canvas.itemconfigure('inner', width=event.width)
        canvas.bind('<Configure>', _on_canvas_resize)

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        def _bind_wheel_recursive(widget):
            try:
                widget.bind('<MouseWheel>', _on_wheel)
            except Exception:
                pass
            for child in widget.winfo_children():
                _bind_wheel_recursive(child)

        def _do_bind():
            _bind_wheel_recursive(canvas)
            _bind_wheel_recursive(inner)
            for canvas_child in canvas.find_all():
                pass

        canvas.after(300, _do_bind)
        canvas.after(1000, _do_bind)

        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self._scrollable_tabs.append(canvas)
        return inner

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

    def _build_ai_news(self, parent):
        config = load_ai_config()
        status_var = tk.StringVar()

        main = ttk.Frame(parent, padding=15)
        main.pack(fill='both', expand=True)

        def refresh_models(*_args):
            prov = provider_var.get()
            endpoint_var.set({
                'github_models': 'https://models.github.ai/inference',
                'groq': 'https://api.groq.com/openai/v1',
                'rules': '',
            }.get(prov, endpoint_var.get()))
            if prov == 'rules':
                model_cb.configure(values=[])
                model_var.set('')
                return
            models = PROVIDER_MODELS.get(prov, [])
            model_cb.configure(values=models)
            cur = model_var.get()
            if cur not in models:
                model_var.set(DEFAULT_MODELS.get(prov, models[0] if models else ''))

        def load_models():
            prov = provider_var.get()
            if prov == 'rules':
                model_cb.configure(values=[])
                model_var.set('')
                return
            key = key_var.get()
            ep = endpoint_var.get()
            model_btn.configure(text='Загрузка...', state='disabled')
            status_var.set('')
            main.update_idletasks()
            try:
                models = fetch_available_models(prov, key, ep)
                model_cb.configure(values=models)
                cur = model_var.get()
                if cur not in models:
                    model_var.set(DEFAULT_MODELS.get(prov, models[0] if models else ''))
                status_var.set(f'Загружено {len(models)} моделей')
            except Exception as e:
                status_var.set(f'Ошибка загрузки: {e}')
            finally:
                model_btn.configure(text='Загрузить модели', state='normal')

        row = 0
        ttk.Label(main, text='Провайдер:', font=('Segoe UI', 10)).grid(
            row=row, column=0, sticky='e', pady=4)
        provider_var = tk.StringVar(value=config.get('provider', 'rules'))
        provider_cb = ttk.Combobox(main, textvariable=provider_var,
                                    values=['github_models', 'groq', 'rules'],
                                    width=25, state='readonly')
        provider_cb.grid(row=row, column=1, sticky='w', pady=4, padx=10)
        provider_cb.bind('<<ComboboxSelected>>', refresh_models)

        row += 1
        ttk.Label(main, text='API ключ:', font=('Segoe UI', 10)).grid(
            row=row, column=0, sticky='e', pady=4)
        key_var = tk.StringVar(value=config.get('api_key', ''))
        key_entry = ttk.Entry(main, textvariable=key_var, width=40, show='*')
        key_entry.grid(row=row, column=1, sticky='w', pady=4, padx=10)

        row += 1
        ttk.Label(main, text='Модель:', font=('Segoe UI', 10)).grid(
            row=row, column=0, sticky='e', pady=4)
        model_var = tk.StringVar(value=config.get('model', 'deepseek-large-fast'))
        model_frame = ttk.Frame(main)
        model_frame.grid(row=row, column=1, sticky='w', pady=4, padx=10)
        model_cb = ttk.Combobox(model_frame, textvariable=model_var, width=37, state='readonly')
        model_cb.pack(side='left')
        model_btn = ttk.Button(model_frame, text='Загрузить модели', command=load_models, width=16)
        model_btn.pack(side='left', padx=(5, 0))

        row += 1
        ttk.Label(main, text='Эндпоинт:', font=('Segoe UI', 10)).grid(
            row=row, column=0, sticky='e', pady=4)
        endpoint_var = tk.StringVar(value=config.get('endpoint', 'https://models.github.ai/inference'))
        endpoint_entry = ttk.Entry(main, textvariable=endpoint_var, width=50)
        endpoint_entry.grid(row=row, column=1, sticky='w', pady=4, padx=10)

        row += 1
        ttk.Separator(main, orient='horizontal').grid(
            row=row, column=0, columnspan=2, sticky='ew', pady=8)

        row += 1
        ttk.Label(main, text='Интервал скана (мин):', font=('Segoe UI', 10)).grid(
            row=row, column=0, sticky='e', pady=4)
        interval_var = tk.StringVar(value=str(config.get('auto_scan_interval_min', 15)))
        interval_entry = ttk.Entry(main, textvariable=interval_var, width=10)
        interval_entry.grid(row=row, column=1, sticky='w', pady=4, padx=10)

        row += 1
        ttk.Label(main, text='Макс. новостей:', font=('Segoe UI', 10)).grid(
            row=row, column=0, sticky='e', pady=4)
        max_var = tk.StringVar(value=str(config.get('max_news', 50)))
        max_entry = ttk.Entry(main, textvariable=max_var, width=10)
        max_entry.grid(row=row, column=1, sticky='w', pady=4, padx=10)

        def save():
            try:
                cfg = {
                    'provider': provider_var.get(),
                    'api_key': key_var.get(),
                    'model': model_var.get(),
                    'endpoint': endpoint_var.get(),
                    'auto_scan_interval_min': int(interval_var.get()),
                    'max_news': int(max_var.get()),
                }
                save_ai_config(cfg)
                status_var.set('Сохранено!')
                if self._on_ai_config_saved:
                    self._on_ai_config_saved()
            except Exception as e:
                status_var.set(f'Ошибка: {e}')

        def reset_defaults():
            provider_var.set('github_models')
            key_var.set('')
            endpoint_var.set('https://models.github.ai/inference')
            interval_var.set('15')
            max_var.set('50')
            status_var.set('')
            refresh_models()

        row += 1
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_frame, text='Сохранить', command=save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='По умолчанию', command=reset_defaults).pack(side='left', padx=5)

        row += 1
        ttk.Label(main, textvariable=status_var, foreground='green',
                  font=('Segoe UI', 10)).grid(
            row=row, column=0, columnspan=2, pady=(8, 0))

        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)

        provider_cb.after(100, refresh_models)

    def _build_strategies(self, parent):
        main = ttk.Frame(parent, padding=10)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text='Сохранённые стратегии для тикеров',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 5))

        ttk.Label(main, text='Двойной клик по строке — редактирование параметров стратегии.',
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

        self._strat_tree.bind('<Double-1>', self._on_strat_dblclick)

        btn_row = ttk.Frame(main)
        btn_row.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_row, text='Удалить выбранную', command=self._delete_strat).pack(side='left')
        ttk.Button(btn_row, text='Удалить все', command=self._delete_all_strat).pack(side='left', padx=(5, 0))
        ttk.Button(btn_row, text='Обновить', command=self._load_strategies).pack(side='right')

        self._load_strategies()

    def _load_strategies(self):
        for item in self._strat_tree.get_children():
            self._strat_tree.delete(item)

        self._ensure_strat_maps()
        path = os.path.join(app_dir(), 'results', 'ticker_settings.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        for ticker, cfg in sorted(data.items()):
            sid = cfg.get('strategy', '?')
            sname = self._strat_name_map.get(sid, sid)
            params = cfg.get('params', {})
            param_str = ', '.join(f'{k}={v}' for k, v in params.items()) if params else '-'
            self._strat_tree.insert('', 'end', iid=ticker, values=(ticker, sname, param_str))

    def _on_strat_dblclick(self, event):
        sel = self._strat_tree.selection()
        if not sel:
            return
        ticker = sel[0]
        self._open_strategy_detail(ticker)

    def _open_strategy_detail(self, ticker):
        path = os.path.join(app_dir(), 'results', 'ticker_settings.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        cfg = data.get(ticker, {})
        current_sid = cfg.get('strategy', 'bounce')
        current_params = cfg.get('params', {})

        self._ensure_strat_maps()
        from strategy.config import get_strategy_names, get_strategy_params, get_default_params

        win = tk.Toplevel(self._dialog or self.root)
        win.title(f'Стратегия: {ticker}')
        win.geometry('620x600')
        win.minsize(500, 400)
        win.transient(self._dialog or self.root)
        win.grab_set()

        try:
            win.iconbitmap('icon.ico')
        except Exception:
            pass

        frm = ttk.Frame(win, padding=15)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text=f'Тикер: {ticker}',
                  font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=(0, 10))

        strat_var = tk.StringVar()
        param_entries = {}

        def on_save():
            selected_name = strat_var.get()
            sid = self._strat_id_map.get(selected_name, 'bounce')
            new_params = {}
            for key, (var, ptype, _pdef) in param_entries.items():
                raw = var.get().strip()
                try:
                    if ptype == int:
                        new_params[key] = int(raw)
                    elif ptype == float:
                        new_params[key] = float(raw)
                    else:
                        new_params[key] = raw
                except ValueError:
                    new_params[key] = raw

            try:
                with open(path, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
            except Exception:
                all_data = {}

            all_data[ticker] = {'strategy': sid, 'params': new_params}
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                messagebox.showerror('Ошибка', f'Не удалось сохранить: {e}', parent=win)
                return

            self._load_strategies()
            win.destroy()

        def on_delete():
            if not messagebox.askyesno('Удалить', f'Удалить стратегию для {ticker}?', parent=win):
                return
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
                if ticker in all_data:
                    del all_data[ticker]
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(all_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                messagebox.showerror('Ошибка', f'Не удалось удалить: {e}', parent=win)
                return
            self._load_strategies()
            win.destroy()

        strat_frm = ttk.Frame(frm)
        strat_frm.pack(fill='x', pady=(0, 10))
        ttk.Label(strat_frm, text='Стратегия:', font=('Segoe UI', 10)).pack(side='left')
        strat_names = [name for _, name in get_strategy_names()]
        strat_cb = ttk.Combobox(strat_frm, textvariable=strat_var,
                                 values=strat_names, state='readonly', width=30)
        strat_cb.pack(side='left', padx=(10, 0))
        current_display = self._strat_name_map.get(current_sid, current_sid)
        strat_cb.set(current_display)
        ttk.Button(strat_frm, text='Сохранить', command=on_save).pack(side='left', padx=(10, 0))

        params_canvas = tk.Canvas(frm, highlightthickness=0)
        params_scroll = ttk.Scrollbar(frm, orient='vertical', command=params_canvas.yview)
        params_inner = ttk.Frame(params_canvas)
        params_inner.bind('<Configure>',
                          lambda e: params_canvas.configure(scrollregion=params_canvas.bbox('all')))
        params_canvas.create_window((0, 0), window=params_inner, anchor='nw')
        params_canvas.configure(yscrollcommand=params_scroll.set)

        def rebuild_params(*_args):
            for w in params_inner.winfo_children():
                w.destroy()
            param_entries.clear()

            selected_name = strat_var.get()
            sid = self._strat_id_map.get(selected_name, 'bounce')
            params_def = get_strategy_params(sid)
            defaults = get_default_params(sid)

            for i, p in enumerate(params_def):
                lbl = ttk.Label(params_inner, text=p.get('label', p['key']),
                                font=('Segoe UI', 9))
                lbl.grid(row=i, column=0, sticky='w', pady=2, padx=(0, 10))

                key = p['key']
                val = current_params.get(key) if sid == current_sid else defaults.get(key)
                if val is None:
                    val = p.get('default', '')

                ptype = p.get('type', str)
                if ptype == int and p.get('hint', '').count('=') >= 2:
                    cb_var = tk.StringVar(value=str(val))
                    entry = ttk.Combobox(params_inner, textvariable=cb_var,
                                         values=['0', '1', '2'], width=8, state='readonly')
                    entry.grid(row=i, column=1, sticky='ew', pady=2)
                    param_entries[key] = (cb_var, ptype, p)
                else:
                    sv = tk.StringVar(value=str(val))
                    entry = ttk.Entry(params_inner, textvariable=sv, width=18)
                    entry.grid(row=i, column=1, sticky='ew', pady=2)
                    param_entries[key] = (sv, ptype, p)

                hint = p.get('hint', '')
                if hint:
                    hint_lines = hint.split('\n')
                    short_hint = hint_lines[0] if hint_lines else ''
                    ttk.Label(params_inner, text=short_hint,
                              font=('Segoe UI', 8), foreground='gray').grid(
                        row=i, column=2, sticky='w', padx=(5, 0), pady=2)

            params_inner.columnconfigure(1, weight=1)

        strat_cb.bind('<<ComboboxSelected>>', rebuild_params)
        rebuild_params()

        params_canvas.pack(side='left', fill='both', expand=True)
        params_scroll.pack(side='right', fill='y')



    def _delete_strat(self):
        sel = self._strat_tree.selection()
        if not sel:
            return
        ticker = sel[0]
        if not messagebox.askyesno('Удалить', f'Удалить стратегию для {ticker}?'):
            return

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

# visual.py
# -*- coding: utf-8 -*-
import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime

import pandas as pd

from utils import normalize_numeric_params, sort_tickers_by_favorites, ToolTip, tree_batch_insert


def _tip(widget, text):
    """Attach a tooltip hint to a widget."""
    return ToolTip(widget, text)



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
                  on_sensitivity=None, on_fundamental=None,
                  on_heatmap=None,
                 favorites=None, on_toggle_favorite=None,
                 sector_db=None, on_pending=None):
        self.root = parent.winfo_toplevel()
        self._last_signal = None
        self._last_params = None
        self._favorites = favorites or []
        self._on_toggle_favorite = on_toggle_favorite
        self._sector_db = sector_db
        self._on_pending = on_pending

        # Разделяем вкладку на левую панель (управление) и правую (график)
        parent.grid_columnconfigure(0, weight=0, minsize=480)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        left_frame = ttk.Frame(parent)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        left_frame.grid_rowconfigure(9, weight=1)

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
        _tip(self.stock_combobox, 'Выберите тикер для загрузки данных и бэктеста')
        if all_tickers:
            self.stock_combobox.set(all_tickers[0] if self._all_tickers else all_tickers[0])

        self._star_btn = ttk.Button(ticker_frame, text='★', width=3,
                                    command=self._toggle_current_favorite)
        self._star_btn.pack(side=tk.LEFT, padx=(4, 0))
        _tip(self._star_btn, 'Добавить/удалить тикер в избранное')
        self._ticker_status_var = tk.StringVar()
        self._ticker_status_label = ttk.Label(ticker_frame, textvariable=self._ticker_status_var, foreground='gray')
        self._ticker_status_label.pack(side=tk.LEFT, padx=(8, 0))
        self._update_star_button()
        self._on_select = on_select
        self._select_after_id = None
        self.stock_combobox.bind('<<ComboboxSelected>>', lambda e: (self._restore_ticker_list(), self._load_ticker_settings(), self._update_star_button(), self._schedule_auto_fetch()))

        self._autocomplete_hit = False
        self.stock_combobox.bind('<KeyRelease>', self._on_ticker_keyrelease)

        ToolTip(self.stock_combobox, 'Выбор тикера акции для анализа.\nНачните вводить символ — список отфильтруется автоматически.\nТикеры сгруппированы по секторам экономики.')
        ToolTip(self._star_btn, 'Добавить тикер в избранное (★) или удалить (☆).\nИзбранные тикеры отображаются вверху списка.')

        label_start = ttk.Label(parent, text="Начальная дата (гггг-мм-дд):")
        label_start.grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.start_date_entry = ttk.Entry(parent)
        self.start_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        self.start_date_entry.insert(0, "2015-01-01")
        _tip(self.start_date_entry, 'Начальная дата загрузки истории (гггг-мм-дд)')
        ToolTip(self.start_date_entry, 'Начальная дата периода загрузки исторических свечей.\nФормат: гггг-мм-дд (например 2015-01-01).\nЧем длиннее период — тем точнее бэктест, но дольше загрузка.')

        label_end = ttk.Label(parent, text="Конечная дата (гггг-мм-дд):")
        label_end.grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.end_date_entry = ttk.Entry(parent)
        self.end_date_entry.grid(row=2, column=1, padx=5, pady=5, sticky='w')
        self.end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        _tip(self.end_date_entry, 'Конечная дата загрузки истории (гггг-мм-дд)')
        ToolTip(self.end_date_entry, 'Конечная дата периода загрузки исторических свечей.\nФормат: гггг-мм-дд.\nПо умолчанию — текущая дата.')

        parent.grid_rowconfigure(8, weight=1)

        self.result_text = tk.Text(parent, height=6, width=55)
        self.result_text.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        _add_copy_menu(self.result_text)
        ToolTip(self.result_text, 'Журнал загрузки данных и статуса операций.\nПоказывает прогресс, ошибки и количество загруженных свечей.', delay=300)

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
        ToolTip(self._strategy_combo, 'Выбор торговой стратегии для тестирования.\nПри смене стратегии параметры ниже обновляются автоматически.\nКаждая стратегия использует свой набор индикаторов и правил входа/выхода.')

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
        ToolTip(self.get_data_button, 'Загрузить дневные свечи с MOEX ISS за указанный период.\nДанные кэшируются — повторная загрузка того же тикера быстрее.\nНеобходимо перед запуском бэктеста или оптимизации.')

        self.backtest_button = ttk.Button(
            action_frame, text="2. Backtest", command=on_backtest)
        self.backtest_button.grid(row=0, column=1, padx=2, pady=1)
        ToolTip(self.backtest_button, 'Запустить бэктест выбранной стратегии с текущими параметрами.\nПоказывает: количество сделок, win-rate, профит-фактор,\nмакс. просадку, доходность и кривую equity.')

        self.optimize_button = ttk.Button(
            action_frame, text="3. Оптимизация", command=lambda: on_optimize() if on_optimize else None)
        self.optimize_button.grid(row=0, column=2, padx=2, pady=1)
        ToolTip(self.optimize_button, 'Автоматический подбор параметров стратегии (grid-search).\nПеребирает комбинации и показывает топ-5 результатов.\nМожно применить лучший набор параметров одним кликом.\nТребует предварительно загруженных данных.')

        self.portfolio_button = ttk.Button(
            action_frame, text="4. Портфель", command=lambda: on_portfolio() if on_portfolio else None)
        self.portfolio_button.grid(row=1, column=0, padx=2, pady=1)
        ToolTip(self.portfolio_button, 'Бэктест стратегии на всех тикерах из торгового дневника.\nКапитал распределяется поровну между инструментами.\nПоказывает агрегированную кривую equity и статистику по каждому тикеру.')

        self.walkforward_button = ttk.Button(
            action_frame, text="5. Walk-fwd", command=lambda: on_walkforward() if on_walkforward else None)
        self.walkforward_button.grid(row=1, column=1, padx=2, pady=1)
        ToolTip(self.walkforward_button, 'Walk-forward анализ — проверка устойчивости параметров.\nДанные разбиваются на окна: обучение → тест → сдвиг.\nПоказывает, как стратегия ведёт себя на данных вне выборки.\nПомогает избежать переобучения.')

        self.sensitivity_button = ttk.Button(
            action_frame, text="6. Чувств.", command=lambda: on_sensitivity() if on_sensitivity else None)
        self.sensitivity_button.grid(row=1, column=2, padx=2, pady=1)
        ToolTip(self.sensitivity_button, 'Анализ чувствительности — насколько результат зависит от параметров.\nВарьирует каждый параметр ±5/10/20% и показывает влияние на Sharpe.\nПомогает понять, какие параметры критичны, а какие нет.')

        self.fundamental_button = ttk.Button(
            action_frame, text="7. Фундам.", command=lambda: on_fundamental() if on_fundamental else None)
        self.fundamental_button.grid(row=1, column=3, padx=2, pady=1)
        ToolTip(self.fundamental_button, 'Фундаментальный анализ — мультипликаторы, дивиденды, скоринг.\nP/E, P/B, дивидендная доходность, капитализация,\nистория дивидендов и рекомендация ПОКУПАТЬ/ДЕРЖАТЬ/ИЗБЕГАТЬ.')

        self.heatmap_button = ttk.Button(
            action_frame, text="8. Heatmap", command=lambda: on_heatmap() if on_heatmap else None)
        self.heatmap_button.grid(row=1, column=4, padx=2, pady=1)
        ToolTip(self.heatmap_button, '2D-тепловая карта — как два параметра влияют на метрику.\nПомогает визуально найти оптимальную зону параметров.')

        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)
        action_frame.grid_columnconfigure(2, weight=1)
        action_frame.grid_columnconfigure(3, weight=1)

        # Second btn row: Настройки, В дневник, Индивид., Сохранить
        btn_row = ttk.Frame(parent)
        btn_row.grid(row=7, column=0, columnspan=2, pady=1)

        self.save_settings_btn = ttk.Button(
            btn_row, text="Настройки", width=10,
            command=lambda: self._save_current_settings())
        self.save_settings_btn.pack(side=tk.LEFT, padx=2)
        ToolTip(self.save_settings_btn, 'Сохранить текущие параметры и стратегию для выбранного тикера.\nПри следующем выборе этого тикера настройки восстановятся автоматически.\nХранится в results/ticker_settings.json')

        self.diary_btn = ttk.Button(
            btn_row, text="В дневник", width=9,
            command=lambda: on_diary() if on_diary else None)
        self.diary_btn.pack(side=tk.LEFT, padx=2)
        self.diary_btn.config(state='disabled')
        ToolTip(self.diary_btn, 'Добавить последний сигнал (с параметрами и результатом)\nв торговый дневник для отслеживания сделок.\nДневник сохраняется в results/diary.json')

        self.pending_btn = ttk.Button(
            btn_row, text="В ожидание", width=10,
            command=lambda: self._on_pending() if self._on_pending else None)
        self.pending_btn.pack(side=tk.LEFT, padx=2)
        self.pending_btn.config(state='disabled')
        ToolTip(self.pending_btn, 'Поставить лимитный ордер на вход по уровню сигнала.\nМонитор автоматически отследит касание цены\nи переведёт ордер в дневник как открытую сделку.\nФайл: results/pending_trades.json')

        self._on_show_settings = on_show_settings
        self._settings_btn = ttk.Button(
            btn_row, text="Индивид.", width=9,
            command=lambda: self._show_settings())
        self._settings_btn.pack(side=tk.LEFT, padx=2)
        ToolTip(self._settings_btn, 'Индивидуальные настройки параметров для конкретного тикера.\nПозволяет задать кастомные уровни стопов и тейков,\nотличающиеся от стандартных параметров стратегии.')

        self._save_results_btn = ttk.Button(
            btn_row, text="Сохранить", width=9,
            command=lambda: on_save_results() if on_save_results else None)
        self._save_results_btn.pack(side=tk.LEFT, padx=2)
        self._save_results_btn.config(state='disabled')
        ToolTip(self._save_results_btn, 'Сохранить результаты последнего бэктеста / оптимизации.\nФорматы: CSV (таблица) или JSON (структурированные данные).\nФайлы сохраняются в папку results/')

        risk_frame = ttk.LabelFrame(parent, text='Лимиты портфеля')
        risk_frame.grid(row=8, column=0, columnspan=2, padx=5, pady=(2, 0), sticky='ew')

        ttk.Label(risk_frame, text='Макс. поз.').grid(row=0, column=0, padx=2, sticky='e')
        self.max_positions_entry = ttk.Entry(risk_frame, width=5)
        self.max_positions_entry.insert(0, '5')
        self.max_positions_entry.grid(row=0, column=1, padx=2)
        ToolTip(self.max_positions_entry, 'Максимальное число одновременно открытых позиций.\n0 = без лимита. При достижении лимита новые входы блокируются.')

        ttk.Label(risk_frame, text='Стоп-DD %').grid(row=0, column=2, padx=2, sticky='e')
        self.max_drawdown_entry = ttk.Entry(risk_frame, width=5)
        self.max_drawdown_entry.insert(0, '15')
        self.max_drawdown_entry.grid(row=0, column=3, padx=2)
        ToolTip(self.max_drawdown_entry, 'Портфельный стоп при просадке (%).\nЕсли просадка портфеля >= порога — новые входы блокируются.\n0 = без лимита.')

        ttk.Label(risk_frame, text='Охлаждение').grid(row=0, column=4, padx=2, sticky='e')
        self.cooldown_entry = ttk.Entry(risk_frame, width=5)
        self.cooldown_entry.insert(0, '0')
        self.cooldown_entry.grid(row=0, column=5, padx=2)
        ToolTip(self.cooldown_entry, 'Число свечей после срабатывания стоп-просадки,\nпрежде чем разрешить новые входы.\n0 = возобновить входы сразу после снижения просадки.')

        ttk.Label(risk_frame, text='Сектор %').grid(row=0, column=6, padx=2, sticky='e')
        self.sector_exposure_entry = ttk.Entry(risk_frame, width=5)
        self.sector_exposure_entry.insert(0, '30')
        self.sector_exposure_entry.grid(row=0, column=7, padx=2)
        ToolTip(self.sector_exposure_entry, 'Макс. доля капитала в одном секторе (%).\n30 = не более 30% капитала в одном секторе.\n0 = без лимита. Требуется загрузка секторов.')

        ttk.Label(risk_frame, text='Взвешивание').grid(row=0, column=8, padx=(10, 2), sticky='e')
        self.weighting_var = tk.StringVar(value='equal')
        self.weighting_combo = ttk.Combobox(risk_frame, textvariable=self.weighting_var,
                                            values=['equal', 'risk_parity', 'min_variance'],
                                            state='readonly', width=12)
        self.weighting_combo.grid(row=0, column=9, padx=2)
        ToolTip(self.weighting_combo, 'Способ распределения капитала между тикерами.\n'
                'equal: равномерное (1/N).\n'
                'risk_parity: обратно пропорц. волатильности.\n'
                'min_variance: минимум портфельной дисперсии.')

        parent.grid_rowconfigure(10, weight=1)

        self.top_signals_frame = ttk.LabelFrame(parent, text='Последние сигналы')
        self.top_signals_frame.grid(row=9, column=0, columnspan=2, padx=5, pady=(2, 0), sticky='ew')
        self._top_signals_labels = []
        for i in range(5):
            lbl = ttk.Label(self.top_signals_frame, text='', font=('Consolas', 9), anchor='w')
            lbl.pack(fill=tk.X, padx=3, pady=1)
            self._top_signals_labels.append(lbl)

        self.backtest_text = tk.Text(parent, height=8, width=55)
        self.backtest_text.grid(row=10, column=0, columnspan=2, padx=5, pady=5, sticky='nsew')
        _add_copy_menu(self.backtest_text)
        ToolTip(self.backtest_text, 'Результаты бэктеста, оптимизации, портфеля и walk-forward.\nПоказывает статистику сделок, профит-фактор, просадку и т.д.\nПравый клик — копировать выделенное.', delay=300)

    def enable_save_results_button(self):
        self._save_results_btn.config(state='normal')

    def disable_save_results_button(self):
        self._save_results_btn.config(state='disabled')

    def update_top_signals(self, signals: list):
        if not hasattr(self, '_top_signals_labels'):
            return
        side_icons = {'Лонг': '\u25b2', 'Шорт': '\u25bc'}
        side_colors = {'Лонг': '#008800', 'Шорт': '#cc0000'}
        for i, lbl in enumerate(self._top_signals_labels):
            if i < len(signals):
                s = signals[i]
                side = s.get('side', '')
                icon = side_icons.get(side, '')
                color = side_colors.get(side, '')
                ticker = s.get('ticker', '')
                price = s.get('price', '')
                price_str = f'@ {price:.2f}' if price and isinstance(price, (int, float)) else ''
                strategy = s.get('strategy', '')
                lbl.configure(text=f'{icon} {ticker} {side} {price_str}  [{strategy}]')
                try:
                    lbl.configure(foreground=color)
                except Exception:
                    pass
            else:
                lbl.configure(text='', foreground='')

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

    def _schedule_auto_fetch(self):
        if self._select_after_id:
            self.root.after_cancel(self._select_after_id)
        self._select_after_id = self.root.after(500, self._do_auto_fetch)

    def _do_auto_fetch(self):
        self._select_after_id = None
        if self._on_select:
            self._on_select()

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
            f"Доля прибыльных:    {metrics['win_rate']:.1f} %",
            f"Профит-фактор:      {metrics['profit_factor']}",
            f"Макс. просадка:     -{metrics['max_drawdown']:.2f} %",
            f"Коэф. Шарпа:        {metrics['sharpe']}",
            "",
        ]
        # Advanced metrics (only when include_advanced was used upstream).
        sortino = metrics.get('sortino')
        calmar = metrics.get('calmar')
        var_95 = metrics.get('var_95')
        cvar_95 = metrics.get('cvar_95')
        ulcer = metrics.get('ulcer_index')
        if any(v is not None for v in (sortino, calmar, var_95, cvar_95, ulcer)):
            lines.append("-- Риск-метрики --")
            if sortino is not None:
                lines.append(f"Коэф. Сортино:      {sortino}")
            if calmar is not None:
                lines.append(f"Коэф. Кальмара:     {calmar}")
            if var_95 is not None:
                lines.append(f"VaR (95%):          {var_95:+.2f} %")
            if cvar_95 is not None:
                lines.append(f"CVaR (95%):         {cvar_95:+.2f} %")
            if ulcer is not None:
                lines.append(f"Индекс Язвы:        {ulcer:.2f}")
            lines.append("")

        lines.append(f"Средняя прибыль:    {metrics['avg_win']:+,.2f} руб" if metrics.get('avg_win') else "")
        lines.append(f"Средний убыток:     {metrics['avg_loss']:+,.2f} руб" if metrics.get('avg_loss') else "")
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
            self.pending_btn.config(state='normal')
        else:
            self.diary_btn.config(state='disabled')
            self.pending_btn.config(state='disabled')

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
                ToolTip(combo, pcfg.get('hint', ''))
            elif pcfg['key'] == 'trailing_sl':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=14, font=('', 8),
                    values=['Выкл', 'Фикс. отступ', 'По MA'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
                ToolTip(combo, pcfg.get('hint', ''))
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

        for pcfg in params_config:
            entry = self._param_entries.get(pcfg['key'])
            hint = pcfg.get('hint', '')
            if entry and hint:
                ToolTip(entry, hint)

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

    def get_portfolio_risk_params(self):
        try:
            max_pos = int(self.max_positions_entry.get().strip())
            max_dd = float(self.max_drawdown_entry.get().strip())
            cooldown = int(self.cooldown_entry.get().strip())
            sector_pct = float(self.sector_exposure_entry.get().strip())
            return {
                'max_open_positions': max_pos,
                'max_drawdown_pct': max_dd,
                'cooldown_bars': cooldown,
                'max_sector_exposure': sector_pct / 100.0,
                'weighting': self.weighting_var.get(),
            }
        except (ValueError, TypeError):
            return None

    def _settings_path(self):
        import os
        from utils import app_dir
        return os.path.join(app_dir(), 'results', 'ticker_settings.json')

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
        ToolTip(self._strategy_combo, 'Выбор стратегии для сканирования.\nКаждая стратегия использует свой набор индикаторов.\nПараметры ниже обновятся автоматически при смене стратегии.')
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
        ToolTip(self.scanner_date_from, 'Начальная дата периода для сканирования.\nФормат: гггг-мм-дд.\nВлияет на расчёт индикаторов и уровней.')

        ttk.Label(date_frame, text="До:").pack(side=tk.LEFT, padx=2)
        self.scanner_date_to = ttk.Entry(date_frame, width=12)
        self.scanner_date_to.pack(side=tk.LEFT, padx=2)
        self.scanner_date_to.insert(0, datetime.now().strftime("%Y-%m-%d"))
        ToolTip(self.scanner_date_to, 'Конечная дата периода для сканирования.\nФормат: гггг-мм-дд.\nПо умолчанию — текущая дата.')

        fund_frame = ttk.LabelFrame(parent, text='Фундаментальный фильтр', padding=3)
        fund_frame.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        row += 1

        ff_row1 = ttk.Frame(fund_frame)
        ff_row1.pack(fill=tk.X, pady=1)
        ttk.Label(ff_row1, text='Мин. див.%:').pack(side=tk.LEFT, padx=2)
        self.fund_min_div = ttk.Entry(ff_row1, width=6)
        self.fund_min_div.pack(side=tk.LEFT, padx=2)
        self.fund_min_div.insert(0, '0')

        ttk.Label(ff_row1, text='Макс. P/E:').pack(side=tk.LEFT, padx=(10, 2))
        self.fund_max_pe = ttk.Entry(ff_row1, width=6)
        self.fund_max_pe.pack(side=tk.LEFT, padx=2)
        self.fund_max_pe.insert(0, '0')

        ttk.Label(ff_row1, text='Мин. капит. (млрд):').pack(side=tk.LEFT, padx=(10, 2))
        self.fund_min_cap = ttk.Entry(ff_row1, width=8)
        self.fund_min_cap.pack(side=tk.LEFT, padx=2)
        self.fund_min_cap.insert(0, '0')

        self.fund_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ff_row1, text='Применить', variable=self.fund_enabled_var).pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(fund_frame, 'Фильтр по фундаментальным показателям.\nМин. див.% — минимальная дивидендная доходность.\nМакс. P/E — максимальный P/E (0 = не фильтровать).\nМин. капит. — минимальная капитализация в млрд руб.\nВключите чекбокс «Применить» для активации.')

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        self.scan_button = ttk.Button(
            btn_frame, text="Запустить сканер", command=on_scan)
        self.scan_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.scan_button, 'Запустить сканирование всех эмитентов выбранных секторов.\nПроверяет стратегию на каждом тикере и показывает сигналы.\nПрогресс отображается в полосе ниже.')

        self.legend_button = ttk.Button(
            btn_frame, text="Скрыть легенду",
            command=lambda: self._toggle_legend())
        self.legend_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.legend_button, 'Показать/скрыть панель легенды сигналов.\nЛегенда объясняет обозначения цветов и значков в результатах.')

        self.export_excel_button = ttk.Button(
            btn_frame, text="Экспорт в Excel",
            command=lambda: self._request_excel())
        self.export_excel_button.pack(side=tk.LEFT, padx=5)
        self.export_excel_button.config(state='disabled')
        ToolTip(self.export_excel_button, 'Экспортировать результаты сканирования в Excel-файл.\nВключает все сигналы, параметры и метрики.\nДоступно после завершения сканирования.')

        self.diary_button = ttk.Button(
            btn_frame, text="В дневник",
            command=lambda: self._request_diary())
        self.diary_button.pack(side=tk.LEFT, padx=5)
        self.diary_button.config(state='disabled')
        ToolTip(self.diary_button, 'Добавить выбранный сигнал в торговый дневник.\nДневник хранится в results/diary.json.\nДоступно после завершения сканирования.')

        self.settings_button = ttk.Button(
            btn_frame, text="Индивид. настройки",
            command=lambda: self._request_show_settings())
        self.settings_button.pack(side=tk.LEFT, padx=5)
        ToolTip(self.settings_button, 'Индивидуальные настройки параметров для тикера.\nПозволяет задать кастомные уровни стопов и тейков\nдля конкретного инструмента.')

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
                ToolTip(combo, pcfg.get('hint', ''))
            elif pcfg['key'] == 'trailing_sl':
                combo = ttk.Combobox(
                    self._params_frame, state='readonly', width=14, font=('', 8),
                    values=['Выкл', 'Фикс. отступ', 'По MA'])
                combo.current(pcfg['default'])
                combo.grid(row=row_num, column=col + 1, padx=(0, 4), sticky='w')
                self._param_entries[pcfg['key']] = combo
                ToolTip(combo, pcfg.get('hint', ''))
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

        for pcfg in params_config:
            entry = self._param_entries.get(pcfg['key'])
            hint = pcfg.get('hint', '')
            if entry and hint:
                ToolTip(entry, hint)

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

    def get_fund_filter(self):
        enabled = self.fund_enabled_var.get()
        if not enabled:
            return None
        try:
            min_div = float(self.fund_min_div.get().strip())
        except (ValueError, TypeError):
            min_div = 0
        try:
            max_pe = float(self.fund_max_pe.get().strip())
        except (ValueError, TypeError):
            max_pe = 0
        try:
            min_cap = float(self.fund_min_cap.get().strip())
        except (ValueError, TypeError):
            min_cap = 0
        criteria = {}
        if min_div > 0:
            criteria['min_div_yield'] = min_div
        if max_pe > 0:
            criteria['max_pe'] = max_pe
        if min_cap > 0:
            criteria['min_market_cap'] = min_cap * 1e9
        return criteria if criteria else None

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
            {'key': 'min_trades', 'label': 'Мин.сд.', 'default': '10', 'width': 6},
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

        strategy_reverse = {sid: name for sid, name in self._strategy_names}

        items = []
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
        entries = self.storage.load()
        items = []
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
            items.append({'values': values, 'tags': tags})

        tree_batch_insert(self.tree, items)

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
        from utils import app_dir
        os.makedirs(os.path.join(app_dir(), 'results'), exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(app_dir(), f'results/diary_{ts}.csv')
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

        from guide_text import GUIDE_LINES as lines

        text.configure(state='normal')
        text.insert('1.0', '\n'.join(lines))
        text.configure(state='disabled')
        text.see('1.0')


class PositionDashboardUI:
    COLUMNS = ('ticker', 'side', 'entry_price', 'current_price', 'pnl',
               'pnl_pct', 'sl_price', 'tp_price', 'dist_sl', 'dist_tp', 'status')

    HEADERS = {
        'ticker': 'Тикер', 'side': 'Напр.', 'entry_price': 'Вход',
        'current_price': 'Текущая', 'pnl': 'P&L (₽)', 'pnl_pct': 'P&L %',
        'sl_price': 'SL', 'tp_price': 'TP',
        'dist_sl': 'До SL %', 'dist_tp': 'До TP %', 'status': 'Статус',
    }

    WIDTHS = {
        'ticker': 70, 'side': 55, 'entry_price': 80, 'current_price': 80,
        'pnl': 90, 'pnl_pct': 70, 'sl_price': 75, 'tp_price': 75,
        'dist_sl': 70, 'dist_tp': 70, 'status': 80,
    }

    STATUS_LABELS = {
        'profit': 'В прибыли',
        'loss': 'В убытке',
        'near_sl': 'Близко SL',
        'near_tp': 'Близко TP',
        'ok': 'Нейтрально',
    }

    def __init__(self, parent, on_refresh=None, on_start_monitor=None,
                 on_stop_monitor=None):
        self.parent = parent
        self._on_refresh = on_refresh
        self._on_start_monitor = on_start_monitor
        self._on_stop_monitor = on_stop_monitor
        self._monitor_running = False

        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl_frame = ttk.Frame(top_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 5))

        self.refresh_btn = ttk.Button(ctrl_frame, text='Обновить сейчас',
                                      command=self._on_refresh_click)
        self.refresh_btn.pack(side=tk.LEFT, padx=2)

        self.monitor_btn = ttk.Button(ctrl_frame, text='Запустить монитор',
                                       command=self._toggle_monitor)
        self.monitor_btn.pack(side=tk.LEFT, padx=2)
        ToolTip(self.monitor_btn, 'Автоматическая периодическая проверка открытых позиций.\nПредупреждает о приближении к SL/TP и срабатывании.')

        ttk.Label(ctrl_frame, text='Интервал (мин):').pack(side=tk.LEFT, padx=(10, 2))
        self.interval_entry = ttk.Entry(ctrl_frame, width=4)
        self.interval_entry.insert(0, '5')
        self.interval_entry.pack(side=tk.LEFT, padx=2)
        ToolTip(self.interval_entry, 'Интервал авто-проверки в минутах (мин. 0.5).')

        ttk.Label(ctrl_frame, text='Порог близости %:').pack(side=tk.LEFT, padx=(10, 2))
        self.near_entry = ttk.Entry(ctrl_frame, width=4)
        self.near_entry.insert(0, '3')
        self.near_entry.pack(side=tk.LEFT, padx=2)
        ToolTip(self.near_entry, 'Расстояние до SL/TP в % от цены входа,\nпри котором выводится предупреждение.')

        self.status_label = ttk.Label(ctrl_frame, text='Монитор: остановлен')
        self.status_label.pack(side=tk.RIGHT, padx=5)

        tree_frame = ttk.Frame(top_frame)
        tree_frame.pack(fill=tk.BOTH, expand=1)

        self.tree = ttk.Treeview(
            tree_frame, columns=self.COLUMNS, show='headings',
            height=15, selectmode='browse'
        )

        for col in self.COLUMNS:
            self.tree.heading(col, text=self.HEADERS[col])
            self.tree.column(col, width=self.WIDTHS[col], anchor='center')

        scroll_y = ttk.Scrollbar(tree_frame, orient='vertical',
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure('profit', foreground='#00aa00')
        self.tree.tag_configure('loss', foreground='#cc0000')
        self.tree.tag_configure('near_sl', foreground='#ff8800')
        self.tree.tag_configure('near_tp', foreground='#0088ff')
        self.tree.tag_configure('ok', foreground='')

        self.alert_text = tk.Text(top_frame, height=4, width=80, state='disabled')
        self.alert_text.pack(fill=tk.X, pady=(5, 0))

    def _on_refresh_click(self):
        if self._on_refresh:
            self._on_refresh()

    def _toggle_monitor(self):
        if self._monitor_running:
            if self._on_stop_monitor:
                self._on_stop_monitor()
            self._monitor_running = False
            self.monitor_btn.config(text='Запустить монитор')
            self.status_label.config(text='Монитор: остановлен')
        else:
            if self._on_start_monitor:
                self._on_start_monitor()
            self._monitor_running = True
            self.monitor_btn.config(text='Остановить монитор')
            self.status_label.config(text='Монитор: активен')

    def set_monitor_running(self, running):
        self._monitor_running = running
        if running:
            self.monitor_btn.config(text='Остановить монитор')
            self.status_label.config(text='Монитор: активен')
        else:
            self.monitor_btn.config(text='Запустить монитор')
            self.status_label.config(text='Монитор: остановлен')

    def get_interval_sec(self):
        try:
            val = float(self.interval_entry.get().strip())
            return max(val * 60, 30)
        except (ValueError, TypeError):
            return 300

    def get_near_distance_pct(self):
        try:
            return float(self.near_entry.get().strip())
        except (ValueError, TypeError):
            return 3.0

    def update_positions(self, positions):
        items = []
        for p in positions:
            status = p.get('status', 'ok')
            tag = status if status in ('profit', 'loss', 'near_sl', 'near_tp') else 'ok'
            values = (
                p.get('ticker', ''),
                p.get('side', ''),
                f"{p.get('entry_price', 0):.2f}" if p.get('entry_price') else '',
                f"{p.get('current_price', 0):.2f}" if p.get('current_price') else '—',
                f"{p.get('pnl', 0):+.2f}" if p.get('pnl') is not None else '—',
                f"{p.get('pnl_pct', 0):+.2f}" if p.get('pnl_pct') is not None else '—',
                f"{p.get('sl_price', 0):.2f}" if p.get('sl_price') else '',
                f"{p.get('tp_price', 0):.2f}" if p.get('tp_price') else '',
                f"{p.get('distance_sl_pct', 0):.1f}" if p.get('distance_sl_pct') is not None else '—',
                f"{p.get('distance_tp_pct', 0):.1f}" if p.get('distance_tp_pct') is not None else '—',
                self.STATUS_LABELS.get(status, status),
            )
            items.append({'values': values, 'tags': (tag,)})

        tree_batch_insert(self.tree, items)

    def update_alerts(self, alerts):
        self.alert_text.configure(state='normal')
        self.alert_text.delete('1.0', tk.END)
        if alerts:
            lines = []
            for a in alerts:
                if a.ticker:
                    lines.append(f"⚠ {a.message}")
                else:
                    lines.append(f"📋 {a.message}")
            self.alert_text.insert(tk.END, '\n'.join(lines))
        else:
            self.alert_text.insert(tk.END, 'Предупреждений нет.')
        self.alert_text.configure(state='disabled')


class TradeReviewUI:
    BREAKDOWN_COLS = ('key', 'count', 'wins', 'win_rate', 'pnl')
    BREAKDOWN_HEADERS = {
        'key': 'Категория', 'count': 'Сделок', 'wins': 'Выигрышей',
        'win_rate': 'WR %', 'pnl': 'P&L',
    }
    BREAKDOWN_WIDTHS = {
        'key': 120, 'count': 60, 'wins': 75, 'win_rate': 60, 'pnl': 100,
    }

    def __init__(self, parent, on_refresh=None):
        self.parent = parent
        self._on_refresh = on_refresh
        self._last_result = None

        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(ctrl_frame, text='Обновить анализ',
                   command=self._refresh).pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl_frame, text='Капитал:').pack(side=tk.LEFT, padx=(15, 2))
        self.capital_entry = ttk.Entry(ctrl_frame, width=12)
        self.capital_entry.insert(0, '1000000')
        self.capital_entry.pack(side=tk.LEFT, padx=2)

        self.summary_label = ttk.Label(ctrl_frame, text='', font=('', 9))
        self.summary_label.pack(side=tk.RIGHT, padx=5)

        paned = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=1)

        top_pane = ttk.Frame(paned)
        paned.add(top_pane, weight=2)

        mid_pane = ttk.Frame(paned)
        paned.add(mid_pane, weight=2)

        bot_pane = ttk.Frame(paned)
        paned.add(bot_pane, weight=1)

        self.report_text = tk.Text(top_pane, wrap=tk.WORD, font=('Consolas', 9))
        report_scroll = ttk.Scrollbar(top_pane, orient='vertical',
                                       command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=report_scroll.set)
        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        report_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        breakdown_nb = ttk.Notebook(mid_pane)
        breakdown_nb.pack(fill=tk.BOTH, expand=1)

        self.ticker_frame = ttk.Frame(breakdown_nb)
        self.side_frame = ttk.Frame(breakdown_nb)
        self.reason_frame = ttk.Frame(breakdown_nb)
        self.month_frame = ttk.Frame(breakdown_nb)
        self.dow_frame = ttk.Frame(breakdown_nb)

        breakdown_nb.add(self.ticker_frame, text='По тикерам')
        breakdown_nb.add(self.side_frame, text='По направлению')
        breakdown_nb.add(self.reason_frame, text='По причине')
        breakdown_nb.add(self.month_frame, text='По месяцам')
        breakdown_nb.add(self.dow_frame, text='По дням')

        self.ticker_tree = self._make_breakdown_tree(self.ticker_frame)
        self.side_tree = self._make_breakdown_tree(self.side_frame)
        self.reason_tree = self._make_breakdown_tree(self.reason_frame)
        self.month_tree = self._make_breakdown_tree(self.month_frame)
        self.dow_tree = self._make_breakdown_tree(self.dow_frame)

        self.chart_canvas = None
        self.chart_frame = bot_pane

    def _make_breakdown_tree(self, parent):
        tree = ttk.Treeview(parent, columns=self.BREAKDOWN_COLS,
                            show='headings', height=8)
        for col in self.BREAKDOWN_COLS:
            tree.heading(col, text=self.BREAKDOWN_HEADERS[col])
            tree.column(col, width=self.BREAKDOWN_WIDTHS[col], anchor='center')
        scroll = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.tag_configure('positive', foreground='#00aa00')
        tree.tag_configure('negative', foreground='#cc0000')
        return tree

    def _refresh(self):
        if self._on_refresh:
            self._on_refresh()

    def get_capital(self):
        try:
            return float(self.capital_entry.get().strip())
        except (ValueError, TypeError):
            return 1_000_000

    def update_review(self, result):
        self._last_result = result

        from diary.trade_review_format import format_review_report
        report = format_review_report(result)

        self.report_text.configure(state='normal')
        self.report_text.delete('1.0', tk.END)
        self.report_text.insert(tk.END, report)
        self.report_text.configure(state='disabled')

        wr_color = '#00aa00' if result.win_rate >= 50 else '#cc0000'
        pnl_color = '#00aa00' if result.total_pnl >= 0 else '#cc0000'
        self.summary_label.configure(
            text=f"Сделок: {result.closed_trades} | WR: {result.win_rate:.1f}% | "
                 f"P&L: {result.total_pnl:+,.0f} RUB | DD: -{result.max_drawdown:.1f}%"
        )

        self._fill_tree(self.ticker_tree, result.by_ticker)
        self._fill_tree(self.side_tree, result.by_side,
                        key_labels={'LONG': 'Лонг', 'SHORT': 'Шорт'})
        self._fill_tree(self.reason_tree, result.by_reason,
                        key_labels={'SL': 'По SL', 'TP': 'По TP',
                                    'TIMEOUT': 'Таймаут', 'Вручную': 'Вручную'})
        self._fill_tree(self.month_tree, result.by_month)
        self._fill_tree(self.dow_tree, result.by_dow)

        self._draw_chart(result)

    def _fill_tree(self, tree, data, key_labels=None):
        sorted_items = sorted(data.items(), key=lambda x: x[1]['pnl'], reverse=True)
        items = []
        for key, d in sorted_items:
            label = (key_labels.get(key, key) if key_labels else key)
            tag = 'positive' if d['pnl'] >= 0 else 'negative'
            items.append({
                'values': (label, d['count'], d['wins'],
                           f"{d['win_rate']:.1f}", f"{d['pnl']:+,.2f}"),
                'tags': (tag,),
            })
        tree_batch_insert(tree, items)

    def _draw_chart(self, result):
        if self.chart_canvas is not None:
            self.chart_canvas.get_tk_widget().destroy()
            self.chart_canvas = None

        for w in self.chart_frame.winfo_children():
            w.destroy()

        if len(result.equity_curve) < 2:
            ttk.Label(self.chart_frame,
                      text='Недостаточно данных для графика').pack(pady=20)
            return

        try:
            import matplotlib
            matplotlib.use('TkAgg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            return

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 3),
                                        gridspec_kw={'height_ratios': [3, 1]})

        dates = result.dates
        if not dates:
            dates = list(range(len(result.equity_curve)))

        step = max(1, len(dates) // 20)
        tick_positions = list(range(0, len(dates), step))

        ax1.plot(result.equity_curve, linewidth=1.2, color='#2196F3')
        ax1.fill_between(range(len(result.equity_curve)),
                         result.equity_curve[0],
                         result.equity_curve, alpha=0.15, color='#2196F3')
        ax1.set_ylabel('Капитал')
        ax1.set_title('Equity + Просадка')
        if tick_positions:
            ax1.set_xticks(tick_positions)
            ax1.set_xticklabels([dates[i] if i < len(dates) else '' for i in tick_positions],
                                rotation=45, fontsize=7)

        ax2.fill_between(range(len(result.drawdown_curve)),
                         result.drawdown_curve, color='#cc0000', alpha=0.4)
        ax2.set_ylabel('DD %')
        ax2.set_xlabel('Сделки')
        if tick_positions:
            ax2.set_xticks(tick_positions)
            ax2.set_xticklabels([dates[i] if i < len(dates) else '' for i in tick_positions],
                                rotation=45, fontsize=7)

        fig.tight_layout()

        self.chart_canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.chart_canvas.draw()
        self.chart_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)


class NotificationSettingsUI:
    def __init__(self, parent, notification_manager, on_close=None):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self.nm = notification_manager
        self._on_close = on_close

        win = tk.Toplevel(self.root)
        win.title('Настройки уведомлений')
        win.geometry('520x580')
        win.resizable(False, False)
        self.win = win

        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=1)

        gen_frame = ttk.LabelFrame(main, text='Общие', padding=5)
        gen_frame.pack(fill=tk.X, pady=(0, 10))

        self.toast_var = tk.BooleanVar(value=self.nm.toast_enabled)
        ttk.Checkbutton(gen_frame, text='Всплывающие уведомления (Windows toast)',
                        variable=self.toast_var).pack(anchor='w')

        self.sound_var = tk.BooleanVar(value=self.nm.sound_enabled)
        ttk.Checkbutton(gen_frame, text='Звуковые сигналы',
                        variable=self.sound_var).pack(anchor='w')

        thresh_frame = ttk.Frame(gen_frame)
        thresh_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(thresh_frame, text='Порог просадки (%):').pack(side=tk.LEFT)
        self.dd_entry = ttk.Entry(thresh_frame, width=6)
        self.dd_entry.insert(0, str(self.nm.drawdown_threshold))
        self.dd_entry.pack(side=tk.LEFT, padx=5)

        near_frame = ttk.Frame(gen_frame)
        near_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(near_frame, text='Близость к SL/TP (%):').pack(side=tk.LEFT)
        self.near_entry = ttk.Entry(near_frame, width=6)
        self.near_entry.insert(0, str(self.nm.near_distance_pct))
        self.near_entry.pack(side=tk.LEFT, padx=5)

        trig_frame = ttk.LabelFrame(main, text='Триггеры уведомлений', padding=5)
        trig_frame.pack(fill=tk.X, pady=(0, 10))

        from monitoring.notification_manager import TRIGGER_TYPES
        self.trigger_vars = {}
        for trig_type, label in TRIGGER_TYPES.items():
            var = tk.BooleanVar(value=self.nm.triggers.get(trig_type, False))
            self.trigger_vars[trig_type] = var
            ttk.Checkbutton(trig_frame, text=label, variable=var).pack(anchor='w')

        hist_frame = ttk.LabelFrame(main, text='История уведомлений', padding=5)
        hist_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        hist_cols = ('time', 'trigger', 'title', 'message')
        hist_headers = {'time': 'Время', 'trigger': 'Тип', 'title': 'Заголовок', 'message': 'Сообщение'}
        hist_widths = {'time': 120, 'trigger': 100, 'title': 130, 'message': 200}

        self.hist_tree = ttk.Treeview(hist_frame, columns=hist_cols, show='headings', height=8)
        for col in hist_cols:
            self.hist_tree.heading(col, text=hist_headers[col])
            self.hist_tree.column(col, width=hist_widths[col], anchor='w')
        scroll = ttk.Scrollbar(hist_frame, orient='vertical', command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=scroll.set)
        self.hist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.hist_tree.tag_configure('warning', foreground='#cc6600')
        self.hist_tree.tag_configure('error', foreground='#cc0000')

        self._refresh_history()

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text='Очистить историю',
                   command=self._clear_history).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Отметить прочитанными',
                   command=self._ack_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Тест уведомления',
                   command=self._test_toast).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Сохранить',
                   command=self._save).pack(side=tk.RIGHT, padx=2)

    def _refresh_history(self):
        from monitoring.notification_manager import TRIGGER_TYPES
        items = []
        for n in reversed(self.nm.history):
            trig_label = TRIGGER_TYPES.get(n.trigger_type, n.trigger_type)
            tag = 'warning' if n.icon == 'warning' else ('error' if n.icon == 'error' else '')
            items.append({
                'values': (n.timestamp, trig_label, n.title, n.message[:80]),
                'tags': (tag,),
            })
        tree_batch_insert(self.hist_tree, items)

    def _clear_history(self):
        self.nm.clear_history()
        self._refresh_history()

    def _ack_all(self):
        self.nm.ack_all()

    def _test_toast(self):
        from monitoring.toast import show_toast
        show_toast('Тест', 'Уведомления работают!', icon='info', duration=4)
        self.nm.notify('sl_hit', 'Тест', 'Тестовое уведомление', icon='info')
        self._refresh_history()

    def _save(self):
        try:
            dd = float(self.dd_entry.get().strip())
            near = float(self.near_entry.get().strip())
        except (ValueError, TypeError):
            dd = self.nm.drawdown_threshold
            near = self.nm.near_distance_pct

        config = {
            'triggers': {k: v.get() for k, v in self.trigger_vars.items()},
            'drawdown_threshold': dd,
            'near_distance_pct': near,
            'toast_enabled': self.toast_var.get(),
            'sound_enabled': self.sound_var.get(),
        }
        self.nm.set_trigger_config(config)
        self.win.destroy()
        if self._on_close:
            self._on_close()


class PerformanceAnalyticsUI:
    CHART_NAMES = [
        ('equity', 'Equity + DD'),
        ('pnl_dist', 'Распределение P&L'),
        ('r_dist', 'R-multiples'),
        ('monthly', 'По месяцам'),
        ('rolling_wr', 'Скользящий WR'),
        ('rolling_pnl', 'Скользящий P&L'),
        ('drawdown', 'Просадки (underwater)'),
    ]

    def __init__(self, parent, on_analyze=None):
        self.parent = parent
        self._on_analyze = on_analyze
        self._last_metrics = None
        self._last_trades = None

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(ctrl, text='Анализировать',
                   command=self._analyze).pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl, text='Бенчмарк:').pack(side=tk.LEFT, padx=(15, 2))
        self.bench_var = tk.StringVar(value='IMOEX')
        bench_cb = ttk.Combobox(ctrl, textvariable=self.bench_var,
                                values=['Нет', 'IMOEX'], width=10, state='readonly')
        bench_cb.pack(side=tk.LEFT, padx=2)

        self.status_label = ttk.Label(ctrl, text='', font=('', 9))
        self.status_label.pack(side=tk.RIGHT, padx=5)

        paned = ttk.PanedWindow(main, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=1)

        top_pane = ttk.Frame(paned)
        paned.add(top_pane, weight=1)

        self.report_text = tk.Text(top_pane, wrap=tk.WORD, font=('Consolas', 9))
        report_scroll = ttk.Scrollbar(top_pane, orient='vertical',
                                       command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=report_scroll.set)
        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        report_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        chart_pane = ttk.Frame(paned)
        paned.add(chart_pane, weight=2)

        chart_ctrl = ttk.Frame(chart_pane)
        chart_ctrl.pack(fill=tk.X, pady=(0, 2))

        ttk.Label(chart_ctrl, text='График:').pack(side=tk.LEFT)
        self.chart_var = tk.StringVar(value='equity')
        chart_cb = ttk.Combobox(chart_ctrl, textvariable=self.chart_var,
                                values=[n[1] for n in self.CHART_NAMES],
                                width=20, state='readonly')
        chart_cb.pack(side=tk.LEFT, padx=2)
        chart_cb.bind('<<ComboboxSelected>>', self._on_chart_change)

        self.chart_frame = ttk.Frame(chart_pane)
        self.chart_frame.pack(fill=tk.BOTH, expand=1)
        self.chart_canvas = None

    def _analyze(self):
        if self._on_analyze:
            self._on_analyze()

    def get_benchmark(self):
        return self.bench_var.get()

    def update_analytics(self, metrics, trades=None):
        self._last_metrics = metrics
        self._last_trades = trades

        from analytics.performance import format_performance_report
        report = format_performance_report(metrics)
        self.report_text.configure(state='normal')
        self.report_text.delete('1.0', tk.END)
        self.report_text.insert(tk.END, report)
        self.report_text.configure(state='disabled')

        self.status_label.configure(
            text=f"Trades: {metrics['total_trades']} | "
                 f"WR: {metrics['win_rate']:.1f}% | "
                 f"Sharpe: {metrics['sharpe']:.2f} | "
                 f"DD: -{metrics['max_drawdown']:.1f}%"
        )

        self._show_chart('equity')

    def _on_chart_change(self, event=None):
        selected = self.chart_var.get()
        key = None
        for k, name in self.CHART_NAMES:
            if name == selected:
                key = k
                break
        if key:
            self._show_chart(key)

    def _show_chart(self, chart_key):
        if self._last_metrics is None:
            return

        for w in self.chart_frame.winfo_children():
            w.destroy()
        self.chart_canvas = None

        m = self._last_metrics

        try:
            import matplotlib
            matplotlib.use('TkAgg')
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        except ImportError:
            ttk.Label(self.chart_frame, text='matplotlib не установлен').pack(pady=20)
            return

        fig = None

        if chart_key == 'equity':
            from analytics.visualizations import plot_equity_drawdown
            dates = self._get_dates()
            fig = plot_equity_drawdown(m.get('equity_curve', []), m.get('drawdown_curve', []), dates=dates)

        elif chart_key == 'pnl_dist':
            if self._last_trades:
                from analytics.visualizations import plot_pnl_distribution
                pnls = [t['pnl'] for t in self._last_trades]
                fig = plot_pnl_distribution(pnls)

        elif chart_key == 'r_dist':
            from analytics.visualizations import plot_r_distribution
            r_vals = []
            for t in (self._last_trades or []):
                sl = t.get('sl_price', 0)
                ep = t.get('entry_price', 0)
                if sl and ep:
                    risk = abs(ep - sl)
                    if risk > 0:
                        r_vals.append(t['pnl'] / (risk * t.get('qty', 1)))
            fig = plot_r_distribution(r_vals)

        elif chart_key == 'monthly':
            from analytics.visualizations import plot_monthly_heatmap
            fig = plot_monthly_heatmap(m.get('by_month', {}))

        elif chart_key == 'rolling_wr':
            from analytics.visualizations import plot_rolling_metric
            wr = m.get('rolling_win_rate', [])
            fig = plot_rolling_metric(wr, window_label='Win Rate %', title='Rolling Win Rate')

        elif chart_key == 'rolling_pnl':
            from analytics.visualizations import plot_rolling_metric
            rp = m.get('rolling_pnl', [])
            fig = plot_rolling_metric(rp, window_label='P&L (RUB)', title='Rolling P&L')

        elif chart_key == 'drawdown':
            if self._last_trades:
                from analytics.drawdown import calc_underwater_data
                from analytics.visualizations import plot_drawdown_underwater
                uw = calc_underwater_data(self._last_trades)
                if uw.get('drawdown'):
                    fig = plot_drawdown_underwater(uw)

        if fig is None:
            ttk.Label(self.chart_frame, text='Нет данных для графика').pack(pady=20)
            return

        self.chart_canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.chart_canvas.draw()
        self.chart_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)
        toolbar = NavigationToolbar2Tk(self.chart_canvas, self.chart_frame)
        toolbar.update()

    def _get_dates(self):
        if self._last_trades:
            return [str(t.get('entry_date', ''))[:10] for t in self._last_trades]
        return []


class PairsTradingUI:
    PAIR_COLS = ('rank', 'pair', 'corr', 'hedge', 'adf', 'p_val', 'hl', 'zscore')
    PAIR_HEADERS = {
        'rank': '#', 'pair': 'Пара', 'corr': 'Корр.', 'hedge': 'Hedge',
        'adf': 'ADF', 'p_val': 'p-value', 'hl': 'HL(дн)', 'zscore': 'Z-score',
    }
    PAIR_WIDTHS = {
        'rank': 30, 'pair': 120, 'corr': 55, 'hedge': 60,
        'adf': 55, 'p_val': 55, 'hl': 55, 'zscore': 60,
    }

    TRADE_COLS = ('date', 'side', 'z_in', 'z_out', 'pnl', 'reason')
    TRADE_HEADERS = {
        'date': 'Дата', 'side': 'Направление', 'z_in': 'Z вх.',
        'z_out': 'Z вых.', 'pnl': 'P&L', 'reason': 'Причина',
    }
    TRADE_WIDTHS = {
        'date': 90, 'side': 100, 'z_in': 55, 'z_out': 55, 'pnl': 80, 'reason': 120,
    }

    def __init__(self, parent, on_scan=None, on_backtest=None):
        self.parent = parent
        self._on_scan = on_scan
        self._on_backtest = on_backtest
        self._pairs = []

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(ctrl, text='Найти пары',
                   command=self._scan).pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl, text='Тикеры (через запятую):').pack(side=tk.LEFT, padx=(10, 2))
        self.tickers_entry = ttk.Entry(ctrl, width=40)
        self.tickers_entry.pack(side=tk.LEFT, padx=2)
        ToolTip(self.tickers_entry, 'Список тикеров для поиска пар.\nНапример: SBER, GAZP, LKOH, ROSN')

        ttk.Button(ctrl, text='Бэктест пары',
                   command=self._backtest).pack(side=tk.LEFT, padx=(15, 2))

        self.status_label = ttk.Label(ctrl, text='', font=('', 9))
        self.status_label.pack(side=tk.RIGHT, padx=5)

        params_frame = ttk.LabelFrame(main, text='Параметры', padding=3)
        params_frame.pack(fill=tk.X, pady=(0, 5))

        row1 = ttk.Frame(params_frame)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text='Z вход:').pack(side=tk.LEFT, padx=2)
        self.entry_z = ttk.Entry(row1, width=5)
        self.entry_z.insert(0, '2.0')
        self.entry_z.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text='Z выход:').pack(side=tk.LEFT, padx=2)
        self.exit_z = ttk.Entry(row1, width=5)
        self.exit_z.insert(0, '0.5')
        self.exit_z.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text='Z стоп:').pack(side=tk.LEFT, padx=2)
        self.stop_z = ttk.Entry(row1, width=5)
        self.stop_z.insert(0, '4.0')
        self.stop_z.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text='Макс. удержание:').pack(side=tk.LEFT, padx=2)
        self.max_hold = ttk.Entry(row1, width=4)
        self.max_hold.insert(0, '30')
        self.max_hold.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text='Lookback:').pack(side=tk.LEFT, padx=2)
        self.lookback = ttk.Entry(row1, width=4)
        self.lookback.insert(0, '60')
        self.lookback.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text='Макс. пар:').pack(side=tk.LEFT, padx=2)
        self.max_pairs = ttk.Entry(row1, width=4)
        self.max_pairs.insert(0, '20')
        self.max_pairs.pack(side=tk.LEFT, padx=2)

        paned = ttk.PanedWindow(main, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=1)

        pairs_pane = ttk.Frame(paned)
        paned.add(pairs_pane, weight=2)

        result_pane = ttk.Frame(paned)
        paned.add(result_pane, weight=1)

        pair_tree_frame = ttk.Frame(pairs_pane)
        pair_tree_frame.pack(fill=tk.BOTH, expand=1)

        self.pair_tree = ttk.Treeview(pair_tree_frame, columns=self.PAIR_COLS,
                                       show='headings', height=10, selectmode='browse')
        for col in self.PAIR_COLS:
            self.pair_tree.heading(col, text=self.PAIR_HEADERS[col])
            self.pair_tree.column(col, width=self.PAIR_WIDTHS[col], anchor='center')
        scroll = ttk.Scrollbar(pair_tree_frame, orient='vertical',
                                command=self.pair_tree.yview)
        self.pair_tree.configure(yscrollcommand=scroll.set)
        self.pair_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.pair_tree.tag_configure('coint', foreground='#008800')
        self.pair_tree.tag_configure('weak', foreground='#888888')

        self.result_text = tk.Text(result_pane, wrap=tk.WORD, font=('Consolas', 9),
                                   height=10)
        res_scroll = ttk.Scrollbar(result_pane, orient='vertical',
                                    command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=res_scroll.set)
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        res_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _scan(self):
        if self._on_scan:
            self._on_scan()

    def _backtest(self):
        if self._on_backtest:
            self._on_backtest()

    def get_tickers(self):
        text = self.tickers_entry.get().strip()
        if not text:
            return []
        return [t.strip().upper() for t in text.split(',') if t.strip()]

    def get_params(self):
        try:
            entry_z = float(self.entry_z.get().strip())
        except (ValueError, TypeError):
            entry_z = 2.0
        try:
            exit_z = float(self.exit_z.get().strip())
        except (ValueError, TypeError):
            exit_z = 0.5
        try:
            stop_z = float(self.stop_z.get().strip())
        except (ValueError, TypeError):
            stop_z = 4.0
        try:
            max_hold = int(self.max_hold.get().strip())
        except (ValueError, TypeError):
            max_hold = 30
        try:
            lookback = int(self.lookback.get().strip())
        except (ValueError, TypeError):
            lookback = 60
        try:
            max_pairs = int(self.max_pairs.get().strip())
        except (ValueError, TypeError):
            max_pairs = 20

        return {
            'entry_z': entry_z,
            'exit_z': exit_z,
            'stop_z': stop_z,
            'max_hold': max_hold,
            'lookback': lookback,
            'max_pairs': max_pairs,
        }

    def get_selected_pair(self):
        sel = self.pair_tree.selection()
        if not sel:
            return None
        idx = self.pair_tree.index(sel[0])
        if 0 <= idx < len(self._pairs):
            return self._pairs[idx]
        return None

    def update_pairs(self, pairs):
        self._pairs = pairs
        items = []
        for rank, p in enumerate(pairs, 1):
            tag = 'coint' if p['p_value'] <= 0.05 else 'weak'
            items.append({
                'values': (rank,
                           f"{p['ticker_y']}/{p['ticker_x']}",
                           f"{p['correlation']:.2f}",
                           f"{p['hedge_ratio']:.3f}",
                           f"{p['adf_stat']:.1f}",
                           f"{p['p_value']:.3f}",
                           f"{p['half_life']:.1f}",
                           f"{p['zscore_last']:+.2f}"),
                'tags': (tag,),
            })
        tree_batch_insert(self.pair_tree, items)

    def update_result(self, text):
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, text)
        self.result_text.configure(state='disabled')

    def set_status(self, text):
        self.status_label.configure(text=text)


class WatchlistUI:
    COLS = ('ticker', 'price', 'change_pct', 'div_yield', 'market_cap', 'volume', 'sector')
    HEADERS = {
        'ticker': 'Тикер', 'price': 'Цена', 'change_pct': 'Изм. %',
        'div_yield': 'Див.%', 'market_cap': 'Капитализ.', 'volume': 'Объём', 'sector': 'Сектор',
    }
    WIDTHS = {
        'ticker': 80, 'price': 90, 'change_pct': 70, 'div_yield': 60,
        'market_cap': 100, 'volume': 90, 'sector': 120,
    }

    def __init__(self, parent, on_add=None, on_remove=None, on_refresh=None,
                 on_select=None, on_dividends=None, on_correlation=None,
                 all_tickers=None):
        self.parent = parent
        self._on_add = on_add
        self._on_remove = on_remove
        self._on_refresh = on_refresh
        self._on_select = on_select
        self._on_dividends = on_dividends
        self._on_correlation = on_correlation
        self._all_tickers = list(all_tickers) if all_tickers else []

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(ctrl, text='Тикер:').pack(side=tk.LEFT, padx=2)
        self.ticker_combo = ttk.Combobox(ctrl, values=self._all_tickers, width=12)
        self.ticker_combo.pack(side=tk.LEFT, padx=2)
        self.ticker_combo.bind('<Return>', lambda e: self._add())

        ttk.Button(ctrl, text='Добавить', command=self._add).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text='Удалить', command=self._remove).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text='Обновить цены', command=self._refresh).pack(side=tk.LEFT, padx=(15, 2))
        ttk.Button(ctrl, text='Дивиденды', command=self._divs).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text='Корреляция', command=self._corr).pack(side=tk.LEFT, padx=2)

        self.status_label = ttk.Label(ctrl, text='', font=('', 9))
        self.status_label.pack(side=tk.RIGHT, padx=5)

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=1)

        self.tree = ttk.Treeview(tree_frame, columns=self.COLS,
                                  show='headings', height=15, selectmode='browse')
        for col in self.COLS:
            self.tree.heading(col, text=self.HEADERS[col])
            self.tree.column(col, width=self.WIDTHS[col], anchor='center')

        scroll = ttk.Scrollbar(tree_frame, orient='vertical',
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure('up', foreground='#00aa00')
        self.tree.tag_configure('down', foreground='#cc0000')
        self.tree.tag_configure('neutral', foreground='#888888')

        if self._on_select:
            self.tree.bind('<<TreeviewSelect>>', self._on_select_click)

    def _add(self):
        ticker = self.ticker_combo.get().strip().upper()
        if not ticker:
            return
        if self._on_add:
            self._on_add(ticker)
        self.ticker_combo.set('')

    def _remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        values = self.tree.item(sel[0])['values']
        ticker = str(values[0]) if values else ''
        if ticker and self._on_remove:
            self._on_remove(ticker)

    def _refresh(self):
        if self._on_refresh:
            self._on_refresh()

    def _divs(self):
        if self._on_dividends:
            self._on_dividends()

    def _corr(self):
        if self._on_correlation:
            self._on_correlation()

    def _on_select_click(self, event):
        sel = self.tree.selection()
        if sel and self._on_select:
            values = self.tree.item(sel[0])['values']
            ticker = str(values[0]) if values else ''
            self._on_select(ticker)

    def update_watchlist(self, items):
        tree_items = []
        for item in items:
            change = item.get('change_pct', 0)
            if change > 0:
                tag = 'up'
            elif change < 0:
                tag = 'down'
            else:
                tag = 'neutral'

            mc = item.get('market_cap')
            if mc:
                if mc >= 1e12:
                    mc_str = f'{mc / 1e12:.1f}T'
                elif mc >= 1e9:
                    mc_str = f'{mc / 1e9:.0f}M'
                else:
                    mc_str = f'{mc / 1e6:.0f}M'
            else:
                mc_str = '—'

            div_y = item.get('div_yield')
            div_str = f'{div_y:.1f}' if div_y is not None else '—'

            tree_items.append({
                'values': (item.get('ticker', ''),
                           f"{item.get('price', 0):.2f}" if item.get('price') else '—',
                           f"{change:+.2f}" if item.get('change_pct') is not None else '—',
                           div_str, mc_str,
                           f"{item.get('volume', 0):,.0f}" if item.get('volume') else '—',
                           item.get('sector', '')),
                'tags': (tag,),
            })
        tree_batch_insert(self.tree, tree_items)

    def set_status(self, text):
        self.status_label.configure(text=text)


class SectorRotationUI:
    COLS = ('sector', 'ret_5d', 'ret_10d', 'ret_20d', 'avg_ret', 'trend', 'tickers')
    HEADERS = {
        'sector': 'Сектор', 'ret_5d': '5д %', 'ret_10d': '10д %',
        'ret_20d': '20д %', 'avg_ret': 'Средн. %', 'trend': 'Тренд',
        'tickers': 'Тикеров',
    }
    WIDTHS = {
        'sector': 130, 'ret_5d': 65, 'ret_10d': 65,
        'ret_20d': 65, 'avg_ret': 70, 'trend': 80, 'tickers': 60,
    }

    def __init__(self, parent, on_scan=None, on_compare=None):
        self.parent = parent
        self._on_scan = on_scan
        self._on_compare = on_compare

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(ctrl, text='Период (дней):').pack(side=tk.LEFT, padx=2)
        self.period_entry = ttk.Entry(ctrl, width=5)
        self.period_entry.insert(0, '20')
        self.period_entry.pack(side=tk.LEFT, padx=2)

        ttk.Button(ctrl, text='Сканировать', command=self._scan).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text='Фундаментал по сектору', command=self._compare).pack(side=tk.LEFT, padx=2)

        self.status_label = ttk.Label(ctrl, text='', font=('', 9))
        self.status_label.pack(side=tk.RIGHT, padx=5)

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=1)

        self.tree = ttk.Treeview(tree_frame, columns=self.COLS,
                                  show='headings', height=15, selectmode='browse')
        for col in self.COLS:
            self.tree.heading(col, text=self.HEADERS[col])
            self.tree.column(col, width=self.WIDTHS[col], anchor='center')

        scroll = ttk.Scrollbar(tree_frame, orient='vertical',
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure('strong', foreground='#00aa00')
        self.tree.tag_configure('weak', foreground='#cc0000')
        self.tree.tag_configure('neutral', foreground='#888888')

    def _scan(self):
        if self._on_scan:
            self._on_scan()

    def _compare(self):
        if self._on_compare:
            self._on_compare()

    def get_period(self):
        try:
            return int(self.period_entry.get().strip())
        except (ValueError, TypeError):
            return 20

    def update_sectors(self, sectors):
        items = []
        for s in sectors:
            avg = s.get('avg_ret', 0)
            if avg > 1:
                tag = 'strong'
            elif avg < -1:
                tag = 'weak'
            else:
                tag = 'neutral'
            items.append({
                'values': (s.get('sector', ''),
                           f"{s.get('ret_5d', 0):+.1f}",
                           f"{s.get('ret_10d', 0):+.1f}",
                           f"{s.get('ret_20d', 0):+.1f}",
                           f"{avg:+.1f}",
                           s.get('trend', ''),
                           s.get('ticker_count', 0)),
                'tags': (tag,),
            })
        tree_batch_insert(self.tree, items)

    def set_status(self, text):
        self.status_label.configure(text=text)


class PositionCalculatorUI:
    def __init__(self, parent, on_calculate=None, get_current_price=None,
                 all_tickers=None):
        self.parent = parent
        self._on_calculate = on_calculate
        self._get_current_price = get_current_price
        self._all_tickers = list(all_tickers) if all_tickers else []

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        input_frame = ttk.LabelFrame(main, text='Параметры', padding=10)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        row1 = ttk.Frame(input_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text='Тикер:').pack(side=tk.LEFT, padx=2)
        self.ticker_combo = ttk.Combobox(row1, values=self._all_tickers, width=12)
        self.ticker_combo.pack(side=tk.LEFT, padx=2)
        self.ticker_combo.bind('<Return>', lambda e: self._fill_price())

        ttk.Label(row1, text='Цена входа:').pack(side=tk.LEFT, padx=(15, 2))
        self.entry_price = ttk.Entry(row1, width=10)
        self.entry_price.pack(side=tk.LEFT, padx=2)

        ttk.Label(row1, text='Цена SL:').pack(side=tk.LEFT, padx=(15, 2))
        self.sl_price = ttk.Entry(row1, width=10)
        self.sl_price.pack(side=tk.LEFT, padx=2)

        row2 = ttk.Frame(input_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text='Капитал (руб.):').pack(side=tk.LEFT, padx=2)
        self.capital_entry = ttk.Entry(row2, width=12)
        self.capital_entry.insert(0, '1000000')
        self.capital_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(row2, text='Риск на сделку (%):').pack(side=tk.LEFT, padx=(15, 2))
        self.risk_pct_entry = ttk.Entry(row2, width=6)
        self.risk_pct_entry.insert(0, '2.0')
        self.risk_pct_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(row2, text='Цена TP:').pack(side=tk.LEFT, padx=(15, 2))
        self.tp_price = ttk.Entry(row2, width=10)
        self.tp_price.pack(side=tk.LEFT, padx=2)

        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text='Рассчитать', command=self._calc).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Загрузить цену', command=self._fill_price).pack(side=tk.LEFT, padx=2)

        result_frame = ttk.LabelFrame(main, text='Результат', padding=10)
        result_frame.pack(fill=tk.BOTH, expand=1)

        self.result_text = tk.Text(result_frame, wrap='word', font=('Consolas', 10),
                                    height=12, state='disabled', padx=10, pady=10)
        res_scroll = ttk.Scrollbar(result_frame, orient='vertical',
                                    command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=res_scroll.set)
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        res_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _fill_price(self):
        if self._get_current_price:
            ticker = self.ticker_combo.get().strip().upper()
            if ticker:
                price = self._get_current_price(ticker)
                if price:
                    self.entry_price.delete(0, tk.END)
                    self.entry_price.insert(0, f'{price:.2f}')

    def _calc(self):
        if self._on_calculate:
            self._on_calculate()

    def get_params(self):
        try:
            entry_price = float(self.entry_price.get().strip())
        except (ValueError, TypeError):
            entry_price = 0
        try:
            sl_price = float(self.sl_price.get().strip())
        except (ValueError, TypeError):
            sl_price = 0
        try:
            tp_price = float(self.tp_price.get().strip())
        except (ValueError, TypeError):
            tp_price = 0
        try:
            capital = float(self.capital_entry.get().strip())
        except (ValueError, TypeError):
            capital = 1_000_000
        try:
            risk_pct = float(self.risk_pct_entry.get().strip())
        except (ValueError, TypeError):
            risk_pct = 2.0
        ticker = self.ticker_combo.get().strip().upper()

        return {
            'ticker': ticker,
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'capital': capital,
            'risk_pct': risk_pct,
        }

    def show_result(self, text):
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, text)
        self.result_text.configure(state='disabled')


class SignalJournalUI:
    COLS = ('date', 'ticker', 'side', 'price', 'strategy', 'sl', 'tp', 'entered')
    HEADERS = {
        'date': 'Дата', 'ticker': 'Тикер', 'side': 'Напр.',
        'price': 'Цена', 'strategy': 'Стратегия', 'sl': 'SL',
        'tp': 'TP', 'entered': 'Вход?',
    }
    WIDTHS = {
        'date': 90, 'ticker': 70, 'side': 55,
        'price': 80, 'strategy': 100, 'sl': 70,
        'tp': 70, 'entered': 55,
    }

    def __init__(self, parent, on_filter=None, on_export=None,
                 all_tickers=None, all_strategies=None):
        self.parent = parent
        self._on_filter = on_filter
        self._on_export = on_export
        self._all_tickers = list(all_tickers) if all_tickers else []
        self._all_strategies_set = set(all_strategies) if all_strategies else set()

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(ctrl, text='Тикер:').pack(side=tk.LEFT, padx=2)
        self.ticker_filter = ttk.Combobox(ctrl, values=self._all_tickers, width=12)
        self.ticker_filter.pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl, text='Стратегия:').pack(side=tk.LEFT, padx=(10, 2))
        self.strategy_var = tk.StringVar(value='Все')
        strategy_vals = ['Все'] + sorted(all_strategies) if all_strategies else ['Все']
        self.strategy_cb = ttk.Combobox(ctrl, textvariable=self.strategy_var,
                                         values=strategy_vals, width=15,
                                         state='readonly')
        self.strategy_cb.pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl, text='Направление:').pack(side=tk.LEFT, padx=(10, 2))
        self.side_var = tk.StringVar(value='Все')
        ttk.Combobox(ctrl, textvariable=self.side_var,
                      values=['Все', 'BUY', 'SELL'], width=6,
                      state='readonly').pack(side=tk.LEFT, padx=2)

        ttk.Button(ctrl, text='Фильтр', command=self._filter).pack(side=tk.LEFT, padx=(10, 2))
        ttk.Button(ctrl, text='Экспорт CSV', command=self._export).pack(side=tk.LEFT, padx=2)

        self.count_label = ttk.Label(ctrl, text='', font=('', 9))
        self.count_label.pack(side=tk.RIGHT, padx=5)

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=1)

        self.tree = ttk.Treeview(tree_frame, columns=self.COLS,
                                  show='headings', height=20, selectmode='browse')
        for col in self.COLS:
            self.tree.heading(col, text=self.HEADERS[col])
            self.tree.column(col, width=self.WIDTHS[col], anchor='center')

        scroll = ttk.Scrollbar(tree_frame, orient='vertical',
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure('buy', foreground='#00aa00')
        self.tree.tag_configure('sell', foreground='#cc0000')
        self.tree.tag_configure('entered_yes', foreground='#0066cc')
        self.tree.tag_configure('entered_no', foreground='#888888')

    def _filter(self):
        if self._on_filter:
            self._on_filter()

    def _export(self):
        if self._on_export:
            self._on_export()

    def get_filters(self):
        return {
            'ticker': self.ticker_filter.get().strip().upper(),
            'strategy': self.strategy_var.get(),
            'side': self.side_var.get(),
        }

    def update_strategies(self, strategies):
        all_set = set(strategies)
        all_set.update(self._all_strategies_set)
        values = ['Все'] + sorted(all_set)
        self.strategy_cb.configure(values=values)
        if self.strategy_var.get() not in values:
            self.strategy_var.set('Все')

    def update_signals(self, signals):
        items = []
        for s in signals:
            side = s.get('side', '')
            entered = s.get('entered', False)
            tag = ('buy' if side == 'BUY' else 'sell') if side else ''
            entered_tag = 'entered_yes' if entered else 'entered_no'
            items.append({
                'values': (s.get('date', ''),
                           s.get('ticker', ''),
                           side,
                           f"{s.get('price', 0):.2f}" if s.get('price') else '—',
                           s.get('strategy', ''),
                           f"{s.get('sl', 0):.2f}" if s.get('sl') else '—',
                           f"{s.get('tp', 0):.2f}" if s.get('tp') else '—',
                           'Да' if entered else 'Нет'),
                'tags': (tag, entered_tag),
            })
        tree_batch_insert(self.tree, items)

        self.count_label.configure(text=f'Сигналов: {len(signals)}')

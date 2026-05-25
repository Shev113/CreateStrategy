# CreateStrategyTrading.py
# -*- coding: utf-8 -*-
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from collections import Counter

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import requests
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from backtest.engine import BacktestEngine, export_results, candles_to_df
from screening.reporter import generate_report
from screening.scanner import Scanner
from screening.sectors import SectorDB
from strategy.bounce import check_bounce
from strategy.indicators import calc_atr
from strategy.levels import find_horizontal_levels, round_to_tolerance
from visual import StockAppVisual, ScannerUI, DiaryUI, _add_copy_menu
from diary.journal import DiaryStorage, DiaryEntry, calc_position_qty, calc_position_volume

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


class StrategyAppState:
    """Хранение состояния приложения"""
    def __init__(self):
        self.stock_data = None
        self.current_step = 0
        self.horizontal_lines = []
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
        self.diary_storage = DiaryStorage()
        self.setup_ui()
        self.bind_events()

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

    def setup_ui(self) -> None:
        """Настройка GUI"""
        self.root.title("CreateStrategy — Технический анализ MOEX")
        self.root.geometry("1250x800")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=1)

        tab_analysis = ttk.Frame(notebook)
        tab_scanner = ttk.Frame(notebook)
        tab_diary = ttk.Frame(notebook)
        notebook.add(tab_analysis, text='Анализ')
        notebook.add(tab_scanner, text='Сканер')
        notebook.add(tab_diary, text='Дневник сделок')

        self.app = StockAppVisual(
            tab_analysis, self.on_select, self.on_plot_button, self.on_export_button,
            self.step, self.get_moex_tickers, self.on_backtest
        )

        self.scanner_ui = ScannerUI(
            tab_scanner, sectors=self.sector_db.get_all_sectors(),
            on_scan=self.on_scanner, on_legend=self.on_show_legend,
            on_excel=self.on_export_excel, on_diary=self.on_add_to_diary
        )

        self.diary_ui = DiaryUI(
            tab_diary, storage=self.diary_storage,
            on_check_positions=self.on_check_positions,
            on_show_analysis=self.on_show_analysis
        )

    def bind_events(self) -> None:
        """Привязка событий"""
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
        min_repeats = int(self.app.min_repeats_entry.get()) if self.app.min_repeats_entry.get() else DEFAULT_MIN_REPEATS
        if min_repeats < 1:
            min_repeats = 1

        self.state.horizontal_lines = find_horizontal_levels(
            stock_data, min_hits=min_repeats)

        if self.state.df is not None and len(stock_data) > 0:
            avg_price = sum(float(c[3]) for c in stock_data if c and len(c) >= 4) / len(stock_data)
            tolerance = avg_price * 0.005
            price_counter = Counter()
            for c in stock_data:
                if c and len(c) >= 4:
                    price_counter[round_to_tolerance(float(c[1]), tolerance)] += 1
                    price_counter[round_to_tolerance(float(c[2]), tolerance)] += 1
                    price_counter[round_to_tolerance(float(c[3]), tolerance)] += 1

            for price in self.state.horizontal_lines:
                count = price_counter.get(price, 0)
                self.app.result_text.insert(tk.END, f"Price: {price:.2f}, Count: {count}\n")

        self.state.current_step = 0
        self.app.get_data_button.config(state='normal', text='1. Получить данные')

        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        total_days = (end_dt - start_dt).days
        self.app.result_text.insert(tk.END, f"\nСвечей: {len(stock_data)}, период: ~{total_days} дн.")

    def on_select(self) -> None:
        """Обработка выбора акции и дат (асинхронная загрузка)"""
        selected_stock = self.app.stock_combobox.get()
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

    def plot_candles(self, candles: list) -> tuple:
        """Построение свечного графика"""
        df = self.candles_to_df_custom(candles)
        if df is None or df.empty:
            return None, None
        fig, axlist = mpf.plot(df, type='candle', style='yahoo', volume=True, returnfig=True)
        return fig, axlist[0]

    def parse_prices_from_result_text(self, text: str) -> list[float]:
        """Извлечение цен из текстового поля результатов"""
        prices = []
        for line in text.strip().split("\n"):
            try:
                if "Price:" in line and "Count:" in line:
                    price_str = line.split("Price:")[1].split(",")[0].strip()
                    prices.append(float(price_str))
            except (ValueError, IndexError):
                continue
        return prices

    def on_plot_button(self) -> None:
        """Построение графика с горизонтальными уровнями"""
        if self.state.stock_data is None:
            print("Ошибка: данные по акции не загружены")
            return
        selected_stock = self.app.stock_combobox.get()
        if isinstance(self.state.stock_data, list):
            fig, ax = self.plot_candles(self.state.stock_data)
            if fig is None:
                return

            lines_text = self.app.result_text.get("1.0", tk.END)
            for price in self.parse_prices_from_result_text(lines_text):
                ax.axhline(y=price, color='r', linestyle='--', linewidth=1, alpha=0.7)

            plot_window = tk.Toplevel(self.app.root)
            plot_window.title(f"График {selected_stock}")
            canvas = FigureCanvasTkAgg(fig, master=plot_window)
            canvas.draw()
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
            toolbar = NavigationToolbar2Tk(canvas, plot_window)
            toolbar.update()
            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def on_export_button(self) -> None:
        """Экспорт данных в текстовый файл"""
        if self.state.stock_data is None:
            print("Ошибка: данные по акции не загружены")
            return
        selected_stock = self.app.stock_combobox.get()
        if isinstance(self.state.stock_data, list):
            filename = f"{selected_stock}_data.txt"
            if self.export_data_to_txt(self.state.stock_data, filename):
                print(f"Data exported to {filename}")
            else:
                print("Failed to export data.")

    def find_nearest_horizontal_line(self, current_price: float) -> float | None:
        """Поиск ближайшего горизонтального уровня"""
        if not self.state.horizontal_lines:
            return None
        return min(self.state.horizontal_lines, key=lambda x: abs(x - current_price))

    def step(self) -> None:
        """Шаг по свечам с отображением ближайшего уровня"""
        if not self.state.stock_data:
            print("Ошибка: данные не загружены")
            return
        if self.state.current_step >= len(self.state.stock_data):
            print("Шаги закончились")
            return
        current_candle = self.state.stock_data[self.state.current_step]
        if current_candle is None or len(current_candle) < 4:
            self.state.current_step += 1
            return
        current_price = float(current_candle[1])
        nearest_line = self.find_nearest_horizontal_line(current_price)
        if nearest_line is not None and self.state.df is not None:
            fig, axlist = mpf.plot(self.state.df, type='candle', style='yahoo',
                                   volume=True, returnfig=True)
            axlist[0].axhline(y=nearest_line, color='r', linestyle='--', linewidth=2)
            for widget in self.app.canvas.get_tk_widget().winfo_children():
                widget.destroy()
            self.app.canvas.figure = fig
            self.app.canvas.draw()
        self.state.current_step += 1

    def plot_with_trades(self, stock_data: list, trades: list) -> None:
        """Визуализация сделок на графике"""
        df = self.candles_to_df_custom(stock_data)
        if df is None or df.empty:
            return
        fig, axlist = mpf.plot(df, type='candle', style='yahoo',
                               volume=True, returnfig=True)
        ax = axlist[0]
        for trade in trades:
            entry_idx = trade['entry_idx']
            exit_idx = trade['exit_idx']
            ep = trade['entry_price']
            xp = trade['exit_price']
            ec, xc = ('lime', 'gold') if trade['pnl'] > 0 else ('red', 'orange')
            marker_entry = '^' if trade['side'] == 'BUY' else 'v'
            marker_exit = 'v' if trade['side'] == 'BUY' else '^'
            ax.scatter(entry_idx, ep, marker=marker_entry, color=ec, s=180,
                       zorder=5, edgecolors='black', linewidths=0.5)
            ax.scatter(exit_idx, xp, marker=marker_exit, color=xc, s=180,
                       zorder=5, edgecolors='black', linewidths=0.5)

        selected_stock = self.app.stock_combobox.get()
        plot_window = tk.Toplevel(self.app.root)
        plot_window.title(f"Backtest - {selected_stock}")
        plot_window.geometry("1200x700")
        canvas = FigureCanvasTkAgg(fig, master=plot_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        toolbar = NavigationToolbar2Tk(canvas, plot_window)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def _run_backtest_task(self, atr_sl, atr_tp, risk_pct, min_hits):
        try:
            engine = BacktestEngine(
                capital=INITIAL_CAPITAL, risk_per_trade=risk_pct / 100,
                atr_sl=atr_sl, atr_tp=atr_tp, min_hits=min_hits,
                strategy='bounce')

            trades, metrics = engine.run(self.state.stock_data)
            selected_stock = self.app.stock_combobox.get()
            csv_path, json_path = export_results(trades, metrics, selected_stock)

            self.root.after(0, lambda: self._on_backtest_complete(
                trades, metrics, csv_path, json_path, selected_stock))
        except Exception as e:
            self.root.after(0, lambda: self._on_backtest_error(str(e)))

    def _on_backtest_complete(self, trades, metrics, csv_path, json_path, selected_stock):
        self.app.backtest_button.config(state='normal', text='3. Запустить Backtest')
        self.app.display_backtest_results(metrics)
        self.app.backtest_text.insert(tk.END, f"\n\nФайлы:\n  {csv_path}\n  {json_path}")
        if self.app.show_trades_var.get():
            self.plot_with_trades(self.state.stock_data, trades)

    def _on_backtest_error(self, error_msg):
        self.app.add_backtest_result(f"Ошибка backtest: {error_msg}")
        self.app.backtest_button.config(state='normal', text='3. Запустить Backtest')
        logging.exception("Backtest error")

    def on_backtest(self) -> None:
        """Запуск backtesting стратегии (асинхронно)"""
        if self.state.stock_data is None or not isinstance(self.state.stock_data, list):
            self.app.add_backtest_result("Ошибка: сначала загрузите данные (кнопка 1)")
            return
        if len(self.state.stock_data) < MIN_CANDLES_FOR_BACKTEST:
            self.app.add_backtest_result("Ошибка: слишком мало данных (нужно >= 30 свечей)")
            return
        try:
            atr_sl = float(self.app.atr_sl_entry.get())
            atr_tp = float(self.app.atr_tp_entry.get())
            risk_pct = float(self.app.risk_entry.get())
            min_hits = int(self.app.min_repeats_entry.get()) if self.app.min_repeats_entry.get() else DEFAULT_MIN_REPEATS
            if atr_sl <= 0 or atr_tp <= 0:
                self.app.add_backtest_result("Ошибка: ATR множители должны быть > 0")
                return
            if risk_pct <= 0 or risk_pct > 100:
                self.app.add_backtest_result("Ошибка: риск должен быть 0-100%")
                return
            if min_hits < 1:
                min_hits = 1

            self.app.backtest_button.config(state='disabled', text='Backtest запущен...')

            t = threading.Thread(
                target=self._run_backtest_task,
                args=(atr_sl, atr_tp, risk_pct, min_hits),
                daemon=True
            )
            t.start()
        except ValueError:
            self.app.add_backtest_result("Ошибка: проверьте введённые числа")
            self.app.backtest_button.config(state='normal', text='3. Запустить Backtest')

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
                results = scanner.scan(
                    sectors=selected,
                    date_from=date_from,
                    date_to=date_to,
                    backtest_params=params,
                    progress_fn=lambda c, t, tick, sec: self.scanner_ui.update_progress(c, t, tick, sec)
                )
                self._last_scan_results = results
                report = generate_report(results, top_n=5, params=params)
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

        capital = 1_000_000
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
        root.mainloop()

    main()

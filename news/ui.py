import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, List, Optional, Dict

from news.provider import load_ai_config, save_ai_config
from utils import tree_batch_insert


class NewsUI:
    COLS = ('published_at', 'title', 'sentiment', 'impact', 'tickers', 'recommendation')
    HEADERS = {
        'published_at': 'Дата',
        'title': 'Заголовок',
        'sentiment': 'Сентимент',
        'impact': 'Сила',
        'tickers': 'Тикеры',
        'recommendation': 'Рекомендация',
    }
    WIDTHS = {
        'published_at': 120,
        'title': 350,
        'sentiment': 90,
        'impact': 50,
        'tickers': 120,
        'recommendation': 100,
    }

    def __init__(self, parent, on_refresh=None, on_analyze=None,
                 on_settings=None, all_tickers=None):
        self.parent = parent
        self._on_refresh = on_refresh
        self._on_analyze = on_analyze
        self._on_settings = on_settings
        self._all_tickers = list(all_tickers) if all_tickers else []
        self._last_results = []

        main = ttk.Frame(parent)
        main.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(ctrl, text='Обновить', command=self._refresh).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text='Анализировать все', command=self._analyze_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text='Настройки AI', command=self._show_settings).pack(side=tk.LEFT, padx=(15, 2))

        ttk.Label(ctrl, text='Фильтр:').pack(side=tk.LEFT, padx=(15, 2))
        self.sentiment_var = tk.StringVar(value='Все')
        sent_cb = ttk.Combobox(ctrl, textvariable=self.sentiment_var,
                               values=['Все', 'positive', 'neutral', 'negative'],
                               width=10, state='readonly')
        sent_cb.pack(side=tk.LEFT, padx=2)
        sent_cb.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())

        self.ticker_filter_var = tk.StringVar()
        ttk.Label(ctrl, text='Тикер:').pack(side=tk.LEFT, padx=(5, 2))
        self.ticker_filter_combo = ttk.Combobox(ctrl, textvariable=self.ticker_filter_var,
                                                  values=self._all_tickers, width=10)
        self.ticker_filter_combo.pack(side=tk.LEFT, padx=2)
        self.ticker_filter_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())
        self.ticker_filter_combo.bind('<Return>', lambda e: self._apply_filter())

        self.status_label = ttk.Label(ctrl, text='', font=('', 9))
        self.status_label.pack(side=tk.RIGHT, padx=5)

        paned = ttk.PanedWindow(main, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=1)

        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=2)

        self.tree = ttk.Treeview(tree_frame, columns=self.COLS, show='headings',
                                  height=12, selectmode='browse')
        for c in self.COLS:
            self.tree.heading(c, text=self.HEADERS[c])
            self.tree.column(c, width=self.WIDTHS[c], anchor='center' if c != 'title' else 'w')

        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure('positive', foreground='#008800')
        self.tree.tag_configure('negative', foreground='#cc0000')
        self.tree.tag_configure('neutral', foreground='#888888')
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        detail_frame = ttk.LabelFrame(paned, text='Детали анализа')
        paned.add(detail_frame, weight=1)

        self.detail_text = tk.Text(detail_frame, wrap=tk.WORD, font=('Consolas', 9), height=6)
        detail_scroll = ttk.Scrollbar(detail_frame, orient='vertical',
                                       command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _refresh(self):
        if self._on_refresh:
            self._on_refresh()

    def _analyze_all(self):
        if self._on_analyze:
            self._on_analyze()

    def _show_settings(self, on_saved=None):
        if self._on_settings:
            self._on_settings()
            return

        config = load_ai_config()

        win = tk.Toplevel(self.parent.winfo_toplevel())
        win.title('Настройки AI')
        win.geometry('450x300')
        win.resizable(False, False)
        win.grab_set()

        frame = ttk.Frame(win, padding=15)
        frame.pack(fill=tk.BOTH, expand=1)

        row = 0
        ttk.Label(frame, text='Провайдер:').grid(row=row, column=0, sticky='e', pady=3)
        provider_var = tk.StringVar(value=config.get('provider', 'rules'))
        provider_cb = ttk.Combobox(frame, textvariable=provider_var,
                                    values=['rules', 'groq'], width=20, state='readonly')
        provider_cb.grid(row=row, column=1, sticky='w', pady=3, padx=5)

        row += 1
        ttk.Label(frame, text='API ключ:').grid(row=row, column=0, sticky='e', pady=3)
        key_var = tk.StringVar(value=config.get('api_key', ''))
        key_entry = ttk.Entry(frame, textvariable=key_var, width=30, show='*')
        key_entry.grid(row=row, column=1, sticky='w', pady=3, padx=5)

        row += 1
        ttk.Label(frame, text='Модель:').grid(row=row, column=0, sticky='e', pady=3)
        model_var = tk.StringVar(value=config.get('model', 'llama-3.3-70b-versatile'))
        model_entry = ttk.Entry(frame, textvariable=model_var, width=30)
        model_entry.grid(row=row, column=1, sticky='w', pady=3, padx=5)

        row += 1
        ttk.Label(frame, text='Эндпоинт:').grid(row=row, column=0, sticky='e', pady=3)
        endpoint_var = tk.StringVar(value=config.get('endpoint', 'https://api.groq.com/openai/v1'))
        endpoint_entry = ttk.Entry(frame, textvariable=endpoint_var, width=30)
        endpoint_entry.grid(row=row, column=1, sticky='w', pady=3, padx=5)

        row += 1
        ttk.Label(frame, text='Интервал скана (мин):').grid(row=row, column=0, sticky='e', pady=3)
        interval_var = tk.StringVar(value=str(config.get('auto_scan_interval_min', 15)))
        interval_entry = ttk.Entry(frame, textvariable=interval_var, width=10)
        interval_entry.grid(row=row, column=1, sticky='w', pady=3, padx=5)

        row += 1
        ttk.Label(frame, text='Макс. новостей:').grid(row=row, column=0, sticky='e', pady=3)
        max_var = tk.StringVar(value=str(config.get('max_news', 50)))
        max_entry = ttk.Entry(frame, textvariable=max_var, width=10)
        max_entry.grid(row=row, column=1, sticky='w', pady=3, padx=5)

        row += 1
        info_label = ttk.Label(frame, text='', foreground='green')
        info_label.grid(row=row, column=0, columnspan=2, pady=5)

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
                info_label.configure(text='Сохранено!', foreground='green')
                if on_saved:
                    on_saved()
                win.after(1500, win.destroy)
            except Exception as e:
                info_label.configure(text=f'Ошибка: {e}', foreground='red')

        row += 1
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text='Сохранить', command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Отмена', command=win.destroy).pack(side=tk.LEFT, padx=5)

    def update_news(self, results: List[Dict]):
        self._last_results = results
        all_tickers = set(self._all_tickers)
        for r in results:
            for t in r.get('tickers', []):
                if isinstance(t, str):
                    all_tickers.add(t)
        sorted_tickers = sorted(all_tickers)
        self.ticker_filter_combo.configure(values=sorted_tickers)
        self._apply_filter()

    def _apply_filter(self):
        sentiment_filter = self.sentiment_var.get()
        ticker_filter = self.ticker_filter_var.get().strip().upper()

        sent_labels = {'positive': 'Позитив', 'neutral': 'Нейтрал', 'negative': 'Негатив'}

        items = []
        for r in self._last_results:
            sentiment = r.get('sentiment', 'neutral')
            if sentiment_filter != 'Все' and sentiment != sentiment_filter:
                continue
            tickers = r.get('tickers', [])
            tickers_str = ', '.join(tickers) if isinstance(tickers, list) else str(tickers)
            if ticker_filter and ticker_filter not in tickers_str:
                continue

            title = r.get('title', '')
            if len(title) > 80:
                title = title[:77] + '...'
            published = r.get('published_at', '')[:16]
            impact = r.get('impact', 0)
            rec = r.get('recommendation', '')
            tag = sentiment

            items.append({
                'values': (published, title,
                           sent_labels.get(sentiment, sentiment),
                           impact, tickers_str, rec),
                'tags': (tag,),
            })

        tree_batch_insert(self.tree, items)
        self.status_label.configure(text=f'{len(items)} новостей')

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])

        sentiment_filter = self.sentiment_var.get()
        ticker_filter = self.ticker_filter_var.get().strip().upper()
        filtered = []
        for r in self._last_results:
            sentiment = r.get('sentiment', 'neutral')
            if sentiment_filter != 'Все' and sentiment != sentiment_filter:
                continue
            tickers = r.get('tickers', [])
            tickers_str = ', '.join(tickers) if isinstance(tickers, list) else str(tickers)
            if ticker_filter and ticker_filter not in tickers_str:
                continue
            filtered.append(r)

        if idx >= len(filtered):
            return

        r = filtered[idx]
        self.detail_text.configure(state='normal')
        self.detail_text.delete('1.0', tk.END)

        sent_labels = {'positive': 'Позитивный', 'neutral': 'Нейтральный', 'negative': 'Негативный'}
        text = f"Заголовок: {r.get('title', '')}\n"
        text += f"Дата: {r.get('published_at', '')}\n"
        text += f"Сентимент: {sent_labels.get(r.get('sentiment', ''), r.get('sentiment', ''))} ({r.get('score', 0):.2f})\n"
        text += f"Сила влияния: {r.get('impact', 0)}/5\n"
        text += f"Тикеры: {', '.join(r.get('tickers', []))}\n"
        text += f"Резюме: {r.get('summary', '')}\n"
        text += f"Рекомендация: {r.get('recommendation', '')}\n"

        self.detail_text.insert(tk.END, text)
        self.detail_text.configure(state='disabled')

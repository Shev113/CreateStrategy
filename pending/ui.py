import tkinter as tk
from tkinter import ttk, messagebox


COLS = ('created', 'ticker', 'side', 'entry_price', 'sl', 'tp', 'qty', 'source', 'status')
HEADERS = {
    'created': 'Создан',
    'ticker': 'Тикер',
    'side': 'Напр.',
    'entry_price': 'Вход',
    'sl': 'SL',
    'tp': 'TP',
    'qty': 'Кол-во',
    'source': 'Источник',
    'status': 'Статус',
}
WIDTHS = {
    'created': 90,
    'ticker': 70,
    'side': 55,
    'entry_price': 80,
    'sl': 70,
    'tp': 70,
    'qty': 80,
    'source': 80,
    'status': 90,
}


class PendingTradesUI:
    def __init__(self, parent, on_remove=None, on_refresh=None):
        self.parent = parent
        self._on_remove = on_remove
        self._on_refresh = on_refresh
        self._build()

    def _build(self):
        main = ttk.Frame(self.parent, padding=5)
        main.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_frame, text='Обновить', command=self._on_refresh_click).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Удалить', command=self._on_remove_click).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Очистить сработавшие', command=self._on_clear_triggered).pack(side=tk.LEFT, padx=2)
        self.count_label = ttk.Label(btn_frame, text='Ожидает: 0')
        self.count_label.pack(side=tk.RIGHT, padx=5)

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=COLS, show='headings', height=15)
        for c in COLS:
            self.tree.heading(c, text=HEADERS[c])
            self.tree.column(c, width=WIDTHS.get(c, 80), minwidth=50)

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure('active', foreground='#aa7700')
        self.tree.tag_configure('triggered', foreground='#00aa00')
        self.tree.tag_configure('removed', foreground='#888888')

    def _on_refresh_click(self):
        if self._on_refresh:
            self._on_refresh()

    def _on_remove_click(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Удаление', 'Выберите запись для удаления.')
            return
        if not messagebox.askyesno('Удаление', 'Удалить выбранную запись из ожидания?'):
            return
        for item in sel:
            pid = self.tree.set(item, 'created')
            if self._on_remove:
                self._on_remove(pid)

    def _on_clear_triggered(self):
        if not messagebox.askyesno('Очистка', 'Удалить все сработавшие записи?'):
            return
        if self._on_remove:
            self._on_remove('__clear_triggered__')

    def update_trades(self, trades):
        self.tree.delete(*self.tree.get_children())
        active_count = 0
        for t in trades:
            if t.triggered:
                status = 'Сработал'
                tag = 'triggered'
                if t.triggered_at:
                    status = f'Сработал {t.triggered_at}'
            else:
                status = 'Ожидает'
                tag = 'active'
                active_count += 1

            self.tree.insert('', tk.END, values=(
                t.created,
                t.ticker,
                t.side,
                f'{t.entry_price:.2f}',
                f'{t.sl_price:.2f}',
                f'{t.tp_price:.2f}',
                f'{t.qty:.2f}',
                t.source,
                status,
            ), tags=(tag,))
        self.count_label.config(text=f'Ожидает: {active_count}')

    def get_selected_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        item = sel[0]
        return self.tree.set(item, 'created')

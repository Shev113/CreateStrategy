# utils.py
import json
import os
import sys
import tkinter as tk
from tkinter import ttk


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


FAVORITES_PATH = os.path.join(app_dir(), 'results', 'favorites.json')
INT_KEYS = {'min_hits', 'max_hold', 'rsi_period', 'entry_type', 'fisher_period', 'trend_period', 'lookback', 'smooth1', 'smooth2', 'smooth3', 'vol_period', 'cog_period', 'tsi_roc', 'tsi_smooth', 'tsi_signal', 'eco_ave1', 'eco_ave2', 'eco_ave3', 'psych_period', 'hv_fast', 'hv_slow', 'tcf_period', 'adjust_method', 'tether_period', 'tether_vol_period', 'tether_ma_fast', 'tether_ma_slow', 'reg_period', 'fear_period', 'dx_period', 'j2l_period', 'ma_rs_rsi', 'ma_rs_fast', 'ma_rs_slow', 'rmta_period', 'fazola_ema', 'fazola_roc_fast', 'fazola_roc_slow', 'ifish_rsi_period', 'ifish_wma_period', 'progo_period', 'siroc_prd1', 'siroc_prd2', 'siroc_prd3', 'jkl_opt2', 'jkl_opt3', 'cci_period', 'cci_ma_period', 'trend_osc_ma', 'trend_osc_slope', 'trend_osc_smooth', 'dinapoli_k', 'dinapoli_d', 'dinapoli_slow', 'coppock_roc1', 'coppock_roc2', 'coppock_wma', 'dt_lookback', 'sd_fast_ma', 'sd_slow_ma', 'sd_vol_period', 'lc_timezone', 'lc_phase_shift', 'dbo_lookback', 'dbo_vol_lookback', 'dbo_floor', 'dbo_ceiling', 'bbm_macd_fast', 'bbm_macd_slow', 'bbm_macd_signal', 'bbm_bb_period', 'bc_period', 'bc_vol_period'}


def normalize_numeric_params(params):
    result = {}
    for k, v in params.items():
        if isinstance(v, str):
            try:
                result[k] = int(v) if k in INT_KEYS else float(v)
            except (ValueError, TypeError):
                result[k] = v
        else:
            result[k] = v
    return result


def migrate_ticker_settings(path):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    changed = False
    for ticker, entry in data.items():
        params = entry.get('params', {})
        normalized = normalize_numeric_params(params)
        if normalized != params:
            data[ticker]['params'] = normalized
            changed = True
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_favorites():
    if not os.path.exists(FAVORITES_PATH):
        return []
    try:
        with open(FAVORITES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_favorites(favorites):
    os.makedirs(os.path.join(app_dir(), 'results'), exist_ok=True)
    with open(FAVORITES_PATH, 'w', encoding='utf-8') as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)


def toggle_favorite(favorites, ticker):
    if ticker in favorites:
        favorites.remove(ticker)
    else:
        favorites.insert(0, ticker)
    save_favorites(favorites)
    return favorites


def sort_tickers_by_favorites(all_tickers, favorites):
    all_set = set(all_tickers)
    favs = [t for t in favorites if t in all_set]
    others = [t for t in all_tickers if t not in set(favs)]
    return favs + others


def tree_batch_insert(tree, items, clear=True):
    """Batch-insert items into ttk.Treeview with minimized redraws.
    
    items: list of dicts with keys 'values' and optionally 'tags', 'iid'
    """
    if clear:
        tree.delete(*tree.get_children())
    if not items:
        return
    for item in items:
        kwargs = {'values': item['values']}
        if 'tags' in item:
            kwargs['tags'] = item['tags']
        if 'iid' in item:
            kwargs['iid'] = item['iid']
        tree.insert('', 'end', **kwargs)
    tree.update_idletasks()


class ToolTip:
    """Всплывающая подсказка при наведении на виджет."""

    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tw = None
        self._after_id = None
        widget.bind('<Enter>', self._schedule)
        widget.bind('<Leave>', self._hide)

    def _schedule(self, event):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
        self._after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self._tw:
            return
        self._tw = tk.Toplevel(self.widget)
        self._tw.wm_overrideredirect(True)
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self._tw.wm_geometry(f'+{x}+{y}')
        lbl = ttk.Label(self._tw, text=self.text, background='lightyellow',
                        foreground='black', relief='solid', padding=4, font=('', 8))
        lbl.pack()
        self._tw.lift()

    def _hide(self, event):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        if self._tw:
            self._tw.destroy()
            self._tw = None

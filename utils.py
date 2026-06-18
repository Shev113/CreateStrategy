# utils.py
import json
import os

FAVORITES_PATH = os.path.join('results', 'favorites.json')
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
    os.makedirs('results', exist_ok=True)
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

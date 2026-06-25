# cointegration.py
import numpy as np
from typing import List, Tuple, Dict, Optional
from itertools import combinations


def _ols_regression(y, x):
    n = len(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    ss_xy = np.sum((x - x_mean) * (y - y_mean))
    ss_xx = np.sum((x - x_mean) ** 2)
    if ss_xx == 0:
        return 0, y_mean
    beta = ss_xy / ss_xx
    alpha = y_mean - beta * x_mean
    return alpha, beta


def _adf_statistic(series):
    n = len(series)
    if n < 20:
        return 0, 1.0

    dy = np.diff(series)
    y_lag = series[:-1]

    alpha, beta = _ols_regression(dy, y_lag)
    residuals = dy - alpha - beta * y_lag
    se = np.sqrt(np.sum(residuals ** 2) / (n - 2))
    if se == 0:
        return 0, 1.0

    t_stat = beta / (se / np.sqrt(np.sum(y_lag ** 2) - np.mean(y_lag) ** 2 * len(y_lag)))

    approx_crit = {
        1: -3.43,
        5: -2.86,
        10: -2.57,
    }

    if t_stat < approx_crit[1]:
        p_value = 0.01
    elif t_stat < approx_crit[5]:
        p_value = 0.05
    elif t_stat < approx_crit[10]:
        p_value = 0.10
    else:
        p_value = 1.0

    return t_stat, p_value


def compute_spread(price_y, price_x, hedge_ratio=None):
    if hedge_ratio is None:
        _, hedge_ratio = _ols_regression(np.array(price_y), np.array(price_x))
    return np.array(price_y) - hedge_ratio * np.array(price_x)


def calc_half_life(spread):
    if len(spread) < 10:
        return float('inf')

    lag = spread[:-1]
    diff = spread[1:] - lag
    alpha, beta = _ols_regression(diff, lag)

    if beta >= 0:
        return float('inf')

    hl = -np.log(2) / beta
    return max(hl, 0.1)


def find_cointegrated_pairs(price_data: Dict[str, List[float]],
                             max_pairs: int = 20,
                             min_half_life: float = 0.5,
                             max_half_life: float = 50,
                             progress_fn=None) -> List[Dict]:
    tickers = list(price_data.keys())
    n = len(tickers)

    if n < 2:
        return []

    pairs = []
    total = n * (n - 1) // 2
    current = 0

    for i, j in combinations(range(n), 2):
        t1 = tickers[i]
        t2 = tickers[j]
        p1 = np.array(price_data[t1])
        p2 = np.array(price_data[t2])

        min_len = min(len(p1), len(p2))
        if min_len < 30:
            current += 1
            continue

        p1 = p1[-min_len:]
        p2 = p2[-min_len:]

        mask = (p1 > 0) & (p2 > 0)
        p1_clean = p1[mask]
        p2_clean = p2[mask]

        if len(p1_clean) < 30:
            current += 1
            continue

        correlation = np.corrcoef(p1_clean, p2_clean)[0, 1]
        if abs(correlation) < 0.5:
            current += 1
            if progress_fn:
                progress_fn(current, total)
            continue

        alpha, hedge_ratio = _ols_regression(p1_clean, p2_clean)
        spread = p1_clean - hedge_ratio * p2_clean

        adf_stat, p_value = _adf_statistic(spread)
        half_life = calc_half_life(spread)

        if p_value > 0.10:
            current += 1
            if progress_fn:
                progress_fn(current, total)
            continue

        if half_life < min_half_life or half_life > max_half_life:
            current += 1
            if progress_fn:
                progress_fn(current, total)
            continue

        spread_mean = np.mean(spread)
        spread_std = np.std(spread)
        if spread_std == 0:
            current += 1
            continue

        zscore_last = (spread[-1] - spread_mean) / spread_std

        pairs.append({
            'ticker_y': t1,
            'ticker_x': t2,
            'correlation': round(correlation, 3),
            'hedge_ratio': round(hedge_ratio, 4),
            'intercept': round(alpha, 2),
            'adf_stat': round(adf_stat, 2),
            'p_value': round(p_value, 3),
            'half_life': round(half_life, 1),
            'spread_mean': round(spread_mean, 4),
            'spread_std': round(spread_std, 4),
            'zscore_last': round(zscore_last, 2),
            'spread': spread.tolist()[-min(500, len(spread)):],
        })

        current += 1
        if progress_fn:
            progress_fn(current, total)

    pairs.sort(key=lambda p: p['p_value'])

    return pairs[:max_pairs]


def format_pairs_report(pairs: List[Dict]) -> str:
    L = []
    L.append("=" * 55)
    L.append("     КОИНТЕГРИРОВАННЫЕ ПАРЫ")
    L.append("=" * 55)
    L.append("")

    if not pairs:
        L.append("  Коинтегрированных пар не найдено.")
        L.append("")
        L.append("  Попробуйте:")
        L.append("  - Увеличить количество тикеров")
        L.append("  - Выбрать тикеры из одного сектора")
        L.append("  - Увеличить период данных")
        L.append("")
        return '\n'.join(L)

    L.append(f"  Найдено пар: {len(pairs)}")
    L.append("")

    for rank, p in enumerate(pairs, 1):
        L.append(f"  --- Пара #{rank} ---")
        L.append(f"  {p['ticker_y']} / {p['ticker_x']}")
        L.append(f"  Корреляция:    {p['correlation']:.3f}")
        L.append(f"  Hedge ratio:   {p['hedge_ratio']:.4f}")
        L.append(f"  ADF стат.:     {p['adf_stat']:.2f} (p={p['p_value']:.3f})")
        L.append(f"  Half-life:     {p['half_life']:.1f} дней")
        L.append(f"  Z-score:      {p['zscore_last']:.2f}")
        L.append("")

    L.append("=" * 55)
    return '\n'.join(L)

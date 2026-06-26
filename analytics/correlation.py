import numpy as np
from typing import List, Dict, Optional, Tuple


def calc_correlation_matrix(price_data: Dict[str, List[float]]) -> Dict:
    tickers = sorted(price_data.keys())
    n = len(tickers)
    if n < 2:
        return {'tickers': tickers, 'matrix': [], 'pairs': []}

    min_len = min(len(price_data[t]) for t in tickers)
    if min_len < 2:
        return {'tickers': tickers, 'matrix': [[0]*n for _ in range(n)], 'pairs': []}

    returns = {}
    for t in tickers:
        prices = np.array(price_data[t][-min_len:], dtype=float)
        ret = np.diff(prices) / prices[:-1]
        ret = ret[np.isfinite(ret)]
        returns[t] = ret

    max_ret_len = min(len(returns[t]) for t in tickers)
    if max_ret_len < 2:
        return {'tickers': tickers, 'matrix': [[0]*n for _ in range(n)], 'pairs': []}

    data_matrix = np.column_stack([returns[t][-max_ret_len:] for t in tickers])
    try:
        corr = np.corrcoef(data_matrix, rowvar=False)
    except Exception:
        corr = np.eye(n)

    if corr.ndim != 2 or corr.shape != (n, n):
        corr = np.eye(n)

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            c = float(corr[i, j])
            if np.isfinite(c):
                pairs.append({
                    'ticker_a': tickers[i],
                    'ticker_b': tickers[j],
                    'correlation': round(c, 3),
                })
    pairs.sort(key=lambda x: abs(x['correlation']), reverse=True)

    return {
        'tickers': tickers,
        'matrix': corr.tolist(),
        'pairs': pairs,
    }

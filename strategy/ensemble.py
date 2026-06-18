# ensemble.py
import logging
from strategy.config import get_strategy_func, get_strategy_params

logger = logging.getLogger(__name__)


def check_ensemble(candles, idx, levels, atr,
                   atr_sl=1.0, atr_tp=2.0,
                   sub_strategies='bounce', vote_method=0,
                   **strategy_kwargs):
    """Ensemble strategy: runs multiple strategies and votes on the signal.

    Args:
        sub_strategies: comma-separated list of strategy IDs
        vote_method: 0=majority (>50%), 1=any (first wins), 2=consensus (all agree)
    """
    if not sub_strategies:
        return None

    sids = [s.strip() for s in sub_strategies.split(',') if s.strip()]
    if len(sids) < 2:
        return None

    signals = []
    for sid in sids:
        func = get_strategy_func(sid)
        if func is None:
            logger.warning("Ensemble: unknown strategy '%s', skipping", sid)
            continue

        valid_keys = {p['key'] for p in get_strategy_params(sid)}
        kwargs = {'atr_sl': atr_sl, 'atr_tp': atr_tp}
        for k, v in strategy_kwargs.items():
            if k in valid_keys:
                kwargs[k] = v

        try:
            sig = func(candles, idx, levels, atr, **kwargs)
            if sig:
                signals.append((sid, sig))
        except Exception as e:
            logger.debug("Ensemble: %s errored: %s", sid, e)

    if not signals:
        return None

    if vote_method == 1:
        return signals[0][1]

    if vote_method == 2:
        sides = {s['side'] for _, s in signals}
        if len(sides) == 1:
            return _aggregate_signals(signals, atr_sl, atr_tp, atr)
        return None

    # Majority vote (default)
    buys = [s for _, s in signals if s['side'] == 'BUY']
    sells = [s for _, s in signals if s['side'] == 'SELL']
    n = len(signals)
    if len(buys) > n / 2:
        return _aggregate_signals([(None, s) for s in buys], atr_sl, atr_tp, atr)
    if len(sells) > n / 2:
        return _aggregate_signals([(None, s) for s in sells], atr_sl, atr_tp, atr)
    return None


def _aggregate_signals(signals, atr_sl, atr_tp, atr):
    """Combine multiple signals of the same side into one."""
    side = signals[0][1]['side']
    levels = [s['level'] for _, s in signals]
    avg_level = sum(levels) / len(levels)

    # Most conservative SL
    sl_prices = [s['sl_price'] for _, s in signals]
    sl_price = min(sl_prices) if side == 'BUY' else max(sl_prices)

    # Most conservative TP
    tp_prices = [s['tp_price'] for _, s in signals]
    tp_price = max(tp_prices) if side == 'BUY' else min(tp_prices)

    return {
        'side': side,
        'level': round(avg_level, 2),
        'sl_price': round(sl_price, 2),
        'tp_price': round(tp_price, 2),
    }

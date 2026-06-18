# levels.py
from collections import Counter, defaultdict


def round_to_tolerance(price, tolerance):
    if tolerance <= 0:
        return price
    return round(price / tolerance) * tolerance


def find_strong_zones(candles_list, atr_value, min_hits=5, max_zones=6):
    if not candles_list or not atr_value or atr_value <= 0:
        return []

    tolerance = atr_value * 0.5
    all_prices = []
    for candle in candles_list:
        if candle is None or len(candle) < 4:
            continue
        all_prices.append(round_to_tolerance(float(candle[1]), tolerance))
        all_prices.append(round_to_tolerance(float(candle[2]), tolerance))
        all_prices.append(round_to_tolerance(float(candle[3]), tolerance))

    if not all_prices:
        return []

    counter = Counter(all_prices)
    sorted_items = sorted(
        counter.items(), key=lambda x: x[1], reverse=True)
    return [(price, count) for price, count in sorted_items if count >= min_hits][:max_zones]


def find_pivot_levels(candles_list, lookback=5, min_strength=2, atr_value=None):
    """Find support/resistance levels using pivot point detection.

    A pivot high = candle whose high is the highest among `lookback` candles on each side.
    A pivot low = candle whose low is the lowest among `lookback` candles on each side.
    Nearby pivots are clustered into zones.

    Returns:
        list of (price, strength, level_type) where level_type is 'support' or 'resistance'
    """
    if not candles_list or len(candles_list) < lookback * 2 + 1:
        return []

    highs = [float(c[2]) for c in candles_list if c is not None and len(c) >= 4]
    lows = [float(c[3]) for c in candles_list if c is not None and len(c) >= 4]

    if len(highs) < lookback * 2 + 1:
        return []

    pivot_highs = []
    pivot_lows = []

    for i in range(lookback, len(highs) - lookback):
        if all(highs[i] >= highs[i - k] and highs[i] >= highs[i + k] for k in range(1, lookback + 1)):
            pivot_highs.append(highs[i])
        if all(lows[i] <= lows[i - k] and lows[i] <= lows[i + k] for k in range(1, lookback + 1)):
            pivot_lows.append(lows[i])

    # Clustering: merge adjacent pivots within tolerance
    def cluster_pivots(prices, tolerance):
        if not prices:
            return []
        sorted_p = sorted(prices)
        groups = []
        current = [sorted_p[0]]
        for p in sorted_p[1:]:
            if p - current[-1] <= tolerance:
                current.append(p)
            else:
                groups.append(current)
                current = [p]
        groups.append(current)
        return [(sum(g) / len(g), len(g)) for g in groups]

    avg_price = (max(max(highs), max(lows)) + min(min(highs), min(lows))) / 2
    tol = atr_value if atr_value and atr_value > 0 else avg_price * 0.005

    resistance = cluster_pivots(pivot_highs, tol)
    support = cluster_pivots(pivot_lows, tol)

    result = []
    for price, strength in resistance:
        if strength >= min_strength:
            result.append((price, strength, 'resistance'))
    for price, strength in support:
        if strength >= min_strength:
            result.append((price, strength, 'support'))

    result.sort(key=lambda x: x[0])
    return result


def filter_levels_by_price(levels, current_price, atr, proximity=2.0):
    """Filter levels to only those within proximity * ATR of current price."""
    threshold = proximity * atr
    in_range = []
    for item in levels:
        price = item[0]
        if abs(price - current_price) <= threshold:
            in_range.append(item)
    return in_range

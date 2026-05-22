# levels.py
from collections import Counter


def round_to_tolerance(price, tolerance):
    if tolerance <= 0:
        return price
    return round(price / tolerance) * tolerance


def find_horizontal_levels(candles_list, min_hits=5, tolerance=None):
    if not candles_list:
        return []

    if tolerance is None:
        if not candles_list:
            return []
        prices_for_estimate = []
        for c in candles_list:
            if c and len(c) >= 4:
                prices_for_estimate.append(float(c[3]))
        if prices_for_estimate:
            avg_price = sum(prices_for_estimate) / len(prices_for_estimate)
            tolerance = avg_price * 0.005
        else:
            tolerance = 0.01

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
    levels = [price for price, count in sorted(
        counter.items(), key=lambda x: x[1], reverse=True) if count >= min_hits]
    return levels

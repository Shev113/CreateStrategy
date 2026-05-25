# levels.py
from collections import Counter


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

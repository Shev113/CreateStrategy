# levels.py
from collections import Counter


def find_horizontal_levels(candles_list, min_hits=5):
    if not candles_list:
        return []

    all_prices = []
    for candle in candles_list:
        if candle is None or len(candle) < 4:
            continue
        all_prices.append(float(candle[1]))
        all_prices.append(float(candle[2]))
        all_prices.append(float(candle[3]))

    if not all_prices:
        return []

    counter = Counter(all_prices)
    levels = [price for price, count in sorted(
        counter.items(), key=lambda x: x[1], reverse=True) if count >= min_hits]
    return levels

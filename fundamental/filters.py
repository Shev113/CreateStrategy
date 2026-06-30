import logging


def filter_by_fundamentals(tickers_data, criteria=None):
    if not criteria:
        criteria = {}

    min_div_yield = criteria.get('min_div_yield')
    max_pe = criteria.get('max_pe')
    min_pe = criteria.get('min_pe')
    max_pb = criteria.get('max_pb')
    min_market_cap = criteria.get('min_market_cap')
    max_market_cap = criteria.get('max_market_cap')
    min_div_count = criteria.get('min_div_count', 0)
    min_score = criteria.get('min_score')

    results = []
    for ticker, data in tickers_data.items():
        if not data:
            continue

        passes = True

        pe = data.get('pe')
        pb = data.get('pb')
        div_yield = data.get('div_yield')
        market_cap = data.get('market_cap')
        div_count = data.get('div_count', len(data.get('dividends', [])))

        if min_pe is not None and pe is not None:
            if pe < min_pe:
                passes = False

        if max_pe is not None and pe is not None:
            if pe > max_pe:
                passes = False

        if max_pb is not None and pb is not None:
            if pb > max_pb:
                passes = False

        if min_div_yield is not None and div_yield is not None:
            if div_yield < min_div_yield:
                passes = False

        if min_market_cap is not None and market_cap is not None:
            if market_cap < min_market_cap:
                passes = False

        if max_market_cap is not None and market_cap is not None:
            if market_cap > max_market_cap:
                passes = False

        if min_div_count > 0 and div_count < min_div_count:
            passes = False

        if min_score is not None and data.get('score') is not None:
            if data['score'] < min_score:
                passes = False

        if passes:
            results.append(ticker)

    return results


def compare_sector(tickers_data, sector_map=None):
    sectors = {}
    for ticker, data in tickers_data.items():
        sector = 'Прочее'
        if sector_map and ticker in sector_map:
            sector = sector_map[ticker]
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(data)

    comparison = {}
    for sector, items in sectors.items():
        if not items:
            continue

        avg_pe = _avg([d.get('pe') for d in items if d.get('pe') is not None and d['pe'] > 0])
        avg_pb = _avg([d.get('pb') for d in items if d.get('pb') is not None and d['pb'] > 0])
        avg_div = _avg([d.get('div_yield') for d in items if d.get('div_yield') is not None])
        avg_cap = _avg([d.get('market_cap') for d in items if d.get('market_cap') is not None])

        comparison[sector] = {
            'sector': sector,
            'count': len(items),
            'avg_pe': round(avg_pe, 1) if avg_pe else None,
            'avg_pb': round(avg_pb, 2) if avg_pb else None,
            'avg_div_yield': round(avg_div, 2) if avg_div else None,
            'avg_market_cap': round(avg_cap, 0) if avg_cap else None,
        }

    return comparison


def _avg(values):
    if not values:
        return None
    return sum(values) / len(values)

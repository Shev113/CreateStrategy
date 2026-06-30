import logging


def score_value(data):
    if not data:
        return 0, {}
    details = {}
    score = 0
    max_score = 40

    pe = data.get('pe')
    pb = data.get('pb')
    div_yield = data.get('div_yield')

    if pe is not None:
        if pe <= 0:
            details['pe'] = 'Отрицательный P/E'
        elif pe < 8:
            score += 10
            details['pe'] = f'Очень дешёвый ({pe:.1f})'
        elif pe < 15:
            score += 7
            details['pe'] = f'Недооценён ({pe:.1f})'
        elif pe < 25:
            score += 4
            details['pe'] = f'Справедливо ({pe:.1f})'
        elif pe < 40:
            score += 2
            details['pe'] = f'Дороговат ({pe:.1f})'
        else:
            details['pe'] = f'Дорогой ({pe:.1f})'
    else:
        max_score -= 10

    if pb is not None:
        if pb <= 0:
            details['pb'] = 'Отрицательный P/B'
        elif pb < 0.8:
            score += 10
            details['pb'] = f'Глубоко ниже бал. стоимости ({pb:.2f})'
        elif pb < 1.2:
            score += 7
            details['pb'] = f'Около бал. стоимости ({pb:.2f})'
        elif pb < 2.5:
            score += 3
            details['pb'] = f'Премия ({pb:.2f})'
        else:
            details['pb'] = f'Высокая премия ({pb:.2f})'
    else:
        max_score -= 10

    if div_yield is not None:
        if div_yield > 8:
            score += 10
            details['div_yield'] = f'Высокая ({div_yield:.1f}%)'
        elif div_yield > 5:
            score += 7
            details['div_yield'] = f'Хорошая ({div_yield:.1f}%)'
        elif div_yield > 2:
            score += 4
            details['div_yield'] = f'Умеренная ({div_yield:.1f}%)'
        elif div_yield > 0:
            score += 1
            details['div_yield'] = f'Низкая ({div_yield:.1f}%)'
        else:
            details['div_yield'] = 'Нет'
    else:
        max_score -= 10

    mc = data.get('market_cap')
    if mc:
        if mc > 500e9:
            score += 10
            details['cap_size'] = 'Крупнокап (>500 млрд)'
        elif mc > 100e9:
            score += 7
            details['cap_size'] = 'Среднекап (100-500 млрд)'
        elif mc > 10e9:
            score += 4
            details['cap_size'] = 'Малокап (10-100 млрд)'
        else:
            details['cap_size'] = 'Микрокап (<10 млрд)'
    else:
        max_score -= 10

    pct = round((score / max_score) * 100) if max_score > 0 else 0
    return pct, details


def score_dividend(data):
    if not data:
        return 0, {}
    details = {}
    score = 0
    max_score = 30

    dividends = data.get('dividends', [])
    div_yield = data.get('div_yield')

    if not dividends:
        return 0, {'status': 'Дивиденды не выплачиваются'}

    if len(dividends) >= 4:
        score += 10
        details['consistency'] = f'Стабильная ({len(dividends)} выплат)'
    elif len(dividends) >= 2:
        score += 5
        details['consistency'] = f'Недавние ({len(dividends)} выплат)'
    else:
        details['consistency'] = f'Единичная ({len(dividends)})'

    if div_yield is not None:
        if div_yield > 8:
            score += 10
        elif div_yield > 5:
            score += 7
        elif div_yield > 2:
            score += 4
        elif div_yield > 0:
            score += 1
        details['yield_score'] = f'{div_yield:.1f}%'
    else:
        max_score -= 10

    if len(dividends) >= 2:
        values = [d['value'] for d in dividends[:4]]
        avg = sum(values) / len(values)
        if len(values) >= 2:
            min_v = min(values)
            growth = (values[0] / values[-1] - 1) * 100 if values[-1] > 0 else 0
            if growth > 20:
                score += 10
                details['growth'] = f'Рост {growth:.0f}%'
            elif growth > 0:
                score += 6
                details['growth'] = f'Рост {growth:.0f}%'
            elif growth > -10:
                score += 3
                details['growth'] = f'Стабильно ({growth:.0f}%)'
            else:
                details['growth'] = f'Сокращение {growth:.0f}%'
        else:
            max_score -= 10
    else:
        max_score -= 10

    pct = round((score / max_score) * 100) if max_score > 0 else 0
    return pct, details


def score_quality(data):
    if not data:
        return 0, {}
    details = {}
    score = 0
    max_score = 30

    mc = data.get('market_cap')
    if mc:
        if mc > 500e9:
            score += 15
            details['size'] = 'Large cap — высокая ликвидность'
        elif mc > 100e9:
            score += 10
            details['size'] = 'Mid cap — хорошая ликвидность'
        elif mc > 10e9:
            score += 5
            details['size'] = 'Small cap — ограниченная ликвидность'
        else:
            details['size'] = 'Micro cap — низкая ликвидность'
    else:
        max_score -= 15

    divs = data.get('dividends', [])
    if len(divs) >= 3:
        score += 10
        details['div_history'] = f'История дивидендов ({len(divs)}) лет'
    elif len(divs) >= 1:
        score += 4
        details['div_history'] = 'Единичные дивиденды'
    else:
        max_score -= 10

    pe = data.get('pe')
    if pe is not None and pe > 0:
        if 5 < pe < 25:
            score += 5
            details['pe_quality'] = f'Разумная оценка (P/E={pe:.1f})'
        else:
            details['pe_quality'] = f'P/E={pe:.1f} — возможный риск'
    else:
        max_score -= 5

    pct = round((score / max_score) * 100) if max_score > 0 else 0
    return pct, details


def compute_total_score(data):
    if not data:
        return 0, {}, ''

    val_score, val_details = score_value(data)
    div_score, div_details = score_dividend(data)
    qual_score, qual_details = score_quality(data)

    total = round(val_score * 0.4 + div_score * 0.3 + qual_score * 0.3)

    if total >= 75:
        rating = 'ПОКУПАТЬ'
    elif total >= 55:
        rating = 'ДЕРЖАТЬ'
    elif total >= 35:
        rating = 'ОСТОРОЖНО'
    else:
        rating = 'ИЗБЕГАТЬ'

    details = {
        'value': val_score,
        'value_details': val_details,
        'dividend': div_score,
        'dividend_details': div_details,
        'quality': qual_score,
        'quality_details': qual_details,
        'rating': rating,
    }

    return total, details, rating


def format_score_report(total, details, rating):
    lines = []
    lines.append(f"{'=' * 45}")
    lines.append(f"  ФУНДАМЕНТАЛЬНЫЙ СКОРИНГ")
    lines.append(f"{'=' * 45}")
    lines.append('')

    rating_colors = {'ПОКУПАТЬ': '★★★★★', 'ДЕРЖАТЬ': '★★★☆☆', 'ОСТОРОЖНО': '★★☆☆☆', 'ИЗБЕГАТЬ': '★☆☆☆☆'}
    lines.append(f"  Общий балл: {total}/100  {rating_colors.get(rating, '')}")
    lines.append(f"  Рейтинг:    {rating}")
    lines.append('')

    lines.append(f"{'─' * 45}")
    lines.append(f"  ЦЕННОСТЬ (Value): {details.get('value', 0)}/100")
    lines.append(f"{'─' * 45}")
    for k, v in details.get('value_details', {}).items():
        lines.append(f"    {v}")

    lines.append('')
    lines.append(f"{'─' * 45}")
    lines.append(f"  ДИВИДЕНДЫ: {details.get('dividend', 0)}/100")
    lines.append(f"{'─' * 45}")
    for k, v in details.get('dividend_details', {}).items():
        lines.append(f"    {v}")

    lines.append('')
    lines.append(f"{'─' * 45}")
    lines.append(f"  КАЧЕСТВО: {details.get('quality', 0)}/100")
    lines.append(f"{'─' * 45}")
    for k, v in details.get('quality_details', {}).items():
        lines.append(f"    {v}")

    lines.append(f"\n{'=' * 45}")
    return '\n'.join(lines)

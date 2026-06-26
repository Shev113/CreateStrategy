def calc_position(entry_price, sl_price, capital, risk_pct,
                   tp_price=None, commission_pct=0.05):
    if not entry_price or entry_price <= 0:
        return None
    if not sl_price or sl_price <= 0:
        return None
    if not capital or capital <= 0:
        return None
    if not risk_pct or risk_pct <= 0:
        return None

    risk_rub = capital * (risk_pct / 100.0)
    risk_per_share = abs(entry_price - sl_price)
    if risk_per_share <= 0:
        return None

    qty = int(risk_rub / risk_per_share)
    if qty <= 0:
        return None

    position_value = entry_price * qty
    commission = position_value * (commission_pct / 100.0)
    total_cost = position_value + commission

    actual_risk = risk_per_share * qty
    actual_risk_pct = actual_risk / capital * 100

    r_multiple = None
    reward_risk = None
    if tp_price and tp_price > 0:
        reward_per_share = abs(tp_price - entry_price)
        r_multiple = reward_per_share / risk_per_share if risk_per_share else None
        reward_risk = r_multiple

    result = {
        'ticker': '',
        'entry_price': entry_price,
        'sl_price': sl_price,
        'tp_price': tp_price,
        'capital': capital,
        'risk_pct': risk_pct,
        'qty': qty,
        'position_value': round(position_value, 2),
        'commission': round(commission, 2),
        'total_cost': round(total_cost, 2),
        'risk_per_share': round(risk_per_share, 2),
        'actual_risk_rub': round(actual_risk, 2),
        'actual_risk_pct': round(actual_risk_pct, 2),
        'r_multiple': round(r_multiple, 2) if r_multiple else None,
        'reward_risk': round(reward_risk, 2) if reward_risk else None,
        'side': 'BUY' if sl_price < entry_price else 'SELL',
    }

    if tp_price:
        tp_pnl_per_share = abs(tp_price - entry_price)
        sl_pnl_per_share = abs(entry_price - sl_price)
        result['tp_pnl'] = round(tp_pnl_per_share * qty - commission * 2, 2)
        result['sl_pnl'] = round(-sl_pnl_per_share * qty - commission * 2, 2)

    return result


def format_position_report(result):
    if not result:
        return 'Ошибка: невозможно рассчитать позицию.\nПроверьте входные данные.'

    side_label = 'ЛОНГ' if result['side'] == 'BUY' else 'ШОРТ'
    lines = [
        f"{'=' * 45}",
        f"  КАЛЬКУЛЯТОР ПОЗИЦИИ",
        f"{'=' * 45}",
        "",
        f"  Тикер:            {result['ticker'] or '—'}",
        f"  Направление:      {side_label}",
        f"  Цена входа:       {result['entry_price']:.2f} руб.",
        f"  Стоп-лосс:        {result['sl_price']:.2f} руб.",
    ]

    if result.get('tp_price'):
        lines.append(f"  Тейк-профит:      {result['tp_price']:.2f} руб.")

    lines += [
        "",
        f"{'─' * 45}",
        f"  РАСЧЁТ",
        f"{'─' * 45}",
        "",
        f"  Капитал:          {result['capital']:,.0f} руб.",
        f"  Риск на сделку:   {result['risk_pct']:.1f}% ({result['capital'] * result['risk_pct'] / 100:,.0f} руб.)",
        f"  Риск на акцию:    {result['risk_per_share']:.2f} руб.",
        "",
        f"  >>> КОЛИЧЕСТВО:   {result['qty']} шт.",
        f"  Объём позиции:    {result['position_value']:,.2f} руб.",
        f"  Комиссия:         {result['commission']:,.2f} руб.",
        f"  Итого затраты:    {result['total_cost']:,.2f} руб.",
        "",
        f"  Фактич. риск:     {result['actual_risk_rub']:,.2f} руб. ({result['actual_risk_pct']:.2f}%)",
    ]

    if result.get('r_multiple') is not None:
        lines += [
            "",
            f"{'─' * 45}",
            f"  СООТНОШЕНИЕ РИСК/ПРИБЫЛЬ",
            f"{'─' * 45}",
            "",
            f"  R-кратность:      {result['r_multiple']:.2f}R",
            f"  Reward/Risk:      1 : {result['reward_risk']:.2f}",
        ]

    if result.get('tp_pnl') is not None:
        lines += [
            "",
            f"  P&L при TP:       {result['tp_pnl']:+,.2f} руб.",
            f"  P&L при SL:       {result['sl_pnl']:+,.2f} руб.",
        ]

    lines.append(f"\n{'=' * 45}")
    return '\n'.join(lines)

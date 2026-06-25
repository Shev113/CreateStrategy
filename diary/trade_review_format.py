# trade_review_format.py
from diary.trade_review import TradeReviewResult

SIDE_LABELS = {'LONG': 'Лонг', 'SHORT': 'Шорт'}
REASON_LABELS = {'SL': 'По SL', 'TP': 'По TP', 'TIMEOUT': 'Таймаут', 'Вручную': 'Вручную'}


def format_review_report(r: TradeReviewResult) -> str:
    L = []
    L.append("=" * 55)
    L.append("        ОБЗОР ТОРГОВЛИ (TRADE REVIEW 2.0)")
    L.append("=" * 55)
    L.append("")

    L.append("-- Общая статистика --")
    L.append(f"  Всего сделок:      {r.total_trades}")
    L.append(f"  Закрытых:          {r.closed_trades}")
    L.append(f"  Открытых:          {r.open_trades}")
    L.append(f"  Выигрышей:         {r.wins}")
    L.append(f"  Проигрышей:        {r.losses}")
    L.append(f"  Безубытков:        {r.breakeven}")
    L.append(f"  Win Rate:          {r.win_rate:.1f}%")
    L.append(f"  Profit Factor:     {r.profit_factor:.2f}")
    L.append("")

    L.append("-- Доходность --")
    L.append(f"  Общий P&L:         {r.total_pnl:+,.2f} RUB")
    L.append(f"  Средний выигрыш:   {r.avg_win:+,.2f} RUB")
    L.append(f"  Средний проигрыш:  {r.avg_loss:+,.2f} RUB")
    L.append(f"  Макс. выигрыш:     {r.max_win:+,.2f} RUB")
    L.append(f"  Макс. проигрыш:    {r.max_loss:+,.2f} RUB")
    L.append(f"  Ожидание:          {r.expectancy:+,.2f} RUB ({r.expectancy_pct:+.4f}%)")
    L.append("")

    L.append("-- Риск-метрики --")
    L.append(f"  Макс. просадка:    -{r.max_drawdown:.2f}%")
    L.append(f"  Длит. просадки:    {r.max_drawdown_duration} сделок")
    L.append(f"  Avg R-multiple:    {r.avg_rr:.2f}R")
    L.append(f"  Sharpe (сделок):   {r.sharpe_ratio:.2f}")
    L.append("")

    L.append("-- Серии --")
    streak_label = {'win': 'прибыльная', 'loss': 'убыточная', 'none': 'нет'}
    L.append(f"  Макс. подряд выигрышей:  {r.max_consecutive_wins}")
    L.append(f"  Макс. подряд проигрышей: {r.max_consecutive_losses}")
    L.append(f"  Текущая серия: {streak_label.get(r.current_streak_type, r.current_streak_type)} ({r.current_streak_len})")
    L.append("")

    L.append("-- Срок удержания --")
    h = r.hold_days_stats
    L.append(f"  Средний:  {h['avg']} дн.")
    L.append(f"  Медиана:  {h['median']} дн.")
    L.append(f"  Мин/Макс: {h['min']}/{h['max']} дн.")
    L.append("")

    L.append("-- По направлению --")
    for side, d in r.by_side.items():
        label = SIDE_LABELS.get(side, side)
        L.append(f"  {label}: {d['count']} сделок, WR={d['win_rate']:.1f}%, P&L={d['pnl']:+,.2f}")
    L.append("")

    L.append("-- По причине выхода --")
    for reason, d in r.by_reason.items():
        label = REASON_LABELS.get(reason, reason)
        L.append(f"  {label}: {d['count']} сделок, WR={d['win_rate']:.1f}%, P&L={d['pnl']:+,.2f}")
    L.append("")

    if r.by_ticker:
        L.append("-- По тикерам --")
        sorted_tickers = sorted(r.by_ticker.items(), key=lambda x: x[1]['pnl'], reverse=True)
        for ticker, d in sorted_tickers:
            L.append(f"  {ticker:8s}: {d['count']} сделок, WR={d['win_rate']:.1f}%, P&L={d['pnl']:+,.2f}")
        L.append("")

    if r.by_month:
        L.append("-- По месяцам --")
        for month, d in r.by_month.items():
            L.append(f"  {month}: {d['count']} сделок, WR={d['win_rate']:.1f}%, P&L={d['pnl']:+,.2f}")
        L.append("")

    if r.by_dow:
        L.append("-- По дню недели --")
        for dow, d in r.by_dow.items():
            L.append(f"  {dow}: {d['count']} сделок, WR={d['win_rate']:.1f}%, P&L={d['pnl']:+,.2f}")
        L.append("")

    if r.best_trades:
        L.append("-- Лучшие сделки --")
        for t in r.best_trades[:3]:
            L.append(f"  {t['ticker']} {t['side']} @ {t['entry_price']:.2f} -> {t['exit_price'] or 0:.2f} P&L={t['pnl']:+,.2f} ({t['exit_reason']})")
        L.append("")

    if r.worst_trades:
        L.append("-- Худшие сделки --")
        for t in r.worst_trades[:3]:
            L.append(f"  {t['ticker']} {t['side']} @ {t['entry_price']:.2f} -> {t['exit_price'] or 0:.2f} P&L={t['pnl']:+,.2f} ({t['exit_reason']})")
        L.append("")

    L.append("=" * 55)
    return '\n'.join(L)

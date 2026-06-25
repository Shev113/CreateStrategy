# visualizations.py
import numpy as np
from typing import List, Dict, Optional


def plot_equity_drawdown(equity_curve, drawdown_curve, dates=None, title='Equity & Drawdown'):
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    except ImportError:
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5),
                                    gridspec_kw={'height_ratios': [3, 1]})

    x = range(len(equity_curve))
    ax1.plot(x, equity_curve, linewidth=1.2, color='#2196F3', label='Capital')
    ax1.fill_between(x, equity_curve[0], equity_curve, alpha=0.1, color='#2196F3')
    ax1.axhline(y=equity_curve[0], color='gray', linestyle='--', linewidth=0.5)
    ax1.set_ylabel('Capital (RUB)')
    ax1.set_title(title)
    ax1.legend(fontsize=8)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    step = max(1, len(equity_curve) // 15)
    if dates and len(dates) >= len(x) - 1:
        tick_pos = list(range(0, len(dates), step))
        ax1.set_xticks(tick_pos)
        ax1.set_xticklabels([dates[i] for i in tick_pos if i < len(dates)], rotation=45, fontsize=7)

    ax2.fill_between(x, drawdown_curve, color='#cc0000', alpha=0.4, label='Drawdown')
    ax2.set_ylabel('DD %')
    ax2.set_xlabel('Trades')
    ax2.legend(fontsize=8)

    fig.tight_layout()
    return fig


def plot_pnl_distribution(pnl_values, title='P&L Distribution'):
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(8, 4))

    colors = ['#cc4444' if v < 0 else '#44aa44' for v in pnl_values]
    ax.hist(pnl_values, bins=min(25, max(5, len(pnl_values) // 3)),
            color='#2196F3', alpha=0.7, edgecolor='white')
    ax.axvline(x=0, color='black', linewidth=1)
    ax.axvline(x=np.mean(pnl_values), color='red', linestyle='--', linewidth=1, label=f'Mean={np.mean(pnl_values):.0f}')
    ax.axvline(x=np.median(pnl_values), color='orange', linestyle='--', linewidth=1, label=f'Median={np.median(pnl_values):.0f}')
    ax.set_xlabel('P&L (RUB)')
    ax.set_ylabel('Count')
    ax.set_title(title)
    ax.legend(fontsize=8)

    fig.tight_layout()
    return fig


def plot_r_distribution(r_values, title='R-Multiple Distribution'):
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not r_values:
        return None

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.hist(r_values, bins=min(20, max(5, len(r_values) // 3)),
            color='#9C27B0', alpha=0.7, edgecolor='white')
    ax.axvline(x=0, color='black', linewidth=1)
    ax.axvline(x=np.mean(r_values), color='red', linestyle='--', linewidth=1, label=f'Mean={np.mean(r_values):.2f}R')
    ax.axvline(x=np.median(r_values), color='orange', linestyle='--', linewidth=1, label=f'Median={np.median(r_values):.2f}R')
    ax.set_xlabel('R-multiple')
    ax.set_ylabel('Count')
    ax.set_title(title)
    ax.legend(fontsize=8)

    fig.tight_layout()
    return fig


def plot_rolling_metric(values, window_label='', title='Rolling Metric'):
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not values:
        return None

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(values, linewidth=1, color='#2196F3')
    ax.axhline(y=np.mean(values), color='orange', linestyle='--', linewidth=0.8, label=f'Mean={np.mean(values):.1f}')
    ax.fill_between(range(len(values)), np.mean(values), values, alpha=0.15, color='#2196F3')
    ax.set_ylabel(window_label)
    ax.set_xlabel('Trade window')
    ax.set_title(title)
    ax.legend(fontsize=8)

    fig.tight_layout()
    return fig


def plot_monthly_heatmap(by_month, title='Monthly P&L Heatmap'):
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not by_month:
        return None

    months = sorted(by_month.keys())
    pnls = [by_month[m]['pnl'] for m in months]

    fig, ax = plt.subplots(figsize=(max(6, len(months) * 0.8), 3))

    colors = ['#cc4444' if p < 0 else '#44aa44' for p in pnls]
    bars = ax.bar(range(len(months)), pnls, color=colors, edgecolor='white')
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, rotation=45, fontsize=8)
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.set_ylabel('P&L (RUB)')
    ax.set_title(title)

    for bar, val in zip(bars, pnls):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f'{val:+,.0f}', ha='center', va='bottom' if val >= 0 else 'top',
                fontsize=7)

    fig.tight_layout()
    return fig


def plot_benchmark_comparison(equity_curve, benchmark_curve, title='Strategy vs Benchmark'):
    try:
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not benchmark_curve or len(benchmark_curve) < 2:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))

    norm_strategy = [v / equity_curve[0] * 100 for v in equity_curve]
    norm_bench = [v / benchmark_curve[0] * 100 for v in benchmark_curve]

    min_len = min(len(norm_strategy), len(norm_bench))
    ax.plot(norm_strategy[:min_len], linewidth=1.2, color='#2196F3', label='Strategy')
    ax.plot(norm_bench[:min_len], linewidth=1.2, color='#FF9800', label='IMOEX')
    ax.axhline(y=100, color='gray', linestyle='--', linewidth=0.5)
    ax.set_ylabel('Normalized (%)')
    ax.set_title(title)
    ax.legend(fontsize=8)

    fig.tight_layout()
    return fig

# guide.py — Extended strategy descriptions for the guide tab
# Each entry: { 'author', 'source', 'logic', 'example_params', 'formula_hint' }

STRATEGY_GUIDE = {
    'bounce': {
        'author': 'Общеизвестная',
        'source': 'Классический price action',
        'logic': (
            'Стратегия ищет отскок цены от уровня поддержки/сопротивления. '
            'Сигнал BUY: цена открытия выше уровня, минимум коснулся уровня (или чуть ниже), '
            'закрытие выше уровня — бычий отскок. '
            'Сигнал SELL: цена открытия ниже уровня, максимум коснулся уровня (или чуть выше), '
            'закрытие ниже уровня — медвежий отскок.'
        ),
        'example_params': 'ATR SL=1.0, ATR TP=2.0, min_hits=5',
    },
    'breakout': {
        'author': 'Общеизвестная',
        'source': 'Классический price action',
        'logic': (
            'Стратегия входа при пробое уровня с подтверждением закрытием за уровнем. '
            'BUY: цена закрывается выше уровня + порог пробоя (breakout_threshold × ATR). '
            'SELL: цена закрывается ниже уровня + порог пробоя.'
        ),
        'example_params': 'breakout_threshold=0.3 (ATR), min_hits=5',
    },
    'rsi_levels': {
        'author': 'Уэллс Уайлдер / адаптация',
        'source': 'Классический RSI + уровни',
        'logic': (
            'Комбинация уровней поддержки/сопротивления и RSI. '
            'BUY: цена у уровня поддержки, RSI выходит из зоны перепроданности (пересекает oversold снизу вверх). '
            'SELL: цена у уровня сопротивления, RSI выходит из зоны перекупленности (пересекает overbought сверху вниз).'
        ),
        'example_params': 'RSI period=14, oversold=30, overbought=70, level_proximity=0.5',
    },
    'fisher': {
        'author': 'John Ehlers',
        'source': 'Библиотека стратегий (Fisher Transform by John Ehlers.pdf)',
        'logic': (
            'Fisher Transform преобразует цены в гауссово нормальное распределение для раннего обнаружения '
            'разворотов. Нормализованная цена (0..1) сглаживается EMA (0.33/0.67), затем применяется '
            'Fisher Transform: 0.5 × ln((1+val)/(1-val)). '
            'BUY: Fisher пересекает oversold (-1.5) снизу вверх у уровня поддержки. '
            'SELL: Fisher пересекает overbought (+1.5) сверху вниз у уровня сопротивления.'
        ),
        'example_params': 'fisher_period=10, overbought=1.5, oversold=-1.5',
    },
    'trend': {
        'author': 'M.H. Pee',
        'source': 'Библиотека стратегий (Trend Detection Index + Trend Intensity Index.pdf)',
        'logic': (
            'Комбинация двух индикаторов M.H. Pee: TDI (Trend Detection Index) определяет направление '
            'тренда (1/-1), TII (Trend Intensity Index) измеряет силу тренда (0-100). '
            'BUY: TDI=1 (восходящий тренд), TII ≥ strength (80) у уровня поддержки. '
            'SELL: TDI=-1 (нисходящий тренд), TII ≥ strength (80) у уровня сопротивления.'
        ),
        'example_params': 'trend_period=20, trend_strength=80',
    },
    'smi': {
        'author': 'Robert Lambert',
        'source': 'Библиотека стратегий (Stochastic Momentum Index w. Kase Filter.pdf)',
        'logic': (
            'Stochastic Momentum Index — тройное сглаживание стохастика для фильтрации шума. '
            'Расчёт: value1 = close - midpoint(HHV,LLV), value2 = HHV - LLV, '
            'затем тройное EMA сглаживание (smooth1, smooth2, smooth3). '
            'SMI = 100 × num / (0.5 × den). '
            'BUY: SMI пересекает oversold (-40) снизу вверх у поддержки. '
            'SELL: SMI пересекает overbought (+40) сверху вниз у сопротивления.'
        ),
        'example_params': 'lookback=25, smooth1=13, smooth2=1, smooth3=1, OB=40, OS=-40',
    },
    'volume_divergence': {
        'author': 'Pablo Bozzolo',
        'source': 'Библиотека стратегий (Volume-Price Divergence Indicator by Pablo Bozzolo.pdf)',
        'logic': (
            'Дивергенция объёма и цены: когда цена касается уровня, а объём падает (текущий объём ниже '
            'EMA объёма и ниже предыдущего бара), это указывает на истощение движения. '
            'BUY: цена у поддержки, объём падает — продавцы истощены. '
            'SELL: цена у сопротивления, объём падает — покупатели истощены.'
        ),
        'example_params': 'vol_period=5, level_proximity=0.5',
    },
    'cog': {
        'author': 'John Ehlers',
        'source': 'Библиотека стратегий (Center of Gravity Oscillator by John Ehlers.pdf)',
        'logic': (
            'Center of Gravity Oscillator определяет "центр тяжести" цен за период. '
            'CG = -(sum(i × MP[-i]) / sum(MP[-i])) для i=0..period-1. '
            'Когда CG растёт — центр тяжести смещается к новым барам (бычий импульс). '
            'BUY: CG > CG[-1] (растущий) у поддержки. '
            'SELL: CG < CG[-1] (падающий) у сопротивления.'
        ),
        'example_params': 'cog_period=10',
    },
    'tsi': {
        'author': 'William Blau',
        'source': 'Библиотека стратегий (True Strength Index and TSI Moving Average.pdf)',
        'logic': (
            'True Strength Index — двойное сглаживание ROC цен. '
            'TSI = 100 × EMA(EMA(ROC, roc_period), smooth) / EMA(EMA(|ROC|, roc_period), smooth). '
            'Сигнальная линия — EMA(TSI, signal_period). '
            'BUY: TSI пересекает сигнал снизу вверх у поддержки. '
            'SELL: TSI пересекает сигнал сверху вниз у сопротивления.'
        ),
        'example_params': 'tsi_roc=25, tsi_smooth=13, tsi_signal=20',
    },
    'eco': {
        'author': 'William Blau',
        'source': 'Библиотека стратегий (ECO - Ergodic Candlestick Oscillator II by William Blau.pdf)',
        'logic': (
            'Ergodic Candlestick Oscillator II использует тело (C-O) и размах (H-L) свечи. '
            'ECO = 100 × EMA(EMA(C-O, ave1), ave2) / EMA(EMA(H-L, ave1), ave2). '
            'Сигнал = EMA(ECO, ave3). '
            'BUY: ECO пересекает сигнал снизу вверх у поддержки. '
            'SELL: ECO пересекает сигнал сверху вниз у сопротивления.'
        ),
        'example_params': 'eco_ave1=11, eco_ave2=4, eco_ave3=5',
    },
    'psychological': {
        'author': 'N.N. (обобщение)',
        'source': 'Библиотека стратегий (Psychological Index.pdf)',
        'logic': (
            'Psychological Index измеряет долю "бычьих" свечей за период: процент баров, '
            'где close > close[-1]. Значение от 0 до 100. '
            'BUY: индекс ≤ oversold (25%) — слишком много медвежьих свечей, ожидание разворота. '
            'SELL: индекс ≥ overbought (75%) — слишком много бычьих свечей, ожидание коррекции.'
        ),
        'example_params': 'psych_period=12, overbought=75, oversold=25',
    },
    'historical_volatility': {
        'author': 'N.N.',
        'source': 'Библиотека стратегий (Historical Volatility Trading System.pdf)',
        'logic': (
            'Сравнение краткосрочной и долгосрочной исторической волатильности. '
            'HV_ratio = HV_fast / HV_slow, где HV = StdDev(ln(C/C[-1])) × √365 × 100. '
            'Когда отношение падает ниже порога (0.5) — волатильность сжата, ожидание рывка. '
            'BUY: HV_ratio ≤ threshold И close > EMA(20) (бычий тренд) у поддержки. '
            'SELL: HV_ratio ≤ threshold И close < EMA(20) (медвежий тренд) у сопротивления.'
        ),
        'example_params': 'hv_fast=10, hv_slow=100, hv_threshold=0.5',
    },
    'tcf': {
        'author': 'M.H. Pee',
        'source': 'Библиотека стратегий (Trend Continuation Factor by M. H. Pee.pdf)',
        'logic': (
            'Trend Continuation Factor измеряет силу продолжения тренда. '
            'pc = max(ROC, 0), nc = max(-ROC, 0). pcf/ncf — кумулятивные суммы с обнулением. '
            '+TCF = sum(pc, period) - sum(ncf, period). '
            '-TCF = sum(nc, period) - sum(pcf, period). '
            'BUY: +TCF > 0 (бычий импульс сильнее) у поддержки. '
            'SELL: -TCF > 0 (медвежий импульс сильнее) у сопротивления.'
        ),
        'example_params': 'tcf_period=35',
    },
    'self_adjusting_rsi': {
        'author': 'David Sepiashvili',
        'source': 'Библиотека стратегий (Self-Adjusting RSI by David Sepiashvili.pdf)',
        'logic': (
            'RSI с адаптивными границами перекупленности/перепроданности. '
            'Метод 1 (SD): границы = 50 ± k × StdDev(RSI). '
            'Метод 2 (SMA): границы = 50 ± c × SMA(|RSI - SMA(RSI)|). '
            'Границы автоматически расширяются/сужаются вслед за волатильностью RSI. '
            'BUY: RSI пересекает нижнюю границу снизу вверх у поддержки. '
            'SELL: RSI пересекает верхнюю границу сверху вниз у сопротивления.'
        ),
        'example_params': 'rsi_period=14, k1=1.8 (SD), c1=2 (SMA), method=1',
    },
    'tether': {
        'author': 'Bryan Strain',
        'source': 'Библиотека стратегий (Tether Line Trading System by Bryan Strain.pdf)',
        'logic': (
            'Многофакторная система на основе трёх индикаторов: '
            '1) VolOsc = SMA(if(C>O,+V,if(C<O,-V,0)), period) — направление объёма. '
            '2) MBO = SMA(C, fast) - SMA(C, slow) —动量平衡振荡器. '
            'BUY: VolOsc > 0 (бычий объём) AND MBO > 0 (бычий импульс) у поддержки. '
            'SELL: VolOsc < 0 AND MBO < 0 у сопротивления.'
        ),
        'example_params': 'tether_period=50, vol_period=7, ma_fast=25, ma_slow=200',
    },
    'regularized_momentum': {
        'author': 'Chris Satchwell',
        'source': 'Библиотека стратегий (Regularized Momentum by Chris Satchwell.pdf)',
        'logic': (
            'Regularized Momentum — регуляризованный момент для фильтрации шума. '
            'a = 2/(period+1), f — рекурсивный фильтр, '
            'Momentum = (f - f[-1]) / f. '
            'Регуляризация (d) контролирует сглаживание. '
            'BUY: Momentum пересекает 0 снизу вверх у поддержки. '
            'SELL: Momentum пересекает 0 сверху вниз у сопротивления.'
        ),
        'example_params': 'reg_period=21, reg_d=0.5',
    },
    'bull_bear_fear': {
        'author': 'N.N.',
        'source': 'Библиотека стратегий (Bull Fear-Bear Fear with DX System.pdf)',
        'logic': (
            'Система на основе индекса направленного движения (DX) и уровней Bull/Bear Fear. '
            'DX = 100 × |+DI - -DI| / (+DI + -DI) — измеряет силу тренда независимо от направления. '
            'BUY: DX ≥ threshold (тренд достаточно сильный) у поддержки (откат в тренде). '
            'SELL: DX ≥ threshold у сопротивления (откат в тренде).'
        ),
        'example_params': 'fear_period=12, dx_period=10, dx_threshold=25',
    },
    'j2l': {
        'author': 'Jean-Louis Lepreux',
        'source': 'Библиотека стратегий (J2L Trading System by Jean-Louis Lepreux.pdf)',
        'logic': (
            'J2L = TSF(Close) - LinearReg(Close) — разница между прогнозом линейной регрессии '
            'и текущим значением регрессии, отражающая наклон линии тренда. '
            'BUY: J2L пересекает 0 (наклон становится положительным) у поддержки. '
            'SELL: J2L пересекает trigger (0..0.05) сверху вниз у сопротивления.'
        ),
        'example_params': 'j2l_period=50, j2l_trigger=0.0',
    },
    'ma_relative_strength': {
        'author': 'N.N.',
        'source': 'Библиотека стратегий (Moving Average of Relative Strength System.pdf)',
        'logic': (
            'Пересечение скользящих средних от RSI. '
            'fast_MA = EMA(RSI(14), fast), slow_MA = EMA(RSI(14), slow). '
            'BUY: быстрая EMA пересекает медленную снизу вверх у поддержки. '
            'SELL: быстрая EMA пересекает медленную сверху вниз у сопротивления.'
        ),
        'example_params': 'ma_rs_rsi=14, ma_rs_fast=10, ma_rs_slow=30',
    },
    'rmta': {
        'author': 'Dennis Meyers',
        'source': 'Библиотека стратегий (Recursive Moving Trend Average by Dennis Meyers.pdf)',
        'logic': (
            'Recursive Moving Trend Average — рекурсивный фильтр тренда. '
            'Bot = (1-α)×PREV + C, RMTA = (1-α)×PREV + α×|C + Bot - Bot[-1]|. '
            'TOSC = RMTA - EMA(C, period) — осциллятор. '
            'BUY: TOSC пересекает -|entry| снизу вверх у поддержки. '
            'SELL: TOSC пересекает +|entry| сверху вниз у сопротивления.'
        ),
        'example_params': 'rmta_period=21, rmta_entry=3.0',
    },
    'fazola': {
        'author': 'Fazola (псевдоним)',
        'source': 'Библиотека стратегий (Fazola MAROC System.pdf)',
        'logic': (
            'Многофакторная система Fazola MAROC. Три условия должны выполняться одновременно: '
            '1) Цена выше/ниже EMA (трендовый фильтр). '
            '2) Краткосрочный ROC(4) > 0 / < 0 (импульс). '
            '3) Долгосрочный ROC(14) > 0 / < 0 (тренд). '
            'BUY: C > EMA И ROC(4) > 0 И ROC(14) > 0 у поддержки. '
            'SELL: C < EMA И ROC(4) < 0 И ROC(14) < 0 у сопротивления.'
        ),
        'example_params': 'fazola_ema=10, fazola_roc_fast=4, fazola_roc_slow=14',
    },
    'inverse_fisher': {
        'author': 'John Ehlers',
        'source': 'Библиотека стратегий (Inverse Fisher Transform by John Ehlers.pdf)',
        'logic': (
            'Inverse Fisher Transform применяется к RSI для получения более чётких сигналов. '
            'v1 = 0.1 × (RSI(5) - 50), v2 = WMA(v1, 9). '
            'IFT = (exp(2×v2) - 1) / (exp(2×v2) + 1) — значение от -1 до +1. '
            'BUY: IFT пересекает oversold (-0.5) снизу вверх у поддержки. '
            'SELL: IFT пересекает overbought (+0.5) сверху вниз у сопротивления.'
        ),
        'example_params': 'ifish_rsi_period=5, ifish_wma_period=9, OS=-0.5, OB=0.5',
    },
    'pro_go': {
        'author': 'Larry Williams',
        'source': 'Библиотека стратегий (Pro Go I by Larry Williams.pdf)',
        'logic': (
            'Professional Index (Pro Go I) Ларри Уильямса измеряет активность '
            '"профессионалов" через разницу Open-Close. '
            'Prof = SMA(O-C, period), затем stochastic(Prof, period) для шкалы 0-100. '
            'Когда Professional Index ≥ 75 — профессионалы активно покупают (бычий сигнал). '
            'Когда Professional Index ≤ 25 — профессионалы продают (медвежий сигнал). '
            'BUY: ProGo ≥ 75 (профессионалы покупают) у поддержки. '
            'SELL: ProGo ≤ 25 (профессионалы продают) у сопротивления.'
        ),
        'example_params': 'progo_period=7, OB=75, OS=25',
    },
    'siroc': {
        'author': 'Jose Silva',
        'source': 'Библиотека стратегий (Siroc IV by Jose Silva.pdf)',
        'logic': (
            'Siroc IV — нормализованный ROC-осциллятор с автоматическими уровнями '
            'перекупленности/перепроданности на основе исторических пиков/впадин. '
            'Расчёт: y = EMA(MP, prd1), z = EMA((MP-y)/y[-prd1], prd2). '
            'Siroc = 100 × EMA(up,prd3) / (EMA(up,prd3)+EMA(down,prd3)). '
            'Сигнальная линия dTrigger = EMA(Siroc, prd3). '
            'BUY: Siroc пересекает dTrigger снизу вверх у поддержки. '
            'SELL: Siroc пересекает dTrigger сверху вниз у сопротивления.'
        ),
        'example_params': 'prd1=21, prd2=10, prd3=5',
    },
    'jkl': {
        'author': 'Jarosław Kilon',
        'source': 'Библиотека стратегий (JKL Trading System by Jarosław Kilon.pdf)',
        'logic': (
            'JKL — взвешенная по стандартному отклонению скользящая средняя '
            'цены (O+C)/2. Веса = StdDev(mid, opt2). '
            'X = Sum(w × mid, opt2) / Sum(w, opt2), MA_X = SMA(X, opt3). '
            'Сигнал = X - MA_X. '
            'BUY: сигнал > порог (opt1) у поддержки. '
            'SELL: сигнал < порог у сопротивления.'
        ),
        'example_params': 'opt1=0, opt2=5, opt3=15',
    },
    'cci_ma': {
        'author': 'N.N.',
        'source': 'Библиотека стратегий (CCI Moving Average Crossover System Test.pdf)',
        'logic': (
            'CCI пересекает свою EMA. '
            'CCI = (TP - SMA(TP, period)) / (0.015 × MeanDeviation). '
            'Mean-reversion подход: когда CCI падает ниже своей EMA — перепроданность (BUY), '
            'когда CCI растёт выше EMA — перекупленность (SELL). '
            'BUY: CCI пересекает EMA снизу вверх у поддержки. '
            'SELL: CCI пересекает EMA сверху вниз у сопротивления.'
        ),
        'example_params': 'cci_period=14, cci_ma_period=14',
    },
    'trend_osc': {
        'author': 'N.N.',
        'source': 'Библиотека стратегий (Combining Trend and Oscillator Signals.pdf)',
        'logic': (
            'Комбинация трендового фильтра (C > SMA) и осциллятора (LinRegSlope > своей '
            'долгосрочной регрессии). Трендовый фильтр определяет направление, '
            'осциллятор подтверждает ускорение/замедление импульса. '
            'BUY: C > EMA(ma) AND LinRegSlope > smoothed slope у поддержки. '
            'SELL: C < EMA(ma) AND LinRegSlope < smoothed slope у сопротивления.'
        ),
        'example_params': 'trend_osc_ma=20, trend_osc_slope=14, trend_osc_smooth=50',
    },
    'dinapoli': {
        'author': 'Joe DiNapoli',
        'source': 'Библиотека стратегий (Preferred (Slow) Oscillator by Joe DiNapoli.pdf)',
        'logic': (
            'Preferred Slow Oscillator ДиНаполи — двойное сглаживание стохастика '
            '(8,3,3). FK = 8-периодный %K, FD = EMA(FK,3), STO = EMA(FD,3). '
            'Двойное сглаживание убирает шум и даёт чёткие сигналы на экстремумах. '
            'BUY: STO пересекает oversold (30) снизу вверх у поддержки. '
            'SELL: STO пересекает overbought (70) сверху вниз у сопротивления.'
        ),
        'example_params': 'K=8, D=3, Slow=3, OB=70, OS=30',
    },
    'coppock': {
        'author': 'Edwin Coppock',
        'source': 'Библиотека стратегий (Coppock Indicator.pdf, Coppock Curve - Signal Formulas.pdf)',
        'logic': (
            'Coppock Curve — долгосрочный индикатор для поиска крупных bottoms. '
            'WMA(10) от суммы ROC(11) + ROC(14). Рост кривой указывает на '
            'ослабление нисходящего импульса и возможный разворот. '
            'BUY: Coppock растёт (current > prev) у поддержки. '
            'SELL: Coppock падает (current < prev) у сопротивления.'
        ),
        'example_params': 'coppock_roc1=11, coppock_roc2=14, coppock_wma=10',
    },
}


def get_guide(strategy_id):
    return STRATEGY_GUIDE.get(strategy_id)


def get_all_guides():
    return dict(STRATEGY_GUIDE)

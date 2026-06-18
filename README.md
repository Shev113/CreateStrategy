# CreateStrategy — система тестирования торговых стратегий

Сбор и анализ данных MOEX, бэктестинг, оптимизация, сканирование секторов.

## Установка

```bash
pip install -r requirements.txt
python CreateStrategyTrading.py
```

## Возможности

### Вкладка «Анализ»
- **Загрузка данных** — исторические свечи по тикеру с MOEX
- **Backtest** — запуск стратегии с заданными параметрами
- **Оптимизация** — grid search по параметрам, топ-5 результатов с возможностью применить
- **Портфельный бэктест** — анализ набора тикеров из дневника сделок
- **Walk-forward** — проверка стабильности параметров на разных временных окнах

### Параметры стратегий
- `capital` — стартовый капитал (руб)
- `risk_per_trade` — риск на сделку (%)
- `atr_sl` — множитель ATR для стоп-лосса
- `atr_tp` — множитель ATR для тейк-профита
- `min_hits` — мин. кол-во касаний уровня для входа
- `max_hold` — макс. свечей удержания позиции
- `commission` — комиссия (%)
- `entry_type` — 0=по рынку, 1=лимитный по цене уровня

### Трейлинг-стоп
- 0=Выкл, 1=Фикс. отступ (ATR), 2=По скользящей средней
- `trailing_activation` — прибыль в ATR для активации
- `trailing_offset` — отступ от максимума

### Частичное фиксирование
- `partial_tp` — 0=Выкл, 1=Вкл
- `partial_tp_ratio1/2` — TP1 и TP2 в ATR
- `partial_tp_size1` — доля закрытия на TP1

### Pivot-уровни
- 0=Частотный метод, 1=Pivot detection (swing high/low)
- `pivot_lookback` — глубина поиска пивотов

### Ансамбль стратегий
- `sub_strategies` — ID стратегий через запятую (bounce,fisher,trend)
- `vote_method` — 0=Большинство, 1=Любой сигнал, 2=Консенсус

### MTF-фильтр (Multi-Timeframe)
- `use_mtf_filter` — 0=Выкл, 1=Вкл
- `mtf_ma_period` — период MA на недельных свечах
- BUY только при weekly close > MA, SELL при weekly close < MA

### Управление размером позиции
- 0=Фикс. риск, 1=Kelly Criterion, 2=ATR-зависимый
- `kelly_fraction` — доля от Kelly (0.0–1.0)
- `atr_sizing_mult` — множитель ATR для волатильного позиционирования

### Вкладка «Сканер»
- Сканирование секторов MOEX, поиск лучших сигналов
- Фильтр по стратегиям, экспорт в Excel, добавление в дневник

### Вкладка «Умный сканер»
- Multi-timeframe сканер (H1 + D1) продвинутых стратегий (Solabuto)

### Вкладка «Дневник сделок»
- Журнал открытых/закрытых позиций
- Автопроверка стоп-лоссов и тейк-профитов
- Экспорт/импорт JSON

### Вкладка «Справочник стратегий»
- Описание, логика входа, параметры каждой стратегии

### Вкладка «Интрадей»
- Бэктестинг и сканирование на часовых данных

## Сокращения (Abbreviations)

| Сокр. | Расшифровка |
|-------|------------|
| ATR | Average True Range — средний истинный диапазон |
| SL | Stop Loss — стоп-лосс |
| TP | Take Profit — тейк-профит |
| MA | Moving Average — скользящая средняя |
| MTF | Multi-Timeframe — мульти-таймфрейм |
| DD | Drawdown — просадка |
| PF | Profit Factor — фактор прибыли |
| IS | In-Sample — обучающая выборка |
| OOS | Out-Of-Sample — тестовая выборка |
| SMA | Simple Moving Average |
| EMA | Exponential Moving Average |
| RSI | Relative Strength Index |
| ROC | Rate of Change |
| TSI | True Strength Index |
| ECO | Ehlers Cyber Cycle |
| COG | Center of Gravity |
| TCF | Time Cycle Factor |
| HV | Historical Volatility |
| BB | Bollinger Bands |
| MACD | Moving Average Convergence Divergence |
| DMI | Directional Movement Index |
| ADX | Average Directional Index |

## Лицензия

MIT

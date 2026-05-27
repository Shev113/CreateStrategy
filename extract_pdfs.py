import os, sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_dir = r"E:\!!!OnlyUP\Python\CreateStrategy\Книги\Библиотека стратегий"

# Skip PDFs that are already known/implemented
skip_patterns = [
    'Fisher Transform by John Ehlers',
    'Trend Detection Index',
    'Trend Intensity Index',
    'Stochastic Momentum',
    'Volume-Price Divergence',
    '_Upper BB',
    '!_Библиотека стратегий',
]

# Focus on PDFs that look promising for new strategies
target_pdfs = [
    "Base Channel System.pdf",
    "Bollinger Band of MACD.pdf",
    "Bull Fear-Bear Fear with DX System.pdf",
    "Center of Gravity Oscillator by John Ehlers.pdf",
    "Combining Trend and Oscillator Signals.pdf",
    "Coppock Curve - Signal Formulas.pdf",
    "Coppock Indicator.pdf",
    "Cyclical MA Projection by Andrew Tomlinson.pdf",
    "Dynamic BreakOut System I.pdf",
    "ECO - Ergodic Candlestick Oscillator II by William Blau.pdf",
    "End Point Moving Average by Patrick E. Lafferty.pdf",
    "Fazola MAROC System.pdf",
    "GANN - HiVisual & LoVisual.pdf",
    "Historical Volatility Trading System.pdf",
    "Instantaneous Trendline & Sinewave Indicator by John Ehlers.pdf",
    "Intraday High-Low by Jose Silva.pdf",
    "Inverse Fisher Transform by John Ehlers.pdf",
    "J2L Trading System by Jean-Louis Lepreux.pdf",
    "JKL Trading System by Jaros+Вaw Kilon.pdf",
    "Kaleidoscope - CCT.pdf",
    "Linear Regression True Slope by Jose Silva.pdf",
    "LinRegSlope Divergence.pdf",
    "Lunar Cycle by Jose Silva.pdf",
    "MACD - %-normalized by Jose Silva.pdf",
    "MACD Histogram - CCT.pdf",
    "Maximum Profit System I.pdf",
    "Moving Average of Relative Strength System.pdf",
    "OMEGA - Confluence.pdf",
    "OMEGA - Hilbert Channel Indicator by Roger Darley.pdf",
    "OMEGA - LBR_HistVoltyRatio by Linda Bradford-Raschke.pdf",
    "OMEGA - LBR_IntraHL Channel by Linda Bradford-Raschke.pdf",
    "OMEGA - LMS Predictor by John Ehlers.pdf",
    "OMEGA - Meander system v. 1.pdf",
    "OMEGA - Modified Moving Averages by Joe Sharp.pdf",
    "OMEGA - Moving Beyond the Closing Price by Thomas Stridsman.pdf",
    "OMEGA - R-Squared by Jack Karczewski.pdf",
    "OMEGA - SMI Oscillator.pdf",
    "OMEGA - SystemD by George Pruitt.pdf",
    "OMEGA - Volatility Quality Index by Thomas Stridsman.pdf",
    "Optimized Weighted Moving Average.pdf",
    "Pivot Points & Volume.pdf",
    "Point & Figure Indicator by Adam Hefner.pdf",
    "Point of Balance Oscillator and Mov. Averages by Walter Downs.pdf",
    "Point of Balance.pdf",
    "Preferred (Slow) Oscillator by Joe DiNapoli.pdf",
    "Pro Go I by Larry Williams.pdf",
    "Psychological Index.pdf",
    "Recursive Moving Trend Average by Dennis Meyers.pdf",
    "Regression Oscillator & Slope-Close Indicator by Richard Goedde.pdf",
    "Regularized Momentum by Chris Satchwell.pdf",
    "ROC Moving Average System Test.pdf",
    "Self-Adjusting RSI by David Sepiashvili.pdf",
    "Siroc IV by Jose Silva.pdf",
    "Slope of a Linear Regression Line.pdf",
    "Slope-Close Indicator.pdf",
    "Smoothed DMI Index (20 Period MA) (#028a).pdf",
    "Smoothed Momentum w. Dynamic Bands.pdf",
    "Smoothed Momentum.pdf",
    "Stochastic Momentum Indicator II by Robert Lambert.pdf",
    "Stochastic Momentum Indicator - Volume.pdf",
    "TEMA - Multiple-type by Jose Silva.pdf",
    "Tether Line Trading System by Bryan Strain.pdf",
    "Threshold Trading Revisited - RSI by Rudy Teseo.pdf",
    "Tick Line Momentum Oscillator by Daniel E. Downing.pdf",
    "Time Series Forecast System Test.pdf",
    "Trend Continuation Factor by M. H. Pee.pdf",
    "Trending Bandini.pdf",
    "True Strength Index (TSI) and TSI Moving Average.pdf",
    "Volume Accumulation Percent Indicator.pdf",
    "Wallie's 20% Stop Loss Indicator.pdf",
    "WL - Trend Walker.pdf",
    "WLD - _Dual Thrust_.pdf",
    "CCI Moving Average Crossover System Test.pdf",
    "Tema PDI - MDI.pdf",
    "Tema PV Binary Wave.pdf",
    "Linear Regression True Slope by Jose Silva.pdf",
    "LinRegSlope & Standard Deviation of Daily ROC's.pdf",
    "PLdot H-L Price's by Przemys+Вaw Neyder.pdf",
    "SeqSETUP & SeqINTERSECTION.pdf",
    "Stochastic Smoothed by Mark Peterman.pdf",
    "JKL by Jaros+Вaw Kilon.pdf",
]

import PyPDF2

output_dir = r"E:\!!!OnlyUP\Python\CreateStrategy\extracted_texts"
os.makedirs(output_dir, exist_ok=True)

for pdf_name in target_pdfs:
    pdf_path = os.path.join(pdf_dir, pdf_name)
    if not os.path.exists(pdf_path):
        print(f"NOT FOUND: {pdf_name}")
        continue
    
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n---PAGE BREAK---\n"
        
        # Save text
        safe_name = pdf_name.replace('.pdf', '') + '.txt'
        out_path = os.path.join(output_dir, safe_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"OK ({len(reader.pages)}p, {len(text)} chars): {pdf_name}")
    except Exception as e:
        print(f"ERROR ({pdf_name}): {e}")

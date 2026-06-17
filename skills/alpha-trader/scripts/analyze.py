#!/usr/bin/env python3
"""
AlphaTrader Analysis Runner
===========================
Main entry point for technical analysis.
Pulls data from Alpaca, calculates indicators, caches results.

Usage:
    python analyze.py SPY --timeframe 5Min
    python analyze.py SPY --multi  # Multi-timeframe analysis
    python analyze.py SPY --report  # Full report
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

# These will be imported when running locally
try:
    from technical_indicators import TechnicalAnalyzer, MultiTimeframeAnalyzer
    from data_cache import DataCache, SmartCache
except ImportError:
    # Running standalone - define minimal versions
    pass


def parse_alpaca_bars(raw_output: str) -> pd.DataFrame:
    """
    Parse Alpaca bar output into DataFrame.
    Handles the text format returned by Alpaca MCP tools.
    """
    lines = raw_output.strip().split('\n')
    data = []
    
    for line in lines:
        if line.startswith('Time:'):
            # Parse: Time: 2026-01-22 19:00:00 UTC, Open: $690.50, High: $690.75, Low: $690.40, Close: $690.62, Volume: 350000.0
            parts = line.split(', ')
            row = {}
            for part in parts:
                if part.startswith('Time:'):
                    row['time'] = part.replace('Time:', '').strip()
                elif part.startswith('Open:'):
                    row['open'] = float(part.replace('Open: $', ''))
                elif part.startswith('High:'):
                    row['high'] = float(part.replace('High: $', ''))
                elif part.startswith('Low:'):
                    row['low'] = float(part.replace('Low: $', ''))
                elif part.startswith('Close:'):
                    row['close'] = float(part.replace('Close: $', ''))
                elif part.startswith('Volume:'):
                    row['volume'] = float(part.replace('Volume:', ''))
            if row:
                data.append(row)
    
    if data:
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        return df
    return pd.DataFrame()


def format_indicator_table(signals: Dict) -> str:
    """Format signals as a nice ASCII table."""
    lines = []
    
    # Header
    lines.append("┌" + "─" * 58 + "┐")
    lines.append("│" + " SPY TECHNICAL INDICATORS ".center(58) + "│")
    lines.append("├" + "─" * 28 + "┬" + "─" * 14 + "┬" + "─" * 14 + "┤")
    lines.append("│" + " Indicator".ljust(28) + "│" + " Value".center(14) + "│" + " Signal".center(14) + "│")
    lines.append("├" + "─" * 28 + "┼" + "─" * 14 + "┼" + "─" * 14 + "┤")
    
    # MACD
    macd_val = f"{signals['macd']['value']:.4f}"
    macd_sig = "🟢 BULL" if signals['macd']['signal'] == 'BULLISH' else "🔴 BEAR"
    lines.append(f"│ {'MACD Histogram'.ljust(27)}│{macd_val.center(14)}│{macd_sig.center(14)}│")
    
    # RSI
    rsi_val = f"{signals['rsi']['value']:.1f}"
    rsi_sig = signals['rsi']['condition'][:4]
    rsi_emoji = "🟢" if rsi_sig == "OVER" and signals['rsi']['value'] < 50 else "🔴" if signals['rsi']['value'] > 70 else "⚪"
    lines.append(f"│ {'RSI (14)'.ljust(27)}│{rsi_val.center(14)}│{(rsi_emoji + ' ' + signals['rsi']['condition'][:6]).center(14)}│")
    
    # Stochastic
    stoch_val = f"K:{signals['stochastic']['k']:.1f}"
    stoch_sig = signals['stochastic']['signal'][:8]
    lines.append(f"│ {'Stochastic'.ljust(27)}│{stoch_val.center(14)}│{stoch_sig.center(14)}│")
    
    # CCI
    cci_val = f"{signals['cci']['value']:.1f}"
    lines.append(f"│ {'CCI (20)'.ljust(27)}│{cci_val.center(14)}│{signals['cci']['condition'][:8].center(14)}│")
    
    # Williams %R
    wr_val = f"{signals['williams_r']['value']:.1f}"
    lines.append(f"│ {'Williams %R'.ljust(27)}│{wr_val.center(14)}│{signals['williams_r']['condition'][:8].center(14)}│")
    
    # MFI
    mfi_val = f"{signals['mfi']['value']:.1f}"
    lines.append(f"│ {'MFI (14)'.ljust(27)}│{mfi_val.center(14)}│{signals['mfi']['condition'][:8].center(14)}│")
    
    lines.append("├" + "─" * 28 + "┼" + "─" * 14 + "┼" + "─" * 14 + "┤")
    
    # VWAP
    vwap_val = f"${signals['vwap']['value']:.2f}"
    vwap_sig = "🟢 ABOVE" if signals['vwap']['position'] == 'ABOVE' else "🔴 BELOW"
    lines.append(f"│ {'VWAP'.ljust(27)}│{vwap_val.center(14)}│{vwap_sig.center(14)}│")
    
    # OBV
    obv_sig = "🟢 BULL" if signals['obv']['trend'] == 'BULLISH' else "🔴 BEAR"
    lines.append(f"│ {'OBV Trend'.ljust(27)}│{'-'.center(14)}│{obv_sig.center(14)}│")
    
    # Bollinger
    bb_val = f"${signals['bollinger']['middle']:.2f}"
    bb_sig = signals['bollinger']['position'][:8]
    lines.append(f"│ {'Bollinger Mid'.ljust(27)}│{bb_val.center(14)}│{bb_sig.center(14)}│")
    
    # ATR
    atr_val = f"${signals['atr']['value']:.2f}"
    atr_pct = f"{signals['atr']['pct_of_price']:.2f}%"
    lines.append(f"│ {'ATR (14)'.ljust(27)}│{atr_val.center(14)}│{atr_pct.center(14)}│")
    
    lines.append("├" + "─" * 28 + "┼" + "─" * 14 + "┼" + "─" * 14 + "┤")
    
    # Moving Averages
    ema9 = f"${signals['moving_averages']['ema_9']:.2f}"
    ema21 = f"${signals['moving_averages']['ema_21']:.2f}"
    trend = "🟢 BULL" if signals['moving_averages']['trend_short'] == 'BULLISH' else "🔴 BEAR"
    lines.append(f"│ {'EMA 9'.ljust(27)}│{ema9.center(14)}│{trend.center(14)}│")
    lines.append(f"│ {'EMA 21'.ljust(27)}│{ema21.center(14)}│{'-'.center(14)}│")
    
    lines.append("└" + "─" * 28 + "┴" + "─" * 14 + "┴" + "─" * 14 + "┘")
    
    return '\n'.join(lines)


def format_multi_tf_table(results: Dict) -> str:
    """Format multi-timeframe results as table."""
    lines = []
    
    lines.append("┌" + "─" * 50 + "┐")
    lines.append("│" + " MULTI-TIMEFRAME ANALYSIS ".center(50) + "│")
    lines.append("├" + "─" * 12 + "┬" + "─" * 8 + "┬" + "─" * 8 + "┬" + "─" * 8 + "┬" + "─" * 12 + "┤")
    lines.append("│" + " Timeframe".ljust(12) + "│" + " Bull".center(8) + "│" + " Bear".center(8) + "│" + " Neut".center(8) + "│" + " Bias".center(12) + "│")
    lines.append("├" + "─" * 12 + "┼" + "─" * 8 + "┼" + "─" * 8 + "┼" + "─" * 8 + "┼" + "─" * 12 + "┤")
    
    for tf, data in results['timeframes'].items():
        bias_short = data['bias'].replace('STRONG_', 'S_')[:10]
        emoji = "🟢" if 'BULLISH' in data['bias'] else "🔴" if 'BEARISH' in data['bias'] else "⚪"
        lines.append(f"│ {tf.ljust(11)}│{str(data['bullish']).center(8)}│{str(data['bearish']).center(8)}│{str(data['neutral']).center(8)}│{(emoji + bias_short[:9]).center(12)}│")
    
    lines.append("├" + "─" * 12 + "┴" + "─" * 8 + "┴" + "─" * 8 + "┴" + "─" * 8 + "┴" + "─" * 12 + "┤")
    
    conf_emoji = "🟢" if 'BULLISH' in results['confluence'] else "🔴" if 'BEARISH' in results['confluence'] else "⚪"
    lines.append(f"│ {(conf_emoji + ' CONFLUENCE: ' + results['confluence']).center(50)}│")
    lines.append("└" + "─" * 50 + "┘")
    
    return '\n'.join(lines)


def format_trade_signal(score: Dict, price: float) -> str:
    """Generate actionable trade signal."""
    lines = []
    
    bias = score['bias']
    bullish = score['bullish']
    bearish = score['bearish']
    
    lines.append("\n" + "=" * 50)
    lines.append("TRADE SIGNAL")
    lines.append("=" * 50)
    lines.append(f"Current Price: ${price:.2f}")
    lines.append(f"Bullish Signals: {bullish}/{score['total']}")
    lines.append(f"Bearish Signals: {bearish}/{score['total']}")
    lines.append(f"Overall Bias: {bias}")
    lines.append("")
    
    if 'STRONG_BULLISH' in bias:
        lines.append("📈 STRONG BUY SIGNAL")
        lines.append("   Consider: ATM or slightly OTM calls")
        lines.append("   Timeframe: 0-2 DTE for momentum")
    elif 'BULLISH' in bias:
        lines.append("📈 MILD BULLISH")
        lines.append("   Consider: OTM calls on dips")
        lines.append("   Wait for pullback to VWAP/EMA support")
    elif 'STRONG_BEARISH' in bias:
        lines.append("📉 STRONG SELL SIGNAL")
        lines.append("   Consider: ATM or slightly OTM puts")
        lines.append("   Timeframe: 0-2 DTE for momentum")
    elif 'BEARISH' in bias:
        lines.append("📉 MILD BEARISH")
        lines.append("   Consider: OTM puts on rallies")
        lines.append("   Wait for rejection at resistance")
    else:
        lines.append("⚪ NEUTRAL - NO CLEAR SIGNAL")
        lines.append("   Consider: Wait for clearer setup")
        lines.append("   Or play both sides with strangles")
    
    lines.append("=" * 50)
    
    return '\n'.join(lines)


def quick_analysis(df: pd.DataFrame) -> str:
    """
    Run quick analysis and return formatted output.
    This is what gets called most often.
    """
    analyzer = TechnicalAnalyzer(df)
    score = analyzer.score_signals()
    
    output = []
    output.append(format_indicator_table(score['signals']))
    output.append(format_trade_signal(score, df['close'].iloc[-1]))
    
    return '\n'.join(output)


def multi_tf_analysis(data_dict: Dict[str, pd.DataFrame]) -> str:
    """
    Run multi-timeframe analysis.
    """
    mtf = MultiTimeframeAnalyzer(data_dict)
    results = mtf.confluence_score()
    
    output = []
    output.append(format_multi_tf_table(results))
    
    # Add trade recommendation based on confluence
    output.append("\n" + "=" * 50)
    if 'STRONG' in results['confluence'] and 'BULLISH' in results['confluence']:
        output.append("🎯 HIGH CONVICTION LONG SETUP")
        output.append("   All timeframes aligned bullish")
    elif 'STRONG' in results['confluence'] and 'BEARISH' in results['confluence']:
        output.append("🎯 HIGH CONVICTION SHORT SETUP")
        output.append("   All timeframes aligned bearish")
    elif results['confluence'] == 'MIXED':
        output.append("⚠️ CONFLICTING SIGNALS")
        output.append("   Timeframes disagree - reduce size or wait")
    else:
        output.append(f"📊 {results['confluence']}")
        output.append("   Partial alignment - normal position size")
    output.append("=" * 50)
    
    return '\n'.join(output)


# ==================== SAMPLE DATA FOR TESTING ====================

def generate_sample_data(bars: int = 100) -> pd.DataFrame:
    """Generate sample OHLCV data for testing."""
    import numpy as np
    
    np.random.seed(42)
    
    # Start price
    price = 690.0
    data = []
    
    base_time = datetime.now() - timedelta(minutes=bars * 5)
    
    for i in range(bars):
        # Random walk with mean reversion
        change = np.random.randn() * 0.5
        if price > 695:
            change -= 0.2
        elif price < 685:
            change += 0.2
        
        open_price = price
        close_price = price + change
        high_price = max(open_price, close_price) + abs(np.random.randn() * 0.3)
        low_price = min(open_price, close_price) - abs(np.random.randn() * 0.3)
        volume = np.random.randint(100000, 1000000)
        
        data.append({
            'time': base_time + timedelta(minutes=i * 5),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
        
        price = close_price
    
    df = pd.DataFrame(data)
    df.set_index('time', inplace=True)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AlphaTrader Technical Analysis')
    parser.add_argument('symbol', nargs='?', default='SPY', help='Symbol to analyze')
    parser.add_argument('--timeframe', '-t', default='5Min', help='Bar timeframe')
    parser.add_argument('--multi', '-m', action='store_true', help='Multi-timeframe analysis')
    parser.add_argument('--report', '-r', action='store_true', help='Full detailed report')
    parser.add_argument('--test', action='store_true', help='Run with sample data')
    
    args = parser.parse_args()
    
    if args.test:
        print(f"Running test analysis for {args.symbol}...")
        print()
        
        df = generate_sample_data(100)
        
        if args.multi:
            # Generate different timeframes
            data_dict = {
                '1m': generate_sample_data(60),
                '5m': generate_sample_data(100),
                '15m': generate_sample_data(50),
                '30m': generate_sample_data(30)
            }
            print(multi_tf_analysis(data_dict))
        elif args.report:
            analyzer = TechnicalAnalyzer(df)
            print(analyzer.full_report())
        else:
            print(quick_analysis(df))
    else:
        print("To run analysis, use with --test flag or integrate with Alpaca data")
        print("Example: python analyze.py SPY --test")
        print("Example: python analyze.py SPY --test --multi")
        print("Example: python analyze.py SPY --test --report")

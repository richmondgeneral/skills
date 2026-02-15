#!/usr/bin/env python3
"""
AlphaTrader Technical Indicators Module
=======================================
Comprehensive technical analysis for SPY options trading.
Calculates indicators from Alpaca OHLCV data.

Usage:
    from technical_indicators import TechnicalAnalyzer
    analyzer = TechnicalAnalyzer(df)  # df with OHLCV columns
    report = analyzer.full_report()
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json

class TechnicalAnalyzer:
    """
    Technical analysis calculator for trading decisions.
    Feed it OHLCV data, get back actionable signals.
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.
        
        Expected columns: open, high, low, close, volume
        Index should be datetime or 'time' column present.
        """
        self.df = df.copy()
        self._validate_data()
        self._ensure_columns()
    
    def _validate_data(self):
        """Validate required columns exist."""
        required = ['open', 'high', 'low', 'close', 'volume']
        # Handle case-insensitive column names
        self.df.columns = self.df.columns.str.lower()
        missing = [col for col in required if col not in self.df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
    
    def _ensure_columns(self):
        """Ensure numeric types."""
        for col in ['open', 'high', 'low', 'close', 'volume']:
            self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
    
    # ==================== TREND INDICATORS ====================
    
    def ema(self, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return self.df['close'].ewm(span=period, adjust=False).mean()
    
    def sma(self, period: int) -> pd.Series:
        """Simple Moving Average."""
        return self.df['close'].rolling(window=period).mean()
    
    def wma(self, period: int) -> pd.Series:
        """Weighted Moving Average."""
        weights = np.arange(1, period + 1)
        return self.df['close'].rolling(period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
    
    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """
        MACD - Moving Average Convergence Divergence.
        Returns dict with macd_line, signal_line, histogram.
        """
        ema_fast = self.ema(fast)
        ema_slow = self.ema(slow)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram,
            'current': {
                'macd': macd_line.iloc[-1],
                'signal': signal_line.iloc[-1],
                'histogram': histogram.iloc[-1]
            }
        }
    
    def adx(self, period: int = 14) -> Dict:
        """
        ADX - Average Directional Index.
        Measures trend strength (not direction).
        >25 = strong trend, <20 = weak/no trend
        """
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Directional Movement
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'current': {
                'adx': adx.iloc[-1],
                'plus_di': plus_di.iloc[-1],
                'minus_di': minus_di.iloc[-1],
                'trend_strength': 'STRONG' if adx.iloc[-1] > 25 else 'WEAK' if adx.iloc[-1] < 20 else 'MODERATE'
            }
        }
    
    # ==================== MOMENTUM INDICATORS ====================
    
    def rsi(self, period: int = 14) -> Dict:
        """
        RSI - Relative Strength Index.
        >70 = overbought, <30 = oversold
        """
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current = rsi.iloc[-1]
        condition = 'OVERBOUGHT' if current > 70 else 'OVERSOLD' if current < 30 else 'NEUTRAL'
        
        return {
            'rsi': rsi,
            'current': {
                'value': current,
                'condition': condition
            }
        }
    
    def stochastic(self, k_period: int = 14, d_period: int = 3, smooth_k: int = 3) -> Dict:
        """
        Stochastic Oscillator.
        %K = fast line, %D = slow line (signal)
        >80 = overbought, <20 = oversold
        """
        low_min = self.df['low'].rolling(window=k_period).min()
        high_max = self.df['high'].rolling(window=k_period).max()
        
        stoch_k = 100 * (self.df['close'] - low_min) / (high_max - low_min)
        stoch_k_smooth = stoch_k.rolling(window=smooth_k).mean()  # Slow %K
        stoch_d = stoch_k_smooth.rolling(window=d_period).mean()  # %D
        
        k_val = stoch_k_smooth.iloc[-1]
        d_val = stoch_d.iloc[-1]
        
        # Signal detection
        signal = 'NEUTRAL'
        if k_val > 80 and d_val > 80:
            signal = 'OVERBOUGHT'
        elif k_val < 20 and d_val < 20:
            signal = 'OVERSOLD'
        elif k_val > d_val and stoch_k_smooth.iloc[-2] <= stoch_d.iloc[-2]:
            signal = 'BULLISH_CROSS'
        elif k_val < d_val and stoch_k_smooth.iloc[-2] >= stoch_d.iloc[-2]:
            signal = 'BEARISH_CROSS'
        
        return {
            'k': stoch_k_smooth,
            'd': stoch_d,
            'current': {
                'k': k_val,
                'd': d_val,
                'signal': signal
            }
        }
    
    def cci(self, period: int = 20) -> Dict:
        """
        CCI - Commodity Channel Index.
        >100 = overbought, <-100 = oversold
        """
        typical_price = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        sma_tp = typical_price.rolling(window=period).mean()
        mean_dev = typical_price.rolling(window=period).apply(
            lambda x: np.mean(np.abs(x - x.mean())), raw=True
        )
        cci = (typical_price - sma_tp) / (0.015 * mean_dev)
        
        current = cci.iloc[-1]
        condition = 'OVERBOUGHT' if current > 100 else 'OVERSOLD' if current < -100 else 'NEUTRAL'
        
        return {
            'cci': cci,
            'current': {
                'value': current,
                'condition': condition
            }
        }
    
    def williams_r(self, period: int = 14) -> Dict:
        """
        Williams %R.
        >-20 = overbought, <-80 = oversold
        """
        high_max = self.df['high'].rolling(window=period).max()
        low_min = self.df['low'].rolling(window=period).min()
        wr = -100 * (high_max - self.df['close']) / (high_max - low_min)
        
        current = wr.iloc[-1]
        condition = 'OVERBOUGHT' if current > -20 else 'OVERSOLD' if current < -80 else 'NEUTRAL'
        
        return {
            'williams_r': wr,
            'current': {
                'value': current,
                'condition': condition
            }
        }
    
    def roc(self, period: int = 12) -> Dict:
        """
        ROC - Rate of Change (Momentum).
        """
        roc = 100 * (self.df['close'] - self.df['close'].shift(period)) / self.df['close'].shift(period)
        
        return {
            'roc': roc,
            'current': {
                'value': roc.iloc[-1],
                'direction': 'BULLISH' if roc.iloc[-1] > 0 else 'BEARISH'
            }
        }
    
    # ==================== VOLATILITY INDICATORS ====================
    
    def bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> Dict:
        """
        Bollinger Bands.
        Price near upper = overbought, near lower = oversold.
        """
        sma = self.sma(period)
        std = self.df['close'].rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        current_price = self.df['close'].iloc[-1]
        
        # %B indicator (where price is within bands)
        pct_b = (current_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])
        
        position = 'ABOVE_UPPER' if current_price > upper.iloc[-1] else \
                   'BELOW_LOWER' if current_price < lower.iloc[-1] else 'WITHIN'
        
        return {
            'upper': upper,
            'middle': sma,
            'lower': lower,
            'current': {
                'upper': upper.iloc[-1],
                'middle': sma.iloc[-1],
                'lower': lower.iloc[-1],
                'pct_b': pct_b,
                'position': position,
                'bandwidth': (upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1] * 100
            }
        }
    
    def atr(self, period: int = 14) -> Dict:
        """
        ATR - Average True Range.
        Measures volatility.
        """
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        current_atr = atr.iloc[-1]
        current_price = close.iloc[-1]
        
        return {
            'atr': atr,
            'current': {
                'value': current_atr,
                'pct_of_price': (current_atr / current_price) * 100
            }
        }
    
    def keltner_channels(self, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> Dict:
        """
        Keltner Channels.
        Similar to Bollinger but uses ATR instead of std dev.
        """
        ema_line = self.ema(ema_period)
        atr_data = self.atr(atr_period)['atr']
        
        upper = ema_line + (multiplier * atr_data)
        lower = ema_line - (multiplier * atr_data)
        
        current_price = self.df['close'].iloc[-1]
        position = 'ABOVE' if current_price > upper.iloc[-1] else \
                   'BELOW' if current_price < lower.iloc[-1] else 'WITHIN'
        
        return {
            'upper': upper,
            'middle': ema_line,
            'lower': lower,
            'current': {
                'upper': upper.iloc[-1],
                'middle': ema_line.iloc[-1],
                'lower': lower.iloc[-1],
                'position': position
            }
        }
    
    # ==================== VOLUME INDICATORS ====================
    
    def vwap(self) -> Dict:
        """
        VWAP - Volume Weighted Average Price.
        Intraday benchmark. Above = bullish, below = bearish.
        """
        typical_price = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        vwap = (typical_price * self.df['volume']).cumsum() / self.df['volume'].cumsum()
        
        current_price = self.df['close'].iloc[-1]
        current_vwap = vwap.iloc[-1]
        
        return {
            'vwap': vwap,
            'current': {
                'value': current_vwap,
                'price_vs_vwap': current_price - current_vwap,
                'position': 'ABOVE' if current_price > current_vwap else 'BELOW'
            }
        }
    
    def obv(self) -> Dict:
        """
        OBV - On Balance Volume.
        Cumulative volume indicator confirming price trends.
        """
        obv = pd.Series(index=self.df.index, dtype=float)
        obv.iloc[0] = self.df['volume'].iloc[0]
        
        for i in range(1, len(self.df)):
            if self.df['close'].iloc[i] > self.df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + self.df['volume'].iloc[i]
            elif self.df['close'].iloc[i] < self.df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - self.df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        # OBV trend (simple: compare to 10-period SMA of OBV)
        obv_sma = obv.rolling(window=10).mean()
        trend = 'BULLISH' if obv.iloc[-1] > obv_sma.iloc[-1] else 'BEARISH'
        
        return {
            'obv': obv,
            'current': {
                'value': obv.iloc[-1],
                'trend': trend
            }
        }
    
    def mfi(self, period: int = 14) -> Dict:
        """
        MFI - Money Flow Index.
        Volume-weighted RSI. >80 = overbought, <20 = oversold.
        """
        typical_price = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        raw_money_flow = typical_price * self.df['volume']
        
        positive_flow = pd.Series(0.0, index=self.df.index)
        negative_flow = pd.Series(0.0, index=self.df.index)
        
        for i in range(1, len(self.df)):
            if typical_price.iloc[i] > typical_price.iloc[i-1]:
                positive_flow.iloc[i] = raw_money_flow.iloc[i]
            elif typical_price.iloc[i] < typical_price.iloc[i-1]:
                negative_flow.iloc[i] = raw_money_flow.iloc[i]
        
        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()
        
        mfi = 100 - (100 / (1 + positive_mf / negative_mf))
        
        current = mfi.iloc[-1]
        condition = 'OVERBOUGHT' if current > 80 else 'OVERSOLD' if current < 20 else 'NEUTRAL'
        
        return {
            'mfi': mfi,
            'current': {
                'value': current,
                'condition': condition
            }
        }
    
    def volume_profile(self, periods: int = 20) -> Dict:
        """
        Volume analysis - average volume and relative volume.
        """
        avg_volume = self.df['volume'].rolling(window=periods).mean()
        current_volume = self.df['volume'].iloc[-1]
        rel_volume = current_volume / avg_volume.iloc[-1]
        
        intensity = 'HIGH' if rel_volume > 1.5 else 'LOW' if rel_volume < 0.5 else 'NORMAL'
        
        return {
            'avg_volume': avg_volume,
            'current': {
                'volume': current_volume,
                'avg_volume': avg_volume.iloc[-1],
                'relative_volume': rel_volume,
                'intensity': intensity
            }
        }
    
    # ==================== SUPPORT/RESISTANCE ====================
    
    def pivot_points(self) -> Dict:
        """
        Classic Pivot Points.
        Uses previous period's H/L/C.
        """
        # Use last complete bar
        h = self.df['high'].iloc[-2]
        l = self.df['low'].iloc[-2]
        c = self.df['close'].iloc[-2]
        
        pivot = (h + l + c) / 3
        r1 = 2 * pivot - l
        r2 = pivot + (h - l)
        r3 = h + 2 * (pivot - l)
        s1 = 2 * pivot - h
        s2 = pivot - (h - l)
        s3 = l - 2 * (h - pivot)
        
        current_price = self.df['close'].iloc[-1]
        
        # Determine position
        if current_price > r2:
            position = 'ABOVE_R2'
        elif current_price > r1:
            position = 'ABOVE_R1'
        elif current_price > pivot:
            position = 'ABOVE_PIVOT'
        elif current_price > s1:
            position = 'BELOW_PIVOT'
        elif current_price > s2:
            position = 'BELOW_S1'
        else:
            position = 'BELOW_S2'
        
        return {
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3,
            'position': position
        }
    
    # ==================== SIGNAL AGGREGATION ====================
    
    def get_all_signals(self) -> Dict:
        """
        Calculate all indicators and return current signals.
        """
        signals = {}
        
        # Trend
        macd_data = self.macd()
        signals['macd'] = {
            'value': macd_data['current']['histogram'],
            'signal': 'BULLISH' if macd_data['current']['histogram'] > 0 else 'BEARISH'
        }
        
        adx_data = self.adx()
        signals['adx'] = adx_data['current']
        
        # Momentum
        rsi_data = self.rsi()
        signals['rsi'] = rsi_data['current']
        
        stoch_data = self.stochastic()
        signals['stochastic'] = stoch_data['current']
        
        cci_data = self.cci()
        signals['cci'] = cci_data['current']
        
        williams_data = self.williams_r()
        signals['williams_r'] = williams_data['current']
        
        # Volatility
        bb_data = self.bollinger_bands()
        signals['bollinger'] = bb_data['current']
        
        atr_data = self.atr()
        signals['atr'] = atr_data['current']
        
        # Volume
        vwap_data = self.vwap()
        signals['vwap'] = vwap_data['current']
        
        obv_data = self.obv()
        signals['obv'] = obv_data['current']
        
        mfi_data = self.mfi()
        signals['mfi'] = mfi_data['current']
        
        vol_data = self.volume_profile()
        signals['volume'] = vol_data['current']
        
        # Moving Averages
        current_price = self.df['close'].iloc[-1]
        signals['moving_averages'] = {
            'ema_9': self.ema(9).iloc[-1],
            'ema_21': self.ema(21).iloc[-1],
            'sma_20': self.sma(20).iloc[-1],
            'sma_50': self.sma(50).iloc[-1] if len(self.df) >= 50 else None,
            'price': current_price,
            'trend_short': 'BULLISH' if current_price > self.ema(9).iloc[-1] else 'BEARISH',
            'trend_medium': 'BULLISH' if current_price > self.sma(20).iloc[-1] else 'BEARISH'
        }
        
        # Pivot Points
        signals['pivots'] = self.pivot_points()
        
        return signals
    
    def score_signals(self) -> Dict:
        """
        Score signals for trading decision.
        Returns bullish/bearish counts and overall bias.
        """
        signals = self.get_all_signals()
        
        bullish = 0
        bearish = 0
        neutral = 0
        
        # MACD
        if signals['macd']['signal'] == 'BULLISH':
            bullish += 1
        else:
            bearish += 1
        
        # RSI
        if signals['rsi']['condition'] == 'OVERSOLD':
            bullish += 1
        elif signals['rsi']['condition'] == 'OVERBOUGHT':
            bearish += 1
        else:
            neutral += 1
        
        # Stochastic
        if 'BULLISH' in signals['stochastic']['signal']:
            bullish += 1
        elif 'BEARISH' in signals['stochastic']['signal']:
            bearish += 1
        elif signals['stochastic']['signal'] == 'OVERSOLD':
            bullish += 1
        elif signals['stochastic']['signal'] == 'OVERBOUGHT':
            bearish += 1
        else:
            neutral += 1
        
        # CCI
        if signals['cci']['condition'] == 'OVERSOLD':
            bullish += 1
        elif signals['cci']['condition'] == 'OVERBOUGHT':
            bearish += 1
        else:
            neutral += 1
        
        # Williams %R
        if signals['williams_r']['condition'] == 'OVERSOLD':
            bullish += 1
        elif signals['williams_r']['condition'] == 'OVERBOUGHT':
            bearish += 1
        else:
            neutral += 1
        
        # VWAP
        if signals['vwap']['position'] == 'ABOVE':
            bullish += 1
        else:
            bearish += 1
        
        # OBV
        if signals['obv']['trend'] == 'BULLISH':
            bullish += 1
        else:
            bearish += 1
        
        # MFI
        if signals['mfi']['condition'] == 'OVERSOLD':
            bullish += 1
        elif signals['mfi']['condition'] == 'OVERBOUGHT':
            bearish += 1
        else:
            neutral += 1
        
        # Price vs EMAs
        if signals['moving_averages']['trend_short'] == 'BULLISH':
            bullish += 1
        else:
            bearish += 1
        
        if signals['moving_averages']['trend_medium'] == 'BULLISH':
            bullish += 1
        else:
            bearish += 1
        
        total = bullish + bearish + neutral
        
        if bullish > bearish + 2:
            bias = 'STRONG_BULLISH'
        elif bullish > bearish:
            bias = 'BULLISH'
        elif bearish > bullish + 2:
            bias = 'STRONG_BEARISH'
        elif bearish > bullish:
            bias = 'BEARISH'
        else:
            bias = 'NEUTRAL'
        
        return {
            'bullish': bullish,
            'bearish': bearish,
            'neutral': neutral,
            'total': total,
            'bias': bias,
            'signals': signals
        }
    
    def full_report(self) -> str:
        """
        Generate human-readable technical analysis report.
        """
        score = self.score_signals()
        signals = score['signals']
        current_price = self.df['close'].iloc[-1]
        
        report = []
        report.append("=" * 60)
        report.append(f"TECHNICAL ANALYSIS REPORT")
        report.append(f"Current Price: ${current_price:.2f}")
        report.append("=" * 60)
        
        # TREND INDICATORS
        report.append("\n📈 TREND INDICATORS")
        report.append("-" * 40)
        report.append(f"MACD Histogram:  {signals['macd']['value']:.4f} ({signals['macd']['signal']})")
        report.append(f"ADX:             {signals['adx']['adx']:.2f} ({signals['adx']['trend_strength']} trend)")
        report.append(f"+DI / -DI:       {signals['adx']['plus_di']:.2f} / {signals['adx']['minus_di']:.2f}")
        
        # MOMENTUM INDICATORS
        report.append("\n⚡ MOMENTUM INDICATORS")
        report.append("-" * 40)
        report.append(f"RSI (14):        {signals['rsi']['value']:.2f} ({signals['rsi']['condition']})")
        report.append(f"Stochastic:      K={signals['stochastic']['k']:.2f}, D={signals['stochastic']['d']:.2f} ({signals['stochastic']['signal']})")
        report.append(f"CCI:             {signals['cci']['value']:.2f} ({signals['cci']['condition']})")
        report.append(f"Williams %R:     {signals['williams_r']['value']:.2f} ({signals['williams_r']['condition']})")
        report.append(f"MFI:             {signals['mfi']['value']:.2f} ({signals['mfi']['condition']})")
        
        # VOLATILITY
        report.append("\n📊 VOLATILITY")
        report.append("-" * 40)
        report.append(f"Bollinger Bands: ${signals['bollinger']['lower']:.2f} | ${signals['bollinger']['middle']:.2f} | ${signals['bollinger']['upper']:.2f}")
        report.append(f"Price Position:  {signals['bollinger']['position']} (B%: {signals['bollinger']['pct_b']:.2f})")
        report.append(f"ATR (14):        ${signals['atr']['value']:.2f} ({signals['atr']['pct_of_price']:.2f}% of price)")
        
        # VOLUME
        report.append("\n📦 VOLUME")
        report.append("-" * 40)
        report.append(f"VWAP:            ${signals['vwap']['value']:.2f} (Price {signals['vwap']['position']})")
        report.append(f"OBV Trend:       {signals['obv']['trend']}")
        report.append(f"Rel. Volume:     {signals['volume']['relative_volume']:.2f}x ({signals['volume']['intensity']})")
        
        # MOVING AVERAGES
        report.append("\n📉 MOVING AVERAGES")
        report.append("-" * 40)
        report.append(f"EMA 9:           ${signals['moving_averages']['ema_9']:.2f}")
        report.append(f"EMA 21:          ${signals['moving_averages']['ema_21']:.2f}")
        report.append(f"SMA 20:          ${signals['moving_averages']['sma_20']:.2f}")
        if signals['moving_averages']['sma_50']:
            report.append(f"SMA 50:          ${signals['moving_averages']['sma_50']:.2f}")
        
        # PIVOT POINTS
        report.append("\n🎯 PIVOT POINTS")
        report.append("-" * 40)
        report.append(f"R3: ${signals['pivots']['r3']:.2f}  R2: ${signals['pivots']['r2']:.2f}  R1: ${signals['pivots']['r1']:.2f}")
        report.append(f"Pivot: ${signals['pivots']['pivot']:.2f}")
        report.append(f"S1: ${signals['pivots']['s1']:.2f}  S2: ${signals['pivots']['s2']:.2f}  S3: ${signals['pivots']['s3']:.2f}")
        report.append(f"Position: {signals['pivots']['position']}")
        
        # SUMMARY
        report.append("\n" + "=" * 60)
        report.append("SIGNAL SUMMARY")
        report.append("=" * 60)
        report.append(f"🟢 Bullish Signals: {score['bullish']}")
        report.append(f"🔴 Bearish Signals: {score['bearish']}")
        report.append(f"⚪ Neutral Signals: {score['neutral']}")
        report.append(f"\n>>> OVERALL BIAS: {score['bias']} <<<")
        report.append("=" * 60)
        
        return "\n".join(report)


# ==================== MULTI-TIMEFRAME ANALYSIS ====================

class MultiTimeframeAnalyzer:
    """
    Analyze multiple timeframes simultaneously.
    """
    
    def __init__(self, data_dict: Dict[str, pd.DataFrame]):
        """
        Initialize with dict of {timeframe: dataframe}.
        Example: {'1m': df_1m, '5m': df_5m, '15m': df_15m, '30m': df_30m}
        """
        self.data = data_dict
        self.analyzers = {tf: TechnicalAnalyzer(df) for tf, df in data_dict.items()}
    
    def analyze_all(self) -> Dict:
        """
        Run analysis on all timeframes.
        """
        results = {}
        for tf, analyzer in self.analyzers.items():
            results[tf] = analyzer.score_signals()
        return results
    
    def confluence_score(self) -> Dict:
        """
        Calculate confluence across timeframes.
        More timeframes agreeing = stronger signal.
        """
        results = self.analyze_all()
        
        bullish_tfs = sum(1 for r in results.values() if 'BULLISH' in r['bias'])
        bearish_tfs = sum(1 for r in results.values() if 'BEARISH' in r['bias'])
        total_tfs = len(results)
        
        if bullish_tfs == total_tfs:
            confluence = 'STRONG_BULLISH_CONFLUENCE'
        elif bearish_tfs == total_tfs:
            confluence = 'STRONG_BEARISH_CONFLUENCE'
        elif bullish_tfs > bearish_tfs:
            confluence = 'BULLISH_LEAN'
        elif bearish_tfs > bullish_tfs:
            confluence = 'BEARISH_LEAN'
        else:
            confluence = 'MIXED'
        
        return {
            'timeframes': results,
            'bullish_count': bullish_tfs,
            'bearish_count': bearish_tfs,
            'total': total_tfs,
            'confluence': confluence
        }
    
    def full_report(self) -> str:
        """
        Generate multi-timeframe report.
        """
        conf = self.confluence_score()
        
        report = []
        report.append("=" * 60)
        report.append("MULTI-TIMEFRAME ANALYSIS")
        report.append("=" * 60)
        
        for tf, result in conf['timeframes'].items():
            bias_emoji = "🟢" if 'BULLISH' in result['bias'] else "🔴" if 'BEARISH' in result['bias'] else "⚪"
            report.append(f"\n{tf.upper()} Timeframe:")
            report.append(f"  {bias_emoji} Bias: {result['bias']}")
            report.append(f"  Bullish: {result['bullish']} | Bearish: {result['bearish']} | Neutral: {result['neutral']}")
        
        report.append("\n" + "=" * 60)
        report.append("CONFLUENCE")
        report.append("=" * 60)
        report.append(f"Bullish Timeframes: {conf['bullish_count']}/{conf['total']}")
        report.append(f"Bearish Timeframes: {conf['bearish_count']}/{conf['total']}")
        report.append(f"\n>>> {conf['confluence']} <<<")
        report.append("=" * 60)
        
        return "\n".join(report)


if __name__ == "__main__":
    print("AlphaTrader Technical Indicators Module")
    print("=" * 50)
    print("Classes available:")
    print("  - TechnicalAnalyzer(df): Single timeframe analysis")
    print("  - MultiTimeframeAnalyzer(data_dict): Multi-TF confluence")
    print("\nIndicators included:")
    print("  TREND: MACD, ADX, EMAs, SMAs")
    print("  MOMENTUM: RSI, Stochastic, CCI, Williams %R, ROC, MFI")
    print("  VOLATILITY: Bollinger Bands, ATR, Keltner Channels")
    print("  VOLUME: VWAP, OBV, Volume Profile")
    print("  S/R: Pivot Points")

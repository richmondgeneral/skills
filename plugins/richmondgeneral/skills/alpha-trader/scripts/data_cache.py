#!/usr/bin/env python3
"""
AlphaTrader Data Cache Module
=============================
Local caching for Alpaca market data to reduce API calls
and enable offline analysis.

Cache Structure:
~/.alpha-trader/cache/
├── bars/
│   ├── SPY_1Min_2026-01-22.parquet
│   ├── SPY_5Min_2026-01-22.parquet
│   └── ...
├── quotes/
│   └── SPY_quotes_2026-01-22.parquet
├── options/
│   └── SPY_chain_2026-01-23_exp.parquet
└── metadata.json
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union
import hashlib

class DataCache:
    """
    Local file cache for market data.
    Uses Parquet for efficient storage and fast reads.
    """
    
    DEFAULT_CACHE_DIR = os.path.expanduser("~/.alpha-trader/cache")
    
    def __init__(self, cache_dir: str = None):
        """
        Initialize cache with directory path.
        Creates directory structure if it doesn't exist.
        """
        self.cache_dir = Path(cache_dir or self.DEFAULT_CACHE_DIR)
        self._ensure_directories()
        self._load_metadata()
    
    def _ensure_directories(self):
        """Create cache directory structure."""
        subdirs = ['bars', 'quotes', 'options', 'snapshots', 'indicators']
        for subdir in subdirs:
            (self.cache_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    def _load_metadata(self):
        """Load or initialize metadata file."""
        self.metadata_file = self.cache_dir / 'metadata.json'
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {
                'created': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'cache_hits': 0,
                'cache_misses': 0,
                'files': {}
            }
            self._save_metadata()
    
    def _save_metadata(self):
        """Save metadata to file."""
        self.metadata['last_updated'] = datetime.now().isoformat()
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _generate_key(self, data_type: str, symbol: str, timeframe: str = None, 
                      date: str = None, extra: str = None) -> str:
        """Generate unique cache key."""
        parts = [symbol]
        if timeframe:
            parts.append(timeframe)
        if date:
            parts.append(date)
        if extra:
            parts.append(extra)
        return f"{data_type}/" + "_".join(parts)
    
    def _get_filepath(self, key: str) -> Path:
        """Get full filepath for cache key."""
        return self.cache_dir / f"{key}.parquet"
    
    # ==================== BARS CACHE ====================
    
    def cache_bars(self, symbol: str, timeframe: str, df: pd.DataFrame, 
                   date: str = None) -> str:
        """
        Cache bar data (OHLCV).
        
        Args:
            symbol: Ticker symbol (e.g., 'SPY')
            timeframe: Bar timeframe (e.g., '1Min', '5Min', '1Day')
            df: DataFrame with OHLCV data
            date: Optional date string for daily partitioning
        
        Returns:
            Cache key
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        key = self._generate_key('bars', symbol, timeframe, date)
        filepath = self._get_filepath(key)
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to parquet
        df.to_parquet(filepath, index=True)
        
        # Update metadata
        self.metadata['files'][key] = {
            'filepath': str(filepath),
            'symbol': symbol,
            'timeframe': timeframe,
            'date': date,
            'rows': len(df),
            'cached_at': datetime.now().isoformat(),
            'size_bytes': filepath.stat().st_size
        }
        self._save_metadata()
        
        return key
    
    def get_bars(self, symbol: str, timeframe: str, date: str = None) -> Optional[pd.DataFrame]:
        """
        Retrieve cached bar data.
        
        Returns:
            DataFrame if cached, None if not found
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        key = self._generate_key('bars', symbol, timeframe, date)
        filepath = self._get_filepath(key)
        
        if filepath.exists():
            self.metadata['cache_hits'] += 1
            self._save_metadata()
            return pd.read_parquet(filepath)
        else:
            self.metadata['cache_misses'] += 1
            self._save_metadata()
            return None
    
    def get_bars_range(self, symbol: str, timeframe: str, 
                       start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        Get bars for a date range, combining multiple cached files.
        """
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        dfs = []
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            df = self.get_bars(symbol, timeframe, date_str)
            if df is not None:
                dfs.append(df)
            current += timedelta(days=1)
        
        if dfs:
            return pd.concat(dfs).sort_index().drop_duplicates()
        return None
    
    # ==================== OPTIONS CACHE ====================
    
    def cache_options_chain(self, symbol: str, expiry: str, df: pd.DataFrame) -> str:
        """
        Cache options chain data.
        
        Args:
            symbol: Underlying symbol
            expiry: Expiration date (YYYY-MM-DD)
            df: DataFrame with options chain data
        """
        key = self._generate_key('options', symbol, 'chain', expiry)
        filepath = self._get_filepath(key)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_parquet(filepath, index=True)
        
        self.metadata['files'][key] = {
            'filepath': str(filepath),
            'symbol': symbol,
            'expiry': expiry,
            'contracts': len(df),
            'cached_at': datetime.now().isoformat()
        }
        self._save_metadata()
        
        return key
    
    def get_options_chain(self, symbol: str, expiry: str) -> Optional[pd.DataFrame]:
        """Retrieve cached options chain."""
        key = self._generate_key('options', symbol, 'chain', expiry)
        filepath = self._get_filepath(key)
        
        if filepath.exists():
            self.metadata['cache_hits'] += 1
            self._save_metadata()
            return pd.read_parquet(filepath)
        else:
            self.metadata['cache_misses'] += 1
            self._save_metadata()
            return None
    
    # ==================== SNAPSHOTS CACHE ====================
    
    def cache_snapshot(self, symbol: str, data: Dict) -> str:
        """
        Cache a point-in-time snapshot.
        Useful for end-of-day or periodic saves.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        key = self._generate_key('snapshots', symbol, timestamp)
        filepath = self.cache_dir / 'snapshots' / f"{symbol}_{timestamp}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        self.metadata['files'][key] = {
            'filepath': str(filepath),
            'symbol': symbol,
            'timestamp': timestamp,
            'cached_at': datetime.now().isoformat()
        }
        self._save_metadata()
        
        return key
    
    # ==================== INDICATORS CACHE ====================
    
    def cache_indicators(self, symbol: str, timeframe: str, 
                         indicators: Dict, date: str = None) -> str:
        """
        Cache calculated indicator values.
        Saves recalculation time.
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        key = self._generate_key('indicators', symbol, timeframe, date)
        filepath = self.cache_dir / 'indicators' / f"{symbol}_{timeframe}_{date}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert any numpy/pandas types to native Python
        def convert(obj):
            if hasattr(obj, 'item'):
                return obj.item()
            elif hasattr(obj, 'tolist'):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(i) for i in obj]
            return obj
        
        with open(filepath, 'w') as f:
            json.dump(convert(indicators), f, indent=2)
        
        self.metadata['files'][key] = {
            'filepath': str(filepath),
            'symbol': symbol,
            'timeframe': timeframe,
            'date': date,
            'cached_at': datetime.now().isoformat()
        }
        self._save_metadata()
        
        return key
    
    def get_indicators(self, symbol: str, timeframe: str, 
                       date: str = None) -> Optional[Dict]:
        """Retrieve cached indicators."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        filepath = self.cache_dir / 'indicators' / f"{symbol}_{timeframe}_{date}.json"
        
        if filepath.exists():
            self.metadata['cache_hits'] += 1
            self._save_metadata()
            with open(filepath, 'r') as f:
                return json.load(f)
        else:
            self.metadata['cache_misses'] += 1
            self._save_metadata()
            return None
    
    # ==================== CACHE MANAGEMENT ====================
    
    def list_cached_files(self, data_type: str = None) -> List[Dict]:
        """List all cached files, optionally filtered by type."""
        files = []
        for key, info in self.metadata['files'].items():
            if data_type is None or key.startswith(data_type):
                files.append({'key': key, **info})
        return files
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        total_size = sum(
            f.get('size_bytes', 0) 
            for f in self.metadata['files'].values()
        )
        
        return {
            'total_files': len(self.metadata['files']),
            'total_size_mb': total_size / (1024 * 1024),
            'cache_hits': self.metadata.get('cache_hits', 0),
            'cache_misses': self.metadata.get('cache_misses', 0),
            'hit_rate': self.metadata.get('cache_hits', 0) / 
                       max(1, self.metadata.get('cache_hits', 0) + 
                           self.metadata.get('cache_misses', 0)),
            'created': self.metadata.get('created'),
            'last_updated': self.metadata.get('last_updated')
        }
    
    def clear_old_cache(self, days: int = 7) -> int:
        """
        Remove cache files older than specified days.
        Returns number of files removed.
        """
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        
        keys_to_remove = []
        for key, info in self.metadata['files'].items():
            cached_at = datetime.fromisoformat(info['cached_at'])
            if cached_at < cutoff:
                filepath = Path(info['filepath'])
                if filepath.exists():
                    filepath.unlink()
                keys_to_remove.append(key)
                removed += 1
        
        for key in keys_to_remove:
            del self.metadata['files'][key]
        
        self._save_metadata()
        return removed
    
    def clear_all(self) -> int:
        """Clear entire cache. Returns number of files removed."""
        removed = 0
        for key, info in self.metadata['files'].items():
            filepath = Path(info['filepath'])
            if filepath.exists():
                filepath.unlink()
                removed += 1
        
        self.metadata['files'] = {}
        self.metadata['cache_hits'] = 0
        self.metadata['cache_misses'] = 0
        self._save_metadata()
        
        return removed
    
    def invalidate(self, symbol: str, data_type: str = None) -> int:
        """
        Invalidate cache for a specific symbol.
        Useful when you know data has changed.
        """
        removed = 0
        keys_to_remove = []
        
        for key, info in self.metadata['files'].items():
            if info.get('symbol') == symbol:
                if data_type is None or key.startswith(data_type):
                    filepath = Path(info['filepath'])
                    if filepath.exists():
                        filepath.unlink()
                    keys_to_remove.append(key)
                    removed += 1
        
        for key in keys_to_remove:
            del self.metadata['files'][key]
        
        self._save_metadata()
        return removed


class SmartCache(DataCache):
    """
    Extended cache with intelligent refresh logic.
    """
    
    # Data freshness thresholds (in seconds)
    FRESHNESS = {
        'bars_1Min': 60,      # 1 minute bars fresh for 1 minute
        'bars_5Min': 300,     # 5 minute bars fresh for 5 minutes
        'bars_1Day': 86400,   # Daily bars fresh for 1 day
        'options': 300,       # Options chain fresh for 5 minutes
        'snapshot': 60,       # Snapshots fresh for 1 minute
        'indicators': 300     # Indicators fresh for 5 minutes
    }
    
    def is_fresh(self, key: str) -> bool:
        """Check if cached data is still fresh."""
        if key not in self.metadata['files']:
            return False
        
        info = self.metadata['files'][key]
        cached_at = datetime.fromisoformat(info['cached_at'])
        age_seconds = (datetime.now() - cached_at).total_seconds()
        
        # Determine freshness threshold
        for pattern, threshold in self.FRESHNESS.items():
            if pattern in key:
                return age_seconds < threshold
        
        # Default: 5 minutes
        return age_seconds < 300
    
    def get_or_none(self, key: str) -> Optional[pd.DataFrame]:
        """
        Get cached data only if fresh, otherwise return None.
        Forces a refresh for stale data.
        """
        if self.is_fresh(key):
            filepath = self._get_filepath(key)
            if filepath.exists():
                return pd.read_parquet(filepath)
        return None


if __name__ == "__main__":
    print("AlphaTrader Data Cache Module")
    print("=" * 50)
    print(f"Default cache directory: {DataCache.DEFAULT_CACHE_DIR}")
    print("\nClasses available:")
    print("  - DataCache: Basic caching functionality")
    print("  - SmartCache: Auto-refresh stale data")
    print("\nMethods:")
    print("  - cache_bars(symbol, timeframe, df)")
    print("  - get_bars(symbol, timeframe, date)")
    print("  - cache_options_chain(symbol, expiry, df)")
    print("  - cache_indicators(symbol, timeframe, indicators)")
    print("  - get_cache_stats()")
    print("  - clear_old_cache(days=7)")

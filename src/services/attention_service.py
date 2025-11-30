"""
Service layer for attention features.
Orchestrates data loading, calculation, and persistence.
"""
import logging
from typing import Optional
import pandas as pd

from src.data.db_storage import load_price_data, load_news_data, get_db, USE_DATABASE, load_attention_data
from src.data.google_trends_fetcher import get_google_trends_series
from src.data.twitter_attention_fetcher import get_twitter_volume_series
from src.features.calculators import calculate_composite_attention
from src.features.event_detectors import detect_attention_spikes, AttentionEvent
from typing import List

logger = logging.getLogger(__name__)

class AttentionService:
    @staticmethod
    def get_attention_events(
        symbol: str,
        start: Optional[pd.Timestamp] = None,
        end: Optional[pd.Timestamp] = None,
        lookback_days: int = 30,
        min_quantile: float = 0.8,
    ) -> List[AttentionEvent]:
        """
        Get attention events for a symbol.
        Orchestrates data loading and event detection logic.
        
        Args:
            symbol: Symbol name.
            start: Start datetime.
            end: End datetime.
            lookback_days: Lookback window for quantile.
            min_quantile: Quantile threshold.
            
        Returns:
            List of AttentionEvent objects.
        """
        # 1. Load Data (IO)
        df = load_attention_data(symbol, start, end)
        if df.empty:
            return []
        
        # 2. Apply Logic (CPU)
        # Ensure datetime is present and valid
        if 'datetime' in df.columns:
            df = df.dropna(subset=['datetime'])
            
        return detect_attention_spikes(df, lookback_days, min_quantile)

    @staticmethod
    def update_attention_features(
        symbol: str,
        freq: str = 'D',
        save_to_db: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        Orchestrate the calculation of attention features for a symbol.
        
        1. Loads price, news, google trends, and twitter data.
        2. Calls the pure calculation logic.
        3. Saves the result to the database.
        
        Args:
            symbol: Symbol name (e.g., 'ZEC')
            freq: Frequency ('D' or '4H')
            save_to_db: Whether to persist results
            
        Returns:
            DataFrame with features or None if failed.
        """
        symbol = symbol.upper()
        freq = freq.upper()
        
        logger.info(f"Processing attention features for {symbol} (freq={freq})")
        
        # 1. Load Price Data (Base for time index)
        # We always use 1d price data to determine the date range, even for 4H attention
        price_data = load_price_data(symbol, timeframe='1d')
        if isinstance(price_data, tuple):
            price_df, _ = price_data
        else:
            price_df = price_data
            
        if price_df is None or price_df.empty:
            logger.error(f"No price data available for {symbol}, cannot generate attention features")
            return None
            
        # Determine date range
        if 'timestamp' in price_df.columns:
            price_df['datetime'] = pd.to_datetime(price_df['timestamp'], unit='ms', utc=True)
        elif 'date' not in price_df.columns and 'datetime' not in price_df.columns:
            logger.error(f"Price data for {symbol} has no datetime column")
            return None
            
        date_col = 'datetime' if 'datetime' in price_df.columns else 'date'
        date_range = pd.to_datetime(price_df[date_col], utc=True)
        start_date = date_range.min()
        end_date = date_range.max()
        
        # 2. Load Auxiliary Data
        # News
        news_df = load_news_data(symbol, start=start_date, end=end_date)
        
        # Google Trends (fetch extra 7 days for rolling window context)
        gt_start = start_date - pd.Timedelta(days=7)
        try:
            google_trends_df = get_google_trends_series(symbol, gt_start, end_date)
        except Exception as e:
            logger.warning(f"Failed to load Google Trends for {symbol}: {e}")
            google_trends_df = None
            
        # Twitter Volume
        try:
            twitter_volume_df = get_twitter_volume_series(symbol, gt_start, end_date)
        except Exception as e:
            logger.warning(f"Failed to load Twitter volume for {symbol}: {e}")
            twitter_volume_df = None
            
        # 3. Calculate Features (Pure Logic)
        result_df = calculate_composite_attention(
            symbol=symbol,
            price_df=price_df,
            news_df=news_df,
            google_trends_df=google_trends_df,
            twitter_volume_df=twitter_volume_df,
            freq=freq
        )
        
        if result_df is None or result_df.empty:
            logger.warning(f"Calculation returned empty result for {symbol}")
            return None
            
        # 4. Persist Results
        if USE_DATABASE and save_to_db:
            try:
                db = get_db()
                # Pass timeframe param to distinguish frequencies
                db.save_attention_features(symbol, result_df.to_dict('records'), timeframe=freq)
                logger.info(f"Saved {len(result_df)} attention rows for {symbol} (freq={freq})")
            except TypeError as te:
                logger.warning(
                    f"save_attention_features does not support timeframe param yet; "
                    f"Data returned but not saved correctly for 4H. Error: {te}"
                )
            except Exception as exc:
                logger.error(f"Failed to persist attention features: {exc}")
                
        return result_df

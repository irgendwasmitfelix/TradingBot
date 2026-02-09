# Technical Analysis Module for Trading Signals

import logging
import numpy as np
from collections import deque


class TechnicalAnalysis:
    """
    Technical analysis tool for generating trading signals based on market data.
    Supports multi-pair analysis with separate price history per pair.
    """
    
    def __init__(self, rsi_period=14, sma_short=20, sma_long=50):
        """
        Initialize the technical analysis tool.
        
        Args:
            rsi_period (int): Period for RSI calculation.
            sma_short (int): Period for short-term SMA.
            sma_long (int): Period for long-term SMA.
        """
        self.rsi_period = rsi_period
        self.sma_short = sma_short
        self.sma_long = sma_long
        self.logger = logging.getLogger(__name__)
        # Per-pair price history for multi-pair analysis
        self.pair_price_history = {}
        self.max_history = max(rsi_period, sma_long)
    
    def _get_price_history(self, pair):
        """Get or create price history for a trading pair."""
        if pair not in self.pair_price_history:
            self.pair_price_history[pair] = deque(maxlen=self.max_history)
        return self.pair_price_history[pair]

    def calculate_rsi(self, prices):
        """
        Calculate the Relative Strength Index (RSI).
        
        Args:
            prices (list): List of prices.
        
        Returns:
            float: RSI value (0-100).
        """
        if len(prices) < self.rsi_period + 1:
            return None
        
        prices = np.array(prices)
        deltas = np.diff(prices)
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])
        
        if avg_loss == 0:
            return 100 if avg_gain > 0 else 0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    def calculate_sma(self, prices, period):
        """
        Calculate Simple Moving Average (SMA).
        
        Args:
            prices (list): List of prices.
            period (int): Period for SMA calculation.
        
        Returns:
            float: SMA value or None if not enough data.
        """
        if len(prices) < period:
            return None
        
        return np.mean(prices[-period:])

    def generate_signal(self, market_data):
        """
        Generate trading signal based on technical indicators.
        
        Args:
            market_data (dict): Market data from Kraken API.
        
        Returns:
            str: Trading signal - "BUY", "SELL", or "HOLD".
        """
        signal, _ = self.generate_signal_with_score(market_data)
        return signal
    
    def generate_signal_with_score(self, market_data):
        """
        Generate trading signal with strength score for multi-pair ranking.
        
        Args:
            market_data (dict): Market data from Kraken API.
        
        Returns:
            tuple: (signal, score) where signal is "BUY"/"SELL"/"HOLD" 
                   and score is -100 to +100 (positive=buy strength, negative=sell strength)
        """
        try:
            if not market_data:
                return "HOLD", 0
            
            # Get the pair key from market_data
            pair_key = list(market_data.keys())[0] if market_data else None
            if not pair_key:
                return "HOLD", 0
            
            pair_data = market_data[pair_key]
            
            if 'c' not in pair_data:
                self.logger.warning("No closing price found in market data")
                return "HOLD", 0
            
            close_price = float(pair_data['c'][0])
            
            # Use per-pair price history
            price_history = self._get_price_history(pair_key)
            price_history.append(close_price)
            
            if len(price_history) < self.sma_long:
                return "HOLD", 0
            
            # Calculate indicators
            prices = list(price_history)
            rsi = self.calculate_rsi(prices)
            sma_short = self.calculate_sma(prices, self.sma_short)
            sma_long = self.calculate_sma(prices, self.sma_long)
            
            if rsi is None or sma_short is None or sma_long is None:
                return "HOLD", 0
            
            # Calculate score based on indicator strength
            # RSI score: 0-30 = strong buy, 70-100 = strong sell
            # SMA score: difference between short and long SMA
            
            rsi_score = 0
            sma_score = 0
            
            # RSI contribution to score
            if rsi < 30:
                rsi_score = (30 - rsi) / 30 * 50  # 0 to 50 for buy
            elif rsi > 70:
                rsi_score = -((rsi - 70) / 30 * 50)  # -50 to 0 for sell
            
            # SMA contribution (positive = bullish, negative = bearish)
            sma_diff_percent = ((sma_short - sma_long) / sma_long) * 100
            sma_score = max(-50, min(50, sma_diff_percent * 10))  # Clamp to -50 to 50
            
            # Combined score
            total_score = rsi_score + sma_score  # Range: -100 to +100
            
            # Generate signal based on indicators
            # BUY when: RSI is oversold (<30) and short SMA > long SMA
            # SELL when: RSI is overbought (>70) and short SMA < long SMA
            # HOLD otherwise
            
            if rsi < 30 and sma_short > sma_long:
                return "BUY", total_score
            elif rsi > 70 and sma_short < sma_long:
                return "SELL", total_score
            else:
                return "HOLD", total_score
        
        except Exception as e:
            self.logger.error(f"Error generating signal: {e}")
            return "HOLD", 0

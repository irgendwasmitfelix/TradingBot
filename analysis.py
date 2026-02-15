# Technical Analysis Module for Trading Signals

import logging
import numpy as np
import os
import json
from collections import deque


class TechnicalAnalysis:
    """
    Technical analysis tool for generating trading signals based on market data.
    Supports multi-pair analysis with separate price history per pair.
    """

    def __init__(self, rsi_period=14, sma_short=20, sma_long=30, min_volatility_pct=0.15):
        self.rsi_period = rsi_period
        self.sma_short = sma_short
        self.sma_long = sma_long
        self.min_volatility_pct = min_volatility_pct
        self.logger = logging.getLogger(__name__)
        self.pair_price_history = {}
        self.max_history = max(rsi_period + 2, sma_long + 5)
        self.buffer_path = os.path.join(os.path.dirname(__file__), 'data', 'history_buffer.json')
        self._load_history()

    def _get_price_history(self, pair):
        if pair not in self.pair_price_history:
            self.pair_price_history[pair] = deque(maxlen=self.max_history)
        return self.pair_price_history[pair]

    def _load_history(self):
        try:
            if os.path.exists(self.buffer_path):
                with open(self.buffer_path, 'r') as f:
                    data = json.load(f)
                for pair, prices in data.items():
                    self.pair_price_history[pair] = deque(prices, maxlen=self.max_history)
                self.logger.info(f"Loaded price history for {len(data)} pairs from buffer")
        except Exception as e:
            self.logger.error(f"Error loading price history buffer: {e}")

    def _save_history(self):
        try:
            os.makedirs(os.path.dirname(self.buffer_path), exist_ok=True)
            data = {pair: list(prices) for pair, prices in self.pair_price_history.items()}
            with open(self.buffer_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.error(f"Error saving price history buffer: {e}")

    def calculate_rsi(self, prices):
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
        return 100 - (100 / (1 + rs))

    def calculate_atr(self, pair, period=14):
        """Calculate Average True Range using price history buffer."""
        prices = self._get_price_history(pair)
        if len(prices) < period + 1:
            return None
        
        # Approximate TR using absolute difference of consecutive closes
        prices_list = list(prices)
        tr = [abs(prices_list[i] - prices_list[i-1]) for i in range(1, len(prices_list))]
        return np.mean(tr[-period:])

    def check_mtf_trend(self, prices, short_p=20, long_p=50):
        """Check if the general trend is bullish on the provided history."""
        if len(prices) < long_p:
            return True # Not enough data, don't block
        
        sma_short = np.mean(prices[-short_p:])
        sma_long = np.mean(prices[-long_p:])
        return sma_short > sma_long

    def generate_signal(self, market_data):
        signal, _ = self.generate_signal_with_score(market_data)
        return signal

    def generate_signal_with_score(self, market_data):
        try:
            if not market_data:
                return "HOLD", 0

            pair_key = list(market_data.keys())[0]
            pair_data = market_data[pair_key]
            if 'c' not in pair_data:
                self.logger.warning("No closing price found in market data")
                return "HOLD", 0

            close_price = float(pair_data['c'][0])
            price_history = self._get_price_history(pair_key)
            price_history.append(close_price)
            self._save_history()

            if len(price_history) < self.sma_long:
                return "HOLD", 0

            prices = np.array(list(price_history))
            
            # Bollinger Band Breakout Logic
            # Use same parameters as backtest: SMA20, STD20, SMA50
            sma20 = np.mean(prices[-20:])
            std20 = np.std(prices[-20:])
            sma50 = np.mean(prices[-50:])
            
            upper_bb = sma20 + (2.0 * std20)
            lower_bb = sma20 - (2.0 * std20)
            
            current_price = prices[-1]
            signal = "HOLD"
            score = 0.0

            if current_price > upper_bb:
                # Bullish Breakout
                if current_price > sma50:
                    signal = "BUY"
                    breakout_pct = ((current_price - upper_bb) / upper_bb) * 100
                    score = 25.0 + (breakout_pct * 50.0)

            elif current_price < lower_bb:
                # Bearish Breakout
                if current_price < sma50:
                    signal = "SELL"
                    breakout_pct = ((lower_bb - current_price) / lower_bb) * 100
                    score = -25.0 - (breakout_pct * 50.0)

            # Cap score
            score = max(-50.0, min(50.0, score))

            # Additional indicators: ATR and Williams %R (approximate from closes)
            atr = None
            willr = None
            try:
                # approximate ATR from close diffs as fallback (we don't have full OHLC here)
                tr = np.abs(np.diff(prices))
                atr = float(np.mean(tr[-14:])) if len(tr) >= 14 else None
            except Exception:
                atr = None

            try:
                window = 14
                if len(prices) >= window:
                    high_w = np.max(prices[-window:])
                    low_w = np.min(prices[-window:])
                    willr = (high_w - current_price) / (high_w - low_w) * -100 if (high_w - low_w) != 0 else None
            except Exception:
                willr = None

            # Boost score slightly if ATR breakout and %R supports momentum
            if atr is not None and willr is not None:
                if current_price > upper_bb and willr < -20:
                    score += min(8.0, (atr / max(1e-6, sma20)) * 100.0)
                if current_price < lower_bb and willr > -80:
                    score -= min(8.0, (atr / max(1e-6, sma20)) * 100.0)

            return signal, score

        except Exception as e:
            self.logger.error(f"Error generating signal: {e}")
            return "HOLD", 0

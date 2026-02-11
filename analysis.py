# Technical Analysis Module for Trading Signals

import logging
import numpy as np
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

    def _get_price_history(self, pair):
        if pair not in self.pair_price_history:
            self.pair_price_history[pair] = deque(maxlen=self.max_history)
        return self.pair_price_history[pair]

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

    def calculate_sma(self, prices, period):
        if len(prices) < period:
            return None
        return np.mean(prices[-period:])

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

            if len(price_history) < self.sma_long:
                return "HOLD", 0

            prices = list(price_history)
            rsi = self.calculate_rsi(prices)
            sma_short = self.calculate_sma(prices, self.sma_short)
            sma_long = self.calculate_sma(prices, self.sma_long)
            if rsi is None or sma_short is None or sma_long is None:
                return "HOLD", 0

            # Volatility filter to avoid flat/noisy markets
            recent = np.array(prices[-self.sma_short:])
            vol_pct = float(np.std(recent) / np.mean(recent) * 100) if np.mean(recent) > 0 else 0
            if vol_pct < self.min_volatility_pct:
                return "HOLD", 0

            rsi_score = 0
            if rsi < 30:
                rsi_score = (30 - rsi) / 30 * 50
            elif rsi > 70:
                rsi_score = -((rsi - 70) / 30 * 50)

            sma_diff_percent = ((sma_short - sma_long) / sma_long) * 100
            sma_score = max(-50, min(50, sma_diff_percent * 10))
            total_score = rsi_score + sma_score
            sma_diff_ratio = (sma_short - sma_long) / sma_long

            # Edge 1: Mean-reversion entries/exits
            if rsi < 33 and sma_diff_ratio > -0.003:
                return "BUY", total_score
            if rsi > 67 and sma_diff_ratio < 0.003:
                return "SELL", total_score

            # Edge 2: Trend-following / breakout continuation
            # Participate when trend is clean and momentum is not overextended.
            if sma_diff_ratio > 0.006 and 45 <= rsi <= 68:
                return "BUY", total_score + 8
            if sma_diff_ratio < -0.006 and 32 <= rsi <= 55:
                return "SELL", total_score - 8

            return "HOLD", total_score
        except Exception as e:
            self.logger.error(f"Error generating signal: {e}")
            return "HOLD", 0

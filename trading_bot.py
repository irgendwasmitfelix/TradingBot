# Trading Bot Core Logic - Multi-Pair Analysis

import logging
import time
import os
from datetime import datetime, timezone
from analysis import TechnicalAnalysis
from utils import load_config


class TradingBot:
    def __init__(self, api_client, config):
        self.api_client = api_client
        self.config = config
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.toml')
        self.logger = logging.getLogger(__name__)

        self.analysis_tool = TechnicalAnalysis(rsi_period=14, sma_short=20, sma_long=50)

        self.trade_pairs = self.config['bot_settings'].get('trade_pairs', ['XBTEUR'])
        self.pair_signals = {}
        self.pair_prices = {}
        self.pair_scores = {}
        self.holdings = {}
        self.purchase_prices = {}
        self.peak_prices = {}
        self.position_qty = {}
        self.short_qty = {}
        self.short_entry_prices = {}
        self.realized_pnl = {}
        self.fees_paid = {}
        self.trade_metrics = {}
        self.last_trade_at = {}
        self.entry_timestamps = {}
        self.last_global_trade_at = 0
        self._normalized_pair_logs_seen = set()
        self._last_empty_sell_log_at = {}

        self.trade_count = 0
        self.consecutive_losses = 0
        self.trading_paused_until_ts = 0
        self.target_balance_eur = self._get_target_balance()
        self.take_profit_percent = self._get_take_profit_percent()
        self.stop_loss_percent = self._get_stop_loss_percent()
        self.max_open_positions = int(self.config.get('risk_management', {}).get('max_open_positions', 3))
        self.trade_cooldown_sec = int(self.config.get('risk_management', {}).get('trade_cooldown_seconds', 180))
        self.global_trade_cooldown_sec = int(self.config.get('risk_management', {}).get('global_trade_cooldown_seconds', 300))
        self.trailing_stop_percent = float(self.config.get('risk_management', {}).get('trailing_stop_percent', 1.5))
        self.min_buy_score = float(self.config.get('risk_management', {}).get('min_buy_score', 18.0))
        self.adaptive_tp_enabled = bool(self.config.get('risk_management', {}).get('adaptive_take_profit', True))
        self.max_tp_percent = float(self.config.get('risk_management', {}).get('max_take_profit_percent', 14.0))
        self.empty_sell_log_cooldown_sec = int(self.config.get('risk_management', {}).get('empty_sell_log_cooldown_seconds', 1800))
        self.enable_regime_filter = bool(self.config.get('risk_management', {}).get('enable_regime_filter', True))
        self.regime_benchmark_pair = str(self.config.get('risk_management', {}).get('regime_benchmark_pair', 'XBTEUR')).upper()
        self.regime_min_score = float(self.config.get('risk_management', {}).get('regime_min_score', -5.0))
        self.enable_hard_stop_loss = bool(self.config.get('risk_management', {}).get('enable_hard_stop_loss', True))
        self.hard_stop_loss_percent = float(self.config.get('risk_management', {}).get('hard_stop_loss_percent', 4.0))
        self.enable_mtf_regime_scoring = bool(self.config.get('risk_management', {}).get('enable_mtf_regime_scoring', True))
        self.mtf_regime_min_score = float(self.config.get('risk_management', {}).get('mtf_regime_min_score', -2.0))
        self.enable_time_stop = bool(self.config.get('risk_management', {}).get('enable_time_stop', True))
        self.time_stop_hours = int(self.config.get('risk_management', {}).get('time_stop_hours', 72))
        self.daily_drawdown_percent = float(self.config.get('risk_management', {}).get('daily_loss_limit_percent', 3.0))
        self.risk_off_allocation_multiplier = float(self.config.get('risk_management', {}).get('risk_off_allocation_multiplier', 0.35))
        self.enable_volatility_targeting = bool(self.config.get('risk_management', {}).get('enable_volatility_targeting', True))
        self.target_volatility_pct = float(self.config.get('risk_management', {}).get('target_volatility_pct', 1.6))
        self.max_consecutive_losses = int(self.config.get('risk_management', {}).get('max_consecutive_losses', 3))
        self.pause_after_loss_streak_minutes = int(self.config.get('risk_management', {}).get('pause_after_loss_streak_minutes', 180))
        self.enable_live_shorts = bool(self.config.get('shorting', {}).get('enabled', False))
        self.short_leverage = str(self.config.get('shorting', {}).get('leverage', '2'))
        self.max_short_notional_eur = float(self.config.get('shorting', {}).get('max_short_notional_eur', 50.0))

        self.start_time = datetime.now()
        self.last_config_reload = datetime.now()
        self.config_reload_interval = 300
        self.daily_start_balance = None
        self.initial_balance_eur = None
        self.start_timestamp = int(time.time())
        self.net_deposits_eur = 0.0
        self.net_withdrawals_eur = 0.0
        self._last_cashflow_refresh_ts = 0
        self.cashflow_refresh_interval_sec = int(self.config.get('reporting', {}).get('cashflow_refresh_seconds', 600))

        self.valid_pairs = self._fetch_valid_trade_pairs(self.trade_pairs)
        self.trade_pairs = self.valid_pairs if self.valid_pairs else []
        self._init_pair_state(self.trade_pairs)

    def _init_pair_state(self, pairs):
        for pair in pairs:
            self.pair_signals.setdefault(pair, "HOLD")
            self.holdings.setdefault(pair, 0.0)
            self.purchase_prices.setdefault(pair, 0.0)
            self.peak_prices.setdefault(pair, 0.0)
            self.position_qty.setdefault(pair, 0.0)
            self.short_qty.setdefault(pair, 0.0)
            self.short_entry_prices.setdefault(pair, 0.0)
            self.realized_pnl.setdefault(pair, 0.0)
            self.fees_paid.setdefault(pair, 0.0)
            self.trade_metrics.setdefault(pair, {"closed": 0, "wins": 0, "losses": 0, "sum_pnl": 0.0})
            self.last_trade_at.setdefault(pair, 0)
            self.entry_timestamps.setdefault(pair, None)

    def _get_target_balance(self):
        try:
            return self.config['bot_settings']['trade_amounts'].get('target_balance_eur', 1000.0)
        except Exception:
            return self.config['bot_settings'].get('target_balance_eur', 1000.0)

    def _get_take_profit_percent(self):
        try:
            return float(self.config['risk_management'].get('take_profit_percent', 5.0))
        except Exception:
            return 5.0

    def _get_stop_loss_percent(self):
        try:
            return float(self.config['risk_management'].get('stop_loss_percent', 2.0))
        except Exception:
            return 2.0

    def _get_trade_amount_eur(self):
        try:
            return float(self.config['bot_settings']['trade_amounts'].get('trade_amount_eur', 30.0))
        except Exception:
            return 30.0

    def _get_dynamic_trade_amount_eur(self, available_eur):
        """Dynamic sizing: use smaller of configured amount and % of free EUR."""
        base_amount = self._get_trade_amount_eur()
        allocation_pct = float(self.config.get('risk_management', {}).get('allocation_per_trade_percent', 2.0))
        dynamic_amount = max(0.0, available_eur * (allocation_pct / 100.0)) * self._allocation_multiplier()
        return min(base_amount, dynamic_amount)

    def _get_min_volume(self, pair):
        try:
            min_volumes = self.config['bot_settings'].get('min_volumes', {})
            if pair in min_volumes:
                return float(min_volumes.get(pair, 0.0001))

            # alias fallback (altname <-> wsname style)
            aliases = {
                'XBTEUR': 'XXBTZEUR',
                'ETHEUR': 'XETHZEUR',
                'XRPEUR': 'XXRPZEUR',
                'XXBTZEUR': 'XBTEUR',
                'XETHZEUR': 'ETHEUR',
                'XXRPZEUR': 'XRPEUR',
            }
            alt = aliases.get(pair)
            if alt and alt in min_volumes:
                return float(min_volumes.get(alt, 0.0001))

            return 0.0001
        except Exception:
            return 0.0001

    def _calculate_volume(self, pair, price, available_eur=None):
        trade_amount_eur = self._get_trade_amount_eur()
        if available_eur is not None:
            trade_amount_eur = min(trade_amount_eur, max(0.0, available_eur))
        min_volume = self._get_min_volume(pair)
        if price <= 0:
            return 0.0
        calculated_volume = trade_amount_eur / price
        return max(calculated_volume, min_volume)

    def _fetch_valid_trade_pairs(self, requested_pairs):
        assets = self.api_client.get_asset_pairs()
        if not assets:
            self.logger.warning("Could not fetch AssetPairs; using configured pairs unchanged")
            return requested_pairs

        valid_requested = []
        seen = set()

        # Build flexible normalization index (ALTNAME, WSNAME, and slashless variants)
        pair_index = {}
        for key, meta in assets.items():
            alt = (meta.get('altname') or key or '').upper()
            ws = (meta.get('wsname') or '').upper()
            ws_noslash = ws.replace('/', '')
            key_u = (key or '').upper()
            for alias in [alt, ws, ws_noslash, key_u, alt.replace('/', '')]:
                if alias:
                    pair_index[alias] = alt

        for raw_pair in requested_pairs:
            pair = (raw_pair or '').upper()
            normalized = pair_index.get(pair) or pair_index.get(pair.replace('/', ''))
            if normalized:
                if normalized not in seen:
                    valid_requested.append(normalized)
                    seen.add(normalized)
                if pair != normalized:
                    normalization_key = f"{pair}->{normalized}"
                    if normalization_key not in self._normalized_pair_logs_seen:
                        self.logger.info(f"Pair normalized: {pair} -> {normalized}")
                        self._normalized_pair_logs_seen.add(normalization_key)
            else:
                self.logger.warning(f"Skipping unknown Kraken pair: {raw_pair}")

        if not valid_requested:
            self.logger.error("No valid trading pairs after Kraken validation")
        else:
            self.logger.info(f"Validated trading pairs: {valid_requested}")
        return valid_requested

    def reload_config(self):
        try:
            new_config = load_config(self.config_path)
            if not new_config:
                return False

            old_pairs = self.trade_pairs
            self.config = new_config
            requested = self.config['bot_settings'].get('trade_pairs', ['XBTEUR'])
            self.trade_pairs = self._fetch_valid_trade_pairs(requested)
            self._init_pair_state(self.trade_pairs)

            self.target_balance_eur = self._get_target_balance()
            self.take_profit_percent = self._get_take_profit_percent()
            self.stop_loss_percent = self._get_stop_loss_percent()
            self.max_open_positions = int(self.config.get('risk_management', {}).get('max_open_positions', self.max_open_positions))
            self.trade_cooldown_sec = int(self.config.get('risk_management', {}).get('trade_cooldown_seconds', self.trade_cooldown_sec))
            self.global_trade_cooldown_sec = int(self.config.get('risk_management', {}).get('global_trade_cooldown_seconds', self.global_trade_cooldown_sec))
            self.trailing_stop_percent = float(self.config.get('risk_management', {}).get('trailing_stop_percent', self.trailing_stop_percent))
            self.empty_sell_log_cooldown_sec = int(self.config.get('risk_management', {}).get('empty_sell_log_cooldown_seconds', self.empty_sell_log_cooldown_sec))
            self.enable_regime_filter = bool(self.config.get('risk_management', {}).get('enable_regime_filter', self.enable_regime_filter))
            self.regime_benchmark_pair = str(self.config.get('risk_management', {}).get('regime_benchmark_pair', self.regime_benchmark_pair)).upper()
            self.regime_min_score = float(self.config.get('risk_management', {}).get('regime_min_score', self.regime_min_score))
            self.enable_hard_stop_loss = bool(self.config.get('risk_management', {}).get('enable_hard_stop_loss', self.enable_hard_stop_loss))
            self.hard_stop_loss_percent = float(self.config.get('risk_management', {}).get('hard_stop_loss_percent', self.hard_stop_loss_percent))
            self.enable_mtf_regime_scoring = bool(self.config.get('risk_management', {}).get('enable_mtf_regime_scoring', self.enable_mtf_regime_scoring))
            self.mtf_regime_min_score = float(self.config.get('risk_management', {}).get('mtf_regime_min_score', self.mtf_regime_min_score))
            self.enable_time_stop = bool(self.config.get('risk_management', {}).get('enable_time_stop', self.enable_time_stop))
            self.time_stop_hours = int(self.config.get('risk_management', {}).get('time_stop_hours', self.time_stop_hours))
            self.daily_drawdown_percent = float(self.config.get('risk_management', {}).get('daily_loss_limit_percent', self.daily_drawdown_percent))
            self.risk_off_allocation_multiplier = float(self.config.get('risk_management', {}).get('risk_off_allocation_multiplier', self.risk_off_allocation_multiplier))
            self.enable_volatility_targeting = bool(self.config.get('risk_management', {}).get('enable_volatility_targeting', self.enable_volatility_targeting))
            self.target_volatility_pct = float(self.config.get('risk_management', {}).get('target_volatility_pct', self.target_volatility_pct))
            self.max_consecutive_losses = int(self.config.get('risk_management', {}).get('max_consecutive_losses', self.max_consecutive_losses))
            self.pause_after_loss_streak_minutes = int(self.config.get('risk_management', {}).get('pause_after_loss_streak_minutes', self.pause_after_loss_streak_minutes))

            if set(old_pairs) != set(self.trade_pairs):
                self.logger.info(f"CONFIG RELOAD: trade_pairs changed {old_pairs} -> {self.trade_pairs}")
                print(f"\n[CONFIG] Trade pairs updated: {self.trade_pairs}")

            self.last_config_reload = datetime.now()
            return True
        except Exception as e:
            self.logger.error(f"Error reloading config: {e}")
            return False

    def get_eur_balance(self):
        try:
            balance = self.api_client.get_account_balance()
            if balance:
                return float(balance.get('ZEUR', 0))
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting EUR balance: {e}")
            return 0.0

    def get_crypto_holdings(self):
        try:
            balance = self.api_client.get_account_balance()
            if not balance:
                return

            pair_to_balance = {
                'XBTEUR': 'XXBT', 'XXBTZEUR': 'XXBT',
                'ETHEUR': 'XETH', 'XETHZEUR': 'XETH',
                'SOLEUR': 'SOL',
                'ADAEUR': 'ADA',
                'DOTEUR': 'DOT',
                'XRPEUR': 'XXRP', 'XXRPZEUR': 'XXRP',
                'LINKEUR': 'LINK',
                'MATICEUR': 'MATIC',
                'POLEUR': 'POL'
            }
            for pair in self.trade_pairs:
                key = pair_to_balance.get(pair)
                if not key:
                    continue
                self.holdings[pair] = float(balance.get(key, 0))
        except Exception as e:
            self.logger.error(f"Error getting holdings: {e}")

    def _sync_account_state(self):
        self.get_crypto_holdings()
        self.load_purchase_prices_from_history()

    def load_purchase_prices_from_history(self):
        """Rebuild per-pair average entry price + realized PnL from Kraken trade history.

        Logic:
        - BUY increases position size and weighted average entry (including fees)
        - SELL reduces position and realizes PnL (net of fees)
        """
        try:
            year_start_ts = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
            trades = self.api_client.get_trade_history(start=year_start_ts, fetch_all=True)
            if not trades:
                return

            watched = set(self.trade_pairs)
            pair_aliases = {
                'XXBTZEUR': 'XBTEUR', 'XBTEUR': 'XBTEUR',
                'XETHZEUR': 'ETHEUR', 'ETHEUR': 'ETHEUR',
                'SOLEUR': 'SOLEUR',
                'ADAEUR': 'ADAEUR',
                'DOTEUR': 'DOTEUR',
                'XXRPZEUR': 'XRPEUR', 'XRPEUR': 'XRPEUR',
                'LINKEUR': 'LINKEUR',
                'MATICEUR': 'MATICEUR',
                'POLEUR': 'POLEUR'
            }

            # Reset state before replay
            for pair in watched:
                self.position_qty[pair] = 0.0
                self.purchase_prices[pair] = 0.0
                self.realized_pnl[pair] = 0.0
                self.fees_paid[pair] = 0.0

            sorted_trades = sorted(trades.values(), key=lambda t: float(t.get('time', 0)))
            history_trade_count = 0

            for trade in sorted_trades:
                raw_pair = trade.get('pair', '')
                pair = pair_aliases.get(raw_pair, raw_pair)
                if pair not in watched:
                    continue

                ttype = trade.get('type', '').lower()
                vol = float(trade.get('vol', 0) or 0)
                cost = float(trade.get('cost', 0) or 0)  # quote currency (EUR)
                fee = float(trade.get('fee', 0) or 0)
                if vol <= 0:
                    continue

                self.fees_paid[pair] += fee
                qty = self.position_qty.get(pair, 0.0)
                avg = self.purchase_prices.get(pair, 0.0)

                if ttype == 'buy':
                    history_trade_count += 1
                    total_cost = cost + fee
                    new_qty = qty + vol
                    if new_qty > 0:
                        new_avg = ((avg * qty) + total_cost) / new_qty
                    else:
                        new_avg = 0.0
                    self.position_qty[pair] = new_qty
                    self.purchase_prices[pair] = new_avg
                    self.peak_prices[pair] = max(self.peak_prices.get(pair, 0.0), new_avg)

                elif ttype == 'sell':
                    history_trade_count += 1
                    sell_qty = min(qty, vol)
                    proceeds_net = cost - fee
                    if sell_qty > 0 and avg > 0:
                        cost_basis = avg * sell_qty
                        self.realized_pnl[pair] += (proceeds_net - cost_basis)
                    remaining_qty = max(0.0, qty - sell_qty)
                    self.position_qty[pair] = remaining_qty
                    if remaining_qty <= self._get_min_volume(pair):
                        self.purchase_prices[pair] = 0.0
                        self.peak_prices[pair] = 0.0

            # Keep displayed trade counter consistent across restarts (history + new trades)
            if history_trade_count > 0:
                self.trade_count = history_trade_count

            # Reconcile with live holdings from balance (source of truth for quantity)
            for pair in watched:
                live_qty = self.holdings.get(pair, 0.0)
                self.position_qty[pair] = live_qty
                if live_qty <= self._get_min_volume(pair):
                    self.purchase_prices[pair] = 0.0
                    self.peak_prices[pair] = 0.0
                    self.entry_timestamps[pair] = None
                elif self.entry_timestamps.get(pair) is None:
                    self.entry_timestamps[pair] = int(time.time())

        except Exception as e:
            self.logger.error(f"Error loading last purchase prices: {e}")

    def _resolve_benchmark_history(self):
        bench = self.regime_benchmark_pair
        aliases = [bench, bench.replace('/', '')]
        if bench == 'XBTEUR':
            aliases += ['XXBTZEUR']
        if bench == 'ETHEUR':
            aliases += ['XETHZEUR']
        for key in aliases:
            history = self.analysis_tool.pair_price_history.get(key)
            if history:
                return list(history)
        return []

    def _compute_mtf_regime_score(self):
        prices = self._resolve_benchmark_history()
        if len(prices) < 80:
            return None

        def _safe_rsi(window):
            val = self.analysis_tool.calculate_rsi(window)
            return 50.0 if val is None else float(val)

        rsi_fast = _safe_rsi(prices[-25:])
        rsi_mid = _safe_rsi(prices[-35:])
        rsi_slow = _safe_rsi(prices[-80:])

        sma10 = sum(prices[-10:]) / 10.0
        sma30 = sum(prices[-30:]) / 30.0
        sma70 = sum(prices[-70:]) / 70.0

        trend = (((sma10 - sma30) / sma30) * 100.0) * 0.9 + (((sma30 - sma70) / sma70) * 100.0) * 1.2
        momentum = ((rsi_fast - 50.0) * 0.4) + ((rsi_mid - 50.0) * 0.35) + ((rsi_slow - 50.0) * 0.25)

        recent = prices[-24:]
        mean = sum(recent) / len(recent)
        vol_pct = 0.0
        if mean > 0:
            variance = sum((p - mean) ** 2 for p in recent) / len(recent)
            vol_pct = ((variance ** 0.5) / mean) * 100.0
        vol_penalty = max(0.0, vol_pct - 2.2) * 1.5

        return trend + momentum - vol_penalty

    def _is_risk_on_regime(self):
        if not self.enable_regime_filter:
            return True

        if self.enable_mtf_regime_scoring:
            mtf_score = self._compute_mtf_regime_score()
            if mtf_score is not None:
                return mtf_score >= self.mtf_regime_min_score

        benchmark = self.regime_benchmark_pair
        score = float(self.pair_scores.get(benchmark, 0.0))
        return score >= self.regime_min_score

    def _benchmark_volatility_pct(self):
        bench = self.regime_benchmark_pair
        aliases = [bench, bench.replace('/', '')]
        # analysis stores histories by raw Kraken key seen in ticker payload
        if bench == 'XBTEUR':
            aliases += ['XXBTZEUR']
        if bench == 'ETHEUR':
            aliases += ['XETHZEUR']

        try:
            history = None
            for key in aliases:
                history = self.analysis_tool.pair_price_history.get(key)
                if history and len(history) >= 20:
                    break
            if not history or len(history) < 20:
                return 0.0
            prices = list(history)[-20:]
            mean = sum(prices) / len(prices)
            if mean <= 0:
                return 0.0
            variance = sum((p - mean) ** 2 for p in prices) / len(prices)
            return ((variance ** 0.5) / mean) * 100.0
        except Exception:
            return 0.0

    def _allocation_multiplier(self):
        base = 1.0 if self._is_risk_on_regime() else self.risk_off_allocation_multiplier
        if not self.enable_volatility_targeting:
            return base
        vol = self._benchmark_volatility_pct()
        if vol <= 0:
            return base
        # Higher volatility -> smaller size, lower volatility -> allow base size
        vol_scale = min(1.25, max(0.35, self.target_volatility_pct / vol))
        return max(0.2, min(1.25, base * vol_scale))

    def _is_temporarily_paused(self):
        return time.time() < self.trading_paused_until_ts

    def _available_eur_for_buy(self):
        # keep a small reserve for fees/slippage
        return max(0.0, self.get_eur_balance() * 0.98)

    def _daily_drawdown_hit(self):
        current = self.get_eur_balance()
        if self.daily_start_balance is None:
            self.daily_start_balance = current
            return False
        if self.daily_start_balance <= 0:
            return False
        dd = ((self.daily_start_balance - current) / self.daily_start_balance) * 100
        if dd >= self.daily_drawdown_percent:
            self.logger.warning(f"Daily drawdown limit reached: {dd:.2f}% >= {self.daily_drawdown_percent:.2f}%")
            return True
        return False

    def _refresh_cashflows_from_ledger(self, force=False):
        now_ts = int(time.time())
        if not force and (now_ts - self._last_cashflow_refresh_ts) < self.cashflow_refresh_interval_sec:
            return

        try:
            ledgers = self.api_client.get_ledgers(asset='ZEUR', start=self.start_timestamp, fetch_all=True)
            if not ledgers:
                self._last_cashflow_refresh_ts = now_ts
                return

            deposits = 0.0
            withdrawals = 0.0
            for entry in ledgers.values():
                ltype = str(entry.get('type', '')).lower()
                try:
                    amount = abs(float(entry.get('amount', 0) or 0))
                except Exception:
                    amount = 0.0

                if amount <= 0:
                    continue

                if ltype == 'deposit':
                    deposits += amount
                elif ltype == 'withdrawal':
                    withdrawals += amount

            self.net_deposits_eur = deposits
            self.net_withdrawals_eur = withdrawals
            self._last_cashflow_refresh_ts = now_ts
        except Exception as e:
            self.logger.error(f"Error refreshing cashflows from ledger: {e}")

    def _adjusted_reference_balance(self):
        base = self.initial_balance_eur if self.initial_balance_eur is not None else (self.daily_start_balance or 0.0)
        return base + self.net_deposits_eur - self.net_withdrawals_eur

    def _adjusted_pnl_eur(self, current_balance):
        return current_balance - self._adjusted_reference_balance()

    def _count_open_positions(self):
        count = 0
        for pair in self.trade_pairs:
            if self.holdings.get(pair, 0) >= self._get_min_volume(pair):
                count += 1
        return count

    def _is_on_cooldown(self, pair):
        return (time.time() - self.last_trade_at.get(pair, 0)) < self.trade_cooldown_sec

    def _is_global_cooldown(self):
        return (time.time() - self.last_global_trade_at) < self.global_trade_cooldown_sec

    def _log_empty_sell_signal_throttled(self, pair):
        now_ts = time.time()
        last_ts = self._last_empty_sell_log_at.get(pair, 0)
        if (now_ts - last_ts) >= self.empty_sell_log_cooldown_sec:
            self.logger.info(f"SELL signal for {pair} but no holdings")
            self._last_empty_sell_log_at[pair] = now_ts

    def _profit_percent_from_entry(self, pair, current_price):
        entry = self.purchase_prices.get(pair, 0.0)
        if entry <= 0 or current_price <= 0:
            return None
        return ((current_price - entry) / entry) * 100.0

    def _required_take_profit_percent(self, pair):
        """Adaptive TP: in stronger momentum, demand a bit more profit before selling."""
        base_tp = self.take_profit_percent
        if not self.adaptive_tp_enabled:
            return base_tp

        score = abs(float(self.pair_scores.get(pair, 0.0)))
        # Map score band [20..50] -> +0..+4%
        bonus = 0.0
        if score > 20:
            bonus = min(4.0, (score - 20.0) / 30.0 * 4.0)

        return min(self.max_tp_percent, base_tp + bonus)

    def _can_sell_profit_target(self, pair, current_price):
        """Only allow sell when current price is at/above configured take-profit threshold from entry."""
        profit_pct = self._profit_percent_from_entry(pair, current_price)
        if profit_pct is None:
            return False
        return profit_pct >= self._required_take_profit_percent(pair)

    def _update_trade_metrics(self, pair, pnl_eur):
        m = self.trade_metrics.setdefault(pair, {"closed": 0, "wins": 0, "losses": 0, "sum_pnl": 0.0})
        m["closed"] += 1
        m["sum_pnl"] += pnl_eur
        if pnl_eur >= 0:
            m["wins"] += 1
            self.consecutive_losses = 0
        else:
            m["losses"] += 1
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                pause_sec = self.pause_after_loss_streak_minutes * 60
                self.trading_paused_until_ts = max(self.trading_paused_until_ts, int(time.time()) + pause_sec)
                self.logger.warning(
                    f"Loss-streak pause activated: {self.consecutive_losses} losses -> pause for {self.pause_after_loss_streak_minutes}m"
                )

    def check_take_profit_or_stop_loss(self):
        """Evaluate exits with TP first, then hard stop, then time stop."""
        for pair in self.trade_pairs:
            current_price = self.pair_prices.get(pair, 0)
            if current_price <= 0:
                continue

            # Long position exits
            holding = self.holdings.get(pair, 0)
            min_vol = self._get_min_volume(pair)
            if holding >= min_vol:
                prev_peak = self.peak_prices.get(pair, 0.0)
                self.peak_prices[pair] = max(prev_peak, current_price)

                change_percent = self._profit_percent_from_entry(pair, current_price)
                if change_percent is not None:
                    req_tp = self._required_take_profit_percent(pair)
                    if self.take_profit_percent > 0 and change_percent >= req_tp:
                        return pair, "TAKE_PROFIT", change_percent

                    if self.enable_hard_stop_loss and change_percent <= -abs(self.hard_stop_loss_percent):
                        return pair, "HARD_STOP", change_percent

                    if self.enable_time_stop:
                        opened_at = self.entry_timestamps.get(pair)
                        if opened_at and (time.time() - opened_at) >= (self.time_stop_hours * 3600):
                            return pair, "TIME_STOP", change_percent

            # Short position exits
            short_qty = self.short_qty.get(pair, 0.0)
            short_entry = self.short_entry_prices.get(pair, 0.0)
            if self.enable_live_shorts and short_qty > 0 and short_entry > 0:
                short_change_percent = ((short_entry - current_price) / short_entry) * 100.0
                req_tp = self._required_take_profit_percent(pair)
                if self.take_profit_percent > 0 and short_change_percent >= req_tp:
                    return pair, "SHORT_TAKE_PROFIT", short_change_percent
                if self.enable_hard_stop_loss and short_change_percent <= -abs(self.hard_stop_loss_percent):
                    return pair, "SHORT_HARD_STOP", short_change_percent
                if self.enable_time_stop:
                    opened_at = self.entry_timestamps.get(pair)
                    if opened_at and (time.time() - opened_at) >= (self.time_stop_hours * 3600):
                        return pair, "SHORT_TIME_STOP", short_change_percent

        return None, None, None

    def analyze_all_pairs(self):
        best_pair = None
        best_signal = "HOLD"
        best_score = 0

        for pair in self.trade_pairs:
            try:
                market_data = self.api_client.get_market_data(pair)
                if not market_data:
                    continue

                pair_key = list(market_data.keys())[0]
                current_price = float(market_data[pair_key]['c'][0])
                self.pair_prices[pair] = current_price

                signal, score = self.analysis_tool.generate_signal_with_score(market_data)
                self.pair_signals[pair] = signal
                self.pair_scores[pair] = score

                if signal in ["BUY", "SELL"] and abs(score) > abs(best_score):
                    best_pair = pair
                    best_signal = signal
                    best_score = score

                time.sleep(0.25)
            except Exception as e:
                self.logger.error(f"Error analyzing {pair}: {e}")

        return best_pair, best_signal, best_score

    def start_trading(self):
        self.logger.info("=" * 60)
        self.logger.info("TRADING BOT STARTED - MULTI-PAIR MODE")
        self.logger.info(f"Watching: {', '.join(self.trade_pairs)}")
        self.logger.info(f"Target: {self.target_balance_eur} EUR")
        self.logger.info("=" * 60)

        print("=" * 60)
        print("KRAKEN TRADING BOT - MULTI-PAIR MODE")
        print(f"Watching {len(self.trade_pairs)} pairs: {', '.join(self.trade_pairs)}")
        print(f"Trade Amount: {self._get_trade_amount_eur()} EUR per trade")
        print(f"Target Balance: {self.target_balance_eur} EUR")
        print("Press Ctrl+C to stop")
        print("=" * 60)

        initial_balance = self.get_eur_balance()
        self.initial_balance_eur = initial_balance
        self.daily_start_balance = initial_balance
        self._sync_account_state()
        self._refresh_cashflows_from_ledger(force=True)

        self.logger.info(f"Initial EUR Balance: {initial_balance:.2f} EUR")
        self.logger.info("Performance baseline is fixed at startup; deposits/withdrawals are tracked separately")
        self.logger.info(f"Take-Profit: {self.take_profit_percent}% | Stop-Loss: {self.stop_loss_percent}%")

        try:
            iteration = 0
            while True:
                iteration += 1

                current_balance = self.get_eur_balance()
                if current_balance >= self.target_balance_eur:
                    self.logger.info(f"TARGET REACHED! Balance: {current_balance:.2f} EUR")
                    print(f"\nTARGET REACHED! Balance: {current_balance:.2f} EUR")
                    break

                best_pair, best_signal, best_score = self.analyze_all_pairs()
                self._sync_account_state()

                # Take profit / stop loss first
                risk_pair, risk_type, change = self.check_take_profit_or_stop_loss()
                if risk_pair:
                    price = self.pair_prices.get(risk_pair, 0)
                    print(f"\n[{risk_type}] {risk_pair} at {change:.2f}%")
                    if str(risk_type).startswith("SHORT_"):
                        self.execute_close_short_order(risk_pair, price)
                    else:
                        self.execute_sell_order(risk_pair, price)

                self._refresh_cashflows_from_ledger()
                adjusted_pnl = self._adjusted_pnl_eur(current_balance)
                regime_state = "RISK_ON" if self._is_risk_on_regime() else "RISK_OFF"
                pause_state = "PAUSED" if self._is_temporarily_paused() else "ACTIVE"

                label_map = {
                    "XBTEUR": "BTC", "XXBTZEUR": "BTC",
                    "ETHEUR": "ETH", "XETHZEUR": "ETH",
                    "SOLEUR": "SOL",
                    "ADAEUR": "ADA",
                    "DOTEUR": "DOT",
                    "XRPEUR": "XRP", "XXRPZEUR": "XRP",
                    "LINKEUR": "LINK",
                }
                pair_status = " ".join([
                    f"{label_map.get(p, p[:4])}:{self.pair_signals.get(p, '?')}" for p in self.trade_pairs
                ])
                status_msg = (
                    f"[{iteration}] {pair_status} | {regime_state}/{pause_state} | Best: {best_pair or 'NONE'} ({best_signal}) "
                    f"| Bal: {current_balance:.2f}EUR | Start: {self.initial_balance_eur:.2f}EUR "
                    f"| NetCF: +{self.net_deposits_eur:.2f}/-{self.net_withdrawals_eur:.2f}EUR "
                    f"| AdjPnL: {adjusted_pnl:+.2f}EUR | Trades: {self.trade_count}"
                )
                self.logger.info(status_msg)
                print(f"\r{status_msg}", end="", flush=True)

                if iteration % 10 == 0:
                    metric_parts = []
                    for p in self.trade_pairs:
                        m = self.trade_metrics.get(p, {})
                        closed = int(m.get("closed", 0))
                        if closed <= 0:
                            continue
                        winrate = (m.get("wins", 0) / closed) * 100.0
                        avg_pnl = m.get("sum_pnl", 0.0) / closed
                        metric_parts.append(f"{p}: WR {winrate:.0f}% avg {avg_pnl:.2f}EUR")
                    if metric_parts:
                        self.logger.info("METRICS | " + " | ".join(metric_parts))

                if best_pair and best_signal != "HOLD" and not self._is_on_cooldown(best_pair) and not self._is_global_cooldown():
                    price = self.pair_prices.get(best_pair, 0)
                    if best_signal == "BUY":
                        score = float(self.pair_scores.get(best_pair, 0.0))
                        if self._is_temporarily_paused():
                            self.logger.warning("BUY paused: loss-streak cooling period active")
                        elif self._daily_drawdown_hit():
                            self.logger.warning("BUY paused: daily loss limit reached")
                        elif self.enable_regime_filter and not self._is_risk_on_regime():
                            self.logger.info("BUY skipped: regime filter is RISK_OFF")
                        elif score < self.min_buy_score:
                            self.logger.info(f"BUY skipped for {best_pair}: weak score {score:.2f} < min {self.min_buy_score:.2f}")
                        elif self._count_open_positions() >= self.max_open_positions:
                            self.logger.info("BUY skipped: max open positions reached")
                        else:
                            self.execute_buy_order(best_pair, price)
                    elif best_signal == "SELL":
                        min_vol = self._get_min_volume(best_pair)
                        if self.holdings.get(best_pair, 0) >= min_vol:
                            if self._can_sell_profit_target(best_pair, price):
                                self.execute_sell_order(best_pair, price)
                            else:
                                pp = self._profit_percent_from_entry(best_pair, price)
                                req = self._required_take_profit_percent(best_pair)
                                self.logger.info(
                                    f"SELL skipped for {best_pair}: profit target not reached ({pp if pp is not None else 'n/a'}% < {req:.2f}%)"
                                )
                        elif self.enable_live_shorts and self.short_qty.get(best_pair, 0.0) <= 0:
                            # Open short mostly in risk-off environments or very strong negative score
                            score = float(self.pair_scores.get(best_pair, 0.0))
                            if (not self._is_risk_on_regime()) or score <= -self.min_buy_score:
                                self.execute_open_short_order(best_pair, price)
                            else:
                                self.logger.info("SHORT skipped: regime not risk-off and sell score not strong enough")
                        elif self.enable_live_shorts and self.short_qty.get(best_pair, 0.0) > 0:
                            # If already short, consider close on reversal buy impulse
                            score = float(self.pair_scores.get(best_pair, 0.0))
                            if score >= self.min_buy_score:
                                self.execute_close_short_order(best_pair, price)
                        else:
                            self._log_empty_sell_signal_throttled(best_pair)

                time_since_reload = (datetime.now() - self.last_config_reload).total_seconds()
                if time_since_reload >= self.config_reload_interval:
                    self.reload_config()

                time.sleep(60)

        except KeyboardInterrupt:
            final_balance = self.get_eur_balance()
            self.logger.info(f"Bot stopped by user. Final balance: {final_balance:.2f} EUR")
            print(f"\nTrading bot stopped. Final Balance: {final_balance:.2f} EUR")

    def execute_buy_order(self, pair, price):
        try:
            available_eur = self._available_eur_for_buy()
            min_trade_eur = float(self.config.get('risk_management', {}).get('min_trade_eur', 10.0))
            planned_eur = self._get_dynamic_trade_amount_eur(available_eur)
            if planned_eur < min_trade_eur:
                self.logger.info(f"BUY skipped for {pair}: insufficient free EUR ({available_eur:.2f})")
                return

            volume = self._calculate_volume(pair, price, available_eur=planned_eur)
            self.logger.info(f"Placing BUY order: {volume:.6f} {pair} at ~{price:.2f} EUR")

            result = self.api_client.place_order(pair=pair, direction='buy', volume=volume)
            if result:
                self.trade_count += 1
                now_ts = time.time()
                self.last_trade_at[pair] = now_ts
                self.last_global_trade_at = now_ts
                self.peak_prices[pair] = max(self.peak_prices.get(pair, 0.0), price)
                if self.entry_timestamps.get(pair) is None:
                    self.entry_timestamps[pair] = int(time.time())
                self._sync_account_state()
                self.logger.info(f"BUY ORDER SUCCESS: {result}")
                self.logger.info(f"BUY SUMMARY: {pair} {volume:.6f} (~{volume*price:.2f} EUR)")
                print(f"\n[BUY] {volume:.6f} {pair} (~{volume*price:.2f} EUR) - Trade #{self.trade_count}")
            else:
                self.logger.error(f"BUY ORDER FAILED for {pair}")
        except Exception as e:
            self.logger.error(f"Error executing buy order: {e}", exc_info=True)

    def execute_sell_order(self, pair, price, require_profit_target=True):
        try:
            volume = self.holdings.get(pair, 0)
            if volume < self._get_min_volume(pair):
                self.logger.info(f"SELL skipped for {pair}: no holdings")
                return

            if require_profit_target and not self._can_sell_profit_target(pair, price):
                pp = self._profit_percent_from_entry(pair, price)
                self.logger.info(
                    f"SELL blocked for {pair}: target {self.take_profit_percent:.2f}% not reached ({pp if pp is not None else 'n/a'}%)"
                )
                return

            avg_entry = self.purchase_prices.get(pair, 0.0)
            est_profit_pct = self._profit_percent_from_entry(pair, price)
            est_profit_eur = (price - avg_entry) * volume if avg_entry > 0 else 0.0

            self.logger.info(f"Placing SELL order: {volume:.6f} {pair} at ~{price:.2f} EUR")
            result = self.api_client.place_order(pair=pair, direction='sell', volume=volume)
            if result:
                self.trade_count += 1
                now_ts = time.time()
                self.last_trade_at[pair] = now_ts
                self.last_global_trade_at = now_ts
                self.purchase_prices[pair] = 0.0
                self.peak_prices[pair] = 0.0
                self.entry_timestamps[pair] = None
                self._sync_account_state()
                self.logger.info(f"SELL ORDER SUCCESS: {result}")
                self.logger.info(f"SELL SUMMARY: {pair} {volume:.6f} (~{volume*price:.2f} EUR)")
                self.logger.info(
                    f"SELL PNL ESTIMATE {pair}: {est_profit_eur:.2f} EUR ({est_profit_pct if est_profit_pct is not None else 0:.2f}%)"
                )
                self._update_trade_metrics(pair, est_profit_eur)
                print(f"\n[SELL] {volume:.6f} {pair} (~{volume*price:.2f} EUR) - Trade #{self.trade_count}")
            else:
                self.logger.error(f"SELL ORDER FAILED for {pair}")
        except Exception as e:
            self.logger.error(f"Error executing sell order: {e}", exc_info=True)

    def execute_open_short_order(self, pair, price):
        try:
            if not self.enable_live_shorts:
                return
            if self.short_qty.get(pair, 0.0) > 0:
                return

            notional = min(self.max_short_notional_eur, self._get_dynamic_trade_amount_eur(self._available_eur_for_buy()))
            if notional <= 0 or price <= 0:
                return
            volume = max(self._get_min_volume(pair), notional / price)
            self.logger.info(
                f"Placing SHORT OPEN order: {volume:.6f} {pair} at ~{price:.2f} EUR (lev={self.short_leverage}x)"
            )
            result = self.api_client.place_order(pair=pair, direction='sell', volume=volume, leverage=self.short_leverage)
            if result:
                self.trade_count += 1
                now_ts = time.time()
                self.last_trade_at[pair] = now_ts
                self.last_global_trade_at = now_ts
                self.short_qty[pair] = volume
                self.short_entry_prices[pair] = price
                self.entry_timestamps[pair] = int(now_ts)
                self.logger.info(f"SHORT OPEN SUCCESS: {result}")
                self.logger.info(f"SHORT OPEN SUMMARY: {pair} {volume:.6f} (~{notional:.2f} EUR)")
                print(f"\n[SHORT OPEN] {volume:.6f} {pair} (~{notional:.2f} EUR) - Trade #{self.trade_count}")
            else:
                self.logger.error(f"SHORT OPEN FAILED for {pair}")
        except Exception as e:
            self.logger.error(f"Error opening short order: {e}", exc_info=True)

    def execute_close_short_order(self, pair, price):
        try:
            qty = self.short_qty.get(pair, 0.0)
            entry = self.short_entry_prices.get(pair, 0.0)
            if qty <= 0 or entry <= 0:
                return
            pnl_eur = (entry - price) * qty
            pnl_pct = ((entry - price) / entry) * 100.0
            self.logger.info(f"Placing SHORT CLOSE order: {qty:.6f} {pair} at ~{price:.2f} EUR")
            result = self.api_client.place_order(pair=pair, direction='buy', volume=qty, leverage=self.short_leverage)
            if result:
                self.trade_count += 1
                now_ts = time.time()
                self.last_trade_at[pair] = now_ts
                self.last_global_trade_at = now_ts
                self.short_qty[pair] = 0.0
                self.short_entry_prices[pair] = 0.0
                self.entry_timestamps[pair] = None
                self.logger.info(f"SHORT CLOSE SUCCESS: {result}")
                self.logger.info(f"SHORT CLOSE SUMMARY: {pair} {qty:.6f} (~{qty*price:.2f} EUR)")
                self.logger.info(f"SHORT PNL ESTIMATE {pair}: {pnl_eur:.2f} EUR ({pnl_pct:.2f}%)")
                self._update_trade_metrics(pair, pnl_eur)
                print(f"\n[SHORT CLOSE] {qty:.6f} {pair} - Trade #{self.trade_count}")
            else:
                self.logger.error(f"SHORT CLOSE FAILED for {pair}")
        except Exception as e:
            self.logger.error(f"Error closing short order: {e}", exc_info=True)


class Backtester:
    def __init__(self, api_client, config):
        self.api_client = api_client
        self.config = config
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.info("Starting backtesting...")
        print("Backtesting mode activated.")
        print("Backtesting functionality is not yet implemented.")

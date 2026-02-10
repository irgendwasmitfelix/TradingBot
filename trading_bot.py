# Trading Bot Core Logic - Multi-Pair Analysis

import logging
import time
import os
from datetime import datetime
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
        self.last_trade_at = {}

        self.trade_count = 0
        self.target_balance_eur = self._get_target_balance()
        self.take_profit_percent = self._get_take_profit_percent()
        self.stop_loss_percent = self._get_stop_loss_percent()
        self.max_open_positions = int(self.config.get('risk_management', {}).get('max_open_positions', 3))
        self.trade_cooldown_sec = int(self.config.get('risk_management', {}).get('trade_cooldown_seconds', 180))
        self.daily_drawdown_percent = float(self.config.get('risk_management', {}).get('max_drawdown_percent', 5.0))

        self.start_time = datetime.now()
        self.last_config_reload = datetime.now()
        self.config_reload_interval = 300
        self.daily_start_balance = None

        self.valid_pairs = self._fetch_valid_trade_pairs(self.trade_pairs)
        self.trade_pairs = self.valid_pairs if self.valid_pairs else []
        self._init_pair_state(self.trade_pairs)

    def _init_pair_state(self, pairs):
        for pair in pairs:
            self.pair_signals.setdefault(pair, "HOLD")
            self.holdings.setdefault(pair, 0.0)
            self.purchase_prices.setdefault(pair, 0.0)
            self.last_trade_at.setdefault(pair, 0)

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

    def _get_min_volume(self, pair):
        try:
            return float(self.config['bot_settings']['min_volumes'].get(pair, 0.0001))
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
        asset_keys = set(assets.keys())
        wsname_to_altname = {v.get('wsname', ''): v.get('altname', '') for v in assets.values()}

        for pair in requested_pairs:
            if pair in asset_keys:
                valid_requested.append(pair)
                continue
            if pair in wsname_to_altname:
                valid_requested.append(wsname_to_altname[pair])
                self.logger.info(f"Pair normalized: {pair} -> {wsname_to_altname[pair]}")
                continue
            self.logger.warning(f"Skipping unknown Kraken pair: {pair}")

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
            self.daily_drawdown_percent = float(self.config.get('risk_management', {}).get('max_drawdown_percent', self.daily_drawdown_percent))

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
                'XBTEUR': 'XXBT',
                'ETHEUR': 'XETH',
                'SOLEUR': 'SOL',
                'ADAEUR': 'ADA',
                'DOTEUR': 'DOT',
                'XRPEUR': 'XXRP',
                'LINKEUR': 'LINK',
                # MATIC deprecated on Kraken in many setups; POL often used now
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
        try:
            trades = self.api_client.get_trade_history()
            if not trades:
                return

            kraken_pair_map = {
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

            last_buy_price = {}
            last_buy_time = {}
            for _, trade in trades.items():
                kraken_pair = trade.get('pair', '')
                our_pair = kraken_pair_map.get(kraken_pair, kraken_pair)
                if our_pair not in self.trade_pairs:
                    continue
                if trade.get('type', '') != 'buy':
                    continue
                price = float(trade.get('price', 0))
                time_exec = float(trade.get('time', 0))
                if our_pair not in last_buy_time or time_exec > last_buy_time[our_pair]:
                    last_buy_time[our_pair] = time_exec
                    last_buy_price[our_pair] = price

            for pair in self.trade_pairs:
                self.purchase_prices[pair] = float(last_buy_price.get(pair, self.purchase_prices.get(pair, 0.0)))
        except Exception as e:
            self.logger.error(f"Error loading last purchase prices: {e}")

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

    def _count_open_positions(self):
        count = 0
        for pair in self.trade_pairs:
            if self.holdings.get(pair, 0) >= self._get_min_volume(pair):
                count += 1
        return count

    def _is_on_cooldown(self, pair):
        return (time.time() - self.last_trade_at.get(pair, 0)) < self.trade_cooldown_sec

    def check_take_profit_or_stop_loss(self):
        if self.take_profit_percent <= 0 and self.stop_loss_percent <= 0:
            return None, None, None

        for pair in self.trade_pairs:
            holding = self.holdings.get(pair, 0)
            purchase_price = self.purchase_prices.get(pair, 0)
            current_price = self.pair_prices.get(pair, 0)
            min_vol = self._get_min_volume(pair)
            if holding < min_vol or purchase_price <= 0 or current_price <= 0:
                continue

            change_percent = ((current_price - purchase_price) / purchase_price) * 100
            if self.take_profit_percent > 0 and change_percent >= self.take_profit_percent:
                return pair, "TAKE_PROFIT", change_percent
            if self.stop_loss_percent > 0 and change_percent <= -self.stop_loss_percent:
                return pair, "STOP_LOSS", change_percent

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
        self.daily_start_balance = initial_balance
        self._sync_account_state()

        self.logger.info(f"Initial EUR Balance: {initial_balance:.2f} EUR")
        self.logger.info(f"Take-Profit: {self.take_profit_percent}% | Stop-Loss: {self.stop_loss_percent}%")

        try:
            iteration = 0
            while True:
                iteration += 1

                if self._daily_drawdown_hit():
                    print("\n[SAFETY] Daily drawdown limit hit. Pausing trading loop.")
                    time.sleep(300)
                    continue

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
                    self.execute_sell_order(risk_pair, price)

                pair_status = " | ".join([f"{p[:3]}:{self.pair_signals.get(p, '?')}" for p in self.trade_pairs[:4]])
                status_msg = f"[{iteration}] {pair_status} | Best: {best_pair or 'NONE'} ({best_signal}) | Bal: {current_balance:.2f}EUR | Trades: {self.trade_count}"
                self.logger.info(status_msg)
                print(f"\r{status_msg}", end="", flush=True)

                if best_pair and best_signal != "HOLD" and not self._is_on_cooldown(best_pair):
                    price = self.pair_prices.get(best_pair, 0)
                    if best_signal == "BUY":
                        if self._count_open_positions() >= self.max_open_positions:
                            self.logger.info("BUY skipped: max open positions reached")
                        else:
                            self.execute_buy_order(best_pair, price)
                    elif best_signal == "SELL":
                        min_vol = self._get_min_volume(best_pair)
                        if self.holdings.get(best_pair, 0) >= min_vol:
                            self.execute_sell_order(best_pair, price)
                        else:
                            self.logger.info(f"SELL signal for {best_pair} but no holdings")

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
            planned_eur = min(self._get_trade_amount_eur(), available_eur)
            if planned_eur < min_trade_eur:
                self.logger.info(f"BUY skipped for {pair}: insufficient free EUR ({available_eur:.2f})")
                return

            volume = self._calculate_volume(pair, price, available_eur=planned_eur)
            self.logger.info(f"Placing BUY order: {volume:.6f} {pair} at ~{price:.2f} EUR")

            result = self.api_client.place_order(pair=pair, direction='buy', volume=volume)
            if result:
                self.trade_count += 1
                self.last_trade_at[pair] = time.time()
                self._sync_account_state()
                self.logger.info(f"BUY ORDER SUCCESS: {result}")
                print(f"\n[BUY] {volume:.6f} {pair} (~{volume*price:.2f} EUR) - Trade #{self.trade_count}")
            else:
                self.logger.error(f"BUY ORDER FAILED for {pair}")
        except Exception as e:
            self.logger.error(f"Error executing buy order: {e}", exc_info=True)

    def execute_sell_order(self, pair, price):
        try:
            volume = self.holdings.get(pair, 0)
            if volume < self._get_min_volume(pair):
                self.logger.info(f"SELL skipped for {pair}: no holdings")
                return

            self.logger.info(f"Placing SELL order: {volume:.6f} {pair} at ~{price:.2f} EUR")
            result = self.api_client.place_order(pair=pair, direction='sell', volume=volume)
            if result:
                self.trade_count += 1
                self.last_trade_at[pair] = time.time()
                self.purchase_prices[pair] = 0.0
                self._sync_account_state()
                self.logger.info(f"SELL ORDER SUCCESS: {result}")
                print(f"\n[SELL] {volume:.6f} {pair} (~{volume*price:.2f} EUR) - Trade #{self.trade_count}")
            else:
                self.logger.error(f"SELL ORDER FAILED for {pair}")
        except Exception as e:
            self.logger.error(f"Error executing sell order: {e}", exc_info=True)


class Backtester:
    def __init__(self, api_client, config):
        self.api_client = api_client
        self.config = config
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.info("Starting backtesting...")
        print("Backtesting mode activated.")
        print("Backtesting functionality is not yet implemented.")

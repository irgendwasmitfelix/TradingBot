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
        
        # Standard analysis periods for reliable signals (RSI 14, SMA 20/50)
        self.analysis_tool = TechnicalAnalysis(rsi_period=14, sma_short=20, sma_long=50)
        
        # Multi-pair tracking
        self.trade_pairs = self.config['bot_settings'].get('trade_pairs', ['XBTEUR'])
        self.pair_signals = {}  # Current signal per pair
        self.pair_prices = {}   # Current price per pair
        self.pair_scores = {}   # Signal strength score per pair
        self.holdings = {}      # Track holdings per coin for selling
        self.purchase_prices = {}  # Track average purchase price per pair
        
        # Initialize signals
        for pair in self.trade_pairs:
            self.pair_signals[pair] = "HOLD"
            self.holdings[pair] = 0.0
            self.purchase_prices[pair] = 0.0
        
        self.trade_count = 0
        self.target_balance_eur = self._get_target_balance()
        self.take_profit_percent = self._get_take_profit_percent()
        self.start_time = datetime.now()
        self.last_config_reload = datetime.now()
        self.config_reload_interval = 300  # 5 minutes
        
    def _get_target_balance(self):
        """Get target balance from nested config structure."""
        try:
            return self.config['bot_settings']['trade_amounts'].get('target_balance_eur', 1000.0)
        except:
            return self.config['bot_settings'].get('target_balance_eur', 1000.0)

    def _get_take_profit_percent(self):
        """Get take profit percentage from config."""
        try:
            return self.config['risk_management'].get('take_profit_percent', 5.0)
        except:
            return 5.0

    def _get_trade_amount_eur(self):
        """Get trade amount in EUR."""
        try:
            return self.config['bot_settings']['trade_amounts'].get('trade_amount_eur', 30.0)
        except:
            return 30.0

    def _get_min_volume(self, pair):
        """Get minimum volume for a trading pair."""
        try:
            return self.config['bot_settings']['min_volumes'].get(pair, 0.0001)
        except:
            return 0.0001

    def _calculate_volume(self, pair, price):
        """Calculate trade volume based on EUR amount and current price."""
        trade_amount_eur = self._get_trade_amount_eur()
        min_volume = self._get_min_volume(pair)
        
        if price <= 0:
            return min_volume
            
        calculated_volume = trade_amount_eur / price
        return max(calculated_volume, min_volume)

    def reload_config(self):
        """Hot-reload config.toml without restarting the bot."""
        try:
            new_config = load_config(self.config_path)
            if new_config:
                old_pairs = self.trade_pairs
                old_target = self.target_balance_eur
                old_take_profit = self.take_profit_percent
                
                self.config = new_config
                self.trade_pairs = self.config['bot_settings'].get('trade_pairs', ['XBTEUR'])
                self.target_balance_eur = self._get_target_balance()
                self.take_profit_percent = self._get_take_profit_percent()
                
                # Initialize new pairs
                for pair in self.trade_pairs:
                    if pair not in self.pair_signals:
                        self.pair_signals[pair] = "HOLD"
                        self.holdings[pair] = 0.0
                        self.purchase_prices[pair] = 0.0
                
                # Log changes
                if set(old_pairs) != set(self.trade_pairs):
                    self.logger.info(f"CONFIG RELOAD: trade_pairs changed")
                    print(f"\n[CONFIG] Trade pairs updated: {self.trade_pairs}")
                if old_target != self.target_balance_eur:
                    self.logger.info(f"CONFIG RELOAD: target_balance changed {old_target} -> {self.target_balance_eur}")
                    print(f"\n[CONFIG] Target balance updated: {old_target} -> {self.target_balance_eur} EUR")
                if old_take_profit != self.take_profit_percent:
                    self.logger.info(f"CONFIG RELOAD: take_profit changed {old_take_profit} -> {self.take_profit_percent}")
                    print(f"\n[CONFIG] Take profit updated: {old_take_profit}% -> {self.take_profit_percent}%")
                
                self.last_config_reload = datetime.now()
                return True
        except Exception as e:
            self.logger.error(f"Error reloading config: {e}")
        return False

    def get_eur_balance(self):
        """Get current EUR balance from account."""
        try:
            balance = self.api_client.get_account_balance()
            if balance:
                eur = float(balance.get('ZEUR', 0))
                return eur
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting EUR balance: {e}")
            return 0.0

    def get_crypto_holdings(self):
        """Get all crypto holdings from account."""
        try:
            balance = self.api_client.get_account_balance()
            if balance:
                # Map pair names to Kraken balance keys
                pair_to_balance = {
                    'XBTEUR': 'XXBT',
                    'ETHEUR': 'XETH',
                    'SOLEUR': 'SOL',
                    'ADAEUR': 'ADA',
                    'DOTEUR': 'DOT',
                    'XRPEUR': 'XXRP',
                    'LINKEUR': 'LINK',
                    'MATICEUR': 'MATIC'
                }
                for pair, key in pair_to_balance.items():
                    self.holdings[pair] = float(balance.get(key, 0))
        except Exception as e:
            self.logger.error(f"Error getting holdings: {e}")

    def load_purchase_prices_from_history(self):
        """Load purchase prices from Kraken trade history for existing holdings."""
        try:
            self.logger.info("Loading purchase prices from trade history...")
            print("[INFO] Loading purchase prices from Kraken trade history...")
            
            trades = self.api_client.get_trade_history()
            if not trades:
                self.logger.warning("No trade history found")
                return
            
            # Map Kraken pair names to our pair names
            kraken_pair_map = {
                'XXBTZEUR': 'XBTEUR', 'XBTEUR': 'XBTEUR',
                'XETHZEUR': 'ETHEUR', 'ETHEUR': 'ETHEUR',
                'SOLEUR': 'SOLEUR',
                'ADAEUR': 'ADAEUR',
                'DOTEUR': 'DOTEUR',
                'XXRPZEUR': 'XRPEUR', 'XRPEUR': 'XRPEUR',
                'LINKEUR': 'LINKEUR',
                'MATICEUR': 'MATICEUR'
            }
            
            # Calculate average buy price per pair
            buy_totals = {}  # {pair: {'cost': total_cost, 'volume': total_volume}}
            
            for trade_id, trade in trades.items():
                kraken_pair = trade.get('pair', '')
                our_pair = kraken_pair_map.get(kraken_pair)
                
                if not our_pair or our_pair not in self.trade_pairs:
                    continue
                
                trade_type = trade.get('type', '')
                if trade_type != 'buy':
                    continue
                
                price = float(trade.get('price', 0))
                volume = float(trade.get('vol', 0))
                cost = float(trade.get('cost', price * volume))
                
                if our_pair not in buy_totals:
                    buy_totals[our_pair] = {'cost': 0, 'volume': 0}
                
                buy_totals[our_pair]['cost'] += cost
                buy_totals[our_pair]['volume'] += volume
            
            # Calculate average prices
            for pair, data in buy_totals.items():
                if data['volume'] > 0:
                    avg_price = data['cost'] / data['volume']
                    self.purchase_prices[pair] = avg_price
                    self.logger.info(f"Loaded avg buy price for {pair}: {avg_price:.2f} EUR")
                    print(f"[INFO] {pair} avg buy price: {avg_price:.2f} EUR")
            
            self.logger.info("Purchase prices loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading purchase prices: {e}")
            print(f"[WARNING] Could not load purchase prices from history: {e}")

    def check_take_profit(self):
        """Check if any holdings should be sold for take-profit."""
        if self.take_profit_percent <= 0:
            return None, None  # Take-profit disabled
        
        for pair in self.trade_pairs:
            holding = self.holdings.get(pair, 0)
            purchase_price = self.purchase_prices.get(pair, 0)
            current_price = self.pair_prices.get(pair, 0)
            min_vol = self._get_min_volume(pair)
            
            # Skip if no holding or no purchase price
            if holding < min_vol or purchase_price <= 0 or current_price <= 0:
                continue
            
            # Calculate profit percentage
            profit_percent = ((current_price - purchase_price) / purchase_price) * 100
            
            if profit_percent >= self.take_profit_percent:
                self.logger.info(f"TAKE PROFIT: {pair} at +{profit_percent:.2f}% (bought at {purchase_price:.2f}, now {current_price:.2f})")
                return pair, profit_percent
        
        return None, None

    def analyze_all_pairs(self):
        """Analyze all trading pairs and return the best opportunity."""
        best_pair = None
        best_signal = "HOLD"
        best_score = 0
        
        for pair in self.trade_pairs:
            try:
                market_data = self.api_client.get_market_data(pair)
                if not market_data:
                    continue
                
                # Get current price
                pair_key = list(market_data.keys())[0]
                current_price = float(market_data[pair_key]['c'][0])
                self.pair_prices[pair] = current_price
                
                # Generate signal with score
                signal, score = self.analysis_tool.generate_signal_with_score(market_data)
                self.pair_signals[pair] = signal
                self.pair_scores[pair] = score
                
                # Track best opportunity
                if signal in ["BUY", "SELL"] and abs(score) > abs(best_score):
                    best_pair = pair
                    best_signal = signal
                    best_score = score
                    
                # Small delay between API calls
                time.sleep(0.3)
                
            except Exception as e:
                self.logger.error(f"Error analyzing {pair}: {e}")
                continue
        
        return best_pair, best_signal, best_score

    def start_trading(self):
        """Start the main trading loop - runs 24/7 with multi-pair analysis."""
        self.logger.info("=" * 60)
        self.logger.info("TRADING BOT STARTED - MULTI-PAIR MODE")
        self.logger.info(f"Watching: {', '.join(self.trade_pairs)}")
        self.logger.info(f"Target: {self.target_balance_eur} EUR")
        self.logger.info("=" * 60)
        
        for handler in logging.root.handlers:
            handler.flush()
        
        print("=" * 60)
        print("KRAKEN TRADING BOT - MULTI-PAIR MODE")
        print(f"Watching {len(self.trade_pairs)} pairs: {', '.join(self.trade_pairs)}")
        print(f"Trade Amount: {self._get_trade_amount_eur()} EUR per trade")
        print(f"Target Balance: {self.target_balance_eur} EUR")
        print("Press Ctrl+C to stop")
        print("=" * 60)
        
        initial_balance = self.get_eur_balance()
        self.get_crypto_holdings()
        self.load_purchase_prices_from_history()  # Load existing purchase prices
        self.logger.info(f"Initial EUR Balance: {initial_balance:.2f} EUR")
        self.logger.info(f"Take-Profit: {self.take_profit_percent}%")
        print(f"Starting Balance: {initial_balance:.2f} EUR")
        print(f"Take-Profit Target: {self.take_profit_percent}%")
        print(f"Need to earn: {self.target_balance_eur - initial_balance:.2f} EUR")
        print("-" * 60)
        
        try:
            iteration = 0
            
            while True:
                try:
                    iteration += 1
                    
                    # Check if target reached
                    current_balance = self.get_eur_balance()
                    if current_balance >= self.target_balance_eur:
                        self.logger.info(f"TARGET REACHED! Balance: {current_balance:.2f} EUR")
                        print(f"\n{'=' * 60}")
                        print(f"TARGET REACHED! Current Balance: {current_balance:.2f} EUR")
                        print(f"Total Trades: {self.trade_count}")
                        print(f"Runtime: {datetime.now() - self.start_time}")
                        print(f"{'=' * 60}")
                        break
                    
                    # Analyze all pairs
                    best_pair, best_signal, best_score = self.analyze_all_pairs()
                    
                    # Check for take-profit opportunities FIRST
                    self.get_crypto_holdings()
                    tp_pair, tp_profit = self.check_take_profit()
                    if tp_pair:
                        price = self.pair_prices.get(tp_pair, 0)
                        print(f"\n[TAKE PROFIT] {tp_pair} at +{tp_profit:.2f}% profit!")
                        self.execute_sell_order(tp_pair, price)
                        # Reset purchase price after selling
                        self.purchase_prices[tp_pair] = 0.0
                    
                    # Build status display
                    pair_status = " | ".join([f"{p[:3]}:{self.pair_signals.get(p, '?')}" for p in self.trade_pairs[:4]])
                    status_msg = f"[{iteration}] {pair_status} | Best: {best_pair or 'NONE'} ({best_signal}) | Bal: {current_balance:.2f}EUR | Trades: {self.trade_count}"
                    
                    self.logger.info(status_msg)
                    print(f"\r{status_msg}", end="", flush=True)
                    
                    # Execute trade on best opportunity
                    if best_pair and best_signal != "HOLD":
                        price = self.pair_prices.get(best_pair, 0)
                        
                        if best_signal == "BUY":
                            print(f"\n[BEST BUY] {best_pair} at {price:.2f} EUR (Score: {best_score:.2f})")
                            self.logger.info(f"BEST BUY SIGNAL: {best_pair} Score: {best_score}")
                            self.execute_buy_order(best_pair, price)
                            
                        elif best_signal == "SELL":
                            # Check if we have holdings to sell
                            self.get_crypto_holdings()
                            min_vol = self._get_min_volume(best_pair)
                            if self.holdings.get(best_pair, 0) >= min_vol:
                                print(f"\n[BEST SELL] {best_pair} at {price:.2f} EUR (Score: {best_score:.2f})")
                                self.logger.info(f"BEST SELL SIGNAL: {best_pair} Score: {best_score}")
                                self.execute_sell_order(best_pair, price)
                            else:
                                self.logger.info(f"SELL signal for {best_pair} but no holdings")
                    
                    # Flush logs
                    for handler in logging.root.handlers:
                        handler.flush()
                    
                    # Check if we should reload config
                    time_since_reload = (datetime.now() - self.last_config_reload).total_seconds()
                    if time_since_reload >= self.config_reload_interval:
                        self.reload_config()
                    
                    # Wait before next iteration
                    time.sleep(60)
                    
                except Exception as e:
                    self.logger.error(f"Error in trading loop: {e}", exc_info=True)
                    for handler in logging.root.handlers:
                        handler.flush()
                    time.sleep(3)

        except KeyboardInterrupt:
            final_balance = self.get_eur_balance()
            self.logger.info(f"Bot stopped by user. Final balance: {final_balance:.2f} EUR")
            print(f"\n{'=' * 60}")
            print("Trading bot stopped by user.")
            print(f"Final Balance: {final_balance:.2f} EUR")
            print(f"Total Trades: {self.trade_count}")
            print(f"Runtime: {datetime.now() - self.start_time}")
            print(f"{'=' * 60}")

    def execute_buy_order(self, pair, price):
        """Execute a buy order with calculated volume."""
        try:
            volume = self._calculate_volume(pair, price)
            self.logger.info(f"Placing BUY order: {volume:.6f} {pair} at ~{price:.2f} EUR")
            
            result = self.api_client.place_order(
                pair=pair,
                direction='buy',
                volume=volume
            )
            if result:
                self.trade_count += 1
                # Track purchase price for take-profit
                old_holding = self.holdings.get(pair, 0)
                old_price = self.purchase_prices.get(pair, 0)
                new_cost = (old_holding * old_price) + (volume * price)
                new_holding = old_holding + volume
                if new_holding > 0:
                    self.purchase_prices[pair] = new_cost / new_holding  # Weighted average
                self.logger.info(f"BUY ORDER SUCCESS: {result}")
                self.logger.info(f"Updated avg buy price for {pair}: {self.purchase_prices[pair]:.2f} EUR")
                print(f"[BUY] {volume:.6f} {pair} (~{volume*price:.2f} EUR) - Trade #{self.trade_count}")
            else:
                self.logger.error(f"BUY ORDER FAILED for {pair}")
                print(f"[ERROR] Buy order failed for {pair}")
        except Exception as e:
            self.logger.error(f"Error executing buy order: {e}", exc_info=True)
            print(f"[ERROR] Buy order error: {e}")

    def execute_sell_order(self, pair, price):
        """Execute a sell order."""
        try:
            # Immer 100% des Bestands verkaufen, sofern Mindestvolumen erreicht
            holding = self.holdings.get(pair, 0)
            volume = holding
            
            if volume < self._get_min_volume(pair):
                self.logger.warning(f"Insufficient {pair} to sell")
                return
            
            self.logger.info(f"Placing SELL order: {volume:.6f} {pair} at ~{price:.2f} EUR")
            
            result = self.api_client.place_order(
                pair=pair,
                direction='sell',
                volume=volume
            )
            if result:
                self.trade_count += 1
                self.logger.info(f"SELL ORDER SUCCESS: {result}")
                print(f"[SELL] {volume:.6f} {pair} (~{volume*price:.2f} EUR) - Trade #{self.trade_count}")
            else:
                self.logger.error(f"SELL ORDER FAILED for {pair}")
                print(f"[ERROR] Sell order failed for {pair}")
        except Exception as e:
            self.logger.error(f"Error executing sell order: {e}", exc_info=True)
            print(f"[ERROR] Sell order error: {e}")


class Backtester:
    def __init__(self, api_client, config):
        self.api_client = api_client
        self.config = config
        self.logger = logging.getLogger(__name__)

    def run(self):
        """Run the backtesting module."""
        self.logger.info("Starting backtesting...")
        print("Backtesting mode activated.")
        
        try:
            # TODO: Implement historical data loading
            # TODO: Implement strategy backtesting
            # TODO: Implement results analysis
            
            self.logger.info("Backtesting module is a placeholder. Historical data path: %s", 
                           self.config['backtesting'].get('historical_data_path'))
            print("Backtesting functionality is not yet implemented.")
            print("Please add historical price data to the configured path.")
            
        except Exception as e:
            self.logger.error(f"Error in backtesting: {e}", exc_info=True)
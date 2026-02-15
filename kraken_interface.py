# Kraken API Interface Wrapper

import krakenex
import logging
import time


class KrakenAPI:
    """Wrapper for Kraken API interactions."""

    def __init__(self, api_key, api_secret):
        self.api = krakenex.API(api_key, api_secret)
        self.logger = logging.getLogger(__name__)
        self.rate_limit_delay = 0.5  # seconds between API calls

    def _handle_error(self, response, action):
        if response.get('error'):
            self.logger.error(f"{action} - API Error: {response['error']}")
            return True
        return False

    def get_account_balance(self):
        try:
            response = self.api.query_private('Balance')
            if self._handle_error(response, "Balance Query"):
                return None
            return response.get('result', {})
        except Exception as e:
            self.logger.exception(f"Error fetching account balance: {e}")
            return None

    def get_market_data(self, pair):
        try:
            time.sleep(self.rate_limit_delay)
            response = self.api.query_public('Ticker', {'pair': pair})
            if self._handle_error(response, f"Market Data for {pair}"):
                return None
            return response.get('result', {})
        except Exception as e:
            self.logger.exception(f"Error fetching market data for {pair}: {e}")
            return None

    def get_ohlc_data(self, pair, interval=60, since=None):
        """Fetch OHLC data from Kraken.
        Intervals: 1, 5, 15, 30, 60, 240, 1440, 10080, 21600
        """
        try:
            params = {'pair': pair, 'interval': interval}
            if since:
                params['since'] = since
            time.sleep(self.rate_limit_delay)
            response = self.api.query_public('OHLC', params)
            if self._handle_error(response, f"OHLC Data for {pair}"):
                return None
            return response.get('result', {})
        except Exception as e:
            self.logger.exception(f"Error fetching OHLC data for {pair}: {e}")
            return None

    def get_asset_pairs(self):
        """Fetch tradable asset pairs from Kraken."""
        try:
            time.sleep(self.rate_limit_delay)
            response = self.api.query_public('AssetPairs')
            if self._handle_error(response, "AssetPairs Query"):
                return {}
            return response.get('result', {})
        except Exception as e:
            self.logger.exception(f"Error fetching asset pairs: {e}")
            return {}

    def place_order(self, pair, direction, volume, price=None, leverage=None, post_only=False):
        try:
            if direction not in ['buy', 'sell']:
                self.logger.error(f"Invalid direction: {direction}. Must be 'buy' or 'sell'")
                return None
            if float(volume) <= 0:
                self.logger.error(f"Invalid volume: {volume}. Must be positive")
                return None

            time.sleep(self.rate_limit_delay)

            # Use limit if price provided, otherwise market
            # If post_only is True, force limit order
            order_type = 'limit' if (price or post_only) else 'market'
            
            order_params = {
                'pair': pair,
                'type': direction,
                'ordertype': order_type,
                'volume': str(volume)
            }
            
            if price:
                order_params['price'] = str(price)
            
            if post_only:
                order_params['oflags'] = 'post'
                
            if leverage:
                order_params['leverage'] = str(leverage)

            response = self.api.query_private('AddOrder', order_params)
            if self._handle_error(response, f"Place {direction.upper()} Order"):
                return None
            result = response.get('result', {})
            self.logger.info(f"Order placed successfully: {direction} {volume} {pair} ({order_type}, post_only={post_only})")
            return result
        except Exception as e:
            self.logger.exception(f"Error placing order: {e}")
            return None

    def get_open_orders(self):
        try:
            time.sleep(self.rate_limit_delay)
            response = self.api.query_private('OpenOrders')
            if self._handle_error(response, "Open Orders Query"):
                return None
            return response.get('result', {})
        except Exception as e:
            self.logger.exception(f"Error fetching open orders: {e}")
            return None

    def cancel_order(self, order_id):
        try:
            time.sleep(self.rate_limit_delay)
            response = self.api.query_private('CancelOrder', {'txid': order_id})
            if self._handle_error(response, f"Cancel Order {order_id}"):
                return None
            result = response.get('result', {})
            self.logger.info(f"Order {order_id} cancelled successfully")
            return result
        except Exception as e:
            self.logger.exception(f"Error cancelling order {order_id}: {e}")
            return None

    def get_ledgers(self, asset=None, start=None, fetch_all=False, max_pages=200):
        """Fetch ledger entries (deposits/withdrawals/trades/etc)."""
        try:
            params = {}
            if asset:
                params['asset'] = asset
            if start:
                params['start'] = int(start)

            if not fetch_all:
                time.sleep(self.rate_limit_delay)
                response = self.api.query_private('Ledgers', params)
                if self._handle_error(response, "Ledgers Query"):
                    return None
                return response.get('result', {}).get('ledger', {})

            all_entries = {}
            ofs = 0
            page = 0
            total_count = None

            while page < max_pages:
                query_params = dict(params)
                query_params['ofs'] = ofs
                time.sleep(self.rate_limit_delay)
                response = self.api.query_private('Ledgers', query_params)
                if self._handle_error(response, f"Ledgers Query (ofs={ofs})"):
                    return all_entries if all_entries else None

                result = response.get('result', {})
                ledger = result.get('ledger', {}) or {}
                total_count = result.get('count', total_count)

                if not ledger:
                    break

                all_entries.update(ledger)
                batch_len = len(ledger)
                ofs += batch_len
                page += 1

                if total_count is not None and ofs >= int(total_count):
                    break

            return all_entries
        except Exception as e:
            self.logger.exception(f"Error fetching ledgers: {e}")
            return None

    def get_trade_history(self, start=None, fetch_all=False, max_pages=200):
        try:
            params = {}
            if start:
                params['start'] = int(start)

            # Default behavior: single page (Kraken default limit, usually 50)
            if not fetch_all:
                time.sleep(self.rate_limit_delay)
                response = self.api.query_private('TradesHistory', params)
                if self._handle_error(response, "Trade History Query"):
                    return None
                return response.get('result', {}).get('trades', {})

            # Paginated fetch: collect all pages from start timestamp
            all_trades = {}
            ofs = 0
            page = 0
            total_count = None

            while page < max_pages:
                query_params = dict(params)
                query_params['ofs'] = ofs
                time.sleep(self.rate_limit_delay)
                response = self.api.query_private('TradesHistory', query_params)
                if self._handle_error(response, f"Trade History Query (ofs={ofs})"):
                    return all_trades if all_trades else None

                result = response.get('result', {})
                trades = result.get('trades', {}) or {}
                total_count = result.get('count', total_count)

                if not trades:
                    break

                all_trades.update(trades)
                batch_len = len(trades)
                ofs += batch_len
                page += 1

                if total_count is not None and ofs >= int(total_count):
                    break

            return all_trades
        except Exception as e:
            self.logger.exception(f"Error fetching trade history: {e}")
            return None

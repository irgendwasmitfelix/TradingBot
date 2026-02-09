# Kraken API Interface Wrapper

import krakenex
import logging
import time

class KrakenAPI:
    """Wrapper for Kraken API interactions."""
    
    def __init__(self, api_key, api_secret):
        """
        Initialize the Kraken API client.
        
        Args:
            api_key (str): Kraken API key
            api_secret (str): Kraken API secret
        """
        self.api = krakenex.API(api_key, api_secret)
        self.logger = logging.getLogger(__name__)
        self.rate_limit_delay = 0.5  # seconds between API calls

    def _handle_error(self, response, action):
        """
        Handle API errors.
        
        Args:
            response (dict): API response
            action (str): Description of the action attempted
        
        Returns:
            bool: True if error, False otherwise
        """
        if response.get('error'):
            self.logger.error(f"{action} - API Error: {response['error']}")
            return True
        return False

    def get_account_balance(self):
        """
        Fetch the account balance from Kraken.
        
        Returns:
            dict: Account balances or None if error
        """
        try:
            response = self.api.query_private('Balance')
            if self._handle_error(response, "Balance Query"):
                return None
            
            balance = response.get('result', {})
            self.logger.info(f"Account balance fetched successfully")
            return balance
        
        except Exception as e:
            self.logger.exception(f"Error fetching account balance: {e}")
            return None

    def get_market_data(self, pair):
        """
        Fetch market data for a trading pair.
        
        Args:
            pair (str): Trading pair (e.g., 'BTC/USD')
        
        Returns:
            dict: Market data or None if error
        """
        try:
            time.sleep(self.rate_limit_delay)
            response = self.api.query_public('Ticker', {'pair': pair})
            if self._handle_error(response, f"Market Data for {pair}"):
                return None
            
            market_data = response.get('result', {})
            self.logger.debug(f"Market data fetched for {pair}")
            return market_data
        
        except Exception as e:
            self.logger.exception(f"Error fetching market data for {pair}: {e}")
            return None

    def place_order(self, pair, direction, volume, price=None):
        """
        Place a buy or sell order on Kraken.
        
        Args:
            pair (str): Trading pair (e.g., 'BTC/USD')
            direction (str): 'buy' or 'sell'
            volume (float): Amount to trade
            price (float, optional): Price for limit orders
        
        Returns:
            dict: Order result or None if error
        """
        try:
            if direction not in ['buy', 'sell']:
                self.logger.error(f"Invalid direction: {direction}. Must be 'buy' or 'sell'")
                return None
            
            if volume <= 0:
                self.logger.error(f"Invalid volume: {volume}. Must be positive")
                return None
            
            time.sleep(self.rate_limit_delay)
            
            order_type = 'limit' if price else 'market'
            order_params = {
                'pair': pair,
                'type': direction,
                'ordertype': order_type,
                'volume': str(volume)
            }
            
            if price:
                order_params['price'] = str(price)
            
            response = self.api.query_private('AddOrder', order_params)
            
            if self._handle_error(response, f"Place {direction.upper()} Order"):
                return None
            
            result = response.get('result', {})
            self.logger.info(f"Order placed successfully: {direction} {volume} {pair}")
            return result
        
        except Exception as e:
            self.logger.exception(f"Error placing order: {e}")
            return None

    def get_open_orders(self):
        """
        Fetch open orders.
        
        Returns:
            dict: Open orders or None if error
        """
        try:
            time.sleep(self.rate_limit_delay)
            response = self.api.query_private('OpenOrders')
            if self._handle_error(response, "Open Orders Query"):
                return None
            
            orders = response.get('result', {})
            self.logger.debug("Open orders fetched successfully")
            return orders
        
        except Exception as e:
            self.logger.exception(f"Error fetching open orders: {e}")
            return None

    def cancel_order(self, order_id):
        """
        Cancel an open order.
        
        Args:
            order_id (str): Order ID to cancel
        
        Returns:
            dict: Cancel result or None if error
        """
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
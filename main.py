# Kraken Automated Trading Bot
# Main Script

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from kraken_interface import KrakenAPI
from trading_bot import TradingBot, Backtester
from utils import load_config, validate_config

# Load environment variables from .env file
load_dotenv()

# Load Configuration File
CONFIG_PATH = "config.toml"

try:
    config = load_config(CONFIG_PATH)
except FileNotFoundError:
    print(f"Error: Configuration file '{CONFIG_PATH}' not found.")
    print("Please ensure config.toml exists in the project root.")
    sys.exit(1)
except Exception as e:
    print(f"Error loading configuration: {e}")
    sys.exit(1)

# Validate configuration
if not validate_config(config):
    print("Warning: Configuration validation failed. Some settings may be missing.")

# Setup Logging
log_dir = Path(config['logging'].get('log_file_path', 'logs/bot_activity.log')).parent
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=config['logging'].get('log_level', 'INFO'),
    filename=config['logging']['log_file_path'] if config['logging'].get('log_to_file', True) else None,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True  # Override any existing logging config
)

# Force logging to flush immediately (unbuffered)
for handler in logging.root.handlers:
    handler.flush()

logger = logging.getLogger(__name__)

# Load API credentials from environment variables (with .env file support)
api_key = os.getenv('KRAKEN_API_KEY', '')
api_secret = os.getenv('KRAKEN_API_SECRET', '')

if not api_key or not api_secret:
    logger.warning("API credentials not configured. Set KRAKEN_API_KEY and KRAKEN_API_SECRET in .env file or environment variables.")
    print("WARNING: Kraken API credentials are not configured.")
    print("Please either:")
    print("  1. Create a .env file in the project root with your credentials")
    print("  2. Or set environment variables: KRAKEN_API_KEY and KRAKEN_API_SECRET")
    print("\nFor setup instructions, see SETUP_GUIDE.md")

# Initialize Kraken API Client
kraken = KrakenAPI(api_key=api_key, api_secret=api_secret)

# Initialize Trading Bot
trading_bot = TradingBot(kraken, config)

# Option to Run Backtesting or Live Trading
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kraken Automated Trading Bot")
    parser.add_argument("--backtest", action="store_true", help="Run backtesting mode.")
    parser.add_argument("--test", action="store_true", help="Run test mode (check API connection).")
    args = parser.parse_args()

    if args.test:
        logger.info("Running test mode...")
        print("Testing Kraken API connection...")
        balance = kraken.get_account_balance()
        if balance is not None:
            print("[OK] Successfully connected to Kraken API")
            print(f"Account balance: {balance}")
        else:
            print("[ERROR] Failed to connect to Kraken API")
            print("Please check your API credentials and network connection.")
        sys.exit(0)
    elif args.backtest:
        # Run Backtesting Module
        logger.info("Starting backtesting...")
        backtester = Backtester(kraken, config)
        backtester.run()
    else:
        # Start Live Trading
        logger.info("Starting live trading...")
        print("Starting Kraken Trading Bot...")
        trading_bot.start_trading()
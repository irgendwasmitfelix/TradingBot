# Kraken Automated Trading Bot
# Main Script

import os
import sys
import logging
import atexit
from pathlib import Path
from dotenv import load_dotenv
from kraken_interface import KrakenAPI
from trading_bot import TradingBot, Backtester
from utils import load_config, validate_config

try:
    import fcntl
except Exception:  # pragma: no cover
    fcntl = None

load_dotenv()
CONFIG_PATH = "config.toml"
LOCK_FILE = "/tmp/kraken_bot.lock"
_lock_fp = None


def acquire_single_instance_lock():
    global _lock_fp
    if fcntl is None:
        return
    _lock_fp = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fp.write(str(os.getpid()))
        _lock_fp.flush()
    except BlockingIOError:
        print("Another kraken_bot instance is already running. Exiting.")
        sys.exit(1)


def release_lock():
    global _lock_fp
    try:
        if _lock_fp and fcntl is not None:
            fcntl.flock(_lock_fp.fileno(), fcntl.LOCK_UN)
            _lock_fp.close()
    except Exception:
        pass


atexit.register(release_lock)
acquire_single_instance_lock()

try:
    config = load_config(CONFIG_PATH)
except FileNotFoundError:
    print(f"Error: Configuration file '{CONFIG_PATH}' not found.")
    sys.exit(1)
except Exception as e:
    print(f"Error loading configuration: {e}")
    sys.exit(1)

if not validate_config(config):
    print("Warning: Configuration validation failed. Some settings may be missing.")

log_dir = Path(config['logging'].get('log_file_path', 'logs/bot_activity.log')).parent
log_dir.mkdir(parents=True, exist_ok=True)

log_file = config['logging']['log_file_path'] if config['logging'].get('log_to_file', True) else None
if log_file and config['logging'].get('fresh_log_on_start', True):
    try:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'w') as f:
            f.write('')
    except Exception as e:
        print(f"Warning: Could not reset log file {log_file}: {e}")

logging.basicConfig(
    level=config['logging'].get('log_level', 'INFO'),
    filename=log_file,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

logger = logging.getLogger(__name__)
api_key = os.getenv('KRAKEN_API_KEY', '')
api_secret = os.getenv('KRAKEN_API_SECRET', '')

if not api_key or not api_secret:
    logger.warning("API credentials not configured. Set KRAKEN_API_KEY and KRAKEN_API_SECRET.")
    print("WARNING: Kraken API credentials are not configured.")

kraken = KrakenAPI(api_key=api_key, api_secret=api_secret)
trading_bot = TradingBot(kraken, config)

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
        sys.exit(0)
    elif args.backtest:
        logger.info("Starting backtesting...")
        backtester = Backtester(kraken, config)
        backtester.run()
    else:
        logger.info("Starting live trading...")
        print("Starting Kraken Trading Bot...")
        trading_bot.start_trading()

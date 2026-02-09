# Utility Functions for Kraken Trading Bot

import toml
import logging
from pathlib import Path


def load_config(config_path):
    """
    Load configuration from a TOML file.
    
    Args:
        config_path (str): Path to the TOML configuration file.
    
    Returns:
        dict: Configuration dictionary.
    """
    try:
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = toml.load(f)
        
        logging.info(f"Configuration loaded successfully from {config_path}")
        return config
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        raise


def validate_config(config):
    """
    Validate that all required configuration values are present.
    
    Args:
        config (dict): Configuration dictionary.
    
    Returns:
        bool: True if valid, False otherwise.
    """
    required_keys = {
        'kraken_api': ['key', 'secret'],
        'bot_settings': ['trade_pair', 'initial_balance'],
        'risk_management': ['max_drawdown_percent', 'stop_loss_percent'],
        'logging': ['log_level']
    }
    
    for section, keys in required_keys.items():
        if section not in config:
            logging.warning(f"Missing config section: {section}")
            return False
        
        for key in keys:
            if key not in config[section]:
                logging.warning(f"Missing config key: {section}.{key}")
                return False
    
    return True

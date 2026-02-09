# Setup Guide - Kraken Automated Trading Bot

## Prerequisites

- **Python 3.8+** installed on your system
- **Kraken account** with API access enabled
- **Git** (optional, for cloning the repository)

## Installation Steps

### 1. Clone or Download the Project

```bash
git clone <repository-url>
cd kraken_bot
```

### 2. Create a Virtual Environment (Recommended)

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Kraken API Credentials

#### Step 1: Create .env File from Template

Copy the `.env.example` file to `.env`:

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**On macOS/Linux:**
```bash
cp .env.example .env
```

#### Step 2: Add Your Credentials

Open the `.env` file and add your Kraken API credentials:

```
KRAKEN_API_KEY=your_actual_api_key_here
KRAKEN_API_SECRET=your_actual_api_secret_here
```

✅ **Security**: The `.env` file is automatically ignored by git (see `.gitignore`), so your credentials will never be accidentally committed.

#### Alternative: Using Environment Variables

If you prefer not to use a `.env` file:

**On Windows (PowerShell):**
```powershell
$env:KRAKEN_API_KEY = "your_api_key_here"
$env:KRAKEN_API_SECRET = "your_api_secret_here"
```

**On macOS/Linux:**
```bash
export KRAKEN_API_KEY="your_api_key_here"
export KRAKEN_API_SECRET="your_api_secret_here"
```

### 5. Generate Kraken API Key

1. Log in to your [Kraken account](https://www.kraken.com)
2. Go to Settings → API
3. Click "Generate New Key"
4. Configure permissions:
   - ✓ Query Funds
   - ✓ Query Open Orders & Trades
   - ✓ Query Closed Orders & Trades
   - ✓ Create & Modify Orders
   - ✓ Cancel/Close Orders
5. Copy your API Key and Private Key

## Running the Bot

### Test API Connection

```bash
python main.py --test
```

This will verify your API credentials and connectivity.

### Run Backtesting Mode

```bash
python main.py --backtest
```

This mode analyzes historical data without placing real trades. Requires historical price data in `data/historical_prices.csv`.

### Run Live Trading Mode

```bash
python main.py
```

⚠️ **Warning**: This will place real trades on your Kraken account using actual funds. Make sure your configuration is correct before running.

## Configuration

Edit `config.toml` to customize:

- **Trading Pair**: `trade_pair` (default: "BTC/USD")
- **Trade Volume**: `trade_volume` (amount per trade)
- **Risk Settings**: Stop-loss and drawdown limits
- **Logging**: Log level and output path

## Directory Structure

```
kraken_bot/
├── main.py                 # Entry point
├── trading_bot.py          # Core trading logic
├── kraken_interface.py     # Kraken API wrapper
├── analysis.py             # Technical analysis indicators
├── utils.py                # Helper functions
├── config.toml             # Configuration file
├── requirements.txt        # Python dependencies
├── logs/                   # Log files directory
├── data/                   # Historical data directory
└── reports/                # Trade reports directory
```

## Technical Indicators

The bot uses the following technical analysis indicators:

- **RSI (Relative Strength Index)**: Identifies overbought/oversold conditions
  - BUY when RSI < 30 (oversold)
  - SELL when RSI > 70 (overbought)

- **SMA (Simple Moving Average)**: Identifies trend direction
  - Short-term SMA (20 periods)
  - Long-term SMA (50 periods)

## Troubleshooting

### Import Errors
```
ModuleNotFoundError: No module named 'krakenex'
```
**Solution**: Run `pip install -r requirements.txt`

### API Connection Failed
```
ERROR:kraken_interface:Error fetching account balance: Either key or secret is not set!
```
**Solution**: Check your API credentials in environment variables or config.toml

### Permission Errors
```
API Error: EAPI:Invalid key
```
**Solution**: Verify API key has required permissions enabled on Kraken

### Rate Limiting
```
EAPI:EAPI:Rate limit exceeded
```
**Solution**: Wait a few seconds. The bot has built-in rate limiting (0.5s between calls).

## Security Best Practices

1. ✓ Always use environment variables for API credentials
2. ✓ Never commit credentials to version control
3. ✓ Use API keys with minimal required permissions
4. ✓ Enable IP whitelisting on your Kraken API key
5. ✓ Monitor your account regularly
6. ✓ Start with small trade volumes for testing
7. ✓ Use stop-loss orders to limit potential losses

## Monitoring & Logs

Logs are saved to `logs/bot_activity.log`. Monitor this file for:
- Trading signals and orders
- API errors and warnings
- Performance metrics

View logs in real-time:
```bash
# On Windows (PowerShell)
Get-Content logs/bot_activity.log -Tail 20 -Wait

# On macOS/Linux
tail -f logs/bot_activity.log
```

## Next Steps

1. **Implement Backtesting**: Add historical data to `data/` folder
2. **Add More Indicators**: Extend the `analysis.py` module with MACD, Bollinger Bands, etc.
3. **Risk Management**: Implement position sizing and portfolio rebalancing
4. **Reporting**: Generate trade performance reports
5. **Deployment**: Set up on a VPS for 24/7 operation

## Support & Resources

- [Kraken API Documentation](https://docs.kraken.com/rest/)
- [Krakenex Python Library](https://github.com/veox/python3-krakenex)
- [Technical Analysis Resources](https://www.investopedia.com/)

## Disclaimer

Trading cryptocurrencies involves significant risk. This bot is provided as-is for educational purposes. The developers are not responsible for financial losses. Always:
- Test thoroughly before using real funds
- Use appropriate risk management
- Comply with local regulations
- Never invest more than you can afford to lose

---

**Last Updated**: February 9, 2026

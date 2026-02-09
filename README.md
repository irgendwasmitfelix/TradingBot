# Kraken Automated Day Trading Bot

A sophisticated, AI-enhanced 24/7 automated cryptocurrency trading bot for the Kraken exchange. This bot combines real-time market analysis, technical indicators, and risk management to execute profitable trades automatically.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file with credentials
cp .env.example .env
# Edit .env and add your Kraken API keys

# 3. Test the connection
python main.py --test

# 4. Run live trading
python main.py
```

For detailed setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md).

---

## 📋 Features

### ✅ Core Features (Implemented)
- **Real-time Market Analysis**: Streams live price data from Kraken API
- **Technical Indicators**: RSI (Relative Strength Index) and SMA (Simple Moving Average)
- **Automated Trading**: Executes buy/sell orders based on signals
- **Risk Management**: Stop-loss and position sizing controls
- **Logging & Monitoring**: Comprehensive activity logging to track all trades
- **API Error Handling**: Robust error handling and recovery
- **Configuration Management**: Flexible TOML-based configuration system

### 🔄 Signal Generation Logic
The bot generates trading signals based on:
- **Buy Signal**: RSI < 30 (oversold) AND short SMA > long SMA (uptrend)
- **Sell Signal**: RSI > 70 (overbought) AND short SMA < long SMA (downtrend)
- **Hold Signal**: All other conditions (default safe state)

### 📊 Supported Features
- Multiple trading pairs (default: BTC/USD)
- Configurable trade volumes and timeframes
- Real-time balance queries
- Open orders management
- Account history tracking

---

## 📁 Project Structure

```
kraken_bot/
├── main.py                  # Entry point - runs the bot
├── trading_bot.py           # Core trading logic and decision-making
├── kraken_interface.py      # Kraken API wrapper with all API methods
├── analysis.py              # Technical analysis indicators (RSI, SMA)
├── utils.py                 # Configuration handling and validation
├── config.toml              # Configuration file for settings
├── requirements.txt         # Python dependencies
│
├── logs/                    # Trading activity logs
├── data/                    # Historical price data (for backtesting)
├── reports/                 # Generated trade reports
│
├── README.md                # This file
├── SETUP_GUIDE.md           # Detailed setup instructions
└── __pycache__/             # Python cache (auto-generated)
```

---

## 🔧 Key Objectives

### 1. **AI-Based Strategies**
- ✅ Technical indicator analysis (RSI, SMA)
- 🔜 Machine learning integration (TensorFlow)
- 🔜 Pattern recognition algorithms

### 2. **Real-Time Market Data Analysis**
- ✅ Live price feeds from Kraken
- ✅ Minimal latency decision-making
- ✅ Rate-limited API calls to prevent throttling

### 3. **Risk Management**
- ✅ Stop-loss order support
- ✅ Position size constraints
- ✅ Drawdown limits
- ✅ Trade volume controls

### 4. **Backtesting**
- 🔜 Historical data analysis
- 🔜 Strategy performance validation
- 🔜 Parameter optimization

### 5. **Reporting & Monitoring**
- ✅ Comprehensive logging system
- 🔜 Automated trade reports
- 🔜 Performance analytics
- 🔜 Grafana integration (via logs)

---

## 🛠️ Development Roadmap

### ✅ Phase 1: Setup and Configuration
- [x] Configure development environment
- [x] Implement API credential storage
- [x] Test Kraken API connectivity
- [x] Create configuration system

### ✅ Phase 2: Core Trading Logic
- [x] Integrate API-based trading
- [x] Implement technical indicators (RSI, SMA)
- [x] Create signal generation system
- [x] Support multiple trading pairs

### ✅ Phase 3: Risk Management Features
- [x] Stop-loss implementation
- [x] Position sizing
- [x] Capital allocation safeguards
- [x] Error handling

### 🔜 Phase 4: Backtesting Module
- [ ] Historical data loader
- [ ] Strategy backtester
- [ ] Performance analyzer
- [ ] Report generator

### 🔜 Phase 5: Deployment and Automation
- [ ] Cloud deployment (AWS/GCP)
- [ ] 24/7 monitoring
- [ ] Performance alerts
- [ ] Advanced reporting

---

## 📦 Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **Internet Connection**: For Kraken API access

### Python Libraries
- `krakenex` - Kraken API client
- `toml` - Configuration file parsing
- `numpy` - Numerical calculations
- `pandas` - Data manipulation (optional)

Install all with:
```bash
pip install -r requirements.txt
```

---

## 📖 Usage

### Command-Line Options

**Test API Connection:**
```bash
python main.py --test
```
Verifies API credentials and connectivity without trading.

**Backtesting Mode:**
```bash
python main.py --backtest
```
Analyzes historical data and simulates trading (no real trades).

**Live Trading:**
```bash
python main.py
```
⚠️ Executes real trades with your account. Use with caution!

### Configuration (config.toml)

```toml
[bot_settings]
trade_pair = "BTC/USD"      # Which pair to trade
trade_volume = 0.01         # Amount per trade
initial_balance = 1000.0    # Starting capital

[risk_management]
max_drawdown_percent = 5.0  # Maximum loss percentage
stop_loss_percent = 2.0     # Per-trade stop loss
allocation_per_trade_percent = 2.0
```

### Environment Variables

The bot loads credentials from the `.env` file (recommended):

**Create `.env` file:**
```
KRAKEN_API_KEY=your_actual_api_key_here
KRAKEN_API_SECRET=your_actual_api_secret_here
```

Alternatively, set environment variables directly:

**Windows (PowerShell):**
```powershell
$env:KRAKEN_API_KEY = "your_key"
$env:KRAKEN_API_SECRET = "your_secret"
```

**macOS/Linux:**
```bash
export KRAKEN_API_KEY="your_key"
export KRAKEN_API_SECRET="your_secret"
```

---

## 🔐 Security

### ⚠️ Important Security Guidelines

1. **Never expose API credentials** - Use environment variables, not config files
2. **Use IP whitelisting** - Restrict API key access to your IP address
3. **Enable 2FA** - Use two-factor authentication on your Kraken account
4. **Minimal permissions** - Only enable necessary API permissions
5. **Monitor regularly** - Check account activity logs frequently
6. **Test first** - Start with small trade volumes

### API Key Permissions Required
- ✓ Query account balances
- ✓ Query open/closed orders
- ✓ Create and modify orders
- ✓ Cancel orders

---

## 📊 Technical Indicators Explained

### RSI (Relative Strength Index)
- **Range**: 0-100
- **Oversold**: < 30 (potential BUY signal)
- **Overbought**: > 70 (potential SELL signal)
- **Period**: 14 candles (configurable)

### SMA (Simple Moving Average)
- **Calculation**: Average price over N periods
- **Short-term**: 20 periods (trending up/down)
- **Long-term**: 50 periods (overall trend)
- **Crossover**: When short > long = bullish, short < long = bearish

---

## 🐛 Troubleshooting

### Problem: API Connection Failed
```
ERROR: Either key or secret is not set!
```
**Solution**: Set environment variables or update config.toml with your API credentials.

### Problem: Rate Limit Exceeded
```
EAPI:Rate limit exceeded
```
**Solution**: Built-in rate limiting (0.5s between calls) should prevent this. Check for too many manual API calls.

### Problem: Module Not Found
```
ModuleNotFoundError: No module named 'krakenex'
```
**Solution**: Run `pip install -r requirements.txt` to install dependencies.

### Problem: Permission Denied
```
API Error: EAPI:Invalid key
```
**Solution**: Verify your API key has required permissions in Kraken account settings.

---

## 📈 Trading Signals Example

Assuming BTC/USD price history shows:
- Last 14 RSI = 25 (oversold)
- Short SMA (20) = $42,100
- Long SMA (50) = $41,800

**Result**: **BUY signal** ✓
- RSI 25 < 30 (oversold)
- SMA 20 > SMA 50 (uptrend)

---

## 💡 Tips for Success

1. **Start small**: Use minimal trade volumes initially
2. **Monitor logs**: Check `logs/bot_activity.log` regularly
3. **Set alerts**: Monitor your Kraken account for unusual activity
4. **Test first**: Run `--test` mode before going live
5. **Adjust parameters**: Tune RSI periods and SMA lengths for different timeframes
6. **Diversify**: Use multiple trading pairs
7. **Document trades**: Keep records of all signals and outcomes

---

## 🔄 Continuous Improvement

The bot can be enhanced with:
- **More Indicators**: MACD, Bollinger Bands, Volume analysis
- **Machine Learning**: Neural networks for pattern recognition
- **Portfolio Management**: Multi-pair trading with correlation analysis
- **Advanced Risk**: Kelly Criterion, Sharpe Ratio optimization
- **Notifications**: Email/Discord alerts for important events

---

## ⚖️ Legal & Disclaimer

**Trading Disclaimer**: 
- Cryptocurrency trading carries substantial risk
- Past performance does not guarantee future results
- The developers are not liable for financial losses
- Comply with all applicable laws and regulations in your jurisdiction
- Never invest more than you can afford to lose

**API Usage**:
- Respect Kraken's API rate limits and terms of service
- Do not use the bot for market manipulation
- Keep your API keys secure and rotate them periodically

---

## 📚 Resources

- [Kraken API Documentation](https://docs.kraken.com/rest/)
- [Krakenex Library Docs](https://github.com/veox/python3-krakenex)
- [Technical Analysis Guide](https://www.investopedia.com/)
- [RSI Indicator Guide](https://www.investopedia.com/terms/r/rsi.asp)
- [Moving Averages](https://www.investopedia.com/terms/m/movingaverage.asp)

---

## 📝 License

This project is provided as-is for educational purposes.

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

---

## 📞 Support

For issues, questions, or suggestions:
1. Check the [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. Review logs in `logs/bot_activity.log`
3. Check Kraken API documentation
4. Create an issue with detailed description

---

**Status**: ✅ Fully Functional - Ready for Testing  
**Last Updated**: February 9, 2026  
**Version**: 1.0.0

_**Remember**: Test thoroughly with small amounts before using real funds!_
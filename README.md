# Kraken Trading Bot

Minimal, production-focused Kraken bot with multi-pair trading, safer execution, and clear logging.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# add KRAKEN_API_KEY / KRAKEN_API_SECRET
python main.py --test
python main.py
```

## What it does

- Multi-pair spot trading on Kraken (EUR pairs)
- Signal-based entries with RSI/SMA scoring and filtering
- Sell gate with profit target logic (configured TP, currently 10% base)
- Fee-aware position reconstruction from Kraken trade history
- Risk controls: cooldowns, sizing checks, funds checks, max open positions
- Mentor-v3 protections: auto regime filter, hard stop-loss, time-stop, daily loss guard, risk-off sizing
- Intelligent adaptation extras: volatility-targeted sizing and loss-streak circuit breaker with cooldown pause
- Research backtest tool: `scripts/backtest_v3_detailed.py` (long/short/scalp estimator with fee+slippage assumptions)
- Pair validation/normalization against Kraken AssetPairs
- Single-instance lock to prevent duplicate bot processes
- Structured logging for stream/monitoring integration
- Fixed startup-balance baseline with separate Kraken deposit/withdraw tracking for fair performance display (`Start`, `NetCF`, `AdjPnL`)

## Important files

- `main.py` – startup, runtime loop, single-instance lock
- `trading_bot.py` – strategy + execution + state reconstruction
- `analysis.py` – technical analysis and scoring
- `kraken_interface.py` – Kraken API wrapper
- `utils.py` – config loading/validation
- `config.toml` – bot and risk settings

## Documentation

- Setup guide: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- Full change history: [CHANGELOG.md](CHANGELOG.md)

## Notes

- This bot executes real trades when run without `--test`.
- Keep API keys private and restricted.
- Start small and monitor logs.

---

Status: active development

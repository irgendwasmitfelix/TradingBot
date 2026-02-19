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
- Live autonomous short support (Kraken margin) with leverage and short notional cap via `[shorting]` config
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

## Release / Research Cycle (main vs dev)

- `main` = live branch/runtime (24/7 bot)
- `dev` = research branch (new ideas, stricter gates, simulations)
- Yearly benchmark script: `scripts/prod_dev_yearly_backtest.py`
- Release gate script: `scripts/release_gate_prod_dev.py`
- Data collection scripts:
  - `scripts/collect_kraken_history.py` (initial 5y collection)
  - `scripts/collect_kraken_history_incremental.py` (incremental/resumable collector)
- Progress script: `scripts/research_progress.py`

Suggested promotion rule (`dev -> main`):
- dev return > main return
- dev max drawdown <= main max drawdown
- dev final capital > main final capital

## Storage planning (Fritz NAS `Volume`)

Research path: `/mnt/fritz_nas/Volume/kraken_research_data`

Expected storage footprint (7 pairs):
- 1m + 15m + 1h OHLC, 5 years (gzip CSV): typically ~0.5–5 GB total
- 1m only, 5 years: usually ~0.3–3 GB
- Tick/orderbook multi-year: often 50+ GB up to hundreds of GB

## Notes

- This bot executes real trades when run without `--test`.
- Keep API keys private and restricted.
- Start small and monitor logs.

---

Status: active development

**Last Updated**: February 19, 2026

Note: this repository includes a systemd service unit (kraken-bot.service). To run the bot as a background service, install and enable the provided unit (see kraken-bot.service).

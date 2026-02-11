# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added
- Single-instance runtime lock (`/tmp/kraken_bot.lock`) to prevent duplicate bot processes.
- Asset pair validation + normalization against Kraken `AssetPairs` (e.g. `XXBTZEUR -> XBTEUR`).
- Dynamic buy sizing and additional insufficient-funds safeguards before order placement.
- Global and per-pair trade cooldown controls.
- Fee-aware reconstruction of position quantity, average entry, realized PnL, and fees from Kraken history.
- Per-coin metrics logging and adaptive take-profit controls.
- Trade counter reconstruction from Kraken history on startup.
- Trade history pagination support in API wrapper (`fetch_all=True`) with offset paging.
- Ledger pagination support in API wrapper via `get_ledgers(..., fetch_all=True)`.
- Startup balance baseline is now fixed (`Start`) and external cashflows are tracked separately from Kraken ledger (`NetCF` deposits/withdrawals).
- Mentor-v2 risk hardening: regime filter (auto), hard stop-loss, time-stop, daily loss limit guard, and risk-off position sizing.
- Multi-edge signal engine updated: mean-reversion + trend-following continuation triggers.
- Re-entry tuning made more aggressive: `min_buy_score` 20 -> 14, `regime_min_score` -5 -> -12, `risk_off_allocation_multiplier` 0.35 -> 0.60.
- Mentor-v3 adaptive controls added to live bot: volatility-targeted sizing (`target_volatility_pct`) and loss-streak circuit breaker (`max_consecutive_losses` + cooldown pause).
- Added detailed research simulator `scripts/backtest_v3_detailed.py` for 30d tests with fee/slippage, regime switch behavior, and long/short/scalp estimation.
- Added live autonomous short execution path (Kraken margin) with capped short notional and configurable leverage.

### Changed
- Sell behavior hardened around configured profit target logic (current operating rule: only sell when target criteria are met; base target 10%).
- Signal filtering tightened in `analysis.py` to reduce low-quality entries.
- Config validation in `utils.py` improved to fail safer on invalid/missing settings.
- Startup log behavior: fresh `logs/bot_activity.log` on bot start when configured.
- Trade counter now uses all trades since **2026-01-01** (YTD) instead of a single default page.
- Reduced log noise for pair normalization: identical `Pair normalized: A -> B` messages are now logged once per bot runtime instead of repeating at each config reload.
- Runtime status output now includes `Start`, `NetCF`, and `AdjPnL` so deposits do not distort baseline performance reading.

### Fixed
- Repeated `EQuery:Unknown asset pair` issues from invalid pair usage (notably `MATICEUR`) through pair validation.
- Reduced `EOrder:Insufficient funds` noise with stronger pre-checks and sizing.
- Duplicate-process side effects (conflicting counters/order flow) via lockfile enforcement.
- Counter reset behavior (`Trades: 0` after restart) by rebuilding count from Kraken history.

## [2026-02-10]

### Bot/runtime updates applied today
- Integrated and deployed safety/consistency improvements across:
  - `main.py`
  - `trading_bot.py`
  - `analysis.py`
  - `kraken_interface.py`
  - `utils.py`
  - `config.toml`
- Pushed commits related to these updates, including recent:
  - `ba293df` – Persist displayed trade counter from Kraken history across restarts
  - `b422a00` – Load full Kraken trade history since Jan 2026 for trade counter

### Current operating behavior snapshot
- Multi-pair EUR trading with validated symbols.
- Profit-target-driven exits (10% base target policy currently in use).
- Cooldown + funds-aware execution pipeline.
- Restart-safe state recovery (positions + trade counter) from Kraken history.

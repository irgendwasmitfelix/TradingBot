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

### Changed
- Sell behavior hardened around configured profit target logic (current operating rule: only sell when target criteria are met; base target 10%).
- Signal filtering tightened in `analysis.py` to reduce low-quality entries.
- Config validation in `utils.py` improved to fail safer on invalid/missing settings.
- Startup log behavior: fresh `logs/bot_activity.log` on bot start when configured.
- Trade counter now uses all trades since **2026-01-01** (YTD) instead of a single default page.

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

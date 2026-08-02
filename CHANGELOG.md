# Changelog

## 2026-08-02 — Risiko-Layer repariert (P0)

### 🚨 Kritisch
- **fix(exits): Stop-Loss war strukturell unerreichbar**
  Sämtliche Exits liefen über `require_profit_target=True` und damit durch
  `_can_sell_profit_target()`, das einen Nettogewinn verlangt. Ein Verlust konnte
  deshalb **nie** geschlossen werden — Positionen wurden nur noch angesammelt
  (live beobachtet: XRPEUR 48 Tage offen bei −8 %).
  Fix: neue Konstante `PROTECTIVE_EXIT_REASONS`; Schutz-Exits (HARD_STOP,
  TIME_STOP, ATR, ATR_TRAIL, BREAK_EVEN, TRAILING_STOP, CRASH_AIRBAG,
  BEAR_SHIELD) umgehen das Gate. Nur TAKE_PROFIT und Signal-Verkäufe behalten es.
- **fix(kraken_interface): Datei war syntaktisch kaputt und abgeschnitten**
  Der vorige Commit hatte die Datei von 918 auf 516 Zeilen gekürzt; sechs
  Methoden fehlten (`_acquire_rate`, `get_open_orders`, `get_trade_history`,
  `get_ledgers`, `cancel_order`, `place_order_with_fallback`) und fünf
  `try`-Blöcke hatten kein `except`. **Der Bot konnte nicht starten.**
  Wiederhergestellt aus `a4be91e`, Leverage-Guard erneut angewandt.
- **fix(tp): `max_take_profit_percent = 0` fixierte das TP-Ziel auf 0 %**
  Der Wert wird per `min()` angewandt. Neuer Guard `_sanitize_max_tp()` behandelt
  Werte ≤ 0 als „kein Ceiling konfiguriert".
- **fix(short): Short-Schwelle war invertiert**
  Die Bedingung hing an `-min_buy_score`; bei negativem `min_buy_score` öffnete
  **jedes** SELL-Signal einen Short. Neuer, eigener Parameter `min_short_score`.
- **fix(short): Short-Exits liefen in `execute_sell_order()`**
  `SHORT_TAKE_PROFIT` wird jetzt korrekt an `execute_close_short_order()` geroutet.

### 🛡️ Risikoparameter scharf gestellt
- Hard-Stop **an** (3 %), ATR-Stop **an**, Time-Stop **an** (48 h), Trailing 1.5 %
- `min_net_sell_profit_pct` 2.0 → **0.7** (deckt Fees, blockiert keine Exits mehr)
- `take_profit_percent` 1.5 → **3.0**, `max_take_profit_percent` 0 → **14.0**
- `min_buy_score` −100 → **18.0** (Score-Filter war komplett aus)
- `pause_after_loss_streak_minutes` 0 → **60** — vorher waren Loss-Streak- und
  Drawdown-Bremse No-ops (Pause von 0 Sekunden)
- Trade-Cooldown 0 → **900 s** / global **300 s** (kein sofortiger Re-Entry nach Stop-Out)
- Shorting **aus**, bis Margin-Rollover-Gebühren im Netto-Gate modelliert sind

### 🔁 Robustheit
- Fixed-TP und Legacy-Trailing greifen jetzt als Fallback, wenn kein ATR
  berechnet werden konnte — vorher hätte eine Position dann *gar keinen* Exit gehabt
- `min_buy_score`, `min_short_score`, `max_take_profit_percent`,
  `min_net_sell_profit_pct` und `adaptive_take_profit` werden jetzt auch vom
  Hot-Reload erfasst (vorher nur beim Start)
- Debug-`print`/`logger.error` für `min_buy_score` entfernt

### 🧪 Tests
- Neu: `tests/test_exit_gating.py` — pinnt fest, dass Schutz-Exits mit Verlust
  schließen können und TAKE_PROFIT das Gate behält (25 Tests grün)
- `tests/test_sizing.py`: unvollständiger `APIMock` ergänzt (Test war vorher rot)

### ⚠️ Bekannt / offen
- `[daytrading]` wird **nur** vom Backtest gelesen, nicht vom Live-Bot (kommentiert)
- Indikatoren laufen live auf 30 s-Ticks, Backtests auf 60 m-Candles (P1)
- Margin-Rollover-Gebühren sind nirgends modelliert (P1)

## 2026-06-07 — Bugfixes & Stabilisierung

### 🔧 Bugfixes
- **fix(shorts): Shorts permanent blockiert bei deaktiviertem Regime-Filter**  
  `_is_risk_on_regime()` gab bei `enable_regime_filter = false` immer `True` zurück.  
  Shorts wurden nie geöffnet, weil `not True` → `False`.  
  Fix: Regime-Check nur bei aktiviertem Filter; sonst reichen *bearish Trend + negative Score*.
- **fix(trend): Doppelfilter MTF-Trend (SMA) vs. EMA-Trend behoben**  
  `_is_mtf_trend_bullish` (SMA20/50, lokaler Cache) und `_is_ema_trend_bullish` (EMA20/50, 1h-OHLC)  
  nutzten unterschiedliche Datenquellen → Deadlock: BUYs geblockt (EMA bearish), Shorts geblockt (MTF bullish).  
  Fix: Beide Pfade nutzen jetzt einheitlich EMA20/50 auf 1h-OHLC.

### ⚡ Optimierungen
- **Config vereinfacht** — Regime-Filter, Pyramiding, Partial-Exit, Break-Even, MTF-MACD,  
  Volume-Filter, Daily-Drawdown, Volatility-Targeting deaktiviert (Over-Engineering entfernt)
- **Take-Profit 3.0 %** (Long), **Short-TP 1.5 %** (Short) — ohne Stop-Loss  
  (Felix-Regel: nie bei Verlust schließen, nur bei echtem Nettogewinn)
- **4 Handelspaare**: XXBTZEUR, XETHZEUR, SOLEUR, XXRPZEUR
- **Trade-Cooldown 1 h** — hektisches Overtrading vermieden

### 🛡️ Ops
- **Watchdog-Cronjob** (alle 5 min): prüft Bot-Status, startet bei Crash neu
- **Daily-Report** (08:00 Uhr): Telegram-Nachricht mit Balance, Trades, P&L
- **Backup & Git-Commit** aller relevanten Dateien vor Änderungen

---

## 2026-06-03 — Early Short-Close & Systemd

- **feat(shorts): Early-Close auf BUY-Signal**  
  Bei einem bullishen Signal wird ein offener Short sofort geschlossen,  
  unabhängig vom aktuellen PnL — verhindert adverse Moves gegen die Position.
- **fix(systemd): Kraken-Bot Service** stabilisiert (stale lock cleanup)
- **docs(README)**: Features, Short-Logik, Risk-Management dokumentiert
- **push**: Branch `auto/per-symbol-dot-20260529`

---

## 2026-06-02 — Short-Logik & Airbag

- **fix(shorts)**: Open nur in bestätigtem Downtrend (bearish MTF + risk-off + negative score)
- **fix(shorts)**: Close nur bei echtem Nettogewinn nach Fees
- **fix(airbag)**: Airbag deaktiviert (Threshold 99 % — verhindert Fehlsells)
- **fix(pairs)**: Pair-Handling normalisiert (Groß-/Kleinschreibung)

---

## 2026-06-01 — Short-Close & Persistenz

- **fix(close)**: Short-Close nutzt `reduce_only` und rundet Volumes auf Exchange-Minimum
- **fix(persist)**: `most-recent-buy` persistiert bei Phantom-Positionen; Rate-Limit 60 s
- **chore(rebuild)**: `purchase_prices.json` aus Logs rekonstruiert nach Recovery-Run

---

## 2026-05-30 — DOTEUR & Helpers

- **test**: Fokussierte DOTEUR-Verify-Outputs
- **chore**: Helper-Skripte hinzugefügt

---

*Letzte Commits siehe [GitHub](https://github.com/felix-helleckes/TradingBot/commits/main)*

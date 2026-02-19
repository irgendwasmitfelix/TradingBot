#!/bin/bash
# Autosim runner: run 7/30/365 backtests against local TS and store results
set -euo pipefail
WORKDIR=/home/felix/TradingBot
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
SIM_OUTDIR=$WORKDIR/reports/sim
LOCAL_TS=$WORKDIR/local_ts
PY=$WORKDIR/venv/bin/python3
mkdir -p "$SIM_OUTDIR"
cd "$WORKDIR"
export KRAKEN_TS_DIR="$LOCAL_TS"
# run 3 backtests
for days in 7 30 365; do
  out="$SIM_OUTDIR/backtest_${days}d_${TIMESTAMP}.json"
  log="$SIM_OUTDIR/backtest_${days}d_${TIMESTAMP}.log"
  echo "Running backtest ${days}d -> ${out}"
  USE_LOCAL_TS=1 "$PY" scripts/backtest_v3_detailed.py --days $days --initial 200 --fee 0.0026 --slippage-bps 8 --execution-mode twap --twap-slices 3 --slippage-model volatility --out "$out" > "$log" 2>&1 || true
done
# Commit results (only JSONs)
git -C "$WORKDIR" add "$SIM_OUTDIR"/*.json || true
if ! git -C "$WORKDIR" diff --cached --quiet; then
  git -C "$WORKDIR" commit -m "chore(autosim): nightly backtest results $TIMESTAMP" || true
  git -C "$WORKDIR" push origin main || true
fi

# rotate old logs (keep 30)
find "$SIM_OUTDIR" -type f -name '*.log' -mtime +30 -delete || true

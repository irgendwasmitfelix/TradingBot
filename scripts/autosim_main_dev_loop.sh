#!/bin/bash
set -euo pipefail

# Autosim main loop with safety: lock, trap cleanup, rsync tuning, mount retries
BASE="/home/felix/TradingBot-dev"
PY="$BASE/venv/bin/python3"
# Prefer dev venv python if present, else fall back to main venv python
if [ -x "${PY}" ]; then
  : # use PY as set
else
  PY="/home/felix/TradingBot/venv/bin/python3"
fi
OUT_DIR="$BASE/reports/autosim"
NAS_OUT_DIR="/home/felix/mnt_nas_v2/Volume/kraken_research_data/autosim"
LOG="$OUT_DIR/autosim_loop.log"
LOCKFILE="/tmp/autosim_main_dev.lock"

mkdir -p "$OUT_DIR"

# Prevent parallel runs
exec 200>"$LOCKFILE" || { echo "Cannot open lockfile $LOCKFILE"; exit 1; }
flock -n 200 || { echo "Autosim already running; exiting"; exit 0; }

# Create cache dir early (so trap can clean it)
CACHE_DIR=$(mktemp -d /tmp/sim_ohlc_XXXX)

cleanup(){ rc=$?; if [ -n "$CACHE_DIR" ] && [ -d "$CACHE_DIR" ]; then rm -rf "$CACHE_DIR" || true; fi; exit $rc; }
trap cleanup EXIT INT TERM

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

# rotate log if >5MB
if [ -f "$LOG" ]; then
  sz=$(du -b "$LOG" | cut -f1)
  if [ "$sz" -gt $((5*1024*1024)) ]; then
    mv "$LOG" "$LOG.$(date +%Y%m%d%H%M%S)" || true
    gzip -9 "$LOG.$(date +%Y%m%d%H%M%S)" || true
  fi
fi

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

run_backtest(){
  local days="$1" out_json="$2"
  log "Running backtest for $days days..."
  # use a persistent cache dir under the dev worktree so backtest can read local OHLC
  CACHE_DIR="$BASE/data/ohlc_cache"
  mkdir -p "$CACHE_DIR"
  # clear previous cache to ensure fresh rsync
  rm -rf "$CACHE_DIR"/* || true

  # rsync with retries and limited bandwidth (avoid saturating network)
  RSYNC_SRC="/home/felix/mnt_nas_v2/Volume/kraken_research_data/"
  RSYNC_OPTS=( -az --partial --bwlimit=2000 --include='*/' --include='*.csv' --exclude='*' --timeout=60 )
  rr=0
  while [ $rr -lt 3 ]; do
    log "rsync attempt $((rr+1)) from NAS to $CACHE_DIR"
    rsync "${RSYNC_OPTS[@]}" "$RSYNC_SRC" "$CACHE_DIR" && break
    rr=$((rr+1))
    sleep $((rr * 5))
  done
  if [ $rr -ge 3 ]; then
    log "rsync failed after 3 attempts, attempting local copy fallback"
    cp -r "$RSYNC_SRC"* "$CACHE_DIR" || true
  fi

  # Use timeout + nice + ionice to limit resource impact. Kill if >6h.
  if command -v ionice >/dev/null 2>&1; then
    IONICE_CMD=(ionice -c2 -n7)
  else
    IONICE_CMD=()
  fi
  BACKTEST_CACHE_DIR="$CACHE_DIR" timeout --kill-after=1m 6h nice -n 10 "${IONICE_CMD[@]}" "$PY" "$BASE/scripts/backtest_v3_detailed.py" --days "$days" --out "$out_json" >>"$LOG" 2>&1 || log "backtest command failed or timed out"

  # cleanup cache (leftover will be removed by trap)
  if [ -d "$CACHE_DIR" ]; then
    # copy result to NAS with retry
    cp_attempts=0
    while [ $cp_attempts -lt 3 ]; do
      cp "$out_json" "$NAS_OUT_DIR/backtest_$(date +%Y%m%d_%H%M%S).json" && break
      cp_attempts=$((cp_attempts+1))
      sleep $((cp_attempts*3))
    done
    rm -rf "$CACHE_DIR" || true
  fi
}

main(){
  log "Autosim Cycle START"
  
  # Ensure NAS is mounted (retry on failure)
  if ! mountpoint -q "/home/felix/mnt_nas_v2"; then
    log "NAS not mounted. Attempting mount (up to 3 attempts)..."
    mtry=0
    while [ $mtry -lt 3 ]; do
      sudo mount -t cifs //192.168.178.1/fritz.nas /home/felix/mnt_nas_v2 -o credentials=/root/.smb/fritz_nas_creds,vers=3.0,iocharset=utf8,uid=1000,gid=1000,noserverino && break || true
      mtry=$((mtry+1))
      sleep $((mtry * 3))
    done
    if ! mountpoint -q "/home/felix/mnt_nas_v2"; then
      log "Warning: NAS mount failed after retries. Will continue, rsync will attempt fallback copy."
    else
      log "NAS mount succeeded"
    fi
  fi

  # Run backtest for 30 days
  run_backtest 30 "$OUT_DIR/latest_backtest.json"
  
  # Copy result to NAS for history
  cp "$OUT_DIR/latest_backtest.json" "$NAS_OUT_DIR/backtest_$(date +%Y%m%d_%H%M%S).json" || true
  
  log "Autosim Cycle DONE"
}

main

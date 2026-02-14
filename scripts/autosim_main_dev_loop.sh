#!/bin/bash
set -euo pipefail

BASE="/home/felix/TradingBot"
PY="$BASE/venv/bin/python3"
OUT_DIR="$BASE/reports/autosim"
NAS_OUT_DIR="/home/felix/mnt_nas_v2/Volume/kraken_research_data/autosim"
LOG="$OUT_DIR/autosim_loop.log"

mkdir -p "$OUT_DIR"
mkdir -p "$NAS_OUT_DIR" || true

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

run_backtest(){
  local days="$1" out_json="$2"
  log "Running backtest for $days days..."
  # Use the detailed backtest script pointing to NAS data
  KRAKEN_TS_DIR="/home/felix/mnt_nas_v2/Volume/kraken_research_data" USE_LOCAL_TS=1 \
  $PY "$BASE/scripts/backtest_v3_detailed.py" --days "$days" --out "$out_json" >>"$LOG" 2>&1
}

main(){
  log "Autosim Cycle START"
  
  # Ensure NAS is mounted
  if ! mountpoint -q "/home/felix/mnt_nas_v2"; then
    log "NAS not mounted. Attempting mount..."
    sudo mount -t cifs //192.168.178.1/fritz.nas /home/felix/mnt_nas_v2 -o credentials=/root/.smb/fritz_nas_creds,vers=3.0,iocharset=utf8,uid=1000,gid=1000 || true
  fi

  # Run backtest for 30 days
  run_backtest 30 "$OUT_DIR/latest_backtest.json"
  
  # Copy result to NAS for history
  cp "$OUT_DIR/latest_backtest.json" "$NAS_OUT_DIR/backtest_$(date +%Y%m%d_%H%M%S).json" || true
  
  log "Autosim Cycle DONE"
}

main

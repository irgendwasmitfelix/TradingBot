#!/usr/bin/env bash
set -euo pipefail

BASE="/home/felix/.openclaw/workspace/kraken_bot"
MAIN_WT="/home/felix/.openclaw/workspace/kraken_bot_worktrees/main"
DEV_WT="/home/felix/.openclaw/workspace/kraken_bot_worktrees/dev"
PY="$BASE/venv/bin/python"
OUT_DIR="/home/felix/.openclaw/workspace/kraken_bot/reports/autosim"
NAS_OUT_DIR="/mnt/fritz_nas/Volume/kraken_daten/autosim"
LOG="$OUT_DIR/autosim_loop.log"
mkdir -p "$OUT_DIR"
mkdir -p "$NAS_OUT_DIR" || true

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

run_branch(){
  local wt="$1" branch="$2" days="$3" out="$4"
  cd "$wt"
  git fetch origin >>"$LOG" 2>&1 || true
  git checkout -f "$branch" >>"$LOG" 2>&1
  git reset --hard "origin/$branch" >>"$LOG" 2>&1 || true
  # choose TS dir: 30d uses 2026 if it has recent data, otherwise fallback to Combined
  if [ "$days" -eq 30 ]; then
    # cutoff = 30 days ago epoch
    CUTOFF=$(date -d '30 days ago' +%s)
    NEWEST_TS=0
    if [ -d "/mnt/fritz_nas/Volume/kraken_daten/2026" ]; then
      NEWEST_FILE=$(find /mnt/fritz_nas/Volume/kraken_daten/2026 -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -n1 | awk '{print $1}') || true
      if [ -n "$NEWEST_FILE" ]; then
        NEWEST_TS=${NEWEST_FILE%%.*}
      fi
    fi
    if [ "$NEWEST_TS" -ge "$CUTOFF" ] && [ "$NEWEST_TS" -ne 0 ]; then
      KRAKEN_TS_DIR="/mnt/fritz_nas/Volume/kraken_daten/2026"
    else
      KRAKEN_TS_DIR="/mnt/fritz_nas/Volume/kraken_daten/TimeAndSales_Combined"
    fi
  else
    KRAKEN_TS_DIR="/mnt/fritz_nas/Volume/kraken_daten/TimeAndSales_Combined"
  fi

  USE_LOCAL_TS=1 KRAKEN_TS_DIR="$KRAKEN_TS_DIR" \
    $PY scripts/backtest_v3_detailed.py --days "$days" --initial 200 --out "$out" >>"$LOG" 2>&1
}

while true; do
  log "cycle start"
  run_branch "$MAIN_WT" main 30 "$OUT_DIR/main_30d.json"
  run_branch "$DEV_WT" dev 30 "$OUT_DIR/dev_30d.json"
  run_branch "$MAIN_WT" main 365 "$OUT_DIR/main_1y.json"
  run_branch "$DEV_WT" dev 365 "$OUT_DIR/dev_1y.json"

  $PY - <<'PY' >>"$LOG" 2>&1
import json, pathlib, datetime
out=pathlib.Path('/home/felix/.openclaw/workspace/kraken_bot/reports/autosim')
m30=json.loads((out/'main_30d.json').read_text())
d30=json.loads((out/'dev_30d.json').read_text())
m1y=json.loads((out/'main_1y.json').read_text())
d1y=json.loads((out/'dev_1y.json').read_text())

def better(a,b):
    return a.get('final_eur',0) > b.get('final_eur',0) and a.get('return_pct',-999) > b.get('return_pct',-999)

dev_better_30 = better(d30,m30)
dev_better_1y = better(d1y,m1y)
summary={
  'ts': datetime.datetime.utcnow().isoformat()+'Z',
  'main_final': m1y.get('final_eur'),
  'dev_final': d1y.get('final_eur'),
  'main_return_pct': m1y.get('return_pct'),
  'dev_return_pct': d1y.get('return_pct'),
  'main_winrate_pct': m1y.get('winrate_pct'),
  'dev_winrate_pct': d1y.get('winrate_pct'),
  'main_30d_final': m30.get('final_eur'),
  'dev_30d_final': d30.get('final_eur'),
  'main_30d_return_pct': m30.get('return_pct'),
  'dev_30d_return_pct': d30.get('return_pct'),
  'main_1y_final': m1y.get('final_eur'),
  'dev_1y_final': d1y.get('final_eur'),
  'main_1y_return_pct': m1y.get('return_pct'),
  'dev_1y_return_pct': d1y.get('return_pct'),
  'main_1y_max_drawdown_pct': m1y.get('max_drawdown_pct'),
  'dev_1y_max_drawdown_pct': d1y.get('max_drawdown_pct'),
  'dev_better_30d': dev_better_30,
  'dev_better_1y': dev_better_1y,
  'winner': 'dev' if (dev_better_30 and dev_better_1y) else 'main'
}
(out/'latest_compare.json').write_text(json.dumps(summary,indent=2))
print('compare', json.dumps(summary))
PY

  # best-effort sync to NAS (ignore stale-handle issues)
  cp -f "$OUT_DIR"/*.json "$NAS_OUT_DIR"/ 2>/dev/null || true

  log "cycle done; sleeping 900s"
  sleep 900
done

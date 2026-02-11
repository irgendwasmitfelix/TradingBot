#!/usr/bin/env bash
set -euo pipefail

BASE="/home/felix/.openclaw/workspace/kraken_bot"
MAIN_WT="/home/felix/.openclaw/workspace/kraken_bot_worktrees/main"
DEV_WT="/home/felix/.openclaw/workspace/kraken_bot_worktrees/dev"
PY="$BASE/venv/bin/python"
OUT_DIR="/home/felix/.openclaw/workspace/kraken_bot/reports/autosim"
NAS_OUT_DIR="/mnt/fritz_nas/Volume/kraken_research_data/autosim"
LOG="$OUT_DIR/autosim_loop.log"
mkdir -p "$OUT_DIR"
mkdir -p "$NAS_OUT_DIR" || true

log(){ echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

run_branch(){
  local wt="$1" branch="$2" out="$3"
  cd "$wt"
  git fetch origin >>"$LOG" 2>&1 || true
  git checkout -f "$branch" >>"$LOG" 2>&1
  git reset --hard "origin/$branch" >>"$LOG" 2>&1 || true
  $PY scripts/backtest_v3_detailed.py --days 30 --initial 200 --out "$out" >>"$LOG" 2>&1
}

while true; do
  log "cycle start"
  run_branch "$MAIN_WT" main "$OUT_DIR/main_30d.json"
  run_branch "$DEV_WT" dev "$OUT_DIR/dev_30d.json"

  $PY - <<'PY' >>"$LOG" 2>&1
import json, pathlib, datetime
out=pathlib.Path('/home/felix/.openclaw/workspace/kraken_bot/reports/autosim')
m=json.loads((out/'main_30d.json').read_text())
d=json.loads((out/'dev_30d.json').read_text())
summary={
  'ts': datetime.datetime.utcnow().isoformat()+'Z',
  'main_final': m.get('final_eur'),
  'dev_final': d.get('final_eur'),
  'main_return_pct': m.get('return_pct'),
  'dev_return_pct': d.get('return_pct'),
  'main_winrate_pct': m.get('winrate_pct'),
  'dev_winrate_pct': d.get('winrate_pct'),
  'winner': 'dev' if (d.get('final_eur',0)>m.get('final_eur',0) and d.get('return_pct',-999)>m.get('return_pct',-999)) else 'main'
}
(out/'latest_compare.json').write_text(json.dumps(summary,indent=2))
print('compare', json.dumps(summary))
PY

  # best-effort sync to NAS (ignore stale-handle issues)
  cp -f "$OUT_DIR"/*.json "$NAS_OUT_DIR"/ 2>/dev/null || true

  log "cycle done; sleeping 3600s"
  sleep 3600
done

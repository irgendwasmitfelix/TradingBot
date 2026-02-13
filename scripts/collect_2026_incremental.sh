#!/usr/bin/env bash
set -euo pipefail
BASE="/home/felix/.openclaw/workspace/kraken_bot"
OUT_DIR="/mnt/fritz_nas/Volume/kraken_daten/2026"
PY="$BASE/venv/bin/python3"
PAIRS=("XXBTZEUR" "XETHZEUR" "ADAEUR" "SOLEUR" "DOTEUR" "XXRPZEUR" "LINKEUR")
for pair in "${PAIRS[@]}"; do
  echo "Collecting $pair..."
  $PY $BASE/scripts/collect_kraken_history_incremental.py --pair "$pair" --out-dir "$OUT_DIR" --resume || true
done

echo "Done."
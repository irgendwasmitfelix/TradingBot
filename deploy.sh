#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="/home/felix/.openclaw/workspace/kraken_bot"
SERVICE_NAME="kraken-bot.service"
cd "$REPO_DIR"
TS=$(date +%Y%m%d%H%M%S)
# Ensure we are on main and have the latest origin/main
git fetch origin --quiet
git checkout main
git pull --ff-only origin main || git fetch origin && git reset --hard origin/main
# 3) Clean untracked build/data files (but keep tracked changes backed up)
#    (Untracked files are left alone to avoid data loss; adjust if you want rm -rf)
# 4) Restart service (try system unit first, fallback to --user)
if systemctl status "$SERVICE_NAME" >/dev/null 2>&1; then
  echo "Restarting system service: $SERVICE_NAME"
  sudo systemctl restart "$SERVICE_NAME"
  sudo systemctl status --no-pager "$SERVICE_NAME"
else
  echo "System service not found, trying user service"
  systemctl --user restart "$SERVICE_NAME"
  systemctl --user status --no-pager "$SERVICE_NAME"
fi

echo "DEPLOY COMPLETE: backup branch=backup/pre-deploy-${TS}"
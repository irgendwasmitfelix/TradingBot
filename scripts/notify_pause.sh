#!/bin/bash
# Simple notifier: if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID present, send a message
REASON="$1"
MSG="[TradingBot] Pause activated: $REASON"
LOG=/home/felix/TradingBot/logs/pause_notify.log
mkdir -p $(dirname "$LOG")
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="$TELEGRAM_CHAT_ID" -d text="$MSG" > /dev/null 2>&1 || true
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) SENT: $MSG" >> "$LOG"
else
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) NO-TELEGRAM: $MSG" >> "$LOG"
fi

#!/usr/bin/env bash
# notification-dispatcher.sh — Send Discord notification when Claude stops
# Fires on Stop event. Sends a summary to Discord via webhook.
# Requires: config/discord-webhook.json with {"webhook_url": "https://..."}

set -euo pipefail

INPUT=$(cat)

# Determine project directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
WEBHOOK_CONFIG="$PROJECT_DIR/config/discord-webhook.json"

if [[ ! -f "$WEBHOOK_CONFIG" ]]; then
  # No webhook configured — silent exit
  exit 0
fi

WEBHOOK_URL=$(python3 -c "
import json, sys
with open('$WEBHOOK_CONFIG') as f:
    d = json.load(f)
print(d.get('webhook_url', ''))
" 2>/dev/null || true)

if [[ -z "$WEBHOOK_URL" ]]; then
  exit 0
fi

PROJECT_NAME=$(basename "$PROJECT_DIR")
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"

# Extract stop reason if present
STOP_REASON=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('stop_reason', 'task_complete'))
except:
    print('task_complete')
" 2>/dev/null || echo "task_complete")

# Build Discord message
MESSAGE=$(python3 -c "
import json
msg = {
    'embeds': [{
        'title': 'Claude タスク完了',
        'color': 0x00ff00,
        'fields': [
            {'name': 'プロジェクト', 'value': '$PROJECT_NAME', 'inline': True},
            {'name': '完了時刻', 'value': '$TIMESTAMP', 'inline': True},
            {'name': 'セッション', 'value': '$SESSION_ID', 'inline': True},
            {'name': 'ステータス', 'value': '$STOP_REASON', 'inline': True},
        ],
        'footer': {'text': 'claude-framework notification-dispatcher'}
    }]
}
print(json.dumps(msg))
")

curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$MESSAGE" \
  > /dev/null 2>&1 || true

exit 0

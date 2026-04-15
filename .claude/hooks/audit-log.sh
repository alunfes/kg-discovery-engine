#!/usr/bin/env bash
# audit-log.sh — Log all tool executions for audit trail
# Fires on PostToolUse. Appends a JSON entry to logs/audit.log.
# Skips high-volume read-only tools to keep log manageable.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || true)

# Skip noisy read-only tools
SKIP_TOOLS=("Read" "Glob" "Grep" "mcp__Claude_Preview__preview_screenshot" "mcp__Claude_Preview__preview_logs")
for skip in "${SKIP_TOOLS[@]}"; do
  if [[ "$TOOL_NAME" == "$skip" ]]; then
    exit 0
  fi
done

# Determine log directory: prefer $CLAUDE_PROJECT_DIR, fall back to cwd
LOG_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/audit.log"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"

# Extract a summary of tool input (truncated)
TOOL_INPUT_SUMMARY=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    inp = d.get('tool_input', {})
    s = json.dumps(inp)
    print(s[:300] + ('...' if len(s) > 300 else ''))
except:
    print('parse-error')
" 2>/dev/null || echo "parse-error")

# Write log entry
echo "{\"ts\":\"$TIMESTAMP\",\"session\":\"$SESSION_ID\",\"tool\":\"$TOOL_NAME\",\"input\":$TOOL_INPUT_SUMMARY}" >> "$LOG_FILE"

exit 0

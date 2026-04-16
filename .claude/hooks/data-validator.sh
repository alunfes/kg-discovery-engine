#!/usr/bin/env bash
# data-validator.sh — Validate JSON files before they are written
# Fires on PreToolUse for Write/Edit tools.
# Checks that .json files contain valid JSON before writing.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || true)

if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
  exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
print(inp.get('file_path', inp.get('path', '')))" 2>/dev/null || true)

# Only validate .json files
if [[ "$FILE_PATH" != *.json ]]; then
  exit 0
fi

CONTENT=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
print(inp.get('content', inp.get('new_string', '')))" 2>/dev/null || true)

# For Edit tool, we can't fully validate the result without knowing the original
# For Write tool, validate the full content
if [[ "$TOOL_NAME" == "Write" ]]; then
  VALIDATION=$(echo "$CONTENT" | python3 -c "
import sys, json
try:
    json.load(sys.stdin)
    print('valid')
except json.JSONDecodeError as e:
    print(f'invalid: {e}')
" 2>/dev/null || echo "parse-error")

  if [[ "$VALIDATION" != "valid" ]]; then
    echo "WARNING: Writing invalid JSON to $FILE_PATH — $VALIDATION" >&2
    # Warn but don't block: the file might be a template with placeholders
  fi
fi

exit 0

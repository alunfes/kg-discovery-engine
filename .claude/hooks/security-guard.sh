#!/usr/bin/env bash
# security-guard.sh — Prompt injection defense for Claude Code hooks
# Fires on PreToolUse. Reads JSON from stdin, exits non-zero to block.
# Generic: works in any project directory.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || true)
TOOL_INPUT=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('tool_input','')))" 2>/dev/null || true)

# ── Dangerous command patterns ──────────────────────────────────────────────
DANGEROUS_PATTERNS=(
  "rm -rf /"
  "rm -rf ~"
  "dd if="
  "> /dev/sd"
  "mkfs\."
  ":(){ :|:& };:"
  "chmod -R 777 /"
  "chown -R.*/"
  "shutdown"
  "reboot"
  "halt"
  "poweroff"
  "kill -9 -1"
  "killall"
  "truncate -s 0"
)

if [[ "$TOOL_NAME" == "Bash" ]]; then
  CMD=$(echo "$TOOL_INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null || true)
  for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if echo "$CMD" | grep -qiE "$pattern"; then
      echo "BLOCKED: Dangerous command pattern detected: $pattern" >&2
      echo "{\"decision\": \"block\", \"reason\": \"Dangerous command pattern: $pattern\"}"
      exit 0
    fi
  done

  # Block direct access to sensitive files via Bash commands
  if echo "$CMD" | grep -qiE '(cat|less|more|head|tail|grep|awk|sed|strings|xxd|od|hexdump|base64)[[:space:]]+.*\.(env|pem|key|secret|password|credentials)'; then
    echo "BLOCKED: Sensitive file access via Bash" >&2
    echo "{\"decision\": \"block\", \"reason\": \"Sensitive file access blocked: $CMD\"}"
    exit 0
  fi

  # Block piping/redirecting secret files
  if echo "$CMD" | grep -qiE '<[[:space:]]*.*\.(env|pem|key|secret|password|credentials)'; then
    echo "BLOCKED: Sensitive file redirect via Bash" >&2
    echo "{\"decision\": \"block\", \"reason\": \"Sensitive file redirect blocked: $CMD\"}"
    exit 0
  fi

  # Block sourcing env files with potential exfiltration
  if echo "$CMD" | grep -qiE '(source|\.)[[:space:]]+.*\.(env|secret).*&&.*(echo|curl|wget|nc)'; then
    echo "BLOCKED: Env file sourcing with exfiltration attempt" >&2
    echo "{\"decision\": \"block\", \"reason\": \"Env file exfiltration blocked: $CMD\"}"
    exit 0
  fi
fi

# ── Prompt injection keywords in tool inputs ────────────────────────────────
INJECTION_PHRASES=(
  "ignore previous instructions"
  "ignore all previous"
  "disregard your instructions"
  "forget your instructions"
  "new instructions:"
  "system prompt:"
  "you are now"
  "act as if you"
  "pretend you are"
  "override safety"
  "bypass restrictions"
  "jailbreak"
  "DAN mode"
)

TOOL_INPUT_LOWER=$(echo "$TOOL_INPUT" | tr '[:upper:]' '[:lower:]')
for phrase in "${INJECTION_PHRASES[@]}"; do
  if echo "$TOOL_INPUT_LOWER" | grep -qF "$phrase"; then
    echo "BLOCKED: Possible prompt injection in tool input: $phrase" >&2
    echo "{\"decision\": \"block\", \"reason\": \"Possible prompt injection: $phrase\"}"
    exit 0
  fi
done

# ── Credential leak prevention ───────────────────────────────────────────────
# Block writing known secret patterns to files
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
  CONTENT=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('content', d.get('new_string', '')))" 2>/dev/null || true)

  SECRET_PATTERNS=(
    "sk-[A-Za-z0-9]{20,}"      # OpenAI / Anthropic keys
    "ghp_[A-Za-z0-9]{36}"       # GitHub PAT
    "xoxb-[A-Za-z0-9-]+"        # Slack bot token
    "AKIA[A-Z0-9]{16}"          # AWS access key
  )
  for pattern in "${SECRET_PATTERNS[@]}"; do
    if echo "$CONTENT" | grep -qE "$pattern"; then
      echo "WARNING: Possible credential in file write — pattern: $pattern" >&2
      # Warn but don't block (may be intentional in config templates)
    fi
  done
fi

exit 0

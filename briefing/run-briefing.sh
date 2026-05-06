#!/bin/zsh
# Daily WSJ·NYT briefing entrypoint.
# Invoked by launchd (com.user.daily-briefing.plist) every morning.

set -u
set -o pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"
PROMPT_FILE="$SCRIPT_DIR/prompt.md"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

DATE_KST="$(TZ='Asia/Seoul' date +%F)"
LOG_FILE="$LOG_DIR/${DATE_KST}.log"

exec > >(tee -a "$LOG_FILE") 2>&1
echo "===== $(TZ='Asia/Seoul' date '+%F %T %Z') start ====="

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE missing. Copy .env.example → .env and fill in tokens." >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${NYT_API_KEY:?NYT_API_KEY missing in .env}"
: "${SLACK_TOKEN:?SLACK_TOKEN missing in .env}"
: "${SLACK_CHANNEL:?SLACK_CHANNEL missing in .env}"

CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude || true)}"
if [[ -z "$CLAUDE_BIN" ]]; then
  echo "ERROR: claude CLI not found. Install: https://docs.anthropic.com/claude-code" >&2
  exit 3
fi
echo "claude binary: $CLAUDE_BIN"

# Headless run. --dangerously-skip-permissions because launchd has no TTY for prompts.
# We trust prompt.md (committed to repo). Tools used: WebFetch, Bash, Slack MCP.
"$CLAUDE_BIN" \
  --print \
  --output-format text \
  --dangerously-skip-permissions \
  "$(cat "$PROMPT_FILE")"

EXIT=$?
echo "===== $(TZ='Asia/Seoul' date '+%F %T %Z') end (exit=$EXIT) ====="
exit "$EXIT"

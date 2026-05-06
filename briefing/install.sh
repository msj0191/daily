#!/bin/zsh
# Installs com.user.daily-briefing.plist into ~/Library/LaunchAgents and loads it.
# Re-run safely; it unloads any existing job, replaces the plist, and reloads.

set -euo pipefail

SCRIPT_DIR="${0:A:h}"
REPO_PATH="${SCRIPT_DIR:h}"
LABEL="com.user.daily-briefing"
SRC_PLIST="$SCRIPT_DIR/$LABEL.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST_PLIST="$DEST_DIR/$LABEL.plist"

echo "→ Repo path: $REPO_PATH"
echo "→ Target:    $DEST_PLIST"

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
  echo
  echo "WARNING: $SCRIPT_DIR/.env not found."
  echo "  cp $SCRIPT_DIR/.env.example $SCRIPT_DIR/.env"
  echo "  # then edit and fill in NYT_API_KEY, SLACK_TOKEN, SLACK_CHANNEL"
  echo
fi

mkdir -p "$DEST_DIR"

# Unload any existing job (ignore failure on first install).
launchctl unload "$DEST_PLIST" 2>/dev/null || true

# Substitute __REPO_PATH__ token.
sed "s|__REPO_PATH__|$REPO_PATH|g" "$SRC_PLIST" > "$DEST_PLIST"

chmod +x "$SCRIPT_DIR/run-briefing.sh"
chmod 644 "$DEST_PLIST"

launchctl load "$DEST_PLIST"

echo
echo "Loaded. Schedule: every day 06:30 (system local time)."
echo
echo "Useful commands:"
echo "  launchctl list | grep $LABEL          # confirm loaded"
echo "  launchctl start $LABEL                # run once now"
echo "  tail -f $SCRIPT_DIR/logs/\$(date +%F).log  # follow today's log"
echo "  launchctl unload $DEST_PLIST          # disable"

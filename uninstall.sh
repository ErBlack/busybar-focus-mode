#!/bin/bash
set -euo pipefail

LABEL=app.busy.focus-mode

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -rf "$HOME/Library/LaunchAgents/$LABEL.plist" \
  "$HOME/Library/Application Support/busybar-focus-mode" \
  "$HOME/Library/Logs/busybar-focus-mode.log"
echo "Removed."

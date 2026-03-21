#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$REPO_DIR/venv/bin/python3"
DOPPLER_BIN="$(which doppler 2>/dev/null || echo '')"
PLIST_NAME="com.$(whoami).jobhunt"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

# ── Checks ────────────────────────────────────────────────────────────────────

if [ -z "$DOPPLER_BIN" ]; then
  echo "❌ Doppler CLI not found. Install it: https://docs.doppler.com/docs/install-cli"
  exit 1
fi

if [ ! -f "$VENV_PYTHON" ]; then
  echo "❌ venv not found. Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# ── Doppler project setup ─────────────────────────────────────────────────────

echo "🔑 Setting up Doppler..."
cd "$REPO_DIR"
doppler setup

# ── Generate plist ────────────────────────────────────────────────────────────

echo "📝 Generating launchd plist..."
cat > "$PLIST_DEST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$DOPPLER_BIN</string>
        <string>run</string>
        <string>--</string>
        <string>$VENV_PYTHON</string>
        <string>$REPO_DIR/main.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>
    <key>StandardOutPath</key>
    <string>$REPO_DIR/data/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO_DIR/data/launchd.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# ── Load plist ────────────────────────────────────────────────────────────────

# Unload first if already registered
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo ""
echo "✅ Done! Scraper will run daily at 8:30 AM."
echo ""
echo "Useful commands:"
echo "  launchctl start $PLIST_NAME       # trigger a manual run"
echo "  launchctl unload $PLIST_DEST      # disable the schedule"
echo "  tail -f $REPO_DIR/data/launchd.log  # view logs"

#!/bin/bash
# Install launchd job for automated CRM sync
#
# Usage:
#   ./install_launchd.sh install   # Install and load
#   ./install_launchd.sh uninstall # Unload and remove
#   ./install_launchd.sh status    # Check status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SOURCE="$SCRIPT_DIR/com.richmondgeneral.square-crm-sync.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.richmondgeneral.square-crm-sync.plist"
LABEL="com.richmondgeneral.square-crm-sync"

case "${1:-}" in
    install)
        echo "📦 Installing CRM sync launchd job..."
        
        # Check prerequisites
        if [ -z "${SQUARE_TOKEN:-}" ]; then
            echo "⚠️  WARNING: SQUARE_TOKEN not set in current shell"
            echo "    Make sure it's in ~/.zshrc for launchd to access"
        fi
        
        if ! pgrep -x mongod > /dev/null 2>&1; then
            echo "⚠️  WARNING: MongoDB not running"
            echo "    Start with: brew services start mongodb-community@8.0"
        fi
        
        # Copy plist to LaunchAgents
        mkdir -p "$HOME/Library/LaunchAgents"
        cp "$PLIST_SOURCE" "$PLIST_DEST"
        echo "✅ Copied plist to $PLIST_DEST"
        
        # Load the job
        launchctl load "$PLIST_DEST"
        echo "✅ Loaded launchd job: $LABEL"
        
        # Show next run time
        echo ""
        echo "🕐 Next run: Tomorrow at 6:00 AM"
        echo ""
        echo "To test manually:"
        echo "  $SCRIPT_DIR/auto_sync.sh --dry-run"
        echo ""
        echo "To check logs:"
        echo "  tail -f ~/.claude/skills/square-crm/logs/sync.log"
        ;;
        
    uninstall)
        echo "🗑️  Uninstalling CRM sync launchd job..."
        
        # Unload if loaded
        if launchctl list | grep -q "$LABEL"; then
            launchctl unload "$PLIST_DEST" 2>/dev/null || true
            echo "✅ Unloaded launchd job"
        fi
        
        # Remove plist
        if [ -f "$PLIST_DEST" ]; then
            rm "$PLIST_DEST"
            echo "✅ Removed plist from $PLIST_DEST"
        fi
        
        echo "✅ Uninstall complete"
        ;;
        
    status)
        echo "📊 CRM Sync Status"
        echo ""
        
        if [ -f "$PLIST_DEST" ]; then
            echo "✅ Plist installed: $PLIST_DEST"
        else
            echo "❌ Plist not installed"
        fi
        
        if launchctl list | grep -q "$LABEL"; then
            echo "✅ Job loaded: $LABEL"
        else
            echo "❌ Job not loaded"
        fi
        
        if pgrep -x mongod > /dev/null 2>&1; then
            echo "✅ MongoDB running"
        else
            echo "❌ MongoDB not running"
        fi
        
        if [ -n "${SQUARE_TOKEN:-}" ]; then
            echo "✅ SQUARE_TOKEN set in shell"
        else
            echo "⚠️  SQUARE_TOKEN not set (check ~/.zshrc)"
        fi
        
        echo ""
        echo "Recent sync log:"
        if [ -f ~/.claude/skills/square-crm/logs/sync.log ]; then
            tail -n 5 ~/.claude/skills/square-crm/logs/sync.log
        else
            echo "  (no log file yet)"
        fi
        ;;
        
    *)
        echo "Usage: $0 {install|uninstall|status}"
        echo ""
        echo "Commands:"
        echo "  install   - Install and load the launchd job"
        echo "  uninstall - Unload and remove the launchd job"
        echo "  status    - Show current status and logs"
        exit 1
        ;;
esac

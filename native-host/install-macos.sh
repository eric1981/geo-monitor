#!/bin/bash
# Geo Monitor Doubao Native Host installer for macOS
# Usage: bash install-macos.sh [extension_id]

set -e

EXT_ID="${1:-apdhnfnhlglgkcghoadlolfkglfpioid}"
MANIFEST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
MANIFEST_FILE="$MANIFEST_DIR/com.geo_monitor_doubao.json"
BRIDGE_SCRIPT="$(cd "$(dirname "$0")" && pwd)/doubao_bridge.py"
PYTHON="$(which python3)"

echo "=== Geo Monitor Doubao Native Host (macOS) ==="
echo "Extension ID: $EXT_ID"
echo "Python:       $PYTHON"
echo "Bridge:       $BRIDGE_SCRIPT"
echo ""

# Create manifest dir
mkdir -p "$MANIFEST_DIR"

# Create wrapper script
WRAPPER="$HOME/.geo-monitor/doubao_bridge.sh"
mkdir -p "$HOME/.geo-monitor"
cat > "$WRAPPER" << EOF
#!/bin/bash
exec $PYTHON $BRIDGE_SCRIPT
EOF
chmod +x "$WRAPPER"

# Create native messaging manifest
cat > "$MANIFEST_FILE" << EOF
{
  "name": "com.geo_monitor_doubao",
  "description": "Geo Monitor Doubao Bridge",
  "path": "$WRAPPER",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://$EXT_ID/"]
}
EOF

echo "✅ Installed:"
echo "   Manifest: $MANIFEST_FILE"
echo "   Wrapper:  $WRAPPER"
echo ""
echo "Next steps:"
echo "  1. Quit Chrome completely (Cmd+Q)"
echo "  2. Reopen Chrome"
echo "  3. Load doubao-ext/ as unpacked extension"
echo "  4. Refresh extension → check Service Worker for 'Native host connected'"

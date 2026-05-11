#!/usr/bin/env bash
# claude-secrets installer.
# Pipe this through bash:
#   curl -fsSL https://raw.githubusercontent.com/kzmsvm/claude-secrets/main/install.sh | bash
set -e

if [ "$(uname)" != "Darwin" ]; then
    echo "claude-secrets currently supports macOS only." >&2
    exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required (ships with macOS by default). Aborting." >&2
    exit 2
fi

REPO_DIR="${CS_INSTALL_DIR:-$HOME/.claude-secrets}"
BIN_DIR="${CS_BIN_DIR:-$HOME/.local/bin}"

# Clone or pull.
if [ -d "$REPO_DIR/.git" ]; then
    echo "→ updating $REPO_DIR"
    git -C "$REPO_DIR" pull --ff-only --quiet
else
    echo "→ cloning into $REPO_DIR"
    git clone --depth 1 https://github.com/kzmsvm/claude-secrets "$REPO_DIR" >/dev/null
fi

# Symlink the CLI.
mkdir -p "$BIN_DIR"
ln -sf "$REPO_DIR/bin/cs" "$BIN_DIR/cs"
chmod +x "$REPO_DIR/bin/cs"

echo
echo "✔ claude-secrets installed"
echo "  CLI:  $BIN_DIR/cs"
echo "  Repo: $REPO_DIR"
echo
if ! echo ":$PATH:" | grep -q ":$BIN_DIR:"; then
    echo "⚠  $BIN_DIR is not in your PATH. Add this to ~/.zshrc:"
    echo "    export PATH=\"$BIN_DIR:\$PATH\""
    echo
fi
echo "Quick start:"
echo "    cs add              # add your first secret via browser UI"
echo "    cs list             # show stored entries"
echo "    cs get <name>       # fetch one value"
echo "    source <(cs load)   # export everything as \$ENV_VAR in current shell"

# Skip the interactive prompts if installer is being piped or CS_NONINTERACTIVE=1.
if [ ! -t 0 ] || [ -n "${CS_NONINTERACTIVE:-}" ]; then
    echo
    echo "Non-interactive install — skipping setup questions."
    echo "Run these later if you want them:"
    echo "    cs autostart-install     # UI server runs at every login"
    echo "    claude mcp add cs-secrets python3 $REPO_DIR/mcp/cs-mcp-server.py"
    echo "    echo '[ -x \"\$(command -v cs)\" ] && source <(cs load) 2>/dev/null' >> ~/.zshrc"
    exit 0
fi

echo
echo "════════════════════════════════════════════════════════════════════"
echo "  Quick setup — 3 questions, hit Enter to accept the recommendation."
echo "════════════════════════════════════════════════════════════════════"
echo

# --- Q1: shell auto-load ---
echo "1) Auto-load secrets as environment variables in every new terminal?"
echo "   (Adds one line to ~/.zshrc. Without this you have to run"
echo "    \`source <(cs load)\` manually each time.)"
printf "   Enable [Y/n]? "
read -r ans_shell
case "${ans_shell:-y}" in
    y|Y|yes|YES|"")
        SHELL_RC="$HOME/.zshrc"
        [ -f "$HOME/.bashrc" ] && [ ! -f "$SHELL_RC" ] && SHELL_RC="$HOME/.bashrc"
        SNIPPET='[ -x "$(command -v cs)" ] && source <(cs load) 2>/dev/null  # claude-secrets'
        if grep -qF 'claude-secrets' "$SHELL_RC" 2>/dev/null; then
            echo "   ✔ already present in $SHELL_RC — skipping"
        else
            echo "" >> "$SHELL_RC"
            echo "$SNIPPET" >> "$SHELL_RC"
            echo "   ✔ added to $SHELL_RC (open a new terminal to activate)"
        fi
        ;;
    *)
        echo "   Skipped. Run manually any time: source <(cs load)"
        ;;
esac
echo

# --- Q2: MCP for Claude Code ---
echo "2) Install the MCP server in Claude Code?"
echo "   (Lets Claude fetch secrets without you pasting them. The model gets"
echo "    a temp-file path, never the literal token. Recommended if you use"
echo "    Claude Code daily.)"
printf "   Enable [Y/n]? "
read -r ans_mcp
case "${ans_mcp:-y}" in
    y|Y|yes|YES|"")
        if command -v claude >/dev/null 2>&1; then
            claude mcp add cs-secrets --scope user -- python3 "$REPO_DIR/mcp/cs-mcp-server.py" 2>&1 \
                | sed 's/^/   /'
        else
            echo "   ⚠  'claude' CLI not found — install Claude Code first, then run:"
            echo "       claude mcp add cs-secrets python3 $REPO_DIR/mcp/cs-mcp-server.py"
        fi
        ;;
    *)
        echo "   Skipped. Run later: claude mcp add cs-secrets python3 $REPO_DIR/mcp/cs-mcp-server.py"
        ;;
esac
echo

# --- Q3: UI autostart ---
echo "3) Run the browser UI at every login (LaunchAgent)?"
echo "   You only need this if you plan to ADD/EDIT secrets often and don't"
echo "   want to run \`cs add\` each time. For day-to-day use (cs get / load /"
echo "   the MCP server) you don't need the UI running."
echo "   Recommended: N — start it with \`cs add\` only when you need it."
printf "   Enable [y/N]? "
read -r ans_auto
case "${ans_auto:-n}" in
    y|Y|yes|YES)
        "$BIN_DIR/cs" autostart-install 2>&1 | sed 's/^/   /'
        ;;
    *)
        echo "   Skipped. Run \`cs add\` when you need the UI, \`cs autostart-install\`"
        echo "   any time if you want it always-on."
        ;;
esac
echo

echo "════════════════════════════════════════════════════════════════════"
echo "  Done. Reminders:"
echo "    • cs add               → open UI (only when adding/editing)"
echo "    • cs ui-status         → which port is the UI on?"
echo "    • cs ui-stop           → stop the UI when you're done"
echo "    • cs autostart-install → make UI always-on (later, if you want)"
echo "════════════════════════════════════════════════════════════════════"

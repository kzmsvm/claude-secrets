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
echo "Try it:"
echo "    cs add        # open the browser UI"
echo "    cs list       # show stored entries"
echo "    source <(cs load)   # export all as \$ENV_VAR"
echo

# --- Optional: autostart prompt ---
# Skip if installer is being piped (no tty), or CS_AUTOSTART env already set.
if [ -t 0 ] && [ -z "${CS_AUTOSTART:-}" ]; then
    printf "Enable autostart so the UI runs on every login (Y/n)? "
    read -r reply
else
    reply="${CS_AUTOSTART:-n}"
fi

case "${reply:-y}" in
    y|Y|yes|YES|"")
        "$BIN_DIR/cs" autostart-install
        ;;
    *)
        echo "Skipped autostart. Run 'cs autostart-install' any time to enable later."
        ;;
esac

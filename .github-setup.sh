#!/usr/bin/env bash
# One-shot script to configure the GitHub repo after the initial push.
# Run once: `bash .github-setup.sh` (or copy/paste lines manually).
# Requires: `gh` CLI, authenticated.
set -e

REPO="kzmsvm/claude-secrets"

# Repo description + homepage (shown on the GitHub front page + search results).
gh repo edit "$REPO" \
  --description "Encrypted secret store for Claude Code & other AI agents — macOS Keychain + browser UI. No SaaS, no subscription, no deps." \
  --homepage "https://github.com/$REPO"

# Topics (act like hashtags — drive discovery on github.com/topics/*).
for topic in \
    claude-code \
    secrets-management \
    ai-agents \
    password-manager \
    macos-keychain \
    developer-tools \
    mcp \
    indie-hackers \
    devtools \
    keychain ; do
    gh repo edit "$REPO" --add-topic "$topic"
done

echo "✔ description, homepage and topics set."
gh repo view "$REPO"

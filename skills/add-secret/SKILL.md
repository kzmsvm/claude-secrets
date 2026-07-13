---
name: add-secret
description: Add a new API key/token/secret to the claude-secrets Keychain vault WITHOUT the value ever passing through chat. Opens the local claude-secrets form inside the in-app Browser pane (or the user's browser) so the user pastes the secret there. Trigger on any phrasing like "add api key", "add secret", "store this token", "save this key", or when the user is about to paste an API key into chat.
---

# add-secret — store a secret via the local claude-secrets form

Goal: the user pastes the secret into the local claude-secrets web form (loopback-only, saves to the macOS Keychain). The secret value must NEVER appear in chat, in a Bash command, or in any file.

## Hard rules

- NEVER ask the user to type/paste the secret value in chat. If they paste one anyway, warn them it is now in the transcript and suggest rotating it; still store it via the form, not via chat.
- Never run `cs get <name>` or otherwise print secret values.
- Only ever show secret NAMES (from `cs list`), never values.

## Steps

1. **Start (or reuse) the UI server.** `CS_NO_BROWSER=1` stops it from popping an external browser tab — we open it in-app instead. (`cs` is normally on PATH; fall back to `~/.local/bin/cs`.)

   ```bash
   NS="${CS_NAMESPACE:-cs}"
   LOCK="$(python3 -c 'import tempfile;print(tempfile.gettempdir())')/claude-secrets-ui-$USER-$NS.lock"
   if [ -f "$LOCK" ] && kill -0 "$(python3 -c "import json;print(json.load(open('$LOCK'))['pid'])" 2>/dev/null)" 2>/dev/null; then
     echo "already running"
   else
     CS_NO_BROWSER=1 nohup cs add >/dev/null 2>&1 &
     sleep 1
   fi
   PORT=$(python3 -c "import json;print(json.load(open('$LOCK'))['port'])")
   echo "PORT=$PORT"
   ```

2. **Snapshot the current entries** so you can report what got added later:
   `cs list > "$TMPDIR/cs-before.txt"`

3. **Open the form inside the app**: call the in-app browser tool (e.g. `mcp__Claude_Browser__preview_start`) with `{"url": "http://127.0.0.1:<PORT>"}` — load the Browser tools via ToolSearch first if they are deferred. If no in-app browser is available in this client, tell the user to open `http://127.0.0.1:<PORT>` in their browser themselves.

4. **Tell the user** (in their language): paste the label + token into the form, hit "Save to Keychain", and say "done" when finished. Do NOT watch/screenshot the pane while they type — the secret would end up in the transcript as an image.

5. **When the user says done**:
   - `cs ui-stop` to kill the server.
   - Run `cs list`, diff against the snapshot, and confirm the new entry NAME(s) to the user.
   - Remind them the value is available as an env var in new shells (`source <(cs load)`, or automatically if their `~/.zshrc` has the autoload line), and that agents can use it at runtime via the cs MCP server (`cs_inject`) without ever seeing the value.

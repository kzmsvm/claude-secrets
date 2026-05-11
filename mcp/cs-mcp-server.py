#!/usr/bin/env python3
"""
Minimal MCP (Model Context Protocol) server that exposes claude-secrets
entries as tools an MCP-aware client (Claude Code, Cursor, etc.) can call
WITHOUT the secret value ever entering the chat context.

The model can call `cs_list` to discover available secret names, and
`cs_inject` to use a secret inside a follow-up command. `cs_inject` writes
the secret to a one-shot file under $TMPDIR with mode 0600, returns the
file path to the model, and self-deletes after the first read. The model
never sees the literal value.

Wire up in Claude Code via `claude mcp add`:
    claude mcp add cs-secrets python3 /path/to/cs-mcp-server.py

This file speaks the MCP protocol manually over stdio — no third-party
SDK needed. Pure Python stdlib.

CAVEAT: writing the secret to a temp file means it lives on disk for a
few seconds. Same exposure profile as `cs get` piping into another
command. If you need stricter handling (memory-only inject), pair this
with a proxying agent like Vaulted or secretless-ai.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

NAMESPACE = os.environ.get("CS_NAMESPACE", "cs")
USER = os.environ.get("USER") or os.environ.get("USERNAME") or "user"

# ---------- Keychain helpers (shared with the UI) ----------

def kc_list() -> list[str]:
    p = subprocess.run(["security", "dump-keychain"], capture_output=True, text=True)
    items = set()
    for line in p.stdout.splitlines():
        m = re.search(r'"svce".*"(' + re.escape(NAMESPACE) + r'-[^"]+)"', line)
        if m:
            items.add(m.group(1))
    return sorted(items)

def _decode_hex_if_needed(raw: str) -> str:
    """The `security` CLI returns hex when a value isn't pure ASCII
    (em-dashes, unicode, binary). Detect and decode back to a string."""
    s = raw.rstrip("\n")
    if len(s) > 4 and len(s) % 2 == 0 and all(c in "0123456789abcdef" for c in s):
        try:
            return bytes.fromhex(s).decode("utf-8", errors="replace")
        except Exception:
            return s
    return s

def kc_get(name: str) -> str | None:
    full = name if name.startswith(f"{NAMESPACE}-") else f"{NAMESPACE}-{name}"
    p = subprocess.run(
        ["security", "find-generic-password", "-a", USER, "-s", full, "-w"],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        return None
    return _decode_hex_if_needed(p.stdout)

def kc_note(name: str) -> str | None:
    """Companion '<name>__meta' entry holds the free-form description an
    AI agent can read with `cs_describe` before deciding what to do."""
    base = name[len(NAMESPACE) + 1:] if name.startswith(f"{NAMESPACE}-") else name
    return kc_get(f"{base}__meta")

# ---------- MCP protocol ----------

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "claude-secrets", "version": "0.1.0"}

TOOLS = [
    {
        "name": "cs_list",
        "description": (
            "List the names of secrets stored under the current namespace. "
            "Returns short names (without the namespace prefix). The model can "
            "decide which secret to inject; the value itself is never returned. "
            "Entries ending in '__meta' are companion description notes — "
            "use `cs_describe` to read them rather than listing them as secrets."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "cs_describe",
        "description": (
            "Return metadata about a stored secret WITHOUT revealing the value. "
            "Always call this BEFORE `cs_inject` so you know what kind of "
            "credential it is (FTP password vs API token vs SSH key vs JSON "
            "config blob) and how to use it (host, username, endpoint, etc.). "
            "Returns the value length and any free-form note the user attached. "
            "If the description is missing, the value's shape is the only hint "
            "you have — peek with care."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short name of the secret (without `cs-` prefix)."},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cs_inject",
        "description": (
            "Materialize a stored secret into a short-lived 0600 temp file and "
            "return that file's path. Useful for piping the value into a CLI "
            "without putting it in chat context. The file self-deletes after the "
            "TTL (default 5 minutes — enough to compose and run a command). "
            "RECOMMENDED: call `cs_describe` first to know what to do with the value. "
            "After you're done, call `cs_release(path)` to delete the file immediately "
            "instead of waiting out the TTL."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short name of the secret (without `cs-` prefix)."},
                "ttl_seconds": {"type": "integer", "description": "Optional self-delete delay; default 300 (5 min), min 10, max 3600.", "minimum": 10, "maximum": 3600},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cs_release",
        "description": (
            "Explicitly delete a temp file produced by `cs_inject`, so the secret "
            "doesn't linger on disk for the rest of its TTL. Safe to call multiple "
            "times — a missing file is not an error."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path returned by a previous cs_inject call."},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
]

# ---------- Tool implementations ----------

DEFAULT_INJECT_TTL = int(os.environ.get("CS_INJECT_TTL", "300"))  # 5 minutes default

def _ttl_unlink(path: str, ttl: float = DEFAULT_INJECT_TTL) -> None:
    def _kill():
        time.sleep(ttl)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    threading.Thread(target=_kill, daemon=True).start()

def tool_cs_list(_args: dict) -> dict:
    # Hide __meta sibling entries from the listing — they're descriptions,
    # not secrets, and cs_describe is the right way to read them.
    items = [
        s[len(NAMESPACE) + 1:] for s in kc_list()
        if not s.endswith("__meta")
    ]
    return {"content": [{"type": "text", "text": "\n".join(items) if items else "(no entries)"}]}

def tool_cs_describe(args: dict) -> dict:
    name = (args.get("name") or "").strip()
    if not name:
        return {"content": [{"type": "text", "text": "error: `name` required"}], "isError": True}
    value = kc_get(name)
    if value is None:
        return {"content": [{"type": "text", "text": f"error: no secret named '{name}'"}], "isError": True}
    note = kc_note(name) or "(no note attached — only the raw value is stored)"
    return {
        "content": [{
            "type": "text",
            "text": (
                f"name:         {NAMESPACE}-{name}\n"
                f"value_length: {len(value)} chars\n"
                f"note:\n"
                f"  {note}\n"
                f"\n"
                f"The value itself is NOT in this response — call `cs_inject` "
                f"once you know how to use it."
            ),
        }]
    }

def tool_cs_inject(args: dict) -> dict:
    name = (args.get("name") or "").strip()
    if not name:
        return {"content": [{"type": "text", "text": "error: `name` required"}], "isError": True}
    raw_ttl = args.get("ttl_seconds", DEFAULT_INJECT_TTL)
    try:
        ttl = max(10, min(3600, int(raw_ttl)))
    except Exception:
        ttl = DEFAULT_INJECT_TTL
    value = kc_get(name)
    if value is None:
        return {"content": [{"type": "text", "text": f"error: no secret named '{name}'"}], "isError": True}
    fd, path = tempfile.mkstemp(prefix=f"cs-{name}-", suffix=".secret")
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, value.encode("utf-8"))
    finally:
        os.close(fd)
    _ttl_unlink(path, ttl=ttl)
    return {
        "content": [{
            "type": "text",
            "text": (
                f"Secret materialized to a 0600 file:\n  {path}\n\n"
                f"Self-deletes in {ttl}s (or call `cs_release` to delete it now).\n"
                f"Example uses:\n"
                f"  curl -H \"Authorization: Bearer $(cat '{path}')\" https://api.example.com/...\n"
                f"  rsync -e \"sshpass -f '{path}' ssh -p 22\" ... user@host:/path/\n"
                f"  export FOO=$(cat '{path}'); ...; rm -f '{path}'"
            ),
        }]
    }

def tool_cs_release(args: dict) -> dict:
    path = (args.get("path") or "").strip()
    if not path:
        return {"content": [{"type": "text", "text": "error: `path` required"}], "isError": True}
    # Only allow deleting files we created (TMPDIR + our prefix).
    if not (path.startswith(tempfile.gettempdir()) and "/cs-" in path and path.endswith(".secret")):
        return {"content": [{"type": "text", "text": f"error: refusing to delete {path} — not a cs_inject path"}], "isError": True}
    try:
        os.unlink(path)
        return {"content": [{"type": "text", "text": f"deleted: {path}"}]}
    except FileNotFoundError:
        return {"content": [{"type": "text", "text": f"already gone: {path}"}]}
    except Exception as ex:
        return {"content": [{"type": "text", "text": f"error: {ex}"}], "isError": True}

TOOL_DISPATCH = {
    "cs_list":     tool_cs_list,
    "cs_describe": tool_cs_describe,
    "cs_inject":   tool_cs_inject,
    "cs_release":  tool_cs_release,
}

# ---------- JSON-RPC over stdio ----------

def reply(req_id, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

def handle(req: dict):
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {}) or {}

    if method == "initialize":
        reply(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    elif method == "tools/list":
        reply(req_id, {"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        impl = TOOL_DISPATCH.get(name)
        if not impl:
            reply(req_id, error={"code": -32601, "message": f"unknown tool: {name}"})
            return
        try:
            reply(req_id, impl(args))
        except Exception as ex:
            reply(req_id, error={"code": -32000, "message": str(ex)})
    elif method == "ping":
        reply(req_id, {})
    elif method.startswith("notifications/"):
        # Notifications don't get a reply.
        pass
    else:
        if req_id is not None:
            reply(req_id, error={"code": -32601, "message": f"method not found: {method}"})

def main() -> None:
    if sys.platform != "darwin":
        sys.stderr.write("claude-secrets MCP: macOS only (uses Keychain).\n")
        sys.exit(2)
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except Exception as ex:
            sys.stderr.write(f"bad JSON: {ex}\n")
            continue
        handle(req)

if __name__ == "__main__":
    main()

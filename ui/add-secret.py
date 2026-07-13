#!/usr/bin/env python3
"""
Minimal localhost-only UI for claude-secrets.

Opens http://127.0.0.1:9876 with a form. User picks the secret type
(single value, OAuth client_id+client_secret, username+password,
or a custom n-field group) and saves into the macOS login Keychain
under the `cs-*` namespace.

No external dependencies. Pure stdlib. Single file.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import webbrowser

NAMESPACE = os.environ.get("CS_NAMESPACE", "cs")
PORT = int(os.environ.get("CS_PORT", "9876"))
USER = os.environ.get("USER") or os.environ.get("USERNAME") or "user"

# ---------- Keychain helpers ----------

def _security(*args: str) -> tuple[int, str, str]:
    p = subprocess.run(["security", *args], capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def kc_set(name: str, value: str) -> None:
    rc, _, err = _security(
        "add-generic-password", "-U", "-a", USER, "-s", f"{NAMESPACE}-{name}", "-w", value
    )
    if rc != 0:
        raise RuntimeError(err.strip() or "security add-generic-password failed")

def kc_list() -> list[str]:
    p = subprocess.run(["security", "dump-keychain"], capture_output=True, text=True)
    items = set()
    for line in p.stdout.splitlines():
        m = re.search(r'"svce".*"(' + re.escape(NAMESPACE) + r'-[^"]+)"', line)
        if m:
            items.add(m.group(1))
    return sorted(items)

def kc_rm(name: str) -> None:
    _security("delete-generic-password", "-s", f"{NAMESPACE}-{name}")

def _decode_hex_if_needed(raw: str) -> str:
    """`security` returns hex when a value isn't pure ASCII (em-dash, unicode)."""
    s = raw.rstrip("\n")
    if len(s) > 4 and len(s) % 2 == 0 and all(c in "0123456789abcdef" for c in s):
        try:
            return bytes.fromhex(s).decode("utf-8", errors="replace")
        except Exception:
            return s
    return s

def kc_get_for(name: str) -> str | None:
    """Read a value from the Keychain by bare name (without namespace prefix)."""
    p = subprocess.run(
        ["security", "find-generic-password", "-a", USER, "-s", f"{NAMESPACE}-{name}", "-w"],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        return None
    return _decode_hex_if_needed(p.stdout)

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

# ---------- HTML ----------

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>claude-secrets</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
       margin: 0; padding: 24px; background: #0b1220; color: #e2e8f0; line-height: 1.5; }
.container { max-width: 560px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
.subtitle { color: #94a3b8; margin: 0 0 24px; font-size: 13px; }
.card { background: #111a2e; border: 1px solid #1e293b; border-radius: 12px; padding: 18px; margin: 0 0 16px; }
label { display: block; font-size: 12px; color: #94a3b8; text-transform: uppercase;
        letter-spacing: 0.04em; margin: 12px 0 4px; font-weight: 600; }
input, textarea, select { width: 100%; padding: 10px 12px; background: #0b1220; color: #e2e8f0;
        border: 1px solid #334155; border-radius: 8px; font: inherit; }
input:focus, textarea:focus, select:focus { outline: none; border-color: #38bdf8; }
.field-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.field-row input[type=text] { flex: 1; max-width: 180px; }
.field-row input[type=password] { flex: 2; }
.field-row button.del { flex: 0 0 auto; padding: 6px 10px; background: #1e293b; white-space: nowrap; }
button { background: #38bdf8; color: #0b1220; border: 0; border-radius: 8px;
         padding: 10px 16px; font: inherit; font-weight: 600; cursor: pointer; }
button:hover { background: #0ea5e9; }
button.secondary { background: #1e293b; color: #e2e8f0; }
button.secondary:hover { background: #334155; }
.actions { display: flex; gap: 8px; margin-top: 16px; }
.actions button { flex: 0 0 auto; white-space: nowrap; }
.hint { color: #64748b; font-size: 12px; margin-top: 4px; }
.list { list-style: none; padding: 0; margin: 0; }
.list li { display: flex; justify-content: space-between; align-items: center;
           padding: 8px 0; border-bottom: 1px solid #1e293b; font-size: 13px; }
.list li:last-child { border-bottom: 0; }
.list code { background: #0b1220; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
.list .actions-cell { display: flex; gap: 6px; }
.list .del-btn { padding: 4px 10px; font-size: 12px; background: #1e293b; color: #f87171; }
.list .edit-btn { padding: 4px 10px; font-size: 12px; background: #1e293b; color: #38bdf8; }
.edit-form { display: flex; gap: 6px; flex: 1; align-items: center; }
.edit-form input { flex: 1; padding: 6px 8px; font-size: 12px; }
.edit-form button { padding: 4px 10px; font-size: 12px; }
.edit-form .save-btn { background: #38bdf8; color: #0b1220; }
.edit-form .cancel-btn { background: #1e293b; color: #e2e8f0; }
.empty { color: #64748b; }
.toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
         background: #334155; color: #e2e8f0; padding: 10px 16px; border-radius: 8px;
         opacity: 0; transition: opacity .2s; pointer-events: none; }
.toast.show { opacity: 1; }
.preset-btns { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0 0; }
.preset-btns button { padding: 4px 10px; font-size: 12px; background: #1e293b; color: #e2e8f0; }
.preset-btns button.active { background: #38bdf8; color: #0b1220; }
</style>
</head>
<body>
<div class="container">
  <h1>claude-secrets</h1>
  <p class="subtitle">Encrypted secrets in your macOS Keychain. Used by any shell or AI agent via <code>cs load</code> — Claude Code, Aider, Cursor, deploy scripts, MCP plugins, anything.</p>

  <div class="card">
    <label for="name">What is this secret for? (label)</label>
    <input id="name" type="text" placeholder="e.g. github-token, hostinger-api, stripe-prod" autocomplete="off">
    <div class="hint">Used as the Keychain entry name. Auto-slugified.</div>

    <label>Type</label>
    <div class="preset-btns" id="preset-btns">
      <button type="button" data-preset="single" class="active">Single value</button>
      <button type="button" data-preset="oauth">Client ID + Secret</button>
      <button type="button" data-preset="userpass">Username + Password</button>
      <button type="button" data-preset="custom">Custom fields</button>
    </div>

    <div id="fields"></div>

    <label for="note" style="margin-top:14px;">Note / description <span style="text-transform:none; color:#64748b; font-weight:400;">(optional but recommended)</span></label>
    <textarea id="note" rows="3" placeholder="What kind of credential is this? e.g. 'FTP password for ftp.example.com, user backup. For nightly downloads.' or 'OpenAI API key — Bearer auth. Used by openai-python SDK.'" style="font-family:inherit; resize:vertical;"></textarea>
    <div class="hint">An AI agent reads this BEFORE injecting the value so it knows how to use the credential. Plain English is fine.</div>

    <div class="actions">
      <button id="save" type="button">Save to Keychain</button>
      <button class="secondary" id="cancel" type="button">Clear</button>
    </div>
  </div>

  <div class="card">
    <label>Stored entries</label>
    <ul class="list" id="list"></ul>
  </div>

  <p class="subtitle">Tip: run <code>cs load</code> from a shell to export every entry as <code>$ENV_VAR</code>.</p>
</div>
<div class="toast" id="toast"></div>

<script>
'use strict';
let preset = 'single';
const fieldsEl = document.getElementById('fields');
const nameEl   = document.getElementById('name');
const listEl   = document.getElementById('list');

function el(tag, attrs, children) {
  const e = document.createElement(tag);
  if (attrs) for (const k of Object.keys(attrs)) {
    if (k === 'dataset') for (const dk of Object.keys(attrs.dataset)) e.dataset[dk] = attrs.dataset[dk];
    else if (k === 'on') for (const ek of Object.keys(attrs.on)) e.addEventListener(ek, attrs.on[ek]);
    else if (k === 'class') e.className = attrs[k];
    else if (k === 'text') e.textContent = attrs[k];
    else e.setAttribute(k, attrs[k]);
  }
  if (children) for (const c of children) e.appendChild(c);
  return e;
}

function setPreset(p) {
  preset = p;
  for (const b of document.querySelectorAll('.preset-btns button')) {
    b.classList.toggle('active', b.dataset.preset === p);
  }
  renderFields();
}

function renderFields() {
  fieldsEl.replaceChildren();
  if (preset === 'single')        addField('value', 'password', 'Token / key / secret');
  else if (preset === 'oauth')   { addField('client-id', 'text', 'Client ID'); addField('client-secret', 'password', 'Client Secret'); }
  else if (preset === 'userpass'){ addField('username', 'text', 'Username'); addField('password', 'password', 'Password'); }
  else if (preset === 'custom')  { addCustomRow(); addCustomBtn(); }
}

function addField(suffix, type, placeholder) {
  const sufInput = el('input', { type: 'text', value: suffix, readonly: '' });
  const valInput = el('input', { type: type, placeholder: placeholder, autocomplete: 'off' });
  valInput.dataset.value = '1';
  const row = el('div', { class: 'field-row', dataset: { suffix } }, [sufInput, valInput]);
  fieldsEl.appendChild(row);
}

function addCustomRow() {
  const sufInput = el('input', { type: 'text', placeholder: 'field suffix (e.g. token)' });
  sufInput.dataset.suffix = '1';
  const valInput = el('input', { type: 'password', placeholder: 'value', autocomplete: 'off' });
  valInput.dataset.value = '1';
  const delBtn = el('button', { type: 'button', class: 'del', text: '×' });
  const row = el('div', { class: 'field-row' }, [sufInput, valInput, delBtn]);
  delBtn.addEventListener('click', () => row.remove());
  fieldsEl.appendChild(row);
}

function addCustomBtn() {
  const btn = el('button', { type: 'button', class: 'secondary', text: '+ add field',
    on: { click: () => { addCustomRow(); fieldsEl.appendChild(btn); } } });
  btn.style.marginTop = '6px';
  fieldsEl.appendChild(btn);
}

for (const b of document.querySelectorAll('.preset-btns button')) {
  b.addEventListener('click', () => setPreset(b.dataset.preset));
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1800);
}

document.getElementById('save').addEventListener('click', async () => {
  const name = nameEl.value.trim();
  if (!name) { toast('Label is required'); return; }
  const entries = [];
  for (const row of fieldsEl.querySelectorAll('.field-row')) {
    const sxNode = row.querySelector('[data-suffix]');
    const sx = (row.dataset.suffix || (sxNode ? sxNode.value : '')).trim();
    const valNode = row.querySelector('[data-value]');
    const val = valNode ? valNode.value : '';
    if (!val) continue;
    entries.push({ suffix: sx, value: val });
  }
  if (entries.length === 0) { toast('At least one value is required'); return; }
  const r = await fetch('/save', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, entries }) });
  const j = await r.json();
  if (j.ok) {
    toast('Saved ' + j.stored.length + ' item' + (j.stored.length === 1 ? '' : 's'));
    nameEl.value = '';
    renderFields();
    refreshList();
  } else {
    toast('Error: ' + (j.error || 'unknown'));
  }
});

document.getElementById('cancel').addEventListener('click', () => {
  nameEl.value = '';
  renderFields();
});

function renderListRow(item) {
  const li = el('li');
  const code = el('code', { text: item });
  const editBtn = el('button', { class: 'edit-btn', text: 'Edit' });
  const delBtn  = el('button', { class: 'del-btn', text: 'Delete' });
  const actions = el('div', { class: 'actions-cell' }, [editBtn, delBtn]);

  editBtn.addEventListener('click', () => {
    li.replaceChildren();
    const codeInline = el('code', { text: item });
    const valInput   = el('input', { type: 'password', placeholder: 'New value (leave blank to keep current)', autocomplete: 'off' });
    const saveBtn    = el('button', { class: 'save-btn', text: 'Save' });
    const cancelBtn  = el('button', { class: 'cancel-btn', text: 'Cancel' });
    const form = el('div', { class: 'edit-form' }, [codeInline, valInput, saveBtn, cancelBtn]);
    li.appendChild(form);
    valInput.focus();
    saveBtn.addEventListener('click', async () => {
      const v = valInput.value;
      if (!v) { toast('No change (blank value)'); return; }
      const r = await fetch('/update', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: item, value: v }) });
      const j = await r.json();
      if (j.ok) { toast('Updated ' + item); refreshList(); }
      else      { toast('Error: ' + (j.error || 'unknown')); }
    });
    cancelBtn.addEventListener('click', () => {
      li.replaceChildren(code, actions);
    });
    valInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter')  saveBtn.click();
      if (e.key === 'Escape') cancelBtn.click();
    });
  });

  delBtn.addEventListener('click', async () => {
    if (!confirm('Delete ' + item + '?')) return;
    await fetch('/rm', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: item }) });
    toast('Deleted ' + item);
    refreshList();
  });

  li.appendChild(code);
  li.appendChild(actions);
  return li;
}

async function refreshList() {
  const r = await fetch('/list');
  const j = await r.json();
  listEl.replaceChildren();
  if (!j.items.length) {
    listEl.appendChild(el('li', { class: 'empty', text: 'No entries yet.' }));
    return;
  }
  for (const item of j.items) listEl.appendChild(renderListRow(item));
}

renderFields();
refreshList();
nameEl.focus();
</script>
</body>
</html>
"""

# ---------- HTTP server ----------

class Handler(http.server.BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _refuse_remote(self) -> bool:
        # Loopback-only — defense in depth (server already binds 127.0.0.1).
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self.send_error(403, "loopback only")
            return True
        return False

    def do_GET(self) -> None:
        if self._refuse_remote():
            return
        if self.path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/list":
            # Hide '__meta' sibling entries — they're notes for the model, not secrets.
            # The frontend reads them via /note instead.
            items = [
                s[len(NAMESPACE) + 1:] for s in kc_list()
                if not s.endswith("__meta")
            ]
            self._json(200, {"items": items})

        elif self.path.startswith("/note/"):
            # GET /note/<bare-name>  → returns the attached note, if any.
            name = self.path[len("/note/"):]
            note_value = kc_get_for(f"{name}__meta")
            self._json(200, {"name": name, "note": note_value or ""})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self._refuse_remote():
            return
        n = int(self.headers.get("Content-Length", "0") or "0")
        if n <= 0 or n > 1_000_000:
            self._json(400, {"ok": False, "error": "bad length"}); return
        try:
            data = json.loads(self.rfile.read(n))
        except Exception as e:
            self._json(400, {"ok": False, "error": f"bad json: {e}"}); return

        if self.path == "/save":
            name = slugify(str(data.get("name", "")))
            entries = data.get("entries", []) or []
            note  = str(data.get("note", "")).strip()
            if not name or not entries:
                self._json(400, {"ok": False, "error": "name and entries required"}); return
            stored: list[str] = []
            try:
                for e in entries:
                    sx = slugify(str(e.get("suffix", "value")))
                    val = str(e.get("value", ""))
                    if not val:
                        continue
                    full = name if sx in ("value", "") else f"{name}-{sx}"
                    kc_set(full, val)
                    stored.append(full)
                # Companion __meta entry for free-form description.
                if note:
                    kc_set(f"{name}__meta", note)
                    stored.append(f"{name}__meta (note)")
                self._json(200, {"ok": True, "stored": stored})
            except Exception as ex:
                self._json(500, {"ok": False, "error": str(ex)})

        elif self.path == "/note":
            # POST /note  body: {"name": "...", "note": "..."}
            name = str(data.get("name", "")).strip()
            note = str(data.get("note", ""))
            if not name:
                self._json(400, {"ok": False, "error": "name required"}); return
            # Strip prefix if caller passed full keychain name.
            bare = name[len(NAMESPACE) + 1:] if name.startswith(f"{NAMESPACE}-") else name
            try:
                if note:
                    kc_set(f"{bare}__meta", note)
                else:
                    kc_rm(f"{bare}__meta")
                self._json(200, {"ok": True})
            except Exception as ex:
                self._json(500, {"ok": False, "error": str(ex)})
        elif self.path == "/rm":
            full = str(data.get("name", "")).strip()
            if not full:
                self._json(400, {"ok": False, "error": "name required"}); return
            # Accept both bare ("ui-roundtrip") and full ("cs-ui-roundtrip") forms.
            bare = full[len(NAMESPACE) + 1:] if full.startswith(f"{NAMESPACE}-") else full
            kc_rm(bare)
            self._json(200, {"ok": True})

        elif self.path == "/update":
            full = str(data.get("name", "")).strip()
            value = str(data.get("value", ""))
            if not full or not value:
                self._json(400, {"ok": False, "error": "name and value required"}); return
            # The list returns full Keychain service names like "cs-github-token".
            # kc_set re-prepends the namespace, so strip it if present.
            bare = full[len(NAMESPACE) + 1:] if full.startswith(f"{NAMESPACE}-") else full
            try:
                kc_set(bare, value)
                self._json(200, {"ok": True, "updated": f"{NAMESPACE}-{bare}"})
            except Exception as ex:
                self._json(500, {"ok": False, "error": str(ex)})
        else:
            self.send_error(404)

    def log_message(self, fmt, *args) -> None:  # quiet — only print errors
        if "200" not in fmt % args:
            sys.stderr.write("[cs] %s\n" % (fmt % args))


def find_free_port(start: int) -> int:
    """Pin to the requested port — fail loudly if it's busy instead of silently
    drifting up. Drifting confuses users who bookmarked the original port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", start))
            return start
        except OSError as e:
            raise RuntimeError(
                f"port {start} is already in use. Something else (or an orphan UI) "
                f"is listening there. Run `cs ui-status` to see what's up, "
                f"or `lsof -i :{start} -P -n` to find the culprit. "
                f"Set CS_PORT=<other> to use a different port."
            ) from e


def _lockfile() -> str:
    """One lockfile per (user, namespace) so multiple namespaces can each have a UI."""
    return os.path.join(
        tempfile.gettempdir(),
        f"claude-secrets-ui-{USER}-{NAMESPACE}.lock",
    )


def reuse_existing_if_alive() -> bool:
    """If a cs-ui process is already running for this namespace, reopen its tab and return True."""
    lock = _lockfile()
    if not os.path.exists(lock):
        return False
    try:
        with open(lock) as f:
            data = json.load(f)
        pid = int(data["pid"])
        port = int(data["port"])
    except Exception:
        # Stale / corrupt lockfile — let the caller proceed and overwrite it.
        try: os.unlink(lock)
        except OSError: pass
        return False

    # Is the process still alive?
    try:
        os.kill(pid, 0)
    except OSError:
        try: os.unlink(lock)
        except OSError: pass
        return False

    # Does it respond on its claimed port?
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            pass
    except OSError:
        try: os.unlink(lock)
        except OSError: pass
        return False

    url = f"http://127.0.0.1:{port}"
    print(f"claude-secrets UI is already running for namespace \"{NAMESPACE}\".")
    print(f"  → {url}  (PID {pid})")
    print(f"Reopening that tab instead of starting a second server.")
    print(f"To stop the running instance, run:  kill {pid}")
    if not os.environ.get("CS_NO_BROWSER"):
        webbrowser.open(url)
    return True


def write_lockfile(port: int) -> None:
    with open(_lockfile(), "w") as f:
        json.dump({"pid": os.getpid(), "port": port}, f)


def main() -> None:
    if sys.platform != "darwin":
        print("claude-secrets UI: macOS only (uses Keychain).", file=sys.stderr)
        sys.exit(2)

    if reuse_existing_if_alive():
        return

    port = find_free_port(PORT)
    url = f"http://127.0.0.1:{port}"
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    write_lockfile(port)
    print(f"claude-secrets UI ready: {url}")
    print("(loopback only; Ctrl-C to quit)")
    if not os.environ.get("CS_NO_BROWSER"):
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye.")
        server.shutdown()
    finally:
        try: os.unlink(_lockfile())
        except OSError: pass


if __name__ == "__main__":
    main()

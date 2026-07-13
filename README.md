# claude-secrets

[![Platform: macOS](https://img.shields.io/badge/platform-macOS-blue)]() [![License: MIT](https://img.shields.io/badge/license-MIT-green)]() [![No deps](https://img.shields.io/badge/dependencies-none-brightgreen)]()

> **$0 — forever.** No subscription, no usage tier, no "free up to 10 entries". One MIT-licensed file in your Mac's built-in Keychain.
> Built by [**Kazim Sevim**](https://www.linkedin.com/in/kazimsevim/) — say hi on [LinkedIn](https://www.linkedin.com/in/kazimsevim/) or [GitHub](https://github.com/kzmsvm).

A general-purpose encrypted secret store for any shell-driven workflow — AI coding agents, deploy scripts, CI runners, cron jobs, dotfiles, anything that needs API tokens. Built on your Mac's Keychain. No SaaS subscription, no cloud account, no JS dependencies. A small browser UI so you don't have to memorize CLI flags.

It's named after Claude Code because that's where the maintainer felt the pain first, but everything in this repo is agent-agnostic. If your tool can run a shell command, it can use `cs`.

> **macOS only.** `cs` shells out to Apple's `security` CLI to talk to the Keychain. It will refuse to run on Linux or Windows (`exit 2` with a message) instead of pretending to work. Native Linux (libsecret) and Windows (DPAPI / Credential Manager) backends are on the [Roadmap](#roadmap); contributions welcome.

## When do I need what?

`cs` has four runtime surfaces — knowing which one you actually need saves a lot of confusion:

| Surface | Need it running? | When |
|---|---|---|
| **CLI** (`cs get`, `cs load`, `cs set`, `cs list`) | No server needed — works any time | Daily use. Pulling tokens into a shell, scripts, cron. |
| **MCP server** | Auto-managed by Claude Code | If you use Claude Code / Cursor / Aider etc. Set up once with `claude mcp add`; it spawns on demand. |
| **Browser UI** | Only while you're using it | When you want to **add** or **edit** an entry without writing CLI flags. Start with `cs add`, close with `cs ui-stop` (or `Ctrl-C`). |
| **Claude Code skill** (`/add-secret`) | No — Claude starts/stops the UI for you | Say "add api key" mid-session; the form opens in Claude Code's own browser pane, so the token never touches the chat. See [Claude Code skill](#claude-code-skill--add-secrets-without-leaving-the-app). |

**You don't need to leave anything running all the time.** Daily flow is:

1. Open a terminal → secrets are already loaded as env vars (one line in `~/.zshrc`).
2. Use Claude Code → the MCP server is spawned automatically when it asks for a secret.
3. Need to add a new token? → `cs add`, type it in, close the tab, you're done.

The "always-on UI" (`cs autostart-install`) is the **rare** case. Only enable it if you want a browser bookmark to `127.0.0.1:9876` to be always-clickable. For everyone else, on-demand is fine.

## Why I built this

While building [Dibibu](https://dibibu.com) — a US warehouse rental marketplace — I kept pasting API tokens (Hostinger, Cloudflare, Stripe, R2, OpenAI, Anthropic, Resend, etc.) into Claude Code chats whenever the agent needed to call an external service. Every paste is a secret in conversation logs forever.

What I needed was simple: a place to keep tokens that:

- doesn't require a separate cloud account or monthly subscription
- works from the terminal so agents and scripts can pull from it
- isn't a plain-text dotfile that leaks via screenshots and Time Machine backups
- doesn't require me to learn a new key-management system on top of what macOS already has

So I wrote this in a couple of hours: a thin wrapper around Apple's built-in Keychain, a tiny browser UI for the moments you'd rather click than type, zero dependencies, audit-able in five minutes. Open source under MIT so you can read every line.

```
$ cs add          # open browser UI, fill in label + token, save
$ cs list         # list stored entries
$ source <(cs load)   # export everything as $ENV_VAR for the current shell
```

Works with:

- **AI coding agents** — Claude Code, Aider, Cursor, Codex, Cline, RooCode, OpenHands, Continue, custom MCP setups
- **AI chat clients** — anywhere you'd otherwise paste an API key into a prompt
- **Shell automation** — bash/zsh/fish scripts, Makefiles, justfiles, fishhooks
- **CI / cron** — local development; pair with `op` or `vault` for remote runners
- **Plain humans** — replaces a $5/month password-manager subscription for the "API token" use case

---

## Why

Whenever you work in a terminal or chat with an AI agent, you end up reaching for API tokens — GitHub, Stripe, OpenAI, your hosting provider, Cloudflare, R2, you name it. The two common bad patterns:

1. **Paste tokens into chat / prompt** — they end up in conversation history, transcript files, telemetry logs, screenshots.
2. **Plain text in `~/.zshrc` / `.env`** — visible to any process, leaks via screen shares, Time Machine backups, and accidental `cat .env`s.

`cs` keeps tokens in the macOS Keychain (AES-256, Touch ID, can sync via iCloud Keychain to your other Macs and iPhone if you turn it on). A short Python script gives you a localhost-only browser form to add new entries without thinking about `security add-generic-password` flags. The CLI does the rest.

## Install

One-liner (the installer asks three setup questions interactively):

```bash
curl -fsSL https://raw.githubusercontent.com/kzmsvm/claude-secrets/main/install.sh | bash
```

The interactive prompts are:

1. **Auto-load secrets in every new terminal?** Adds one line to `~/.zshrc` so `$GITHUB_TOKEN`, `$STRIPE_SECRET`, etc. are pre-populated in every shell. Recommended: **Y**.
2. **Install the MCP server in Claude Code?** Lets Claude / Cursor / Aider request a secret without ever seeing the literal value in chat. Recommended: **Y** if you use Claude Code.
3. **Run the browser UI at every login?** Only worth it if you add/edit tokens often. For day-to-day `cs get` / `cs load` / MCP use, the UI doesn't need to be running. Recommended: **N** — just run `cs add` on demand.

Run non-interactively (CI, automated provisioning) by piping or setting `CS_NONINTERACTIVE=1` — the installer prints the manual commands for each step instead of prompting.

Manual install (no installer):

```bash
git clone https://github.com/kzmsvm/claude-secrets ~/.claude-secrets
ln -s ~/.claude-secrets/bin/cs /usr/local/bin/cs
```

Requires:
- **macOS** (uses Apple's `security` CLI to talk to Keychain). Linux / Windows will get `exit 2` — see [Roadmap](#roadmap).
- **Python 3** (ships with macOS; nothing to install).
- **bash** (default on macOS; works on zsh too).
- No third-party packages, no `pip install`, no Homebrew formula.

## Usage

### Adding secrets

The friendly path:

```bash
cs add
```

A browser tab opens at `http://127.0.0.1:9876`. Fill in:

> If a UI is already running for the current namespace, `cs add` just reopens the existing tab instead of starting a second server — no port conflicts, no orphan processes. Close the server with `Ctrl-C` in the original terminal, or `cs ui-stop`.

### Always-on UI (optional)

If you want the UI server to run automatically at every macOS login (so you can just open the browser bookmark without thinking about it), enable autostart:

```bash
cs autostart-install     # installs a LaunchAgent; survives reboots; auto-restart on crash
cs ui-status             # confirms it's running + shows the current URL
cs autostart-remove      # disables it later if you change your mind
```

This drops a single `.plist` at `~/Library/LaunchAgents/com.claude-secrets.ui.plist` and loads it via `launchctl`. The server uses ~20 MB and binds only to `127.0.0.1`. The installer (`install.sh`) also asks once during first setup so you don't have to remember.


- **Label** — what the secret is for. Auto-slugified (`Stripe Prod!` becomes `stripe-prod`).
- **Type** — pick one:
  - **Single value** — most API tokens (`GitHub`, `OpenAI`, `Cloudflare`)
  - **Client ID + Secret** — OAuth-style (`client_id` + `client_secret`)
  - **Username + Password** — Basic Auth credentials
  - **Custom fields** — any N-field grouping (e.g. AWS access key + secret + region)

Hit save. Entries land in your Keychain under the `cs-*` namespace.

### Using secrets in scripts / shells

```bash
# Load all secrets as env vars in the current shell.
source <(cs load)
echo "$GITHUB_TOKEN"
# kebab-case names become SNAKE_CASE env vars:
#   cs-github-token        → $GITHUB_TOKEN
#   cs-stripe-prod-client-id → $STRIPE_PROD_CLIENT_ID
#   cs-stripe-prod-client-secret → $STRIPE_PROD_CLIENT_SECRET

# Or get one specific value:
GITHUB_TOKEN=$(cs get github-token)

# Print as shell-exportable form:
cs export github-token
# → export GITHUB_TOKEN='ghp_...'

# Delete an entry (e.g. after rotation):
cs rm github-token
```

### Auto-load on shell startup (optional)

Add to `~/.zshrc` or `~/.bashrc`:

```bash
[ -x "$(command -v cs)" ] && source <(cs load) 2>/dev/null
```

Now every new terminal session has every stored secret available as an environment variable. Touch ID prompts once per Keychain session.

### Using with AI agents

Any agent that runs shell commands inherits the environment of the shell it was started from. Two patterns work everywhere:

1. **Source on shell startup.** With the auto-load snippet above, every new terminal session has every stored secret available as an env var. When the agent runs `curl -H "Authorization: Bearer $GITHUB_TOKEN" …`, the literal token never appears in the prompt — only `$GITHUB_TOKEN`.
2. **Just-in-time.** Tell the agent to fetch the value inline:

   ```bash
   curl -H "Authorization: Bearer $(cs get cloudflare-api-token)" https://api.cloudflare.com/...
   ```

   The token enters the shell briefly during the command, then disappears.

#### Claude Code

Claude reads the shell environment its `Bash` tool inherits. Add the auto-load snippet to `~/.zshrc`; from then on every Claude session boots with secrets pre-loaded.

#### Aider / Cursor / Codex / Cline / Continue / Roo / OpenHands

Same pattern. These tools execute shell commands in your environment. If `$STRIPE_SECRET` is exported in the shell you launched them from, they can use it.

#### Custom MCP servers / plugins

If you're writing an MCP server in Node or Python and want secrets without `.env` files, call `cs` as a child process. Use the array form to avoid shell parsing:

```js
// node
import { execFileSync } from "node:child_process";
const token = execFileSync("cs", ["get", "github-token"], { encoding: "utf8" }).trim();
```

```python
# python
import subprocess
token = subprocess.check_output(["cs", "get", "github-token"], text=True).strip()
```

#### Plain shell automation

```bash
# in a deploy script:
source <(cs load)
gh release create v1.2.3 --notes "$NOTES"        # uses $GITHUB_TOKEN
aws s3 sync ./dist s3://my-bucket --profile prod # uses $AWS_PROD_*
```

## Commands

| Command | Description |
|---|---|
| `cs add` (alias `cs ui`) | Open browser UI to add / edit / delete entries (port `9876`, reuses an existing instance) |
| `cs ui-status` | Show the URL + PID of the running UI, or "not running" |
| `cs ui-stop` | Stop the running UI server |
| `cs autostart-install` | Install a macOS LaunchAgent so the UI starts at every login + auto-restarts on crash |
| `cs autostart-remove` | Disable login autostart |
| `cs set <name> <value>` | Store / update a secret from the CLI |
| `cs get <name>` | Print one secret to stdout |
| `cs list` (alias `cs ls`) | List stored entry names |
| `cs export <name>` | Print as `export NAME='value'` |
| `cs load` | Print `export …` for every entry (pair with `source <(cs load)`) |
| `cs rm <name>` | Delete an entry |
| `cs import <file.env>` | Bulk-import from a `.env` file (KEY=value lines, supports `--dry-run`) |
| `cs-sync export` / `import` / `status` | Multi-Mac sync via iCloud Drive + `age` encryption (optional, needs `brew install age`) |

### Port behavior

The UI binds to `127.0.0.1:9876` by default. If that port is occupied by something else, the script **fails loudly** with an error message instead of silently drifting to 9877, 9878, etc. — drifting was a source of "which URL is my browser bookmarked to?" confusion. Override with `CS_PORT=<n> cs add` if you genuinely need a different port. The same logic applies to the autostart LaunchAgent: it always tries 9876.

When you run `cs add` and a UI for the same namespace is already running, the script reopens that tab instead of starting a second instance — no port collision, no orphan processes.

## Importing existing `.env` files

Already have a project with a `.env` full of tokens? One command pulls every key into the Keychain:

```bash
cs import path/to/.env --dry-run        # preview first
cs import path/to/.env                   # actually store
```

Lines starting with `#` are skipped, empty values are skipped, `export FOO=…` prefixes and surrounding `'`/`"` quotes are stripped. Keys are auto-slugified — `DATABASE_URL` becomes the Keychain entry `cs-database-url` (and reads back as `$DATABASE_URL` via `cs load`).

## Touch ID / biometric prompt

macOS Keychain's default ACL **already** gates secret reads — the first time a new process tries `security find-generic-password`, you get a system dialog with **Allow**, **Always Allow**, or **Deny**, and the prompt is unlocked via password / Touch ID / Apple Watch like any other Keychain item. There is nothing to configure: `cs get`, `cs load`, the UI and the MCP server all inherit this behavior.

If you want every read to re-prompt (instead of "Always Allow" persisting per app), open **Keychain Access**, find the `cs-…` entry, **Get Info → Access Control**, and uncheck **Allow all applications to access this item**. Apple does not expose this attribute via the `security` CLI; it has to be toggled in the GUI per entry.

## Multi-Mac sync via iCloud Drive + age

You have two paths for using the same `cs` entries on multiple Macs:

**1. Per-entry iCloud Keychain toggle** (built into macOS — see "Multi-Mac and iPhone sync" below).

**2. Encrypted bundle in iCloud Drive** (one-shot script, no per-entry clicking):

```bash
brew install age              # one-time
cs-sync export                # encrypt all cs-* entries → iCloud Drive (prompts for a passphrase)
# ... iCloud syncs the file to your other Mac ...
cs-sync import                # decrypt on the other Mac (same passphrase) → Keychain
cs-sync status                # show file path, size, modified timestamp
```

`cs-sync` writes `~/Library/Mobile Documents/com~apple~CloudDocs/claude-secrets-<namespace>.age`. The passphrase you choose during `export` is never stored — losing it means losing the bundle's contents. Pick something memorable and keep a backup of the passphrase somewhere outside the Keychain (a printed note in a drawer is fine).

## MCP server — keep secrets out of the model context entirely

The shell-load model (`source <(cs load)`) is fast and simple but it does mean the secret enters the agent's bash session as a regular env var — any subprocess sees it. The bundled MCP server is a tighter loop: the model can list entries by name but only ever receives a one-shot file path when it asks to inject a value. The literal token never lands in chat or context.

Wire it up in Claude Code:

```bash
claude mcp add cs-secrets python3 /Users/yourname/.claude-secrets/mcp/cs-mcp-server.py
```

Then ask Claude something like "use my Stripe key to list customers". The flow becomes:

1. Claude calls `cs_list` → sees `stripe-secret` is available.
2. Claude calls `cs_describe({name: "stripe-secret"})` → reads the note you attached (`"Stripe live key, Bearer auth against api.stripe.com..."`) so it knows what to do with the value.
3. Claude calls `cs_inject({name: "stripe-secret"})` → server writes the value into `/tmp/cs-stripe-secret-abc.secret` (mode `0600`), schedules a self-delete in 300 seconds (5 min — configurable per call with `ttl_seconds`, max 3600), returns just the **path**.
4. Claude saves the path in a bash variable and re-uses it for as many commands as needed inside the TTL window:
   ```bash
   CS_FILE=/var/folders/.../cs-stripe-secret-abc.secret
   curl -H "Authorization: Bearer $(cat $CS_FILE)" https://api.stripe.com/v1/customers
   curl -H "Authorization: Bearer $(cat $CS_FILE)" https://api.stripe.com/v1/charges
   ```
   `cs_inject` is called **once per session**, not per command — the literal value never appears in chat, in the tool result text, or in the model's context.
5. Optional: Claude calls `cs_release({path: "..."})` when done, to delete the temp file immediately instead of waiting out the TTL.

No third-party packages — the MCP server is pure stdlib Python, ~250 lines, audit-able in five minutes.

**Tip:** register it with `--scope user` so it's available in every project on your Mac, not just the current one:

```bash
claude mcp add --scope user cs-secrets python3 /Users/yourname/.claude-secrets/mcp/cs-mcp-server.py
```

### Tools the MCP server exposes

| Tool | What it does |
|---|---|
| `cs_list` | List available secret names (no values, `__meta` entries hidden). |
| `cs_describe(name)` | Length + free-form note attached via `cs note <name> "..."`. Helps the model know what kind of credential it is before fetching. |
| `cs_inject(name, ttl_seconds?)` | Write the value to a `0600` temp file, return only the path. Default TTL 300s, range 10–3600s. |
| `cs_release(path)` | Delete a temp file from a previous `cs_inject` call. Refuses paths outside `TMPDIR/cs-*.secret`. |

## Claude Code skill — add secrets without leaving the app

The MCP server covers *reading* secrets. The `/add-secret` skill covers *adding* them: say "add api key" (in any language) and Claude opens the claude-secrets form **inside Claude Code's own browser pane**. You paste the token into the form — not into chat — and it goes straight to the Keychain. The value never touches the conversation transcript, and Claude confirms only the entry *name* afterwards.

Install (skills in `~/.claude/skills/` are global to your user and survive app updates):

```bash
cp -r skills/add-secret ~/.claude/skills/
```

Then in any Claude Code session: type "add api key" (or `/add-secret`) → paste into the side panel → say "done". The skill also instructs Claude to warn you (and suggest rotation) if you ever paste a raw key into chat by accident.

Under the hood it starts the UI with `CS_NO_BROWSER=1` (suppresses the external browser tab, since the form opens in-app instead) and shuts the server down with `cs ui-stop` when you're finished. `CS_NO_BROWSER=1` also works standalone with `cs add` if you ever want the server without a browser popup.

Feel free to localize the skill: copy the folder, translate the `description:` trigger phrases (e.g. "api ekle", "clé api", "api キー追加") and the name, and Claude will trigger it in your language.

## How it works

`cs` is a small bash dispatcher around macOS's `security` CLI. The browser UI is a single Python file that binds to `127.0.0.1` (loopback only — refuses any remote IP) and writes via the same `security` command. Nothing leaves your Mac.

```
┌──────────────────────────────────────┐
│  Browser → http://127.0.0.1:9876    │
│  └─ POST /save → python              │
│                  └─ security CLI     │
│                     └─ login.keychain│  (AES-256, Apple-managed)
└──────────────────────────────────────┘
```

The Python server only ever runs while you're actively using `cs add`; quit with Ctrl-C or close the tab and stop the script.

## Multiple contexts (work / personal / per-client)

`cs` stores everything under a single Keychain prefix that you can change via the `CS_NAMESPACE` env var (default: `cs`). This lets you keep separate buckets of secrets on the same Mac without them colliding:

```bash
# Personal stuff (default — namespace "cs"):
cs add               # → entries land as cs-github-token, cs-openai-api-key, ...

# Work stuff (separate bucket):
export CS_NAMESPACE=work
cs add               # → entries land as work-jira-token, work-aws-prod-key, ...
cs list              # → only shows work-* entries
source <(cs load)    # → only loads work-* into env

# Per-client buckets:
export CS_NAMESPACE=client-acme
cs add               # → acme-stripe-secret, acme-shopify-token, ...
```

Recipe — add a per-directory `.envrc` (with [direnv](https://direnv.net/)) so the right namespace activates when you `cd` into a project:

```bash
# in ~/projects/dibibu/.envrc
export CS_NAMESPACE=dibibu
source <(cs load)
```

Or hard-wire it for a single command without setting it globally:

```bash
CS_NAMESPACE=client-acme cs get stripe-secret
```

The same trick lets you keep separate buckets for different OS users on the same Mac — each user has their own Keychain, so `cs` data is already isolated per login account. Combining per-user Keychain + per-context namespace gives you a clean matrix.

## Multi-Mac and iPhone sync

The `login.keychain` is local-only by default. To sync to other Apple devices:

1. Open **Settings → \[your name\] → iCloud → Passwords & Keychain** and turn it on (if not already).
2. Run **Keychain Access** → right-click each `cs-*` entry → check "Save to iCloud Keychain". (Apple does not expose this attribute via the `security` CLI — toggle it from the GUI once per entry.)
3. On the other Mac, ensure the same iCloud account and the same toggle is on.

On iPhone, entries become visible in **Settings → Passwords** once iCloud Keychain is enabled there.

For a fully scriptable cross-device flow without GUI toggling, see `examples/icloud-drive-sync.md` (uses `age` to encrypt a portable secrets file into iCloud Drive).

## Security model

- Loopback-only HTTP — the UI refuses any non-`127.0.0.1` / `::1` connection.
- No telemetry, no analytics, no calls outside your Mac.
- Tokens are stored in `login.keychain-db` exactly the way Apple's Keychain Access app stores Safari passwords.
- The Python script source is short (≈300 lines, single file) and contains zero third-party imports — audit it yourself in a couple of minutes.
- `cs load` outputs to stdout so it never writes secrets to disk. Pair with `source <(...)` so they live in shell memory only.

## Roadmap

- [x] One-shot import from `.env` files (shipped)
- [x] Optional `age`-encrypted snapshot to iCloud Drive for multi-Mac sync (shipped)
- [x] MCP server so Claude Code can fetch via MCP instead of shell (shipped)
- [ ] Linux support (libsecret) / Windows support (DPAPI / Credential Manager)
- [ ] Cross-shell completion (zsh / bash / fish)
- [ ] Optional native menu-bar app for first-time discoverability
- [ ] Web-of-trust verification for shared `cs-sync` bundles

## License

MIT — see [LICENSE](LICENSE).

---

## About

**Kazim Sevim** — solo developer, full-stack + operations.

What I do:

- **Web & app** — modern JavaScript stack, WordPress plugins / themes, custom Shopify apps
- **Marketplace & e-commerce** — multi-vendor systems, payment & inventory integrations, operational flows
- **ERP / WMS** — deployment and customization
- **Infrastructure & ops** — VPS, Cloudflare, DNS / SMTP, bot-traffic management
- **AI-augmented development** — Claude Code, MCP, automation
- **Business analysis** — international trade, market & platform evaluation

Whole stack self-hosted; if a script does the job, no SaaS needed.

Working style: grasps the brief quickly, allergic to long bullet lists, gives direct answers instead of hedging.

[**LinkedIn →**](https://www.linkedin.com/in/kazimsevim/)

Issues, PRs and ideas welcome.

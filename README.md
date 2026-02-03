Companion Unified (Full)

This build implements:

Kernel: Scheduler → Global Arbiter → Immutable Gate → Controller → Ledger
Draft-only controllers for messages + calendar + coding
Queues for external side effects (send email / create event)
Approval via HMAC token bound to (qid, spec_hash)
Dashboard to mint tokens + attach to queue items
Executor daemon that verifies token binds and performs the write action
Install

python -m venv .venv
source .venv/bin/activate
pip install -e .
LLM backend (Ollama)

export COMPANION_LLM_PROVIDER=ollama
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.1"
Google OAuth (Gmail + Calendar)

Secrets are expected at:

secrets/client_secret.json
secrets/tokens/gmail_token.json (read)
secrets/tokens/gmail_send_token.json (send)
secrets/tokens/gcal_token.json (read)
secrets/tokens/gcal_write_token.json (write)
Run kernel (drafts + queues)

companion --ticks 5 --artifacts artifacts
Run dashboard (approve)

export COMPANION_EXEC_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn companion_ui.app:app --host 127.0.0.1 --port 8787
The control panel lets you:

Start/stop kernel and executor
Approve and edit queue items (email/calendar/moltbook)
Browse artifacts and view ledger
Control panel auth

# none | password | oauth
export COMPANION_AUTH_MODE=password
export COMPANION_AUTH_PASSWORD="change-me"
export COMPANION_SESSION_SECRET="change-me-too"
OAuth (generic):

export COMPANION_AUTH_MODE=oauth
export COMPANION_SESSION_SECRET="change-me-too"
export COMPANION_OAUTH_CLIENT_ID="..."
export COMPANION_OAUTH_CLIENT_SECRET="..."
export COMPANION_OAUTH_AUTH_URL="https://provider.example.com/oauth/authorize"
export COMPANION_OAUTH_TOKEN_URL="https://provider.example.com/oauth/token"
export COMPANION_OAUTH_USERINFO_URL="https://provider.example.com/oauth/userinfo"
export COMPANION_OAUTH_SCOPES="openid email profile"
export COMPANION_OAUTH_ALLOWED_EMAILS="you@example.com"
export COMPANION_OAUTH_ALLOWED_DOMAINS="example.com"
Run executor daemon (executes approved items)

export COMPANION_EXEC_SECRET="(same value)"
python -m companion_exec.daemon
Auto-approval (conservative)

export COMPANION_AUTO_APPROVE=1
export COMPANION_AUTO_APPROVE_POLICY=conservative
export COMPANION_SELF_EMAIL="you@example.com"
export COMPANION_AUTO_APPROVE_TTL_S=600
export COMPANION_AUTO_APPROVE_EVENT_WINDOW_DAYS=7
export COMPANION_AUTO_APPROVE_EVENT_MAX_DURATION_MIN=120
export COMPANION_AUTO_APPROVE_EVENT_START_HOUR=8
export COMPANION_AUTO_APPROVE_EVENT_END_HOUR=20
export COMPANION_AUTO_APPROVE_CALENDAR_ID=primary
Conservative auto-approval rules:

Email send: only to COMPANION_SELF_EMAIL, subject <= 200 chars, draft file exists.
Calendar event: no attendees, within window, duration <= max, hours within start/end.
Moltbook

Install the Moltbook skill:

npx molthub@latest install moltbook
Set Moltbook config:

export MOLTBOOK_ENABLED=1
export MOLTBOOK_BASE_URL="https://moltbook.com" # use /api if required by your Moltbook endpoint
export MOLTBOOK_CREDENTIALS_PATH="~/.config/moltbook/credentials.json"
export MOLTBOOK_FEED_SORT="hot" # or "new"
export MOLTBOOK_FEED_LIMIT=10
Notes:


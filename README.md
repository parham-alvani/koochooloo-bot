# koochooloo-bot

A personal Instagram follower-analysis tool. Logs into **your own** account (no API key —
a saved browser session or a one-time login) and reports:

1. **Ghost followers** — followers who never liked, commented on, *or* viewed a story of any post.
2. **Not following back** — accounts you follow that don't follow you.
3. **Fans** — accounts that follow you that you don't follow back.
4. **Per-post engagement** — follower likes and comments per post.
5. **Unfollower tracking** — new followers and unfollowers since the last run (snapshot diff).
6. **Top fans** — followers ranked by total engagement (likes + comments + story views).
7. **Suspicious followers** — cheap heuristics flagging likely-fake accounts (no extra requests).
8. **Non-follower likers** — accounts that like your posts but don't follow you.

Output: CSV files + a `dashboard.md` in `output/`, plus a terminal summary.

## How it works

There is no official Instagram API for follower lists or per-post likers on personal accounts,
so this uses the **private mobile API** via [`instagrapi`](https://github.com/subzeroid/instagrapi).
It's read-only, single-account, and low-volume — the low-risk kind of automation — but it is
still unofficial. To stay safe it reuses a saved session (`session.json`) and paces requests.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync                       # install dependencies
cp .env.example .env          # then edit .env with ONE auth method (below)
```

### Authentication

Two options — **cookie/session auth is preferred** (no password login, no challenge):

1. **Session cookie (recommended).** Point at a Netscape `cookies.txt` exported from a
   browser where you're logged into Instagram:

   ```
   IG_COOKIES_FILE=/path/to/ig_cookies.txt
   ```

   Or pass it per-run: `--cookies /path/to/ig_cookies.txt` (overrides the env var).

2. **Username / password (fallback).** Used only when no cookies file is configured:

   ```
   IG_USERNAME=your_username
   IG_PASSWORD=your_password
   ```

## Usage

```bash
# Quick smoke test on the 5 most recent posts:
uv run koochooloo-bot run --max-posts 5

# Full run over all posts:
uv run koochooloo-bot run

# Explicit cookies file + options:
uv run koochooloo-bot run --cookies ~/ig_cookies.txt --max-posts 50 --output reports
```

### Options

| Flag | Default | Purpose |
|------|---------|---------|
| `--max-posts N` | `0` (all) | Number of recent posts to inspect. |
| `--output DIR` | `output` | Where CSVs, `dashboard.md`, and `snapshots/` go. |
| `--whitelist FILE` | — | Usernames (one per line) to exclude from the ghost report. Also `IG_WHITELIST_FILE`. |
| `--stories / --no-stories` | on | Count active-story viewers as engagement. |
| `--csv / --no-csv` | on | Write CSV/dashboard files. |

With **password** auth, the first login often triggers a **challenge** (email/SMS code) or a
**two-factor code** — the tool prompts interactively. Cookie auth skips this. Either way the
resolved session is saved to `session.json` and reused on later runs.

### Unfollower tracking

Each run writes a timestamped snapshot to `output/snapshots/` and diffs against the previous
one to produce `new_followers.csv` / `lost_followers.csv`. **The first run has no baseline** —
tracking starts from it. To keep history across machines, persist `output/snapshots/` (e.g.
commit it into a private stats repo, or point `--output` at that repo's directory).

## Notes & limitations

- Request volume ≈ posts × 2 (a likers + a comments fetch per post), plus story viewers.
  Use `--max-posts` to cap it.
- Instagram caps a post's liker list (typically up to ~1000). For a personal account this is
  normally the complete list.
- Suspicious-follower flags are **heuristics** (numeric handle / no display name) computed from
  data already fetched — no per-account requests — so treat them as hints, not proof.
- Stories are ephemeral (24h), so story-view signal is only present when stories are active.
- `.env` and `session.json` hold secrets and are git-ignored — never commit them.

## Development

```bash
uv run ruff check         # lint
uv run ruff format        # format
uv run ty check           # type check
```

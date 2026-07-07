# koochooloo-bot

A personal Instagram follower-analysis tool. Logs into **your own** account (no API key —
username/password once, saved to a local session file) and reports:

1. **Ghost followers** — followers who never liked *any* of your posts.
2. **Not following back** — accounts you follow that don't follow you.
3. **Fans** — accounts that follow you that you don't follow back.
4. **Per-post engagement** — how many of your followers liked each post.

Output: CSV files in `output/` plus a terminal summary.

## How it works

There is no official Instagram API for follower lists or per-post likers on personal accounts,
so this uses the **private mobile API** via [`instagrapi`](https://github.com/subzeroid/instagrapi).
It's read-only, single-account, and low-volume — the low-risk kind of automation — but it is
still unofficial. To stay safe it reuses a saved session (`session.json`) and paces requests.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync                       # install dependencies
cp .env.example .env          # then edit .env with your real credentials
```

`.env`:

```
IG_USERNAME=your_username
IG_PASSWORD=your_password
```

## Usage

```bash
# Quick smoke test on your 5 most recent posts:
uv run koochooloo-bot run --max-posts 5

# Full run over all posts:
uv run koochooloo-bot run

# Options
uv run koochooloo-bot run --max-posts 50 --output reports --no-csv
```

On the **first** login Instagram often sends a **challenge** (email/SMS code) or asks for a
**two-factor code** — the tool prompts for it interactively. After that, `session.json` is
reused so subsequent runs don't re-login.

## Notes & limitations

- Request volume ≈ number of posts (one liker fetch per post). Use `--max-posts` to cap it.
- Instagram caps a post's liker list (typically up to ~1000). For a personal account this is
  normally the complete list.
- `.env` and `session.json` hold secrets and are git-ignored — never commit them.

## Development

```bash
uv run ruff check         # lint
uv run ruff format        # format
uv run ty check           # type check
```

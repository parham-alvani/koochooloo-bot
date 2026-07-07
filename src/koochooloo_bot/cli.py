"""Command-line entry point."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from instagrapi import Client
from rich.console import Console

from koochooloo_bot import analyze, fetch, report, snapshot
from koochooloo_bot.cache import FetchCache
from koochooloo_bot.client import get_client, get_client_by_sessionid
from koochooloo_bot.config import (
    DEFAULT_CACHE_DIR,
    DEFAULT_CACHE_TTL_DAYS,
    DEFAULT_OUTPUT_DIR,
    CookiesError,
    MissingCredentialsError,
    load_credentials,
    load_whitelist,
    resolve_cookies_path,
    resolve_whitelist_path,
    sessionid_from_cookies,
)
from koochooloo_bot.models import Account

app = typer.Typer(
    help="Analyze your Instagram followers: ghost followers, non-mutuals, and engagement.",
    add_completion=False,
)


@app.callback()
def _main() -> None:
    """Analyze your Instagram followers: ghost followers, non-mutuals, and engagement."""


@app.command()
def run(
    cookies: Annotated[
        Path | None,
        typer.Option(
            "--cookies",
            help="Netscape cookies.txt with an Instagram session (overrides IG_COOKIES_FILE). "
            "When set, logs in via the session cookie instead of username/password.",
        ),
    ] = None,
    max_posts: Annotated[
        int,
        typer.Option("--max-posts", help="Number of recent posts to inspect (0 = all)."),
    ] = 0,
    output: Annotated[
        Path,
        typer.Option("--output", help="Directory for CSV reports and the dashboard."),
    ] = DEFAULT_OUTPUT_DIR,
    whitelist: Annotated[
        Path | None,
        typer.Option(
            "--whitelist",
            help="File of usernames to exclude from the ghost report "
            "(overrides IG_WHITELIST_FILE).",
        ),
    ] = None,
    stories: Annotated[
        bool,
        typer.Option("--stories/--no-stories", help="Include active-story viewers as engagement."),
    ] = True,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Directory for the on-disk likers/comments cache."),
    ] = DEFAULT_CACHE_DIR,
    cache_ttl_days: Annotated[
        int,
        typer.Option("--cache-ttl-days", help="Days to keep cached likers/comments."),
    ] = DEFAULT_CACHE_TTL_DAYS,
    use_cache: Annotated[
        bool,
        typer.Option("--cache/--no-cache", help="Read/write the on-disk fetch cache."),
    ] = True,
    refresh: Annotated[
        bool,
        typer.Option("--refresh", help="Ignore cached entries and refetch (still updates cache)."),
    ] = False,
    write_csv: Annotated[
        bool,
        typer.Option("--csv/--no-csv", help="Write CSV reports to the output directory."),
    ] = True,
) -> None:
    """Log in, fetch data, run the analyses, and report the results."""
    console = Console()

    client: Client
    cookies_path = resolve_cookies_path(cookies)
    try:
        if cookies_path is not None:
            console.print(f"[cyan]Logging in via session cookie ({cookies_path})...[/]")
            client = get_client_by_sessionid(sessionid_from_cookies(cookies_path))
        else:
            console.print("[cyan]Logging in with username/password...[/]")
            client = get_client(load_credentials())
    except (CookiesError, MissingCredentialsError) as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error

    try:
        whitelist_names = load_whitelist(resolve_whitelist_path(whitelist))
    except CookiesError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error

    user_id = str(client.user_id)
    account_name = str(client.username or user_id)
    now = datetime.now()
    snapshot_dir = output / "snapshots"

    console.print("[cyan]Fetching followers and following...[/]")
    followers = fetch.fetch_followers(client, user_id)
    following = fetch.fetch_following(client, user_id)

    # Diff against the previous snapshot BEFORE saving this run's snapshot.
    baseline = snapshot.load_latest_snapshot(snapshot_dir)
    delta = snapshot.compute_delta(baseline, followers)
    snapshot.save_snapshot(snapshot_dir, followers, now)

    registry: dict[str, Account] = {}
    scope = "all posts" if max_posts == 0 else f"up to {max_posts} posts"
    console.print(f"[cyan]Fetching {scope} with likers and comments...[/]")
    cache = FetchCache(
        cache_dir,
        cache_ttl_days * 86400,
        enabled=use_cache,
        refresh=refresh,
    )
    with cache, console.status("Fetching engagement...") as status:

        def on_progress(done: int, total: int) -> None:
            status.update(f"Fetching engagement... post {done}/{total}")

        posts = fetch.fetch_posts(
            client, user_id, max_posts, registry, cache, on_progress=on_progress
        )
    if use_cache:
        console.print(
            f"[dim]Cache: {cache.hits} hits, {cache.misses} fetches "
            f"({cache_dir}, ttl {cache_ttl_days}d).[/]"
        )

    story_viewer_counts: dict[str, int] = {}
    stories_checked = 0
    if stories:
        try:
            story_viewer_counts, stories_checked = fetch.fetch_story_engagement(
                client, user_id, registry
            )
        except Exception as error:  # story endpoints are flaky; never fatal
            console.print(f"[yellow]Skipping stories ({error}).[/]")

    result = analyze.analyze(
        followers,
        following,
        posts,
        registry,
        story_viewer_counts,
        delta,
        stories_checked,
        whitelist_names,
    )
    report.print_summary(result, console=console)

    if write_csv:
        paths = report.write_csv(result, output)
        dashboard = report.write_dashboard(result, output, account_name, now)
        console.print("\n[green]Wrote reports:[/]")
        for path in [*paths, dashboard]:
            console.print(f"  {path}")


if __name__ == "__main__":
    app()

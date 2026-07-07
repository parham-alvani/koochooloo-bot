"""CSV writers and a rich terminal summary."""

from __future__ import annotations

import csv
from pathlib import Path

from rich.console import Console
from rich.table import Table

from koochooloo_bot.models import Account, AnalysisResult

_TOP_N = 15


def _write_accounts_csv(path: Path, accounts: list[Account]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user_id", "username", "profile_url"])
        for account in accounts:
            writer.writerow([account.user_id, account.username, account.profile_url])


def write_csv(result: AnalysisResult, output_dir: Path) -> list[Path]:
    """Write all four analyses to CSV files; return the paths written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name, accounts in (
        ("ghost_followers", result.ghost_followers),
        ("not_following_back", result.not_following_back),
        ("fans", result.fans),
    ):
        path = output_dir / f"{name}.csv"
        _write_accounts_csv(path, accounts)
        written.append(path)

    per_post_path = output_dir / "per_post_engagement.csv"
    with per_post_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["taken_at", "code", "url", "total_likes", "follower_likes"])
        for stat in result.per_post:
            writer.writerow(
                [
                    stat.taken_at.isoformat(),
                    stat.code,
                    stat.url,
                    stat.total_likes,
                    stat.follower_likes,
                ]
            )
    written.append(per_post_path)
    return written


def print_summary(result: AnalysisResult, console: Console | None = None) -> None:
    """Print a readable terminal summary of the analyses."""
    console = console or Console()

    counts = Table(title="Summary", show_header=True, header_style="bold cyan")
    counts.add_column("Category")
    counts.add_column("Count", justify="right")
    counts.add_row("Ghost followers (never liked a post)", str(len(result.ghost_followers)))
    counts.add_row("Not following you back", str(len(result.not_following_back)))
    counts.add_row("Fans (you don't follow back)", str(len(result.fans)))
    counts.add_row("Posts analyzed", str(len(result.per_post)))
    console.print(counts)

    if not result.likers_available:
        console.print(
            "[yellow]Note:[/] Instagram returned no liker data, so ghost-follower "
            "detection is unavailable this run. Per-post totals still reflect like counts."
        )

    if result.ghost_followers:
        table = Table(
            title=f"Top {min(_TOP_N, len(result.ghost_followers))} ghost followers",
            header_style="bold magenta",
        )
        table.add_column("#", justify="right")
        table.add_column("Username")
        table.add_column("Profile")
        for i, account in enumerate(result.ghost_followers[:_TOP_N], start=1):
            table.add_row(str(i), f"@{account.username}", account.profile_url)
        console.print(table)

    weakest = sorted(result.per_post, key=lambda s: s.follower_likes)[:_TOP_N]
    if weakest:
        table = Table(title="Weakest posts by follower likes", header_style="bold yellow")
        table.add_column("Date")
        table.add_column("Post")
        table.add_column("Follower likes", justify="right")
        table.add_column("Total likes", justify="right")
        for stat in weakest:
            table.add_row(
                stat.taken_at.date().isoformat(),
                stat.url,
                str(stat.follower_likes),
                str(stat.total_likes),
            )
        console.print(table)

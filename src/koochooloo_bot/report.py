"""CSV writers, a rich terminal summary, and a markdown dashboard."""

from __future__ import annotations

import csv
from datetime import datetime
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
    """Write every analysis to CSV files; return the paths written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    account_reports: list[tuple[str, list[Account]]] = [
        ("ghost_followers", result.ghost_followers),
        ("ghost_following", result.ghost_following),
        ("not_following_back", result.not_following_back),
        ("fans", result.fans),
        ("non_follower_likers", result.non_follower_likers),
        ("new_followers", result.delta.new_followers),
        ("lost_followers", result.delta.lost_followers),
    ]
    for name, accounts in account_reports:
        path = output_dir / f"{name}.csv"
        _write_accounts_csv(path, accounts)
        written.append(path)

    suspicious_path = output_dir / "suspicious_followers.csv"
    with suspicious_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user_id", "username", "profile_url", "reasons"])
        for flagged in result.suspicious_followers:
            writer.writerow(
                [
                    flagged.account.user_id,
                    flagged.account.username,
                    flagged.account.profile_url,
                    "; ".join(flagged.reasons),
                ]
            )
    written.append(suspicious_path)

    engagement_path = output_dir / "engagement_scores.csv"
    with engagement_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["username", "profile_url", "likes", "comments", "story_views", "total"])
        for score in result.engagement:
            writer.writerow(
                [
                    score.account.username,
                    score.account.profile_url,
                    score.likes,
                    score.comments,
                    score.story_views,
                    score.total,
                ]
            )
    written.append(engagement_path)

    per_post_path = output_dir / "per_post_engagement.csv"
    with per_post_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["taken_at", "code", "url", "total_likes", "follower_likes", "follower_comments"]
        )
        for stat in result.per_post:
            writer.writerow(
                [
                    stat.taken_at.isoformat(),
                    stat.code,
                    stat.url,
                    stat.total_likes,
                    stat.follower_likes,
                    stat.follower_comments,
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
    counts.add_row(
        "Ghost followers (no likes/comments/story views)", str(len(result.ghost_followers))
    )
    counts.add_row(
        "Ghost following (you follow, they don't react)", str(len(result.ghost_following))
    )
    counts.add_row("Not following you back", str(len(result.not_following_back)))
    counts.add_row("Fans (you don't follow back)", str(len(result.fans)))
    counts.add_row("Suspicious followers (heuristic)", str(len(result.suspicious_followers)))
    counts.add_row("Non-follower likers", str(len(result.non_follower_likers)))
    if result.delta.has_baseline:
        counts.add_row("New followers (since last run)", str(len(result.delta.new_followers)))
        counts.add_row("Unfollowers (since last run)", str(len(result.delta.lost_followers)))
    counts.add_row("Posts analyzed", str(len(result.per_post)))
    counts.add_row("Active stories checked", str(result.stories_checked))
    console.print(counts)

    if not result.engagement_available:
        console.print(
            "[yellow]Note:[/] Instagram returned no like/comment/story data, so "
            "ghost-follower detection is unavailable this run."
        )
    if not result.delta.has_baseline:
        console.print(
            "[dim]No previous snapshot found — unfollower tracking starts from this run.[/]"
        )

    if result.delta.lost_followers:
        table = Table(title="Recent unfollowers", header_style="bold red")
        table.add_column("Username")
        table.add_column("Profile")
        for account in result.delta.lost_followers[:_TOP_N]:
            table.add_row(f"@{account.username}", account.profile_url)
        console.print(table)

    if result.engagement:
        table = Table(
            title=f"Top {min(_TOP_N, len(result.engagement))} fans", header_style="bold green"
        )
        table.add_column("#", justify="right")
        table.add_column("Username")
        table.add_column("Likes", justify="right")
        table.add_column("Comments", justify="right")
        table.add_column("Story views", justify="right")
        for i, score in enumerate(result.engagement[:_TOP_N], start=1):
            table.add_row(
                str(i),
                f"@{score.account.username}",
                str(score.likes),
                str(score.comments),
                str(score.story_views),
            )
        console.print(table)


def _mermaid_engagement_chart(result: AnalysisResult) -> str:
    """Build a mermaid line chart of follower likes over time (oldest → newest)."""
    stats = sorted(result.per_post, key=lambda s: s.taken_at)
    if not stats:
        return ""
    labels = ", ".join(f'"{stat.taken_at.strftime("%m-%d")}"' for stat in stats)
    values = ", ".join(str(stat.follower_likes) for stat in stats)
    return (
        "```mermaid\n"
        "xychart-beta\n"
        '    title "Follower likes per post (oldest → newest)"\n'
        f"    x-axis [{labels}]\n"
        '    y-axis "Follower likes"\n'
        f"    line [{values}]\n"
        "```\n"
    )


def _account_list_md(title: str, accounts: list[Account], limit: int = _TOP_N) -> str:
    lines = [f"### {title} ({len(accounts)})", ""]
    if not accounts:
        lines.append("_None._")
    else:
        lines.extend(f"- [@{a.username}]({a.profile_url})" for a in accounts[:limit])
        if len(accounts) > limit:
            lines.append(f"- …and {len(accounts) - limit} more (see CSV)")
    lines.append("")
    return "\n".join(lines)


def write_dashboard(
    result: AnalysisResult,
    output_dir: Path,
    account_name: str,
    generated_at: datetime,
) -> Path:
    """Write a GitHub-renderable markdown dashboard (feature: dashboard)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "dashboard.md"

    parts: list[str] = [
        f"# Instagram dashboard — @{account_name}",
        "",
        f"_Generated {generated_at.strftime('%Y-%m-%d %H:%M')} by koochooloo-bot._",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|------:|",
        f"| Ghost followers | {len(result.ghost_followers)} |",
        f"| Ghost following (you follow, they don't react) | {len(result.ghost_following)} |",
        f"| Not following back | {len(result.not_following_back)} |",
        f"| Fans (you don't follow back) | {len(result.fans)} |",
        f"| Suspicious followers (heuristic) | {len(result.suspicious_followers)} |",
        f"| Non-follower likers | {len(result.non_follower_likers)} |",
    ]
    if result.delta.has_baseline:
        parts.append(f"| New followers (since last run) | {len(result.delta.new_followers)} |")
        parts.append(f"| Unfollowers (since last run) | {len(result.delta.lost_followers)} |")
    parts.append(f"| Posts analyzed | {len(result.per_post)} |")
    parts.append("")

    chart = _mermaid_engagement_chart(result)
    if chart:
        parts.extend(["## Engagement trend", "", chart])

    if result.delta.has_baseline:
        parts.append(_account_list_md("Recent unfollowers", result.delta.lost_followers))
        parts.append(_account_list_md("New followers", result.delta.new_followers))

    if result.engagement:
        parts.append("## Top fans")
        parts.append("")
        parts.append("| # | Username | Likes | Comments | Story views |")
        parts.append("|--:|----------|------:|---------:|------------:|")
        for i, score in enumerate(result.engagement[:_TOP_N], start=1):
            parts.append(
                f"| {i} | [@{score.account.username}]({score.account.profile_url}) "
                f"| {score.likes} | {score.comments} | {score.story_views} |"
            )
        parts.append("")

    parts.append(_account_list_md("Ghost followers", result.ghost_followers))
    parts.append(
        _account_list_md("Ghost following (you follow, they don't react)", result.ghost_following)
    )

    path.write_text("\n".join(parts), encoding="utf-8")
    return path

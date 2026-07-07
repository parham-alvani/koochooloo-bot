"""Command-line entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from koochooloo_bot import analyze, fetch, report
from koochooloo_bot.client import get_client
from koochooloo_bot.config import DEFAULT_OUTPUT_DIR, MissingCredentialsError, load_credentials

app = typer.Typer(
    help="Analyze your Instagram followers: ghost followers, non-mutuals, and engagement.",
    add_completion=False,
)


@app.callback()
def _main() -> None:
    """Analyze your Instagram followers: ghost followers, non-mutuals, and engagement."""


@app.command()
def run(
    max_posts: Annotated[
        int,
        typer.Option("--max-posts", help="Number of recent posts to inspect (0 = all)."),
    ] = 0,
    output: Annotated[
        Path,
        typer.Option("--output", help="Directory for CSV reports."),
    ] = DEFAULT_OUTPUT_DIR,
    write_csv: Annotated[
        bool,
        typer.Option("--csv/--no-csv", help="Write CSV reports to the output directory."),
    ] = True,
) -> None:
    """Log in, fetch data, run the analyses, and report the results."""
    console = Console()

    try:
        creds = load_credentials()
    except MissingCredentialsError as error:
        console.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error

    console.print("[cyan]Logging in...[/]")
    client = get_client(creds)
    user_id = str(client.user_id)

    console.print("[cyan]Fetching followers and following...[/]")
    followers = fetch.fetch_followers(client, user_id)
    following = fetch.fetch_following(client, user_id)

    scope = "all posts" if max_posts == 0 else f"up to {max_posts} posts"
    console.print(f"[cyan]Fetching {scope} and their likers...[/]")
    with console.status("Fetching likers...") as status:

        def on_progress(done: int, total: int) -> None:
            status.update(f"Fetching likers... post {done}/{total}")

        posts = fetch.fetch_posts(client, user_id, max_posts, on_progress=on_progress)

    result = analyze.analyze(followers, following, posts)
    report.print_summary(result, console=console)

    if write_csv:
        paths = report.write_csv(result, output)
        console.print("\n[green]Wrote reports:[/]")
        for path in paths:
            console.print(f"  {path}")


if __name__ == "__main__":
    app()

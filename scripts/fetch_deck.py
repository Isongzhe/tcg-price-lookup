"""Batch fetch prices for an entire decklist.

Usage:
    # From a file
    uv run python -m scripts.fetch_deck decks/sample_deck.txt

    # From stdin (paste, then Ctrl+D; or pipe)
    pbpaste | uv run python -m scripts.fetch_deck -

    # Specify a product line, suppress clipboard copy
    uv run python -m scripts.fetch_deck deck.txt \\
        --product-line "Grand Archive TCG" \\
        --no-copy

Decklist format:
    # Material Deck
    1 Alice, Golden Queen

    # Main Deck
    4 Some Card
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from scripts._clipboard import write_to_clipboard
from scripts._config import load_config
from tcg import endpoints
from tcg.client import TCGplayerClient
from tcg.deck import parse_decklist
from tcg.decklist import DeckRow, enrich
from tcg.output import print_tsv
from tcg.product_lines import PRODUCT_LINES, suggest, to_slug

# All human-facing output goes through this console (stderr). stdout is
# reserved for the TSV so piping through pbcopy/xclip works cleanly.
console = Console(stderr=True)


def _clipboard_paste_hint() -> str:
    """Return a platform-aware paste hint string."""
    if sys.platform == "darwin":
        return "paste with ⌘V"
    elif sys.platform == "win32":
        return "paste with Ctrl+V"
    else:
        return "paste with Ctrl+V (or middle-click)"


def print_summary(
    rows: list[DeckRow],
    clipboard_copied: bool,
    no_copy: bool = False,
    output_path: Path | None = None,
) -> None:
    """Post-run UX: loud banner for missing cards, one-line status count,
    and a clear summary of where the TSV was written."""
    from rich.panel import Panel
    from rich.table import Table

    missing = [r for r in rows if r.missing_reason]
    ok = len(rows) - len(missing)

    console.print()

    if missing:
        miss_table = Table(show_header=True, header_style="bold white", box=None)
        miss_table.add_column("Section", style="dim")
        miss_table.add_column("Qty", justify="right", style="dim")
        miss_table.add_column("Card", style="bold yellow")
        miss_table.add_column("Reason", style="red")
        for r in missing:
            miss_table.add_row(
                r.section or "",
                str(r.quantity),
                r.card_name,
                r.missing_reason or "",
            )
        console.print(
            Panel(
                miss_table,
                title=f"[bold red]NOT FOUND — {len(missing)} card(s) need attention[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )

    status_style = "green" if not missing else "yellow"
    status_line = f"[{status_style}]{ok}/{len(rows)} cards priced[/{status_style}]"
    if missing:
        status_line += f"  [red]· {len(missing)} missing[/red]"
    console.print(status_line)

    # --- Output destinations summary ---
    console.print()
    console.print("[bold]Output destinations:[/bold]")
    console.print("  [green]✓[/green] stdout (printed above)")

    if clipboard_copied:
        hint = _clipboard_paste_hint()
        console.print(f"  [green]✓[/green] clipboard ({hint})")
    else:
        console.print("  [dim]✗ clipboard skipped (--no-copy or no clipboard tool)[/dim]")

    if output_path is not None:
        console.print(f"  [green]✓[/green] file: {output_path}")


def read_input(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch fetch prices for a decklist")
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="path to decklist file, or '-' for stdin",
    )
    parser.add_argument(
        "--product-line",
        default=None,
        help="filter to a specific product line, e.g. 'Grand Archive TCG' (default from config)",
    )
    parser.add_argument(
        "--list-product-lines",
        action="store_true",
        help="print all known product lines as display<TAB>slug, then exit",
    )
    parser.add_argument(
        "--show-endpoints",
        action="store_true",
        dest="show_endpoints",
        help="print the TCGplayer endpoints this CLI is configured to call, then exit",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        dest="show_config",
        help="print the resolved configuration and where each value came from, then exit",
    )
    parser.add_argument(
        "--printings",
        default=None,
        help="comma-separated printings to show (default from config: Normal,Foil). Use 'all' for everything.",
    )
    parser.add_argument(
        "--conditions",
        default=None,
        help="comma-separated conditions to show (default from config: Near Mint). Use 'all' for everything.",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="disable auto-copy of TSV to clipboard for this run",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        default=None,
        type=Path,
        metavar="PATH",
        help="Write TSV to this file path in addition to stdout/clipboard. Overrides config output_path.",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        default=None,
        type=Path,
        help="path to a TOML config file (overrides default search locations)",
    )
    args = parser.parse_args(argv)

    # --list-product-lines: print and exit immediately (before config needed)
    if args.list_product_lines:
        for display, slug in PRODUCT_LINES.items():
            print(f"{display}\t{slug}")
        return 0

    # --show-endpoints: render a Rich table of the endpoint catalog, then exit
    if args.show_endpoints:
        from rich.table import Table

        table = Table(title="TCGplayer Endpoint Catalog", show_lines=True)
        table.add_column("Name", style="bold cyan", no_wrap=True)
        table.add_column("Method", style="bold green", no_wrap=True)
        table.add_column("URL", style="dim")
        table.add_column("Purpose")
        for ep in endpoints.ALL:
            table.add_row(ep.name, ep.method, ep.url, ep.purpose)
        console.print(table)
        return 0

    # Build config — CLI values only override when explicitly passed (non-None).
    cli_overrides: dict = {}
    if args.product_line is not None:
        cli_overrides["product_line"] = args.product_line
    if args.printings is not None:
        cli_overrides["printings"] = [p.strip() for p in args.printings.split(",") if p.strip()]
    if args.conditions is not None:
        cli_overrides["conditions"] = [c.strip() for c in args.conditions.split(",") if c.strip()]
    if args.output_path is not None:
        cli_overrides["output_path"] = args.output_path

    config, _config_sources = load_config(cli_overrides, config_path=args.config_path)

    # --show-config: render resolved config + source attribution, then exit
    if args.show_config:
        from rich.table import Table

        _SOURCE_STYLE = {
            "cli": "bold green",
            "env": "bold yellow",
            "toml": "bold cyan",
            "default": "dim",
        }

        console.print("\nResolved configuration:\n")
        cfg_table = Table(show_header=True, box=None, padding=(0, 2))
        cfg_table.add_column("Setting", style="bold", no_wrap=True)
        cfg_table.add_column("Value")
        cfg_table.add_column("Source", no_wrap=True)

        from scripts._config import _DEFAULTS

        for field in _DEFAULTS:
            value = getattr(config, field)
            source = _config_sources.get(field, "default")
            source_label = f"[{_SOURCE_STYLE[source]}]{source}[/{_SOURCE_STYLE[source]}]"
            cfg_table.add_row(field, str(value), source_label)

        console.print(cfg_table)
        console.print(
            "\n[dim]Search order: CLI flags > env vars > tcg.toml > built-in defaults[/dim]"
        )
        return 0

    if args.source is None:
        parser.error("the following arguments are required: source")

    # Soft validation of --product-line
    if args.product_line is not None and to_slug(args.product_line) is None:
        console.print(
            f"[yellow]Warning: product line {args.product_line!r} is not in the known list.[/yellow]"
        )
        hints = suggest(args.product_line)
        if hints:
            console.print(f"[dim]Did you mean: {', '.join(hints)}?[/dim]")

    text = read_input(args.source)
    entries = parse_decklist(text)
    if not entries:
        console.print("[red]No deck entries parsed.[/red]")
        return 1

    console.print(
        f"[dim]Parsed[/dim] [bold]{len(entries)}[/bold] "
        f"[dim]entries from[/dim] [cyan]{args.source}[/cyan]"
    )

    client = TCGplayerClient()
    rows: list[DeckRow] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]·[/dim]"),
        TimeElapsedColumn(),
        TextColumn("[dim]·[/dim]"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )

    with progress:
        task_id = progress.add_task("[cyan]Fetching prices[/cyan]", total=len(entries))
        for i, entry in enumerate(entries, 1):
            progress.update(
                task_id,
                description=f"[cyan]{entry.quantity}x[/cyan] {entry.card_name}",
            )
            results = enrich(client, entry, config.product_line)
            for row, _sales, _listings in results:
                rows.append(row)

            progress.advance(task_id)
            if i < len(entries):
                time.sleep(config.request_interval)

    # Resolve filter sets from config
    printings_str = ",".join(config.printings)
    conditions_str = ",".join(config.conditions)

    printings_filter: set[str] | None = None
    conditions_filter: set[str] | None = None
    if printings_str.strip().lower() != "all":
        printings_filter = {p.strip() for p in config.printings if p.strip()}
    if conditions_str.strip().lower() != "all":
        conditions_filter = {c.strip() for c in config.conditions if c.strip()}

    # Apply condition filter by pruning variants before output (printing filter
    # handled inline in print_tsv so summary stays accurate).
    if conditions_filter is not None:
        for r in rows:
            r.variants = [v for v in r.variants if v.condition in conditions_filter]

    # Build TSV into a buffer so we can print it AND copy to clipboard.
    tsv_buf = io.StringIO()
    print_tsv(rows, variants_filter=printings_filter, file=tsv_buf)
    tsv_text = tsv_buf.getvalue()

    # Print TSV to stdout
    sys.stdout.write(tsv_text)
    sys.stdout.flush()

    # Auto-clipboard
    clipboard_copied = False
    if config.copy_to_clipboard and not args.no_copy:
        clipboard_copied = write_to_clipboard(tsv_text)

    # Write to file if --output / output_path is set. Parent directories
    # are auto-created (mirrors `git`, `curl -o`, `wget -O` behaviour) so
    # users whose config sets `output_path = "prices/last_run.tsv"` don't
    # need to remember to `mkdir prices/` before the first run.
    written_output_path: Path | None = None
    if config.output_path is not None:
        output_path = Path(config.output_path).expanduser()
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(tsv_text, encoding="utf-8")
            written_output_path = output_path
        except OSError as exc:
            console.print(f"[red]Error writing to {output_path}: {exc}[/red]")
            return 1

    print_summary(
        rows,
        clipboard_copied=clipboard_copied,
        no_copy=args.no_copy,
        output_path=written_output_path,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

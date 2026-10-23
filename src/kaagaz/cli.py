from contextlib import closing
from pathlib import Path

import typer

from kaagaz import __version__
from kaagaz.config import get_settings

app = typer.Typer(help="Kaagaz: your documents, ready for any form. Offline.")


@app.callback()
def main() -> None:
    """Kaagaz CLI."""


@app.command()
def version() -> None:
    """Print the Kaagaz version."""
    typer.echo(f"kaagaz {__version__}")


@app.command()
def config() -> None:
    """Show the effective settings."""
    s = get_settings()
    typer.echo(s.model_dump_json(indent=2))
    typer.echo(f"db: {s.db_path}")


@app.command()
def doctor() -> None:
    """Check Ollama, the configured models, and a JSON round-trip."""
    from pydantic import BaseModel

    from kaagaz.ai.client import chat_json, health

    problems = health()
    for p in problems:
        typer.echo(f"FAIL  {p}")
    if problems:
        raise typer.Exit(1)

    class Ping(BaseModel):
        ok: bool

    result, info = chat_json(Ping, "Reply in JSON.", "Set ok to true.")
    status = "OK  " if result and result.ok else f"FAIL ({info.error})"
    typer.echo(f"{status}  {info.model}: JSON round-trip in {info.seconds:.1f}s, "
               f"{info.output_tokens} output tokens")


@app.command()
def scan() -> None:
    """Find documents in your folders and register new ones (fast; no AI yet)."""
    from kaagaz.db import connect, counts
    from kaagaz.scan import scan as run_scan

    s = get_settings()
    with closing(connect(s.db_path)) as conn:
        rep = run_scan(conn, s)
        typer.echo(f"seen {rep.seen}: {rep.new} new, {rep.unchanged} unchanged, "
                   f"{rep.moved} moved, {rep.duplicate} duplicate copies")
        if rep.cloud_only:
            typer.echo(f"skipped {rep.cloud_only} OneDrive online-only files "
                       f"(right-click > Always keep on this device to include them)")
        for f in rep.missing_folders:
            typer.echo(f"WARN  folder not found: {f}")
        for e in rep.errors:
            typer.echo(f"WARN  {e}")
        typer.echo(f"library: {counts(conn)}")


@app.command()
def classify(limit: int = typer.Option(0, help="Stop after N documents (0 = all)."),
             redo: bool = typer.Option(False, help="Re-label everything, e.g. after changing image size.")) -> None:
    """Label pending documents with Gemma (~6-7 s each). Safe to stop and resume."""
    from kaagaz.ai.classify import classify_pending, reset_all
    from kaagaz.ai.client import OllamaUnavailable
    from kaagaz.db import connect, counts

    s = get_settings()
    with closing(connect(s.db_path)) as conn:
        if redo:
            typer.echo(f"reset {reset_all(conn)} documents to pending")
        total = counts(conn).get("pending", 0)
        total = min(total, limit) if limit else total
        times: list[float] = []
        try:
            for i, (row, out) in enumerate(classify_pending(conn, s, limit or None), 1):
                if out.seconds:
                    times.append(out.seconds)
                label = f"{out.doc_type} ({out.confidence:.2f})" if out.doc_type else "-"
                note = f"  [{out.note}]" if out.note else ""
                typer.echo(f"[{i}/{total}] {Path(row['path']).name[:38]:<38} {label:<30} "
                           f"{out.seconds:5.1f}s  {out.status}{note}")
        except OllamaUnavailable as e:
            typer.echo(f"PAUSED  {e} (remaining documents stay pending)")
        except KeyboardInterrupt:
            typer.echo("stopped; remaining documents stay pending")
        if times:
            t = sorted(times)
            typer.echo(f"latency p50 {t[len(t) // 2]:.1f}s, p95 {t[min(len(t) - 1, int(len(t) * 0.95))]:.1f}s, n={len(t)}")
        typer.echo(f"library: {counts(conn)}")


@app.command()
def parse(path: Path) -> None:
    """Parse a portal's upload instructions (text file) into a checklist."""
    from kaagaz.ai.requirements import parse_requirements

    items, info = parse_requirements(path.read_text(encoding="utf-8"))
    if info.error:
        typer.echo(f"FAIL  {info.error}\n{info.raw[:500]}")
        raise typer.Exit(1)
    for it in items:
        flag = f"  [check: {', '.join(it.uncertain_fields)}]" if it.uncertain_fields else ""
        typer.echo(f"- {it.label}{flag}")
        typer.echo(f"    {it.model_dump_json(exclude_defaults=True, exclude={'label', 'uncertain_fields'})}")
    typer.echo(f"{len(items)} items in {info.seconds:.1f}s ({info.output_tokens} output tokens)")
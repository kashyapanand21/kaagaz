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
    """Label pending documents with Gemma (~2 s each). Safe to stop and resume."""
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
            typer.echo(f"latency p50 {t[len(t) // 2]:.1f}s, "
                       f"p95 {t[min(len(t) - 1, int(len(t) * 0.95))]:.1f}s, n={len(t)}")
        typer.echo(f"library: {counts(conn)}")



def _checklist(path: Path):
    """A saved .json checklist, or a .txt of portal instructions parsed with Gemma."""
    if path.suffix.lower() == ".json":
        from kaagaz.packets.checklist import load_checklist
        return load_checklist(path)

    from kaagaz.ai.requirements import parse_requirements
    items, info = parse_requirements(path.read_text(encoding="utf-8"))
    if info.error:
        typer.echo(f"FAIL  {info.error}\n{info.raw[:500]}")
        raise typer.Exit(1)
    typer.echo(f"parsed {len(items)} items in {info.seconds:.1f}s ({info.output_tokens} output tokens)")
    return items


@app.command()
def parse(path: Path,
          save: Path = typer.Option(None, "--save", help="Write the checklist to a .json file you can edit.")) -> None:
    """Parse a portal's upload instructions (text file) into a checklist."""
    items = _checklist(path)
    for it in items:
        flag = f"  [check: {', '.join(it.uncertain_fields)}]" if it.uncertain_fields else ""
        typer.echo(f"- {it.label}{flag}")
        typer.echo(f"    {it.model_dump_json(exclude_defaults=True, exclude={'label', 'uncertain_fields'})}")
    if save:
        from kaagaz.packets.checklist import save_checklist
        save_checklist(items, save)
        typer.echo(f"saved to {save} (edit it, then use it with match/build)")


@app.command()
def match(path: Path) -> None:
    """Pick the best file for each checklist row (.txt instructions or saved .json)."""
    from kaagaz.db import connect
    from kaagaz.packets.matcher import match_items

    items = _checklist(path)
    s = get_settings()
    with closing(connect(s.db_path)) as conn:
        matches = match_items(conn, items, s.profile.name)
    for m in matches:
        picked = m.best.path.name if m.best else "-"
        more = f"  (+{len(m.alternatives)} alternative{'s' if len(m.alternatives) > 1 else ''})" if m.alternatives else ""
        typer.echo(f"{m.status.upper():<10} {m.item.label[:34]:<34} <- {picked}{more}")
        for n in m.notes:
            typer.echo(f"{'':<11}{n}")
    ready = sum(m.status == "matched" for m in matches)
    typer.echo(f"{ready} of {len(matches)} ready" +
               ("; fix the rest before you start the form" if ready < len(matches) else ""))



@app.command()
def build(path: Path,
          name: str = typer.Option("packet", help="Packet name, e.g. NSP-2026."),
          open_folder: bool = typer.Option(True, "--open/--no-open", help="Open the folder when done.")) -> None:
    """Build upload-ready files: convert, size, rename, then measure every output."""
    import os
    import time

    from kaagaz.db import connect
    from kaagaz.packets.builder import build_packet
    from kaagaz.packets.matcher import match_items

    items = _checklist(path)
    s = get_settings()
    t0 = time.perf_counter()
    with closing(connect(s.db_path)) as conn:
        matches = match_items(conn, items, s.profile.name)
    out_dir, rows = build_packet(matches, s, name)
    for r in rows:
        size = f"{r.size_bytes / 1000:6.1f} KB" if r.size_bytes else ""
        typer.echo(f"{r.status:<8} {r.label[:34]:<34} {r.output or '-':<30} {size}")
        for why in r.reasons:
            typer.echo(f"{'':<9}{why}")
    ready = sum(r.status in ("PASS", "WARN") for r in rows)
    typer.echo(f"{ready} of {len(rows)} ready in {time.perf_counter() - t0:.1f}s -> {out_dir}")
    if open_folder:
        os.startfile(out_dir)
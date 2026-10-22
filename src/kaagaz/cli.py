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
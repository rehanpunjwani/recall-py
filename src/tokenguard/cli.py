from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import typer
import uvicorn

from tokenguard import onboard as onboard_mod
from tokenguard.app import create_app, open_connection
from tokenguard.hooks import run_after_response, run_before_prompt
from tokenguard.indexing import index_workspace
from tokenguard.mcp_server import run_mcp
from tokenguard.metrics import summary as metrics_summary
from tokenguard.ollama_client import OllamaClient
from tokenguard.settings import AppSettings
from tokenguard.threads import default_workspace_fingerprint

app = typer.Typer(help="TokenGuard: local cache, RAG, and optional OpenAI-compatible proxy.")


@app.command("hook")
def hook_cmd(
    event: str = typer.Argument(..., help="before-prompt | after-response"),
) -> None:
    """Run Cursor hook handler (reads JSON from stdin)."""
    if event == "before-prompt":
        raise typer.Exit(asyncio.run(run_before_prompt()))
    if event == "after-response":
        raise typer.Exit(asyncio.run(run_after_response()))
    typer.echo(f"Unknown hook event: {event}", err=True)
    raise typer.Exit(2)


@app.command()
def onboard(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Optional YAML config path (merged like other commands).",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Non-interactive: use default answers (create config, pull models).",
    ),
    skip_pull: bool = typer.Option(
        False,
        "--skip-pull",
        help="Do not download Ollama models (still checks Ollama is up).",
    ),
) -> None:
    """Guided first-time setup: config file, database, optional model pulls, MCP snippet."""
    onboard_mod.run(config=config, non_interactive=yes, skip_pull=skip_pull)


@app.command()
def serve(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Optional YAML config path (merged over defaults and XDG).",
    ),
) -> None:
    """Run HTTP API (health + optional /v1/chat/completions when proxy is enabled in config)."""
    settings = AppSettings.load(config)
    conn = open_connection(settings)
    fastapi_app = create_app(settings, conn)
    uvicorn.run(
        fastapi_app,
        host=settings.api.listen_host,
        port=settings.api.listen_port,
        log_level="info",
    )


@app.command()
def metrics(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    thread_id: str | None = typer.Option(
        None,
        "--thread-id",
        "-t",
        help="Limit totals to one thread (default: global).",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """Show estimated token savings and usage events."""
    settings = AppSettings.load(config)
    conn = open_connection(settings)
    data = metrics_summary(conn, thread_id=thread_id)
    conn.close()
    if json_out:
        typer.echo(json.dumps(data, indent=2))
        return
    totals = data["totals"]
    scope = f"thread {thread_id}" if thread_id else "all threads"
    typer.secho(f"TokenGuard metrics ({scope})", fg="cyan", bold=True)
    typer.echo(f"  Events recorded:     {totals['event_count']}")
    typer.echo(f"  Tokens saved (est.): {totals['tokens_saved']:,}")
    typer.echo(f"  Local tokens in:     {totals['tokens_local_in']:,}")
    typer.echo(f"  Local tokens out:    {totals['tokens_local_out']:,}")
    typer.echo(f"  Cloud tokens (est.): {totals['tokens_cloud_estimated']:,}")
    if data["by_event_type"]:
        typer.echo("")
        typer.secho("By event type:", bold=True)
        for row in data["by_event_type"]:
            typer.echo(
                f"  {row['event_type']}: {row['n']} events, "
                f"saved={int(row['saved']):,}, local_in={int(row['local_in']):,}"
            )
    typer.echo("")
    typer.echo(data["note"])


@app.command()
def index(
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Repo root to index (default: cwd or TOKENGUARD_WORKSPACE).",
    ),
    force: bool = typer.Option(False, "--force", help="Re-index files even if unchanged."),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Index README, rules, and docs into workspace RAG memory."""
    settings = AppSettings.load(config)
    conn = open_connection(settings)
    ollama = OllamaClient(settings.ollama)
    root = (workspace or Path(default_workspace_fingerprint())).resolve()
    out = asyncio.run(
        index_workspace(
            conn,
            settings,
            ollama,
            workspace=root,
            force=force,
        )
    )
    conn.close()
    typer.secho(f"Indexed {out['files_indexed']} file(s) for {out['workspace_fingerprint']}", fg="green")
    typer.echo(f"thread_id: {out['thread_id']}")
    if out["indexed"]:
        for p in out["indexed"]:
            typer.echo(f"  + {p}")
    if out["skipped"]:
        typer.echo(f"skipped {len(out['skipped'])} unchanged/empty")
    if out["errors"]:
        typer.secho(f"errors: {len(out['errors'])}", fg="red")


@app.command("mcp-stdio")
def mcp_stdio(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Optional YAML config; can also set TOKENGUARD_CONFIG.",
    ),
) -> None:
    """Run MCP server on stdio (for Cursor, Claude Code, Claude Desktop)."""
    if config is not None:
        os.environ["TOKENGUARD_CONFIG"] = str(config.expanduser().resolve())
    run_mcp()


@app.command()
def doctor(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Check config paths, database migration, and Ollama reachability."""
    settings = AppSettings.load(config)
    db = settings.resolved_db_path()
    typer.echo(f"Database: {db} (exists={db.is_file()})")
    conn = open_connection(settings)
    typer.echo("SQLite migrations: ok")
    conn.close()
    ollama = OllamaClient(settings.ollama)
    ok = asyncio.run(ollama.health())
    typer.echo(f"Ollama at {settings.ollama.base_url}: reachable={ok}")
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def migrate(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Apply SQLite schema migrations only."""
    settings = AppSettings.load(config)
    conn = open_connection(settings)
    conn.close()
    typer.echo("migrate: ok")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

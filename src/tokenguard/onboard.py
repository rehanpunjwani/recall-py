"""First-time user onboarding: config dir, DB migrate, Ollama models, next-step hints."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from importlib import resources
from pathlib import Path
from typing import Any

import httpx
import typer

from tokenguard.app import open_connection
from tokenguard.ollama_client import OllamaClient
from tokenguard.settings import AppSettings


def _user_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "tokenguard"
    return Path.home() / ".config" / "tokenguard"


def _shipped_default_yaml() -> str:
    text = resources.files("tokenguard").joinpath("config", "default.yaml").read_text(encoding="utf-8")
    header = "# TokenGuard user config (created by `tokenguard onboard`).\n\n"
    return header + text


def _confirm(msg: str, *, default: bool, non_interactive: bool) -> bool:
    if non_interactive:
        return default
    return typer.confirm(msg, default=default)


def ollama_pull_model(base_url: str, model: str) -> None:
    url = base_url.rstrip("/") + "/api/pull"
    with httpx.Client(timeout=httpx.Timeout(None)) as client:
        with client.stream("POST", url, json={"name": model}) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    data: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    continue
                status = data.get("status")
                if isinstance(status, str) and status:
                    typer.echo(f"  {model}: {status}")


def run(
    *,
    config: Path | None = None,
    non_interactive: bool = False,
    skip_pull: bool = False,
) -> None:
    typer.secho("TokenGuard onboarding", fg="cyan", bold=True)
    typer.echo("")

    raw = os.environ.get("TOKENGUARD_CONFIG", "").strip()
    if raw:
        typer.echo(f"Using TOKENGUARD_CONFIG={raw} (personal ~/.config file is ignored unless unset).")
        typer.echo("")

    cfg_dir = _user_config_dir()
    user_yaml = cfg_dir / "config.yaml"
    if not user_yaml.is_file() and not raw:
        cfg_dir.mkdir(parents=True, exist_ok=True)
        if _confirm(
            f"Create starter config at {user_yaml} ?",
            default=True,
            non_interactive=non_interactive,
        ):
            user_yaml.write_text(_shipped_default_yaml(), encoding="utf-8")
            typer.secho("  Created config.yaml", fg="green")
        else:
            typer.echo("  Skipped creating config.yaml (defaults only).")
    elif user_yaml.is_file() and not raw:
        typer.echo(f"Using existing config: {user_yaml}")
    typer.echo("")

    settings = AppSettings.load(config)
    db_path = settings.resolved_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_connection(settings)
    conn.close()
    typer.secho(f"Database ready: {db_path}", fg="green")
    typer.echo("")

    ollama = OllamaClient(settings.ollama)
    reachable = asyncio.run(ollama.health())
    if reachable:
        typer.secho(f"Ollama reachable at {settings.ollama.base_url}", fg="green")
    else:
        typer.secho(
            f"Ollama not reachable at {settings.ollama.base_url}. "
            "Install from https://ollama.com and run `ollama serve`, then re-run onboard or `tokenguard doctor`.",
            fg="yellow",
        )
    typer.echo("")

    if reachable and not skip_pull:
        em = settings.ollama.embed_model
        cm = settings.ollama.chat_model
        if _confirm(
            f"Pull Ollama models now ({em}, {cm})? First run may download several GB.",
            default=True,
            non_interactive=non_interactive,
        ):
            for name in (em, cm):
                typer.echo(f"Pulling {name} …")
                try:
                    ollama_pull_model(settings.ollama.base_url, name)
                    typer.secho(f"  Done: {name}", fg="green")
                except httpx.HTTPError as e:
                    typer.secho(f"  Failed {name}: {e}", fg="red")
        else:
            typer.echo(f"Skipped pulls. When ready: `ollama pull {em}` && `ollama pull {cm}`")
    elif reachable and skip_pull:
        typer.echo("--skip-pull: skipped Ollama model downloads.")
    typer.echo("")

    mcp_command = shutil.which("tokenguard") or "tokenguard"

    typer.secho("Next steps", fg="cyan", bold=True)
    typer.echo("  1. HTTP API:     tokenguard serve")
    typer.echo(
        "  2. MCP (IDE):    enable MCP + call `tokenguard_handle_query` each turn "
        f"(command `{mcp_command}` args `mcp-stdio`; see README + .cursor/rules)."
    )
    typer.echo("  3. Cursor hooks: chmod +x .cursor/hooks/*.sh (see .cursor/hooks.json)")
    if raw:
        cfg_hint = str(Path(raw).expanduser().resolve())
    elif user_yaml.is_file():
        cfg_hint = str(user_yaml.resolve())
    else:
        cfg_hint = "(built-in defaults only)"
    typer.echo(f"  4. Edit config:  {cfg_hint}")
    typer.echo("  5. Docker stack: bash scripts/docker-up.sh")
    typer.echo("  6. Health check: tokenguard doctor")
    typer.echo("")
    typer.echo("MCP snippet (copy into Cursor / Claude MCP settings):")
    if raw:
        mcp_env = {"TOKENGUARD_CONFIG": str(Path(raw).expanduser().resolve())}
    elif user_yaml.is_file():
        mcp_env = {"TOKENGUARD_CONFIG": str(user_yaml.resolve())}
    else:
        mcp_env = {}
    typer.echo(
        json.dumps(
            {
                "mcpServers": {
                    "tokenguard": {
                        "command": mcp_command,
                        "args": ["mcp-stdio"],
                        "env": mcp_env,
                    }
                }
            },
            indent=2,
        )
    )
    typer.echo("")
    if mcp_command == "tokenguard":
        typer.echo(
            "Tip: If your IDE cannot find `tokenguard` on PATH, use `python3.12` (or `python3`) "
            'with args ["-m","tokenguard","mcp-stdio"] — see README “Cursor MCP config”.'
        )
        typer.echo("")

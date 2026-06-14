#!/usr/bin/env -S uv run python
"""Point real subscription LLM CLIs (`claude -p`, `codex exec`) at the core API's MCP server,
as a chosen persona, so you can confirm the MCP works end-to-end with the harnesses you
actually use — and that RBAC-by-identity holds there too (a viewer is denied admin tools).

Both CLIs speak streamable-HTTP MCP with custom headers natively (verified 2026-06), so we
forward the persona as the `X-Goog-Authenticated-User-Email` header — the same IAP identity
simulation the SPA/CLI use. No stdio bridge needed.

    # print the ready-to-run command (default) …
    uv run scripts/mcp_harness.py claude --as ada.admin@example.com
    uv run scripts/mcp_harness.py codex  --as vera.viewer@example.com
    # … or run it now:
    uv run scripts/mcp_harness.py claude --as nina.analyst@example.com --run

Needs the backend running (`make -C backend dev`) and the respective CLI installed + logged in.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys

IAP_USER_HEADER = "X-Goog-Authenticated-User-Email"
DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_SERVER = "agentic"
DEFAULT_PROMPT = "List the MCP tools you have. Then call identity_me and tell me my roles, and try admin_users."

# Short persona aliases → the test-persona emails (rbac.PERSONAS). Pass a full email to override.
PERSONAS = {
    "ada": "ada.admin@example.com",
    "nina": "nina.analyst@example.com",
    "otto": "otto.operator@example.com",
    "vera": "vera.viewer@example.com",
}


def _email(as_user: str | None) -> str | None:
    if not as_user:
        return None
    return as_user if "@" in as_user else PERSONAS.get(as_user, as_user)


def _mcp_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/mcp/"


def _require(tool: str) -> None:
    """Fail loud (escalators-not-stairs) if a requested harness isn't installed — never skip."""
    if shutil.which(tool) is None:
        raise SystemExit(f"error: '{tool}' is not on PATH. Install it (and log in) to drive the MCP with it.")


def _emit(argv: list[str], *, run: bool, env: dict[str, str] | None = None, note: str = "") -> None:
    if note:
        print(note)
    print(" ".join(shlex.quote(a) for a in argv))
    if run:
        _require(argv[0])
        print("\n--- running ---", file=sys.stderr)
        raise SystemExit(subprocess.run(argv, env={**os.environ, **(env or {})}).returncode)


def cmd_claude(args: argparse.Namespace) -> None:
    """Build the `claude -p` invocation with an HTTP MCP server config carrying the persona."""
    email = _email(args.as_user)
    server: dict[str, object] = {"type": "http", "url": _mcp_url(args.base_url)}
    if email:
        server["headers"] = {IAP_USER_HEADER: email}
    config = json.dumps({"mcpServers": {args.server_name: server}})
    argv = [
        "claude",
        "-p",
        args.prompt,
        "--mcp-config",
        config,
        "--strict-mcp-config",  # ONLY this MCP loads — no user/project servers bleed in
        "--allowedTools",
        f"mcp__{args.server_name}__*",
        "--permission-mode",
        "bypassPermissions",
    ]
    _emit(argv, run=args.run, note=f"# claude -p as {email or 'anonymous'} → {_mcp_url(args.base_url)}")


def cmd_codex(args: argparse.Namespace) -> None:
    """Build a `codex exec` invocation that injects the HTTP MCP server inline via `-c` config
    overrides (native streamable_http + custom http_headers — no mcp-remote bridge). Using `-c`
    rather than an isolated CODEX_HOME keeps the user's real login (auth.json) intact."""
    email = _email(args.as_user)
    overrides = [f'mcp_servers.{args.server_name}.url="{_mcp_url(args.base_url)}"']
    if email:
        overrides.append(f'mcp_servers.{args.server_name}.http_headers.{IAP_USER_HEADER}="{email}"')
    # codex auto-cancels MCP tool calls under its default approval gate when non-interactive;
    # bypass it so the harness can actually exercise the tools (safe here — local backend, the
    # MCP is read-only-ish and identity is a simulated persona).
    argv = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox"]
    for override in overrides:
        argv += ["-c", override]
    argv.append(args.prompt)
    _emit(argv, run=args.run, note=f"# codex exec as {email or 'anonymous'} → {_mcp_url(args.base_url)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp_harness", description=__doc__)
    parser.set_defaults(func=lambda _a: parser.print_help())
    sub = parser.add_subparsers(dest="harness", required=False)
    for name, handler, helptext in (
        ("claude", cmd_claude, "drive the MCP with `claude -p`"),
        ("codex", cmd_codex, "drive the MCP with `codex exec`"),
    ):
        leaf = sub.add_parser(name, help=helptext)
        leaf.add_argument("--as", dest="as_user", metavar="EMAIL|ALIAS", default="ada", help="persona (ada/nina/otto/vera or an email; omit for anonymous)")
        leaf.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"backend base URL (default {DEFAULT_BASE_URL})")
        leaf.add_argument("--server-name", default=DEFAULT_SERVER, help=f"MCP server name (default {DEFAULT_SERVER})")
        leaf.add_argument("--prompt", default=DEFAULT_PROMPT, help="prompt to send")
        leaf.add_argument("--run", action="store_true", help="execute now instead of just printing the command")
        leaf.set_defaults(func=handler)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

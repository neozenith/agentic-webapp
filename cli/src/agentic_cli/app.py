"""Parser construction + dispatch. No business logic here — every leaf binds a handler from
commands/ via set_defaults(func=...), mirroring the argparse pattern in the project rules.

Global flags (--base-url, --as, --json) live on a shared parent parser so they may appear
after the subcommand, e.g. `agentic_cli assets list --as ada.admin@example.com`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from .client import ApiError
from .commands import admin, analytics, assets, folders, groups, identity
from .config import DEFAULT_BASE_URL

Handler = Callable[[argparse.Namespace], None]


def _help(parser: argparse.ArgumentParser) -> Handler:
    """A default handler that prints `parser`'s help (used when a group gets no subcommand)."""

    def _print_help(_: argparse.Namespace) -> None:
        parser.print_help()

    return _print_help


def _global_flags() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API base URL (default {DEFAULT_BASE_URL})")
    parent.add_argument(
        "--as",
        dest="as_user",
        metavar="EMAIL",
        default=None,
        help="impersonate this persona via the IAP identity header (RBAC simulation)",
    )
    parent.add_argument("--json", action="store_true", help="emit raw JSON instead of a table")
    return parent


def _leaf(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: Handler,
    parent: argparse.ArgumentParser,
    *,
    help_text: str,
) -> argparse.ArgumentParser:
    leaf = sub.add_parser(name, help=help_text, parents=[parent])
    leaf.set_defaults(func=handler)
    return leaf


def build_parser() -> argparse.ArgumentParser:
    g = _global_flags()
    # The global flags live on a shared parent attached at every level (top, group, leaf) so
    # they parse in any position (`agentic_cli --as X me` and `assets list --as X` both work).
    parser = argparse.ArgumentParser(
        prog="agentic_cli", description="Drive the agentic-webapp core API.", parents=[g]
    )
    parser.set_defaults(func=_help(parser))
    top = parser.add_subparsers(dest="group", required=False)

    # --- identity (top-level read-only singletons) ---
    _leaf(top, "me", identity.cmd_me, g, help_text="show my identity, roles, permissions")
    _leaf(top, "personas", identity.cmd_personas, g, help_text="list switchable test personas")
    _leaf(top, "directory", identity.cmd_directory, g, help_text="show the user directory")

    # --- assets ---
    a = top.add_parser("assets", help="manage assets", parents=[g])
    a.set_defaults(func=_help(a))
    asub = a.add_subparsers(dest="assets_cmd", required=False)
    _leaf(asub, "list", assets.cmd_list, g, help_text="list visible assets").add_argument("--limit", type=int, default=100)
    _leaf(asub, "get", assets.cmd_get, g, help_text="show one asset").add_argument("asset_id")
    _leaf(asub, "url", assets.cmd_url, g, help_text="signed URL for an asset").add_argument("asset_id")
    up = _leaf(asub, "upload", assets.cmd_upload, g, help_text="upload a file as a new asset")
    up.add_argument("file")
    up.add_argument("--folder-id", default=None)
    mv = _leaf(asub, "move", assets.cmd_move, g, help_text="move an asset to a folder (or root)")
    mv.add_argument("asset_id")
    mv.add_argument("--folder-id", default=None)
    cb = _leaf(asub, "combine", assets.cmd_combine, g, help_text="combine 2+ assets into a new one")
    cb.add_argument("asset_ids", nargs="+")
    cb.add_argument("--filename", default="combined.bin")
    cb.add_argument("--content-type", default="application/octet-stream")
    _add_share_leaf(asub, "share", assets.cmd_share, g, id_arg="asset_id", help_text="share/unshare an asset")
    _leaf(asub, "delete", assets.cmd_delete, g, help_text="delete an asset (owner/admin)").add_argument("asset_id")

    # --- folders ---
    f = top.add_parser("folders", help="manage folders", parents=[g])
    f.set_defaults(func=_help(f))
    fsub = f.add_subparsers(dest="folders_cmd", required=False)
    _leaf(fsub, "list", folders.cmd_list, g, help_text="list visible folders")
    cr = _leaf(fsub, "create", folders.cmd_create, g, help_text="create a folder")
    cr.add_argument("name")
    cr.add_argument("--parent-id", default=None)
    _add_share_leaf(fsub, "share", folders.cmd_share, g, id_arg="folder_id", help_text="share/unshare a folder")
    _leaf(fsub, "delete", folders.cmd_delete, g, help_text="delete a folder (owner/admin)").add_argument("folder_id")

    # --- groups (public discovery) ---
    gr = top.add_parser("groups", help="discover groups (read-only)", parents=[g])
    gr.set_defaults(func=_help(gr))
    grsub = gr.add_subparsers(dest="groups_cmd", required=False)
    _leaf(grsub, "list", groups.cmd_list, g, help_text="list groups (id + name)")

    # --- admin (RBAC-gated: admin role only) ---
    ad = top.add_parser("admin", help="admin: usage + group management (admin role)", parents=[g])
    ad.set_defaults(func=_help(ad))
    adsub = ad.add_subparsers(dest="admin_cmd", required=False)
    _leaf(adsub, "users", admin.cmd_users, g, help_text="per-user usage roll-up").add_argument("--limit", type=int, default=5000)
    _leaf(adsub, "usage", admin.cmd_usage, g, help_text="aggregate usage").add_argument("--limit", type=int, default=1000)
    _leaf(adsub, "usage-records", admin.cmd_usage_records, g, help_text="recent usage records").add_argument("--limit", type=int, default=100)
    _leaf(adsub, "sessions", admin.cmd_sessions, g, help_text="sessions for one user").add_argument("user_id")
    gc = _leaf(adsub, "group-create", admin.cmd_group_create, g, help_text="create a group")
    gc.add_argument("name")
    gc.add_argument("--member", action="append", metavar="EMAIL", help="member email (repeatable)")
    _leaf(adsub, "group-delete", admin.cmd_group_delete, g, help_text="delete a group").add_argument("group_id")

    # --- analytics (RBAC-gated: analyst/admin) ---
    an = top.add_parser("analytics", help="extraction analytics (analyst/admin)", parents=[g])
    an.set_defaults(func=_help(an))
    ansub = an.add_subparsers(dest="analytics_cmd", required=False)
    _leaf(ansub, "summary", analytics.cmd_summary, g, help_text="extraction summary").add_argument("--limit", type=int, default=1000)
    _leaf(ansub, "extractions", analytics.cmd_extractions, g, help_text="recent extractions").add_argument("--limit", type=int, default=200)

    return parser


def _add_share_leaf(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: Handler,
    parent: argparse.ArgumentParser,
    *,
    id_arg: str,
    help_text: str,
) -> None:
    leaf = _leaf(sub, name, handler, parent, help_text=help_text)
    leaf.add_argument(id_arg)
    leaf.add_argument("--add-user", action="append", metavar="EMAIL", help="grant a user by email (repeatable)")
    leaf.add_argument("--remove-user", action="append", metavar="USER_ID", help="revoke a user id (repeatable)")
    leaf.add_argument("--add-group", action="append", metavar="GROUP_ID", help="grant a group (repeatable)")
    leaf.add_argument("--remove-group", action="append", metavar="GROUP_ID", help="revoke a group (repeatable)")


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ApiError as err:
        print(f"error: {err.detail} (HTTP {err.status_code})", file=sys.stderr)
        raise SystemExit(1) from err

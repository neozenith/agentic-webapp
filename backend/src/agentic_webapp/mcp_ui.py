"""The MCP-UI browse renderer — the single source of UI truth shared by both hosts.

ADR-0012: a narrow, hand-authored UI layer over the OpenAPI projection. `fetch_visible`
reads the caller's folders/assets through the *existing* `/api/*` routes (so RBAC
visibility is inherited, never re-implemented); `render_browse` turns them into an
`io.modelcontextprotocol/ui` resource (HTML in a sandboxed iframe) that Claude Desktop and
the web chat both render. The same function backs the MCP `browse` tool and the web host's
`/ui/browse` drill-in proxy, so the two surfaces can never diverge.

Pure functions (`render_browse`, `browse_summary`, helpers) take already-fetched lists so
they are trivially unit-testable; only `fetch_visible` does I/O.
"""

from __future__ import annotations

import html
import json
from typing import Any

import httpx
from agentic_core.models import AssetMetadata, Folder
from mcp.types import EmbeddedResource
from mcp_ui_server import create_ui_resource  # type: ignore[import-untyped]

# content-type prefix → display icon. Host-agnostic (Claude Desktop's sandbox can't reach
# the byte-stream endpoint, so we show type icons, not thumbnails — see ADR-0012).
_ICONS = {"image/": "🖼", "application/pdf": "📄", "text/": "📝", "video/": "🎞", "audio/": "🎵"}


async def fetch_visible(client: httpx.AsyncClient) -> tuple[list[Folder], list[AssetMetadata]]:
    """The caller's visible folders and assets, via the same loopback `/api/*` client the MCP
    tool already uses — so the identity-forwarding hook scopes RBAC exactly as the API does."""
    folders_resp, assets_resp = await client.get("/api/folders"), await client.get("/api/assets")
    folders_resp.raise_for_status()
    assets_resp.raise_for_status()
    folders = [Folder.model_validate(f) for f in folders_resp.json()]
    assets = [AssetMetadata.model_validate(a) for a in assets_resp.json()]
    return folders, assets


def _icon(content_type: str | None) -> str:
    for prefix, icon in _ICONS.items():
        if content_type and content_type.startswith(prefix):
            return icon
    return "📎"


def _human_size(n: int | None) -> str:
    if not n:
        return ""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _breadcrumb_chain(folders: list[Folder], folder_id: str | None) -> list[Folder]:
    """Folders from root → current (exclusive of root), following parent_id."""
    by_id = {f.folder_id: f for f in folders}
    chain: list[Folder] = []
    cursor = folder_id
    while cursor is not None and cursor in by_id:
        node = by_id[cursor]
        chain.append(node)
        cursor = node.parent_id
    return list(reversed(chain))


def _drill_button(label: str, target_id: str | None, *, icon: str) -> str:
    """A clickable element that asks the host to (re-)invoke `browse` for `target_id`. The
    JSON null/string is emitted explicitly so root navigation works."""
    arg = "null" if target_id is None else f'"{html.escape(target_id, quote=True)}"'
    return f'<button class="nav" onclick=\'drill({arg})\'>{icon} {html.escape(label)}</button>'


def browse_summary(folders: list[Folder], assets: list[AssetMetadata], folder_id: str | None) -> str:
    """A short, model-facing line (the HTML resource is for the host, not the model)."""
    here = "root" if folder_id is None else next(
        (f"“{f.name}”" for f in folders if f.folder_id == folder_id), "that folder"
    )
    subfolders = [f for f in folders if f.parent_id == folder_id]
    contained = [a for a in assets if a.folder_id == folder_id]
    return f"Browsing {here}: {len(subfolders)} subfolder(s), {len(contained)} asset(s)."


def render_browse(folders: list[Folder], assets: list[AssetMetadata], *, folder_id: str | None = None) -> EmbeddedResource:
    """Build the browse UI resource for `folder_id` (None = root) from already-fetched lists."""
    subfolders = sorted((f for f in folders if f.parent_id == folder_id), key=lambda f: f.name.lower())
    contained = sorted((a for a in assets if a.folder_id == folder_id), key=lambda a: (a.filename or "").lower())

    crumbs = [_drill_button("Home", None, icon="🏠")]
    crumbs += [_drill_button(f.name, f.folder_id, icon="📁") for f in _breadcrumb_chain(folders, folder_id)]
    breadcrumb = '<span class="sep">/</span>'.join(crumbs)

    if subfolders:
        folder_rows = "".join(
            f'<div class="row">{_drill_button(f.name, f.folder_id, icon="📂")}</div>' for f in subfolders
        )
    else:
        folder_rows = '<div class="empty">No subfolders.</div>'

    if contained:
        asset_rows = "".join(
            f'<div class="row asset"><span class="name">{_icon(a.content_type)} '
            f"{html.escape(a.filename or a.asset_id)}</span>"
            f'<span class="meta">{html.escape(_human_size(a.size_bytes))}</span></div>'
            for a in contained
        )
    else:
        asset_rows = '<div class="empty">No assets here.</div>'

    body = _PAGE.format(breadcrumb=breadcrumb, folder_rows=folder_rows, asset_rows=asset_rows)
    # UIResource subclasses mcp.types.EmbeddedResource; cast narrows the untyped SDK return.
    resource: EmbeddedResource = create_ui_resource(
        {
            "uri": f"ui://browse/{folder_id or 'root'}",
            "content": {"type": "rawHtml", "htmlString": body},
            "encoding": "text",
        }
    )
    return resource


# ---------------------------------------------------------------------------------------
# Inline dashboards — the AnalyticsManager data→pixels artifact rendered in chat.
#
# Same MCP-UI contract as browse: fetch through the existing /api/* routes (RBAC inherited),
# then build a sandboxed-iframe HTML resource. The figures come pre-built by the backend
# (figures.build_figure), so the inline chat dashboard and the web dashboard suite render the
# IDENTICAL Plotly figures. Plotly loads from its CDN inside the sandboxed iframe (allow-scripts).
# ---------------------------------------------------------------------------------------


async def fetch_dashboards(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """The caller's visible dashboards (id + name), via the loopback /api client (RBAC inherited)."""
    resp = await client.get("/api/dashboards")
    resp.raise_for_status()
    data: list[dict[str, Any]] = resp.json()
    return data


async def fetch_dashboard_render(client: httpx.AsyncClient, dashboard_id: str) -> dict[str, Any]:
    """A dashboard with every chart resolved to a Plotly figure (the /render transform)."""
    resp = await client.get(f"/api/dashboards/{dashboard_id}/render")
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return data


def dashboard_summary(render: dict[str, Any]) -> str:
    """A short, model-facing line describing the rendered dashboard (the HTML is for the host)."""
    charts = render.get("charts", [])
    kpis = [c for c in charts if c.get("chart_type") == "kpi"]
    return (
        f"Rendered dashboard “{render.get('name', '')}”: {len(charts)} chart(s)"
        f"{f', {len(kpis)} KPI(s)' if kpis else ''}."
    )


def render_dashboard_ui(render: dict[str, Any]) -> EmbeddedResource:
    """Build the inline dashboard UI resource from a /render payload (charts carry figures)."""
    cards: list[str] = []
    plots: list[str] = []
    for i, chart in enumerate(render.get("charts", [])):
        title = html.escape(str(chart.get("title", "")))
        if chart.get("error"):
            cards.append(f'<div class="card err"><div class="t">{title}</div>'
                         f'<div class="msg">⚠ {html.escape(str(chart["error"]))}</div></div>')
        elif chart.get("chart_type") == "kpi":
            value = chart.get("value")
            shown = f"{value:,.2f}" if isinstance(value, (int, float)) else "—"
            cards.append(f'<div class="card kpi"><div class="val">{html.escape(shown)}</div>'
                         f'<div class="t">{title}</div></div>')
        else:
            fig = json.dumps(chart.get("figure", {"data": [], "layout": {}}))
            cards.append(f'<div class="card"><div id="plot{i}" class="plot"></div></div>')
            plots.append(f'Plotly.newPlot("plot{i}",{fig}.data,'
                         f'Object.assign({{margin:{{t:30,r:12,b:36,l:48}},height:260,'
                         f'paper_bgcolor:"transparent",plot_bgcolor:"transparent"}},{fig}.layout),'
                         f'{{displayModeBar:false,responsive:true}});')
    body = _DASHBOARD_PAGE.format(
        name=html.escape(str(render.get("name", "Dashboard"))),
        description=html.escape(str(render.get("description", ""))),
        cards="".join(cards) or '<div class="empty">No charts.</div>',
        plot_calls="\n".join(plots),
    )
    resource: EmbeddedResource = create_ui_resource(
        {
            "uri": f"ui://dashboard/{render.get('dashboard_id', 'unknown')}",
            "content": {"type": "rawHtml", "htmlString": body},
            "encoding": "text",
        }
    )
    return resource


_DASHBOARD_PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  body {{ font: 14px system-ui, -apple-system, sans-serif; margin: 0; padding: 16px; color: #111; }}
  h1 {{ font-size: 16px; margin: 0 0 2px; }}
  p.sub {{ color: #666; margin: 0 0 14px; font-size: 13px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
  .card {{ border: 1px solid #e4e4e7; border-radius: 12px; padding: 10px; background: #fff; }}
  .card .t {{ font-size: 12px; color: #555; text-transform: uppercase; letter-spacing: .03em; }}
  .card.kpi {{ display: flex; flex-direction: column; justify-content: center; align-items: center; }}
  .card.kpi .val {{ font-size: 30px; font-weight: 700; color: #0f766e; }}
  .card.err .msg {{ color: #b91c1c; margin-top: 6px; font-size: 13px; }}
  .plot {{ width: 100%; height: 260px; }}
  .empty {{ color: #999; font-style: italic; }}
</style></head>
<body>
  <h1>{name}</h1>
  <p class="sub">{description}</p>
  <div class="grid">{cards}</div>
  <script>
    {plot_calls}
    function reportSize() {{
      window.parent.postMessage({{ type: "ui-size", height: document.documentElement.scrollHeight }}, "*");
    }}
    window.addEventListener("load", reportSize);
    setTimeout(reportSize, 400);
  </script>
</body></html>"""


# Static shell. User-controlled strings are html-escaped before they reach here; the iframe
# is sandboxed by the host on top of that. The drill() helper is the MCP-UI action contract:
# it asks the host to call the `browse` tool again with a folder_id (web host short-circuits
# to /ui/browse; Claude Desktop re-invokes the MCP tool — both end up in render_browse).
_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  body {{ font: 14px system-ui, -apple-system, sans-serif; margin: 0; padding: 16px; color: #111; }}
  .crumbs {{ margin-bottom: 14px; font-size: 13px; }}
  .crumbs .sep {{ color: #aaa; margin: 0 4px; }}
  h2 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #666;
        margin: 16px 0 6px; }}
  .row {{ margin: 4px 0; display: flex; justify-content: space-between; align-items: center; }}
  .asset {{ padding: 6px 8px; border-radius: 8px; }}
  .asset:hover {{ background: #f4f4f5; }}
  .name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .meta {{ color: #888; font-size: 12px; margin-left: 12px; flex: none; }}
  .empty {{ color: #999; font-style: italic; padding: 4px 0; }}
  button.nav {{ font: inherit; padding: 4px 8px; border: 1px solid #d4d4d8; border-radius: 8px;
                background: #fafafa; cursor: pointer; }}
  button.nav:hover {{ background: #ececef; border-color: #a1a1aa; }}
</style></head>
<body>
  <div class="crumbs">{breadcrumb}</div>
  <h2>Folders</h2>
  {folder_rows}
  <h2>Assets</h2>
  {asset_rows}
  <script>
    function drill(folderId) {{
      window.parent.postMessage(
        {{ type: "tool", payload: {{ toolName: "browse", params: {{ folder_id: folderId }} }} }},
        "*"
      );
    }}
    // Report content height so the host can size the iframe to fit (no inner scrollbar).
    function reportSize() {{
      window.parent.postMessage({{ type: "ui-size", height: document.documentElement.scrollHeight }}, "*");
    }}
    window.addEventListener("load", reportSize);
  </script>
</body></html>"""

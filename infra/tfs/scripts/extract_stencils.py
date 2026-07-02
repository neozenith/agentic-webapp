#!/usr/bin/env python3
"""Vendor draw.io stencils into ``src/tfs/assets/stencils.json``.

draw.io ships its shape libraries in ``stencils.min.js`` as ``f['lib.xml'] =
'<base64>'`` where the payload is base64 -> raw-DEFLATE -> urlencoded mxGraph
**stencil XML**. This script:

  1. decodes the SELECTED provider libraries (``SELECT_LIBS_*`` below) and indexes
     their shapes by ``"<library>/<shape>"``;
  2. for EVERY shape in those libraries, transcribes the stencil's drawing verbs
     (path/move/line/quad/curve/arc/rect/roundrect/ellipse + fill/stroke state)
     into an SVG fragment, and re-encodes the single ``<shape>`` as the
     ``shape=stencil(<b64>)`` payload draw.io understands;
  3. writes ``stencils.json``: ``{stencil_id: {w, h, svg, stencil_b64}}``.

This vendors the FULL provider palettes (GCP/AWS/Azure/Kubernetes), so the registry
in :mod:`tfs.diagrams.registry` can map to any of them without re-running against
the draw.io source. It asserts every stencil the registry references is present.

Run (from repo root):

    uv run --directory infra/tfs python scripts/extract_stencils.py \
        /path/to/drawio/src/main/webapp/js/stencils.min.js
"""

from __future__ import annotations

import base64
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

# Import the registry from the package under test (run via `uv run --directory infra/tfs`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from tfs.diagrams.registry import RESOURCE_STENCILS  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "src" / "tfs" / "assets"
# The version-controlled artifact is the ZIP (the ~6 MB JSON would bloat the repo);
# the loader unarchives it in-memory on demand. ARCNAME is the entry inside the zip.
ASSET_ZIP = ASSETS / "stencils.json.zip"
ARCNAME = "stencils.json"


def _num(v: str | None, default: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _fmt(n: float) -> str:
    """Compact float: drop trailing zeros / the point."""
    s = f"{n:.3f}".rstrip("0").rstrip(".")
    return s or "0"


def decode_library(b64: str) -> str:
    return urllib.parse.unquote(zlib.decompress(base64.b64decode(b64), -15).decode("utf-8", "replace"))


def encode_stencil(shape_xml: str) -> str:
    """Reverse of decode: urlencode -> raw deflate -> base64 (draw.io stencil()-style)."""
    deflated = zlib.compress(urllib.parse.quote(shape_xml).encode("utf-8"), 9)
    # strip the 2-byte zlib header + 4-byte adler trailer to get raw deflate
    raw = deflated[2:-4]
    return base64.b64encode(raw).decode("ascii")


def _path_d(path_el: ET.Element) -> str:
    out: list[str] = []
    for c in path_el:
        t = c.tag
        a = c.attrib
        if t == "move":
            out.append(f"M{_fmt(_num(a.get('x')))} {_fmt(_num(a.get('y')))}")
        elif t == "line":
            out.append(f"L{_fmt(_num(a.get('x')))} {_fmt(_num(a.get('y')))}")
        elif t == "quad":
            out.append(
                f"Q{_fmt(_num(a.get('x1')))} {_fmt(_num(a.get('y1')))} {_fmt(_num(a.get('x2')))} {_fmt(_num(a.get('y2')))}"
            )
        elif t == "curve":
            out.append(
                f"C{_fmt(_num(a.get('x1')))} {_fmt(_num(a.get('y1')))} "
                f"{_fmt(_num(a.get('x2')))} {_fmt(_num(a.get('y2')))} "
                f"{_fmt(_num(a.get('x3')))} {_fmt(_num(a.get('y3')))}"
            )
        elif t == "arc":
            laf = a.get("large-arc-flag", "0")
            sf = a.get("sweep-flag", "0")
            rot = a.get("x-axis-rotation", "0")
            out.append(
                f"A{_fmt(_num(a.get('rx')))} {_fmt(_num(a.get('ry')))} {rot} {laf} {sf} "
                f"{_fmt(_num(a.get('x')))} {_fmt(_num(a.get('y')))}"
            )
        elif t == "close":
            out.append("Z")
    return " ".join(out)


def _paint_attrs(state: dict, *, fill: bool, stroke: bool) -> str:
    # Unset/`inherit` paints become `currentColor` so the icon is themeable at
    # render time (a wrapping <g color="..."> tints the whole stencil); explicit
    # colours (#fff emblems, low-alpha black shadows) are preserved verbatim.
    f = state["fill"] if fill else "none"
    s = state["stroke"] if stroke else "none"
    f = "currentColor" if f in (None, "inherit") else f
    s = "currentColor" if s in (None, "inherit") else s
    parts = [f'fill="{f}"', f'stroke="{s}"']
    # mxGraph carries SEPARATE fill/stroke alpha (<fillalpha>/<strokealpha>, and
    # <alpha> sets both). The flat-design GCP icons paint their drop-shadow as
    # black at fillalpha≈0.07 — applied as fill-opacity so it tints, not blacks out.
    if fill and f != "none" and state["fill_alpha"] < 1.0:
        parts.append(f'fill-opacity="{_fmt(state["fill_alpha"])}"')
    if stroke and s != "none":
        parts.append(f'stroke-width="{_fmt(state["stroke_width"])}"')
        if state["stroke_alpha"] < 1.0:
            parts.append(f'stroke-opacity="{_fmt(state["stroke_alpha"])}"')
        if state.get("dashed"):
            parts.append(f'stroke-dasharray="{state.get("dashpattern", "3 3")}"')
    return " ".join(parts)


def _emit(drawable: tuple, state: dict, *, fill: bool, stroke: bool) -> str:
    attrs = _paint_attrs(state, fill=fill, stroke=stroke)
    kind = drawable[0]
    if kind == "path":
        return f'<path d="{drawable[1]}" {attrs}/>'
    if kind == "rect":
        _, x, y, w, h = drawable
        return f'<rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(w)}" height="{_fmt(h)}" {attrs}/>'
    if kind == "roundrect":
        _, x, y, w, h, r = drawable
        return f'<rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(w)}" height="{_fmt(h)}" rx="{_fmt(r)}" {attrs}/>'
    if kind == "ellipse":
        _, x, y, w, h = drawable
        cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
        return f'<ellipse cx="{_fmt(cx)}" cy="{_fmt(cy)}" rx="{_fmt(rx)}" ry="{_fmt(ry)}" {attrs}/>'
    return ""


def transcribe(shape_el: ET.Element) -> tuple[float, float, str]:
    """mxGraph stencil <shape> -> (w, h, svg-fragment) in the shape's own coords."""
    w = _num(shape_el.get("w"), 100.0)
    h = _num(shape_el.get("h"), 100.0)
    state = {"fill": None, "stroke": None, "stroke_width": 1.0, "fill_alpha": 1.0, "stroke_alpha": 1.0, "dashed": False}
    stack: list[dict] = []
    drawable: tuple | None = None
    out: list[str] = []

    def walk(parent: ET.Element) -> None:
        nonlocal drawable, state
        for el in parent:
            t, a = el.tag, el.attrib
            if t == "save":
                stack.append(dict(state))
            elif t == "restore":
                if stack:
                    state = stack.pop()
            elif t == "strokecolor":
                state["stroke"] = a.get("color")
            elif t == "fillcolor":
                state["fill"] = a.get("color")
            elif t == "strokewidth":
                state["stroke_width"] = _num(a.get("width"), 1.0)
            elif t == "alpha":
                state["fill_alpha"] = state["stroke_alpha"] = _num(a.get("alpha"), 1.0)
            elif t == "fillalpha":
                state["fill_alpha"] = _num(a.get("alpha"), 1.0)
            elif t == "strokealpha":
                state["stroke_alpha"] = _num(a.get("alpha"), 1.0)
            elif t == "dashed":
                state["dashed"] = a.get("dashed") == "1"
            elif t == "dashpattern":
                state["dashpattern"] = a.get("pattern", "3 3")
            elif t == "path":
                drawable = ("path", _path_d(el))
            elif t == "rect":
                drawable = ("rect", _num(a.get("x")), _num(a.get("y")), _num(a.get("w")), _num(a.get("h")))
            elif t == "roundrect":
                drawable = (
                    "roundrect",
                    _num(a.get("x")),
                    _num(a.get("y")),
                    _num(a.get("w")),
                    _num(a.get("h")),
                    _num(a.get("arcsize"), 5.0),
                )
            elif t == "ellipse":
                drawable = ("ellipse", _num(a.get("x")), _num(a.get("y")), _num(a.get("w")), _num(a.get("h")))
            elif t in ("fill", "stroke", "fillstroke") and drawable is not None:
                out.append(_emit(drawable, state, fill=t != "stroke", stroke=t != "fill"))

    for section in ("background", "foreground"):
        sec = shape_el.find(section)
        if sec is not None:
            walk(sec)
    return w, h, "".join(out)


# Libraries vendored in full — the Terraform-relevant provider icon sets. Selection
# is by mxGraph library name (the <shapes name="..."> attribute). Add a provider by
# adding its library here (e.g. "mxgraph.aws3") and re-running.
SELECT_LIBS_EXACT = {
    "mxgraph.gcp2",  # Google Cloud (provider: google)
    "mxgraph.aws4",  # AWS, modern resource icons (provider: aws)
    "mxgraph.azure",  # Azure, classic set (provider: azurerm)
    "mxgraph.kubernetes",  # Kubernetes
    "mxgraph.kubernetes2",
}
SELECT_LIBS_PREFIX = (
    "mxgraph.mscae",  # Azure, modern "Cloud and Enterprise" set (mscae.cloud, .enterprise, ...)
)


def _selected(lib: str) -> bool:
    return lib in SELECT_LIBS_EXACT or any(lib.startswith(p) for p in SELECT_LIBS_PREFIX)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    entries = dict(re.findall(r"f\['([^']+)'\]\s*=\s*'([^']*)'", src.read_text(errors="replace")))

    # Index every shape across every SELECTED library: "lib/shape" -> raw <shape> XML.
    index: dict[str, str] = {}
    for b64 in entries.values():
        xml = decode_library(b64)
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue
        lib = root.get("name", "")
        if not _selected(lib):
            continue
        for shape in root.findall("shape"):
            name = shape.get("name")
            if name:
                index[f"{lib}/{name}"] = ET.tostring(shape, encoding="unicode")

    # The registry must only reference stencils we actually vendor.
    referenced = sorted({sid for sid, _ in RESOURCE_STENCILS.values()})
    missing = [sid for sid in referenced if sid not in index]
    if missing:
        print(f"ERROR: {len(missing)} registry stencil id(s) not found in {src.name}:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1

    asset: dict[str, dict] = {}
    empty: list[str] = []
    for sid, shape_xml in index.items():
        shape_el = ET.fromstring(shape_xml)
        w, h, svg = transcribe(shape_el)
        asset[sid] = {"w": w, "h": h, "svg": svg, "stencil_b64": encode_stencil(shape_xml)}
        if not svg:
            empty.append(sid)

    ASSETS.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asset, indent=1, sort_keys=True)
    with zipfile.ZipFile(ASSET_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(ARCNAME, payload)
    # Drop any stale uncompressed asset so only the zip is version-controlled.
    (ASSETS / "stencils.json").unlink(missing_ok=True)

    by_lib: dict[str, int] = {}
    for sid in asset:
        by_lib[sid.split("/", 1)[0]] = by_lib.get(sid.split("/", 1)[0], 0) + 1
    raw_kb, zip_kb = len(payload) // 1024, ASSET_ZIP.stat().st_size // 1024
    print(
        f"wrote {ASSET_ZIP.relative_to(ASSET_ZIP.parents[3])} — {len(asset)} stencils, {zip_kb} KB zip (from {raw_kb} KB json)"
    )
    for lib in sorted(by_lib):
        print(f"  {by_lib[lib]:5d}  {lib}")
    print(f"registry references {len(referenced)} stencils, all present ✅")
    if empty:
        print(
            f"WARNING: {len(empty)} shape(s) produced empty SVG (likely image-only); they render as plain boxes:",
            file=sys.stderr,
        )
        for sid in empty[:20]:
            print(f"  - {sid}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

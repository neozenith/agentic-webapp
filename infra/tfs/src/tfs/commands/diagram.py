"""`tfs diagram <stack> <env>` — render a GCP architecture diagram from Terraform,
using the mingrammer `diagrams` package.

It always runs a `terraform plan` and reads its JSON, which carries everything in
one document:

  * .configuration      -> the reference graph (edges)        [both modes]
  * .planned_values     -> the full intended resource set      [--mode state]
  * .resource_changes   -> the delta, with per-resource action [--mode plan]

(`terraform show -json` of bare state omits .configuration, so there'd be no edges
— hence the plan.) --mode state (default) draws the live/intended architecture;
--mode plan colours each node by action (create/update/delete/replace/no-op).

Resource type -> diagram node is a single editable registry (NODE_MAP). API-enable
toggles + data sources are dropped as noise; IAM grants render as dashed,
role-labelled EDGES by default (--iam nodes to show them as boxes). Unknown types
fall back to a generic node so nothing is silently dropped.

Requires the system graphviz `dot` binary (brew install graphviz).
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import subprocess
from argparse import Namespace
from pathlib import Path

from diagrams import Cluster, Diagram, Edge, Node
from diagrams.gcp.analytics import BigQuery
from diagrams.gcp.compute import CloudRun, ComputeEngine
from diagrams.gcp.devtools import Build, ContainerRegistry
from diagrams.gcp.security import IAP, Iam
from diagrams.gcp.storage import GCS
from diagrams.generic.blank import Blank

from tfs.config import list_stacks
from tfs.errors import TFStackCLIInputError
from tfs.gcp import check_project
from tfs.roots import find_infra_root

log = logging.getLogger(__name__)

# TF resource type -> (diagrams node class, cluster/category label).
NODE_MAP: dict[str, tuple[type[Node], str]] = {
    "google_cloud_run_v2_service": (CloudRun, "Compute"),
    "google_compute_instance": (ComputeEngine, "Compute"),
    "google_service_account": (Iam, "Security & IAM"),
    "google_project_service_identity": (IAP, "Security & IAM"),
    "google_storage_bucket": (GCS, "Storage"),
    "google_bigquery_dataset": (BigQuery, "Data"),
    "google_bigquery_table": (BigQuery, "Data"),
    "google_artifact_registry_repository": (ContainerRegistry, "Build & Registry"),
    "google_cloudbuild_trigger": (Build, "Build & Registry"),
}

# Rendered as boxes only with --iam nodes; otherwise drawn as edges (or dropped).
IAM_TYPES = {
    "google_storage_bucket_iam_member",
    "google_bigquery_dataset_iam_member",
    "google_project_iam_member",
    "google_service_account_iam_member",
    "google_cloud_run_v2_service_iam_member",
    "google_iap_web_cloud_run_service_iam_member",
    "google_artifact_registry_repository_iam_member",
}

# Pure noise on an architecture diagram.
SKIP_TYPES = {"google_project_service", "google_iap_settings"}

# Plan action -> (emoji prefix, colour). Tuple key is sorted(actions).
ACTION_STYLE: dict[tuple[str, ...], tuple[str, str]] = {
    ("create",): ("+ ", "#16a34a"),
    ("update",): ("~ ", "#d97706"),
    ("delete",): ("- ", "#dc2626"),
    ("create", "delete"): ("± ", "#7c3aed"),  # replace
    ("no-op",): ("", "#64748b"),
    ("read",): ("", "#64748b"),
}

_INDEX_SUFFIX = re.compile(r"\[.*\]$")


def _base_address(address: str) -> str:
    """Strip a for_each/count index: foo.bar["k"] -> foo.bar, foo.bar[0] -> foo.bar."""
    return _INDEX_SUFFIX.sub("", address)


def _short_type(tf_type: str) -> str:
    return tf_type.removeprefix("google_")


def _run_tf(infra_root: Path, args: str, *, capture: bool) -> str:
    result = subprocess.run(
        shlex.split(f"terraform {args}"), cwd=infra_root, text=True, capture_output=capture, check=True
    )
    return result.stdout if capture else ""


def _collect_references(expr: object) -> list[str]:
    """Recursively pull every `references` list out of a configuration expression."""
    refs: list[str] = []
    if isinstance(expr, dict):
        maybe = expr.get("references")
        if isinstance(maybe, list):
            refs.extend(str(r) for r in maybe)
        for value in expr.values():
            refs.extend(_collect_references(value))
    elif isinstance(expr, list):
        for value in expr:
            refs.extend(_collect_references(value))
    return refs


def _resolve_reference(ref: str, addresses: set[str]) -> str | None:
    """Map 'google_service_account.runtime.email' -> the longest managed-resource
    address it starts with ('google_service_account.runtime')."""
    parts = ref.split(".")
    for n in range(len(parts), 0, -1):
        candidate = ".".join(parts[:n])
        if candidate in addresses:
            return candidate
    return None


def _iter_planned(doc: dict):
    """Yield (address, type, name, values, mode) from .planned_values."""

    def walk(module: dict):
        for res in module.get("resources", []):
            yield res["address"], res["type"], res["name"], res.get("values", {}), res.get("mode", "managed")
        for child in module.get("child_modules", []):
            yield from walk(child)

    yield from walk(doc.get("planned_values", {}).get("root_module", {}))


def _iter_changes(doc: dict):
    """Yield (address, type, name, actions, after, mode) from .resource_changes."""
    for rc in doc.get("resource_changes", []):
        change = rc.get("change", {})
        yield (
            rc["address"],
            rc["type"],
            rc["name"],
            tuple(change.get("actions", [])),
            (change.get("after") or {}),
            rc.get("mode", "managed"),
        )


def _config_addresses_and_refs(doc: dict) -> tuple[set[str], list[tuple[str, str]]]:
    resources = doc.get("configuration", {}).get("root_module", {}).get("resources", [])
    addresses = {r["address"] for r in resources}
    pairs = [(r["address"], ref) for r in resources for ref in _collect_references(r.get("expressions", {}))]
    return addresses, pairs


def cmd_diagram(args: Namespace) -> None:
    infra_root = find_infra_root(override=args.infra_root)
    if args.stack not in list_stacks(infra_root):
        raise TFStackCLIInputError(f"Stack '{args.stack}' does not exist. One of {list_stacks(infra_root)}")
    check_project(args.env)

    chdir = f"stacks/{args.stack}"
    tfvars = infra_root / chdir / f"{args.env}.tfvars"
    var_file = f"-var-file={args.env}.tfvars" if tfvars.exists() else ""
    (infra_root / chdir / "tmp").mkdir(parents=True, exist_ok=True)

    log.info("Planning %s/%s …", args.stack, args.env)
    _run_tf(infra_root, f"-chdir={chdir} init -backend-config=./backends/{args.env}.config -reconfigure", capture=True)
    _run_tf(
        infra_root,
        # -lock=false: this plan is a throwaway, read-only snapshot for the diagram.
        # Without it, it races the real plan/apply jobs for the GCS state lock.
        f"-chdir={chdir} plan -input=false -no-color -lock=false -out=tmp/diagram.tfplan -var environment={args.env} {var_file}",
        capture=True,
    )
    doc = json.loads(_run_tf(infra_root, f"-chdir={chdir} show -json tmp/diagram.tfplan", capture=True))

    nodes: dict[str, dict] = {}
    if args.mode == "plan":
        for address, tf_type, name, actions, after, mode in _iter_changes(doc):
            if mode == "data":
                continue
            entry = nodes.setdefault(
                _base_address(address), {"type": tf_type, "name": name, "actions": actions, "count": 0}
            )
            entry["count"] += 1
            entry["role"] = after.get("role")
    else:
        for address, tf_type, name, values, mode in _iter_planned(doc):
            if mode == "data":
                continue
            entry = nodes.setdefault(_base_address(address), {"type": tf_type, "name": name, "actions": (), "count": 0})
            entry["count"] += 1
            entry["role"] = values.get("role")

    config_addresses, ref_pairs = _config_addresses_and_refs(doc)

    out_dir = infra_root / "diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_base = out_dir / f"{args.stack}-{args.env}-{args.mode}"
    _render(
        nodes,
        config_addresses,
        ref_pairs,
        out_base=out_base,
        title=f"{args.stack} | {args.env} | {args.mode}",
        mode=args.mode,
        iam=args.iam,
    )
    log.info("✅ wrote %s.png (%d resources)", out_base.relative_to(infra_root), len(nodes))


def _category(tf_type: str) -> str:
    return NODE_MAP.get(tf_type, (Blank, "Other"))[1]


def _node_class(tf_type: str) -> type[Node]:
    return NODE_MAP.get(tf_type, (Blank, "Other"))[0]


def _render(nodes, config_addresses, ref_pairs, *, out_base: Path, title: str, mode: str, iam: str) -> None:
    box_addrs = {
        addr: info
        for addr, info in nodes.items()
        if info["type"] not in SKIP_TYPES and (iam == "nodes" or info["type"] not in IAM_TYPES)
    }

    graph_attr = {"fontsize": "22", "bgcolor": "white", "pad": "0.6", "nodesep": "0.5", "ranksep": "1.1"}
    objs: dict[str, Node] = {}

    with Diagram(title, filename=str(out_base), outformat="png", show=False, direction="LR", graph_attr=graph_attr):
        by_cat: dict[str, list[str]] = {}
        for addr, info in box_addrs.items():
            by_cat.setdefault(_category(info["type"]), []).append(addr)

        for category, addrs in sorted(by_cat.items()):
            with Cluster(category):
                for addr in addrs:
                    objs[addr] = _make_node(box_addrs[addr], mode)

        seen: set[tuple[str, str]] = set()
        for src, ref in ref_pairs:
            src_base = _base_address(src)
            dst = _resolve_reference(ref, config_addresses)
            if dst is None:
                continue
            dst_base = _base_address(dst)
            pair = (src_base, dst_base)
            if src_base in objs and dst_base in objs and src_base != dst_base and pair not in seen:
                seen.add(pair)
                objs[src_base] >> Edge(color="#94a3b8") >> objs[dst_base]

        if iam != "nodes":
            _draw_iam_edges(nodes, config_addresses, ref_pairs, objs)

        if mode == "plan":
            _legend()


def _make_node(info: dict, mode: str) -> Node:
    name = f"{info['name']} x{info['count']}" if info["count"] > 1 else info["name"]
    label = f"{name}\n({_short_type(info['type'])})"
    attrs: dict[str, str] = {}
    if mode == "plan":
        emoji, color = ACTION_STYLE.get(tuple(sorted(info["actions"])), ("", "#334155"))
        label = f"{emoji}{label}"
        attrs["fontcolor"] = color
    return _node_class(info["type"])(label, **attrs)  # type: ignore[arg-type]  # diagrams Node takes **attrs


def _draw_iam_edges(nodes, config_addresses, ref_pairs, objs) -> None:
    refs_by_src: dict[str, list[str]] = {}
    for src, ref in ref_pairs:
        refs_by_src.setdefault(_base_address(src), []).append(ref)

    for addr, info in nodes.items():
        if info["type"] not in IAM_TYPES:
            continue
        resolved = set()
        for ref in refs_by_src.get(addr, []):
            target = _resolve_reference(ref, config_addresses)
            if target is not None:
                resolved.add(_base_address(target))
        members = [a for a in resolved if nodes.get(a, {}).get("type") == "google_service_account" and a in objs]
        targets = [a for a in resolved if a not in members and a in objs]
        role = (info.get("role") or "").removeprefix("roles/")
        for member in members:
            for target in targets:
                objs[member] >> Edge(label=role, style="dashed", color="#cbd5e1", fontsize="9") >> objs[target]  # type: ignore[arg-type]


def _legend() -> None:
    with Cluster("legend"):
        for label, (emoji, color) in [
            ("create", ACTION_STYLE[("create",)]),
            ("update", ACTION_STYLE[("update",)]),
            ("replace", ACTION_STYLE[("create", "delete")]),
            ("delete", ACTION_STYLE[("delete",)]),
        ]:
            Blank(f"{emoji}{label}", fontcolor=color)  # type: ignore[arg-type]

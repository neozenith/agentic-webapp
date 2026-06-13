# ADR-0008: Folders, groups, and unified sharing for the Asset Manager

**Status:** Accepted

## Context

ADR-0006/0007 gave assets an owner and per-user sharing. The Asset Manager now needs real
**folders** (create, move files in, share a whole folder), custom **groups** of users, and
the ability to share a file *or* folder with **individuals or groups** — managed through a
proper dialog, not a prompt. Admins manage groups and see everything.

## Decision

- **Unified sharing model.** A `Shareable` mixin (`owner_id`, `shared_user_ids`,
  `shared_group_ids`) is shared by `AssetMetadata` and the new `Folder`. `Group`
  (`member_ids`) is the third operational entity. All live in the **operational store
  (Firestore)** via `FolderManager` / `GroupManager`, beside `AssetMetadataManager` — *not*
  the analytics warehouse (ADR keeps Sessions+Assets+Folders+Groups on Firestore;
  AnalyticsManager stays BigQuery).
- **Folders are real and nest** (`parent_id`). An asset has a `folder_id`. Sharing a folder
  **cascades** to its files and its whole subtree.
- **Visibility is pure + central** (`agentic_core.access`): a principal match = owner, in
  `shared_user_ids`, or member of a group in `shared_group_ids`; an asset is visible if it
  matches directly *or* its folder is accessible; admins see all; unowned = legacy/public.
  `accessible_folder_ids` resolves the cascade once per request.
- **Server-enforced** (the source of truth): routes resolve `(viewer_id, is_admin,
  group_ids)` and apply the pure rules on list/get/content; move/share/delete and folder
  share are owner/admin-only; group CRUD is under the admin (`require_area("admin")`) router.
  The agent stays scoped via its internal `X-Viewer-User-Id` header.
- **Sharing is a change-set** (`add_user_emails` / `remove_user_ids` / `add_group_ids` /
  `remove_group_ids`) so the UI can add/remove principals idempotently from one modal.
  Emails are pseudonymised to `user_ids` server-side (never stored as keys — ADR-0004).
- **Directory**: a `user_id → {email, name}` map (from personas + configured IAP users) lets
  the Admin page and the share modal show conventional identities for pseudonymous ids,
  without storing emails on every record.

## Consequences

- Old assets (pre-folders) have `owner_id=None` and no folder → treated as public/legacy; we
  reset dev state (`scripts/reset_state.py`) for a clean slate rather than migrating.
- Visibility for a list is O(assets + folders) per request — fine at this scale; a query-side
  index can come later if needed.
- New BigQuery tables `folders`, `groups`; `asset_metadata` gains `folder_id` +
  `shared_user_ids_json` + `shared_group_ids_json` (replacing the single `shared_with_json`).

## Lens

Resolve "can this principal see this thing?" in one pure, table-driven function and call it
from every entry point (UI gating, API, agent) — never re-implement the rule per route.
Inheritance (folder → file) is computed as a reachable-set, not chased per item at read time.
Share by change-set, not by replacing the whole list, so concurrent edits compose.

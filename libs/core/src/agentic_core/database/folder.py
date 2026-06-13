"""FolderManager — real named folders for the Asset Manager, on a DatabaseManager
(operational store). Folders nest via parent_id and carry their own sharing (users +
groups); contained assets and sub-folders inherit that access (see agentic_core.access)."""

from __future__ import annotations

import json

from ..models import Folder
from .base import DatabaseManager, Row


class FolderManager:
    def __init__(self, db: DatabaseManager, *, table: str = "folders") -> None:
        self._db = db
        self._table = table

    async def record(self, folder: Folder) -> Folder:
        await self._db.insert(self._table, [self._to_row(folder)])
        return folder

    async def get(self, folder_id: str) -> Folder | None:
        row = await self._db.get(self._table, key_field="folder_id", key=folder_id)
        return self._from_row(row) if row else None

    async def list(self, *, limit: int = 500) -> list[Folder]:
        rows = await self._db.list(self._table, limit=limit, order_by="created_at")
        return [self._from_row(r) for r in rows]

    async def update(self, folder: Folder) -> Folder:
        await self._db.delete(self._table, key_field="folder_id", key=folder.folder_id)
        await self._db.insert(self._table, [self._to_row(folder)])
        return folder

    async def delete(self, folder_id: str) -> None:
        await self._db.delete(self._table, key_field="folder_id", key=folder_id)

    @staticmethod
    def _to_row(f: Folder) -> Row:
        return {
            "folder_id": f.folder_id,
            "name": f.name,
            "parent_id": f.parent_id,
            "owner_id": f.owner_id,
            "shared_user_ids_json": json.dumps(f.shared_user_ids or []),
            "shared_group_ids_json": json.dumps(f.shared_group_ids or []),
            "created_at": f.created_at.isoformat(),
        }

    @staticmethod
    def _from_row(row: Row) -> Folder:
        def _arr(key: str) -> list[str]:
            raw = row.get(key)
            return json.loads(raw) if isinstance(raw, str) and raw else (raw or [])

        return Folder(
            folder_id=row["folder_id"],
            name=row["name"],
            parent_id=row.get("parent_id"),
            owner_id=row.get("owner_id"),
            shared_user_ids=_arr("shared_user_ids_json"),
            shared_group_ids=_arr("shared_group_ids_json"),
            created_at=row["created_at"],
        )

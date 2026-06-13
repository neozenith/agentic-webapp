"""GroupManager — custom user groups, on a DatabaseManager (operational store: Firestore in
cloud, in-memory in tests). Assets/folders can be shared with a group; a member inherits
that access. Admin-managed."""

from __future__ import annotations

import json

from ..models import Group
from .base import DatabaseManager, Row


class GroupManager:
    def __init__(self, db: DatabaseManager, *, table: str = "groups") -> None:
        self._db = db
        self._table = table

    async def record(self, group: Group) -> Group:
        await self._db.insert(self._table, [self._to_row(group)])
        return group

    async def get(self, group_id: str) -> Group | None:
        row = await self._db.get(self._table, key_field="group_id", key=group_id)
        return self._from_row(row) if row else None

    async def list(self, *, limit: int = 200) -> list[Group]:
        rows = await self._db.list(self._table, limit=limit, order_by="created_at")
        return [self._from_row(r) for r in rows]

    async def update(self, group: Group) -> Group:
        await self._db.delete(self._table, key_field="group_id", key=group.group_id)
        await self._db.insert(self._table, [self._to_row(group)])
        return group

    async def delete(self, group_id: str) -> None:
        await self._db.delete(self._table, key_field="group_id", key=group_id)

    async def group_ids_for_user(self, user_id: str, *, limit: int = 500) -> set[str]:
        """The ids of groups the user is a member of (for visibility resolution)."""
        return {g.group_id for g in await self.list(limit=limit) if user_id in g.member_ids}

    @staticmethod
    def _to_row(g: Group) -> Row:
        return {
            "group_id": g.group_id,
            "name": g.name,
            "member_ids_json": json.dumps(g.member_ids or []),
            "created_at": g.created_at.isoformat(),
        }

    @staticmethod
    def _from_row(row: Row) -> Group:
        raw = row.get("member_ids_json")
        members = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
        return Group(
            group_id=row["group_id"],
            name=row["name"],
            member_ids=members,
            created_at=row["created_at"],
        )

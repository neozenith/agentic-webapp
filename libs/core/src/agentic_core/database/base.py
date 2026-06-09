"""DatabaseManager — the abstract tabular-store interface.

Generic on purpose: it works with tables of ``dict[str, Any]`` rows identified by a
key column. Domain logic (typed records, validation) lives in managers composed on
top of it, e.g. AssetMetadataManager. Concrete implementations:
BigQueryDatabaseManager (production), InMemoryDatabaseManager (tests/local).
"""

from __future__ import annotations  # so the `list` method name can't shadow list[...] hints

from abc import ABC, abstractmethod
from typing import Any

Row = dict[str, Any]
# Alias for the row-list return/param type. Defined at module scope (where the builtin
# `list` isn't shadowed) so the `list` METHOD below doesn't capture `list[Row]` hints.
Rows = list[Row]


class DatabaseManager(ABC):
    """Async access to tables of rows. Table names are logical (the implementation
    maps them onto a dataset/schema)."""

    @abstractmethod
    async def insert(self, table: str, rows: Rows) -> None:
        """Append rows to a table."""

    @abstractmethod
    async def get(self, table: str, *, key_field: str, key: str) -> Row | None:
        """Return the single row whose key_field == key, or None."""

    @abstractmethod
    async def list(self, table: str, *, limit: int = 100, order_by: str | None = None) -> Rows:
        """Return up to `limit` rows, optionally ordered by a column (desc)."""

    @abstractmethod
    async def delete(self, table: str, *, key_field: str, key: str) -> None:
        """Delete rows whose key_field == key. No-op if none match."""

    @abstractmethod
    async def query(self, sql: str, *, params: dict[str, Any] | None = None) -> Rows:
        """Run a read query and return rows. `sql` dialect is implementation-specific
        — use the typed methods above for portable code; reach for query() only when
        you knowingly target a specific backend."""

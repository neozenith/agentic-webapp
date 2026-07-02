"""SemanticManager — the bridge between a human "Domain Model" and the warehouse.

This is the **logical data model** layer (a semantic layer in the lineage of LookML /
dbt MetricFlow / Cube). It stores top-down domain models (entities → dimensions +
measures) and turns a backend-agnostic ``SemanticQuery`` into an answer two ways:

  - **SQL push-down** when the DatabaseManager ``supports_sql`` (BigQuery): the query is
    compiled to a single GROUP BY statement and run in the warehouse.
  - **In-process aggregation** otherwise (in-memory, local/tests): the same query is
    computed in Python over ``list()`` rows.

Both paths return the identical ``SemanticQueryResult`` (same columns, same compiled SQL
for transparency) — a capability axis, never a fallback that drops requirements. The
compiled SQL is always returned so a human or agent can see exactly what was asked.

Persistence mirrors the other managers: one row per model in a ``semantic_models`` table,
the whole model serialised to a ``definition_json`` column (the generic-payload seam).
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from ..models import (
    SemanticEntity,
    SemanticFilter,
    SemanticModel,
    SemanticQuery,
    SemanticQueryResult,
)
from .base import DatabaseManager, Row

_GRAIN_SQL = {"day": "DAY", "week": "WEEK", "month": "MONTH", "quarter": "QUARTER", "year": "YEAR"}


class SemanticModelNotFoundError(KeyError):
    """Raised when a semantic model id does not exist."""


class SemanticQueryError(ValueError):
    """Raised when a SemanticQuery references an unknown entity/dimension/measure."""


class SemanticManager:
    def __init__(self, db: DatabaseManager, *, table: str = "semantic_models") -> None:
        self._db = db
        self._table = table

    # --- CRUD over semantic models -----------------------------------------------------

    async def create_model(self, model: SemanticModel) -> SemanticModel:
        await self._db.insert(self._table, [self._to_row(model)])
        return model

    async def get_model(self, model_id: str) -> SemanticModel | None:
        row = await self._db.get(self._table, key_field="model_id", key=model_id)
        return self._from_row(row) if row else None

    async def list_models(self, *, limit: int = 100) -> list[SemanticModel]:
        rows = await self._db.list(self._table, limit=limit, order_by="updated_at")
        return [self._from_row(r) for r in rows]

    async def update_model(self, model: SemanticModel) -> SemanticModel:
        """Replace a model in place. The generic DB has no upsert, so delete-then-insert
        (the same pattern AssetMetadataManager uses)."""
        await self._db.delete(self._table, key_field="model_id", key=model.model_id)
        await self._db.insert(self._table, [self._to_row(model)])
        return model

    async def delete_model(self, model_id: str) -> None:
        await self._db.delete(self._table, key_field="model_id", key=model_id)

    # --- query the semantic layer ------------------------------------------------------

    async def run_query(self, model: SemanticModel, query: SemanticQuery) -> SemanticQueryResult:
        """Execute a SemanticQuery against `model`, returning rows + the compiled SQL."""
        entity = self._entity(model, query.entity)
        group_specs, measure_specs = self._resolve(entity, query)
        sql = self._compile_sql(entity, query, group_specs, measure_specs)
        columns = [label for label, _ in group_specs] + [label for label, _, _ in measure_specs]

        if self._db.supports_sql:  # pragma: no cover — BigQuery push-down, covered by live deploy
            rows = await self._db.query(sql)
        else:
            source = await self._db.list(entity.table, limit=100_000)
            rows = self._aggregate(source, query, group_specs, measure_specs)

        rows = self._order_and_limit(rows, query, group_specs, measure_specs)
        return SemanticQueryResult(columns=columns, rows=rows, sql=sql, row_count=len(rows))

    def compile_sql(self, model: SemanticModel, query: SemanticQuery) -> str:
        """The BigQuery SQL a query compiles to (transparency / dbt parity)."""
        entity = self._entity(model, query.entity)
        group_specs, measure_specs = self._resolve(entity, query)
        return self._compile_sql(entity, query, group_specs, measure_specs)

    # --- resolution --------------------------------------------------------------------

    @staticmethod
    def _entity(model: SemanticModel, name: str) -> SemanticEntity:
        for e in model.entities:
            if e.name == name:
                return e
        raise SemanticQueryError(f"unknown entity '{name}' in model '{model.model_id}'")

    @staticmethod
    def _resolve(
        entity: SemanticEntity, query: SemanticQuery
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str, str]]]:
        """Return (group_specs, measure_specs).

        group_specs: list of (output_label, source_column). The leading entry is the time
        dimension bucketed by grain when a grain is set.
        measure_specs: list of (output_label, agg_fn, source_column).
        """
        dims = {d.name: d for d in entity.dimensions}
        measures = {m.name: m for m in entity.measures}

        group_specs: list[tuple[str, str]] = []
        if query.time_grain:
            if not entity.time_dimension or entity.time_dimension not in dims:
                raise SemanticQueryError(
                    f"entity '{entity.name}' has no time_dimension for grain '{query.time_grain}'"
                )
            td = dims[entity.time_dimension]
            group_specs.append((td.name, td.column))

        for name in query.dimensions:
            if name == entity.time_dimension and query.time_grain:
                continue  # already added as the time bucket
            if name not in dims:
                raise SemanticQueryError(f"unknown dimension '{name}' on entity '{entity.name}'")
            group_specs.append((dims[name].name, dims[name].column))

        measure_specs: list[tuple[str, str, str]] = []
        for name in query.measures:
            if name not in measures:
                raise SemanticQueryError(f"unknown measure '{name}' on entity '{entity.name}'")
            m = measures[name]
            measure_specs.append((m.name, m.agg, m.column))
        if not measure_specs and not group_specs:
            raise SemanticQueryError("a query needs at least one measure or dimension")
        return group_specs, measure_specs

    def _filter_column(self, entity: SemanticEntity, field: str) -> str:
        """Resolve a filter's field to a physical column (dimension name or raw column)."""
        for d in entity.dimensions:
            if d.name == field:
                return d.column
        return field

    # --- SQL compilation ---------------------------------------------------------------

    def _compile_sql(
        self,
        entity: SemanticEntity,
        query: SemanticQuery,
        group_specs: list[tuple[str, str]],
        measure_specs: list[tuple[str, str, str]],
    ) -> str:
        grain = query.time_grain
        time_dim_label = group_specs[0][0] if grain and group_specs else None

        select_parts: list[str] = []
        group_by_idx: list[str] = []
        for i, (label, column) in enumerate(group_specs, start=1):
            if grain and label == time_dim_label:
                expr = f"DATE_TRUNC(CAST(`{column}` AS DATE), {_GRAIN_SQL[grain]})"
            else:
                expr = f"`{column}`"
            select_parts.append(f"{expr} AS `{label}`")
            group_by_idx.append(str(i))

        for label, agg, column in measure_specs:
            select_parts.append(f"{self._agg_sql(agg, column)} AS `{label}`")

        table = self._db.qualified_table(entity.table)
        sql = f"SELECT {', '.join(select_parts)}\nFROM {table}"
        where = self._where_sql(entity, query.filters)
        if where:
            sql += f"\nWHERE {where}"
        if group_by_idx:
            sql += f"\nGROUP BY {', '.join(group_by_idx)}"
        order = self._order_sql(query, group_specs, measure_specs)
        if order:
            sql += f"\nORDER BY {order}"
        sql += f"\nLIMIT {int(query.limit)}"
        return sql

    @staticmethod
    def _agg_sql(agg: str, column: str) -> str:
        if agg == "count":
            return "COUNT(*)" if column == "*" else f"COUNT(`{column}`)"
        if agg == "count_distinct":
            return f"COUNT(DISTINCT `{column}`)"
        return f"{agg.upper()}(`{column}`)"

    def _where_sql(self, entity: SemanticEntity, filters: list[SemanticFilter]) -> str:
        clauses = []
        for f in filters:
            col = f"`{self._filter_column(entity, f.field)}`"
            if f.op == "in":
                values = f.value if isinstance(f.value, list) else [f.value]
                clauses.append(f"{col} IN ({', '.join(self._lit(v) for v in values)})")
            elif f.op == "like":
                clauses.append(f"{col} LIKE {self._lit(f.value)}")
            else:
                clauses.append(f"{col} {f.op} {self._lit(f.value)}")
        return " AND ".join(clauses)

    def _order_sql(
        self,
        query: SemanticQuery,
        group_specs: list[tuple[str, str]],
        measure_specs: list[tuple[str, str, str]],
    ) -> str:
        target = self._order_target(query, group_specs, measure_specs)
        if not target:
            return ""
        return f"`{target}` {'DESC' if query.descending else 'ASC'}"

    @staticmethod
    def _order_target(
        query: SemanticQuery,
        group_specs: list[tuple[str, str]],
        measure_specs: list[tuple[str, str, str]],
    ) -> str | None:
        if query.order_by:
            return query.order_by
        if measure_specs:
            return measure_specs[0][0]
        if group_specs:
            return group_specs[0][0]
        return None

    @staticmethod
    def _lit(value: Any) -> str:
        """A safe SQL literal. Strings are single-quote-escaped; values come from semantic
        specs and this surface is read-only + RBAC-gated, but we escape regardless."""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"

    # --- in-process aggregation (portable path) ----------------------------------------

    def _aggregate(
        self,
        source: list[Row],
        query: SemanticQuery,
        group_specs: list[tuple[str, str]],
        measure_specs: list[tuple[str, str, str]],
    ) -> list[dict[str, Any]]:
        entity_filters = query.filters
        grain = query.time_grain
        time_dim_label = group_specs[0][0] if grain and group_specs else None

        buckets: dict[tuple[Any, ...], list[Row]] = defaultdict(list)
        for row in source:
            if not all(self._row_matches(row, f, group_specs) for f in entity_filters):
                continue
            key = tuple(
                self._trunc(row.get(col), grain) if grain and label == time_dim_label else row.get(col)
                for label, col in group_specs
            )
            buckets[key].append(row)

        # An ungrouped query is a single all-rows aggregate — yield exactly one row even
        # over no data (matching SQL's `SELECT COUNT(*) FROM empty` → one row).
        if not group_specs and () not in buckets:
            buckets[()] = []

        out: list[dict[str, Any]] = []
        for key, rows in buckets.items():
            record: dict[str, Any] = {label: key[i] for i, (label, _) in enumerate(group_specs)}
            for label, agg, col in measure_specs:
                # COUNT(*) counts rows; every other agg reads the measure's column.
                values = [1] * len(rows) if col == "*" else [r.get(col) for r in rows]
                record[label] = self._apply_agg(agg, values)
            out.append(record)
        return out

    def _row_matches(self, row: Row, f: SemanticFilter, group_specs: list[tuple[str, str]]) -> bool:
        # Resolve filter field to a column via the same map used for groups/dimensions.
        col = f.field
        for label, column in group_specs:
            if label == f.field:
                col = column
                break
        actual = row.get(col)
        if f.op == "in":
            values = f.value if isinstance(f.value, list) else [f.value]
            return bool(actual in values)
        if f.op == "like":
            return bool(actual is not None and str(f.value).replace("%", "") in str(actual))
        if f.op == "=":
            return bool(actual == f.value)
        if f.op == "!=":
            return bool(actual != f.value)
        if actual is None or f.value is None:
            return False
        a_num, b_num = self._num(actual), self._num(f.value)
        if a_num is not None and b_num is not None:
            return {">": a_num > b_num, ">=": a_num >= b_num, "<": a_num < b_num, "<=": a_num <= b_num}[f.op]
        a_str, b_str = str(actual), str(f.value)
        return {">": a_str > b_str, ">=": a_str >= b_str, "<": a_str < b_str, "<=": a_str <= b_str}[f.op]

    @staticmethod
    def _apply_agg(agg: str, values: list[Any]) -> Any:
        if agg == "count":
            return sum(1 for v in values if v is not None)
        if agg == "count_distinct":
            return len({v for v in values if v is not None})
        nums = [n for n in (SemanticManager._num(v) for v in values) if n is not None]
        if not nums:
            return 0
        if agg == "sum":
            return round(sum(nums), 6)
        if agg == "avg":
            return round(sum(nums) / len(nums), 6)
        if agg == "min":
            return min(nums)
        if agg == "max":
            return max(nums)
        return 0

    def _order_and_limit(
        self,
        rows: list[dict[str, Any]],
        query: SemanticQuery,
        group_specs: list[tuple[str, str]],
        measure_specs: list[tuple[str, str, str]],
    ) -> list[dict[str, Any]]:
        # BigQuery already ordered+limited; only re-apply for the in-process path.
        if self._db.supports_sql:  # pragma: no cover — push-down already ordered
            return rows
        target = self._order_target(query, group_specs, measure_specs)
        if target:
            rows = sorted(
                rows,
                key=lambda r: (r.get(target) is None, self._sort_key(r.get(target))),
                reverse=query.descending,
            )
        return rows[: query.limit]

    @staticmethod
    def _sort_key(value: Any) -> Any:
        n = SemanticManager._num(value)
        return n if n is not None else str(value)

    # --- value coercion helpers --------------------------------------------------------

    @staticmethod
    def _num(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _trunc(value: Any, grain: str | None) -> str | None:
        """Truncate a date/datetime/ISO-string to the start of its grain bucket (ISO date)."""
        if value is None or grain is None:
            return None
        d: date
        if isinstance(value, datetime):
            d = value.date()
        elif isinstance(value, date):
            d = value
        else:
            try:
                d = datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
            except ValueError:
                return str(value)
        if grain == "day":
            return d.isoformat()
        if grain == "week":
            return (d - timedelta(days=d.weekday())).isoformat()
        if grain == "month":
            return d.replace(day=1).isoformat()
        if grain == "quarter":
            return d.replace(month=((d.month - 1) // 3) * 3 + 1, day=1).isoformat()
        if grain == "year":
            return d.replace(month=1, day=1).isoformat()
        return d.isoformat()

    # --- row (de)serialisation ---------------------------------------------------------

    @staticmethod
    def _to_row(model: SemanticModel) -> Row:
        return {
            "model_id": model.model_id,
            "name": model.name,
            "description": model.description,
            "definition_json": json.dumps([e.model_dump() for e in model.entities]),
            "created_at": model.created_at.isoformat(),
            "updated_at": model.updated_at.isoformat(),
        }

    @staticmethod
    def _from_row(row: Row) -> SemanticModel:
        raw = row.get("definition_json")
        entities = json.loads(raw) if raw else []
        return SemanticModel(
            model_id=row["model_id"],
            name=row["name"],
            description=row.get("description") or "",
            entities=entities,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

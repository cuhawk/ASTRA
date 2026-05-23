from __future__ import annotations

from pathlib import Path
from typing import Any

import kuzu

_PY_TO_KUZU: dict[type, str] = {
    str: "STRING",
    bool: "BOOLEAN",
    int: "INT64",
    float: "DOUBLE",
}


def _kuzu_type(value: Any) -> str:
    for py_t, kz_t in _PY_TO_KUZU.items():
        if type(value) is py_t:
            return kz_t
    raise ValueError(
        f"Unsupported property type {type(value).__name__!r} for value {value!r}; "
        "supported: str, int, float, bool"
    )


class GraphStore:
    def __init__(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._db = kuzu.Database(str(path))
        self._conn = kuzu.Connection(self._db)
        self._node_tables: dict[str, set[str]] = {}
        self._rel_tables: set[tuple[str, str, str]] = set()
        self._load_existing_tables()

    def _load_existing_tables(self) -> None:
        result = self._conn.execute("CALL show_tables() RETURN *")
        rows: list[tuple[str, str]] = []
        while result.has_next():
            row = result.get_next()
            rows.append((row[1], row[2]))
        for name, kind in rows:
            if kind == "NODE":
                props = self._fetch_node_props(name)
                self._node_tables[name] = props
            elif kind == "REL":
                conn_info = self._conn.execute(f"CALL show_connection('{name}') RETURN *")
                while conn_info.has_next():
                    cr = conn_info.get_next()
                    self._rel_tables.add((cr[0], cr[1], name))

    def _fetch_node_props(self, label: str) -> set[str]:
        result = self._conn.execute(f"CALL table_info('{label}') RETURN *")
        props: set[str] = set()
        while result.has_next():
            row = result.get_next()
            props.add(row[1])
        return props

    def add_node(self, label: str, props: dict[str, Any]) -> None:
        if "id" not in props:
            raise ValueError("node props must contain 'id'")
        if not isinstance(props["id"], str):
            raise ValueError("node 'id' must be str")
        for v in props.values():
            _kuzu_type(v)

        if label not in self._node_tables:
            self._create_node_table(label, props)
        else:
            existing = self._node_tables[label]
            new_keys = set(props.keys()) - existing
            if new_keys:
                raise ValueError(
                    f"node table {label!r} has no columns {sorted(new_keys)}; "
                    "schema evolution is not supported in MVP"
                )

        non_id = {k: v for k, v in props.items() if k != "id"}
        if non_id:
            sets = ", ".join(f"n.{k} = $p_{k}" for k in non_id)
            params = {"id": props["id"], **{f"p_{k}": v for k, v in non_id.items()}}
            self._conn.execute(
                f"MERGE (n:{label} {{id: $id}}) SET {sets}",
                parameters=params,
            )
        else:
            self._conn.execute(
                f"MERGE (n:{label} {{id: $id}})",
                parameters={"id": props["id"]},
            )

    def _create_node_table(self, label: str, props: dict[str, Any]) -> None:
        cols = [f"id STRING"]
        for k, v in props.items():
            if k == "id":
                continue
            cols.append(f"{k} {_kuzu_type(v)}")
        cols.append("PRIMARY KEY(id)")
        self._conn.execute(f"CREATE NODE TABLE {label}({', '.join(cols)})")
        self._node_tables[label] = set(props.keys())

    def add_edge(
        self,
        from_label: str,
        from_id: str,
        to_label: str,
        to_id: str,
        rel_type: str,
        props: dict[str, Any] | None = None,
    ) -> None:
        props = props or {}
        for v in props.values():
            _kuzu_type(v)
        key = (from_label, to_label, rel_type)
        if key not in self._rel_tables:
            self._create_rel_table(from_label, to_label, rel_type, props)

        params: dict[str, Any] = {"from_id": from_id, "to_id": to_id}
        clause = f"MATCH (a:{from_label} {{id: $from_id}}), (b:{to_label} {{id: $to_id}}) MERGE (a)-[r:{rel_type}]->(b)"
        if props:
            sets = ", ".join(f"r.{k} = $p_{k}" for k in props)
            for k, v in props.items():
                params[f"p_{k}"] = v
            clause = f"{clause} SET {sets}"
        self._conn.execute(clause, parameters=params)

    def _create_rel_table(
        self,
        from_label: str,
        to_label: str,
        rel_type: str,
        props: dict[str, Any],
    ) -> None:
        cols = [f"FROM {from_label} TO {to_label}"]
        for k, v in props.items():
            cols.append(f"{k} {_kuzu_type(v)}")
        self._conn.execute(f"CREATE REL TABLE {rel_type}({', '.join(cols)})")
        self._rel_tables.add((from_label, to_label, rel_type))

    def query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            result = self._conn.execute(cypher, parameters=params or {})
        except RuntimeError as e:
            # Kuzu raises "Binder exception: Table X does not exist." when a
            # query references a node/rel label that was never created. For an
            # empty run (zero functions/edges) this is the expected state —
            # surface it as an empty result rather than a 500.
            msg = str(e)
            if "does not exist" in msg and "Binder exception" in msg:
                return []
            raise
        cols = result.get_column_names()
        rows: list[dict[str, Any]] = []
        while result.has_next():
            values = result.get_next()
            rows.append({c: v for c, v in zip(cols, values)})
        return rows

    def close(self) -> None:
        conn = getattr(self, "_conn", None)
        db = getattr(self, "_db", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._conn = None
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
            self._db = None

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

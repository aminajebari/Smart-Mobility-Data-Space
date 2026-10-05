"""SQLite persistence for contracts, audit log and live catalogue metadata."""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    id TEXT PRIMARY KEY,
    requester_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    terms TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    requester_id TEXT NOT NULL,
    provider_id TEXT,
    dataset_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    policy_type TEXT,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    contract_id TEXT,
    via TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dataset_status (
    dataset_id TEXT PRIMARY KEY,
    access_url TEXT,
    last_published TEXT,
    record_count INTEGER
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    # -- contracts -------------------------------------------------------
    def create_contract(self, requester_id, provider_id, dataset_id, purpose, duration_days, terms) -> dict:
        created = datetime.now()
        row = {
            "id": f"ctr-{uuid.uuid4().hex[:10]}",
            "requester_id": requester_id,
            "provider_id": provider_id,
            "dataset_id": dataset_id,
            "purpose": purpose,
            "status": "active",
            "created_at": created.isoformat(timespec="seconds"),
            "expires_at": (created + timedelta(days=duration_days)).isoformat(timespec="seconds"),
            "terms": json.dumps(terms),
        }
        with self._lock:
            self._conn.execute(
                "INSERT INTO contracts VALUES (:id,:requester_id,:provider_id,:dataset_id,:purpose,:status,:created_at,:expires_at,:terms)",
                row,
            )
            self._conn.commit()
        return self._contract_dict(row)

    def find_active_contract(self, requester_id, dataset_id, purpose) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM contracts WHERE requester_id=? AND dataset_id=? AND purpose=? "
                "AND status='active' AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
                (requester_id, dataset_id, purpose, _now()),
            ).fetchone()
        return self._contract_dict(dict(row)) if row else None

    def list_contracts(self, requester_id=None, dataset_id=None) -> list[dict]:
        query, args = "SELECT * FROM contracts WHERE 1=1", []
        if requester_id:
            query += " AND requester_id=?"
            args.append(requester_id)
        if dataset_id:
            query += " AND dataset_id=?"
            args.append(dataset_id)
        with self._lock:
            rows = self._conn.execute(query + " ORDER BY created_at DESC", args).fetchall()
        return [self._contract_dict(dict(r)) for r in rows]

    def revoke_contract(self, contract_id) -> Optional[dict]:
        with self._lock:
            self._conn.execute("UPDATE contracts SET status='revoked' WHERE id=?", (contract_id,))
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        return self._contract_dict(dict(row)) if row else None

    @staticmethod
    def _contract_dict(row: dict) -> dict:
        return {**row, "terms": json.loads(row["terms"]) if isinstance(row["terms"], str) else row["terms"]}

    # -- audit -----------------------------------------------------------
    def add_audit(self, **entry) -> int:
        entry = {"timestamp": _now(), "provider_id": None, "policy_type": None, "contract_id": None, "via": "", **entry}
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO audit (timestamp,requester_id,provider_id,dataset_id,purpose,policy_type,decision,reason,contract_id,via) "
                "VALUES (:timestamp,:requester_id,:provider_id,:dataset_id,:purpose,:policy_type,:decision,:reason,:contract_id,:via)",
                entry,
            )
            self._conn.commit()
            return cur.lastrowid

    def list_audit(self, limit=100, requester_id=None, dataset_id=None, provider_id=None, decision=None) -> list[dict]:
        query, args = "SELECT * FROM audit WHERE 1=1", []
        for column, value in (("requester_id", requester_id), ("dataset_id", dataset_id),
                              ("provider_id", provider_id), ("decision", decision)):
            if value:
                query += f" AND {column}=?"
                args.append(value)
        with self._lock:
            rows = self._conn.execute(query + " ORDER BY id DESC LIMIT ?", [*args, limit]).fetchall()
        return [dict(r) for r in rows]

    def audit_stats(self) -> dict:
        with self._lock:
            rows = self._conn.execute("SELECT decision, COUNT(*) AS n FROM audit GROUP BY decision").fetchall()
        counts = {r["decision"]: r["n"] for r in rows}
        return {"total": sum(counts.values()), "allow": counts.get("allow", 0), "deny": counts.get("deny", 0)}

    # -- live catalogue metadata ----------------------------------------
    def upsert_dataset_status(self, dataset_id, access_url, last_published, record_count):
        with self._lock:
            self._conn.execute(
                "INSERT INTO dataset_status VALUES (?,?,?,?) ON CONFLICT(dataset_id) DO UPDATE SET "
                "access_url=COALESCE(excluded.access_url, access_url), "
                "last_published=COALESCE(excluded.last_published, last_published), "
                "record_count=COALESCE(excluded.record_count, record_count)",
                (dataset_id, access_url, last_published, record_count),
            )
            self._conn.commit()

    def dataset_status(self) -> dict[str, dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM dataset_status").fetchall()
        return {r["dataset_id"]: dict(r) for r in rows}

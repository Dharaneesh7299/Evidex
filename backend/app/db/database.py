"""SQLite access layer.

The MVP uses a tiny custom DAO on top of :mod:`sqlite3` to avoid pulling
in an ORM. All persistence flows through :class:`Database` so the rest
of the codebase can request high-level operations.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.core.config import BACKEND_ROOT


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT,
    authors TEXT,
    year TEXT,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    char_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_paper ON chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_chunks_paper_page ON chunks(paper_id, page_number);

CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    research_question TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    paper_ids_json TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investigation_papers (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    paper_id TEXT NOT NULL,
    relevance_score REAL,
    relevance_label TEXT,
    relevance_explanation TEXT,
    summary TEXT,
    UNIQUE(investigation_id, paper_id),
    FOREIGN KEY(investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
    FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_inv_papers_inv ON investigation_papers(investigation_id);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    paper_id TEXT,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    page_number INTEGER,
    chunk_id TEXT,
    evidence_relationship TEXT NOT NULL,
    support_status TEXT NOT NULL DEFAULT 'supported',
    explanation TEXT,
    limitations_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
    FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_inv ON claims(investigation_id);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    claim_id TEXT,
    paper_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    chunk_id TEXT,
    passage TEXT NOT NULL,
    relationship TEXT NOT NULL,
    explanation TEXT,
    reference_valid INTEGER NOT NULL DEFAULT 0,
    support_status TEXT NOT NULL DEFAULT 'supports',
    validated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
    FOREIGN KEY(claim_id) REFERENCES claims(id) ON DELETE SET NULL,
    FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_inv ON evidence(investigation_id);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL UNIQUE,
    content_json TEXT NOT NULL,
    markdown TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    validation_notes_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
);
"""


class Database:
    """Thread-safe SQLite wrapper with the schema this app needs."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # check_same_thread=False so the FastAPI threadpool can share the
        # connection; we still serialise writes via the lock.
        self._conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None,  # autocommit; we manage transactions explicitly
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        with self._lock:
            self._conn.executescript(SCHEMA_SQL)
            # Automatic schema migration for existing databases
            for migration in [
                "ALTER TABLE evidence ADD COLUMN reference_valid INTEGER DEFAULT 0",
                "ALTER TABLE evidence ADD COLUMN support_status TEXT DEFAULT 'supports'",
                "ALTER TABLE claims ADD COLUMN support_status TEXT DEFAULT 'supported'",
            ]:
                try:
                    self._conn.execute(migration)
                except sqlite3.OperationalError:
                    pass
            try:
                self._conn.execute("UPDATE reports SET content_json = REPLACE(content_json, 'PaperProof', 'Evidex'), markdown = REPLACE(markdown, 'PaperProof', 'Evidex') WHERE content_json LIKE '%PaperProof%' OR markdown LIKE '%PaperProof%'")
            except Exception:
                pass

    # ---- low level ----
    @contextmanager
    def transaction(self):
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, list(params))

    def executemany(self, sql: str, params_list: List[Iterable[Any]]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, [list(p) for p in params_list])

    def query(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, list(params))
            return [dict(row) for row in cur.fetchall()]

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- helpers ----
    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _loads(value: Optional[str]) -> Any:
        if value is None or value == "":
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _dumps(value: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str)

    # ---- papers ----
    def create_paper(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pid = data.get("id") or _new_id("paper")
        now = _utcnow_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO papers (id, title, authors, year, original_filename, stored_path,
                    file_size, page_count, char_count, status, error, metadata_json,
                    created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    pid,
                    data.get("title"),
                    data.get("authors"),
                    data.get("year"),
                    data["original_filename"],
                    data.get("stored_path", ""),
                    int(data.get("file_size", 0)),
                    int(data.get("page_count", 0)),
                    int(data.get("char_count", 0)),
                    data.get("status", "ready"),
                    data.get("error"),
                    self._dumps(data.get("metadata")),
                    now,
                    now,
                ],
            )
        return self.get_paper(pid)  # type: ignore[return-value]

    def update_paper(self, paper_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {
            "title",
            "authors",
            "year",
            "status",
            "error",
            "page_count",
            "char_count",
            "metadata",
        }
        sets: List[str] = []
        params: List[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "metadata":
                sets.append("metadata_json = ?")
                params.append(self._dumps(value))
            else:
                sets.append(f"{key} = ?")
                params.append(value)
        if not sets:
            return
        sets.append("updated_at = ?")
        params.append(_utcnow_iso())
        params.append(paper_id)
        with self.transaction() as conn:
            conn.execute(f"UPDATE papers SET {', '.join(sets)} WHERE id = ?", params)

    def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(self.execute("SELECT * FROM papers WHERE id = ?", [paper_id]).fetchone())
        if row is not None:
            row["metadata"] = self._loads(row.pop("metadata_json"))
        return row

    def list_papers(self) -> List[Dict[str, Any]]:
        rows = self.query("SELECT * FROM papers ORDER BY created_at DESC")
        for row in rows:
            row["metadata"] = self._loads(row.pop("metadata_json"))
        return rows

    def delete_paper(self, paper_id: str) -> bool:
        with self.transaction() as conn:
            cur = conn.execute("DELETE FROM papers WHERE id = ?", [paper_id])
            return cur.rowcount > 0

    # ---- chunks ----
    def insert_chunks(self, paper_id: str, chunks: List[Dict[str, Any]]) -> None:
        if not chunks:
            return
        with self.transaction() as conn:
            conn.execute("DELETE FROM chunks WHERE paper_id = ?", [paper_id])
            conn.executemany(
                """
                INSERT INTO chunks (id, paper_id, page_number, chunk_index, text, token_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    [
                        c["id"],
                        paper_id,
                        int(c["page_number"]),
                        int(c["chunk_index"]),
                        c["text"],
                        int(c.get("token_count", len(c["text"].split()))),
                    ]
                    for c in chunks
                ],
            )

    def get_chunks(self, paper_id: str) -> List[Dict[str, Any]]:
        return self.query(
            "SELECT * FROM chunks WHERE paper_id = ? ORDER BY page_number, chunk_index",
            [paper_id],
        )

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        return self._row_to_dict(self.execute("SELECT * FROM chunks WHERE id = ?", [chunk_id]).fetchone())

    def get_page_text(self, paper_id: str, page_number: int) -> str:
        rows = self.query(
            "SELECT text FROM chunks WHERE paper_id = ? AND page_number = ? ORDER BY chunk_index",
            [paper_id, page_number],
        )
        return "".join(r["text"] for r in rows)

    # ---- investigations ----
    def create_investigation(
        self,
        research_question: str,
        paper_ids: List[str],
    ) -> Dict[str, Any]:
        iid = _new_id("inv")
        now = _utcnow_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO investigations
                    (id, research_question, status, stage, progress, paper_ids_json,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    iid,
                    research_question,
                    "pending",
                    "queued",
                    0,
                    json.dumps(paper_ids),
                    now,
                    now,
                ],
            )
        return self.get_investigation(iid)  # type: ignore[return-value]

    def update_investigation(self, investigation_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {
            "status",
            "stage",
            "progress",
            "error",
            "result",
        }
        sets: List[str] = []
        params: List[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "result":
                sets.append("result_json = ?")
                params.append(self._dumps(value))
            else:
                sets.append(f"{key} = ?")
                params.append(value)
        if not sets:
            return
        sets.append("updated_at = ?")
        params.append(_utcnow_iso())
        params.append(investigation_id)
        with self.transaction() as conn:
            conn.execute(f"UPDATE investigations SET {', '.join(sets)} WHERE id = ?", params)

    def get_investigation(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(
            self.execute("SELECT * FROM investigations WHERE id = ?", [investigation_id]).fetchone()
        )
        if row is None:
            return None
        row["paper_ids"] = self._loads(row.pop("paper_ids_json")) or []
        row["result"] = self._loads(row.pop("result_json"))
        return row

    def list_investigations(self) -> List[Dict[str, Any]]:
        rows = self.query("SELECT * FROM investigations ORDER BY created_at DESC")
        for row in rows:
            row["paper_ids"] = self._loads(row.pop("paper_ids_json")) or []
            row["result"] = self._loads(row.pop("result_json"))
        return rows

    # ---- investigation_papers ----
    def upsert_investigation_paper(self, record: Dict[str, Any]) -> None:
        rid = record.get("id") or _new_id("invp")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO investigation_papers
                    (id, investigation_id, paper_id, relevance_score, relevance_label,
                     relevance_explanation, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(investigation_id, paper_id) DO UPDATE SET
                    relevance_score = excluded.relevance_score,
                    relevance_label = excluded.relevance_label,
                    relevance_explanation = excluded.relevance_explanation,
                    summary = excluded.summary
                """,
                [
                    rid,
                    record["investigation_id"],
                    record["paper_id"],
                    record.get("relevance_score"),
                    record.get("relevance_label"),
                    record.get("relevance_explanation"),
                    record.get("summary"),
                ],
            )

    def get_investigation_papers(self, investigation_id: str) -> List[Dict[str, Any]]:
        return self.query(
            "SELECT * FROM investigation_papers WHERE investigation_id = ?",
            [investigation_id],
        )

    # ---- claims ----
    def create_claim(self, record: Dict[str, Any]) -> Dict[str, Any]:
        cid = record.get("id") or _new_id("claim")
        now = _utcnow_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO claims
                    (id, investigation_id, paper_id, text, category, page_number,
                     chunk_id, evidence_relationship, support_status, explanation, limitations_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    cid,
                    record["investigation_id"],
                    record.get("paper_id"),
                    record["text"],
                    record.get("category", "general"),
                    record.get("page_number"),
                    record.get("chunk_id"),
                    record.get("evidence_relationship", "insufficient_information"),
                    record.get("support_status", "supported"),
                    record.get("explanation"),
                    self._dumps(record.get("limitations", [])),
                    now,
                ],
            )
        return self.get_claim(cid)  # type: ignore[return-value]

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(self.execute("SELECT * FROM claims WHERE id = ?", [claim_id]).fetchone())
        if row is not None:
            row["limitations"] = self._loads(row.pop("limitations_json")) or []
            row["support_status"] = row.get("support_status") or "supported"
        return row

    def list_claims(self, investigation_id: str) -> List[Dict[str, Any]]:
        rows = self.query("SELECT * FROM claims WHERE investigation_id = ? ORDER BY created_at", [investigation_id])
        for row in rows:
            row["limitations"] = self._loads(row.pop("limitations_json")) or []
            row["support_status"] = row.get("support_status") or "supported"
        return rows

    def delete_claims(self, investigation_id: str) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM claims WHERE investigation_id = ?", [investigation_id])

    # ---- evidence ----
    def create_evidence(self, record: Dict[str, Any]) -> Dict[str, Any]:
        eid = record.get("id") or _new_id("evi")
        now = _utcnow_iso()
        ref_valid = int(bool(record.get("reference_valid", record.get("validated", False))))
        support_status = record.get("support_status") or record.get("relationship", "supports")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO evidence
                    (id, investigation_id, claim_id, paper_id, page_number, chunk_id,
                     passage, relationship, explanation, reference_valid, support_status, validated, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    eid,
                    record["investigation_id"],
                    record.get("claim_id"),
                    record["paper_id"],
                    int(record["page_number"]),
                    record.get("chunk_id"),
                    record["passage"],
                    record.get("relationship", "supports"),
                    record.get("explanation"),
                    ref_valid,
                    support_status,
                    ref_valid,
                    now,
                ],
            )
        return self.get_evidence(eid)  # type: ignore[return-value]

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(self.execute("SELECT * FROM evidence WHERE id = ?", [evidence_id]).fetchone())
        if row is not None:
            row["reference_valid"] = bool(row.get("reference_valid", row.get("validated", 0)))
            row["validated"] = row["reference_valid"]
            row["support_status"] = row.get("support_status") or "supports"
        return row

    def list_evidence(self, investigation_id: str) -> List[Dict[str, Any]]:
        rows = self.query("SELECT * FROM evidence WHERE investigation_id = ?", [investigation_id])
        for row in rows:
            row["reference_valid"] = bool(row.get("reference_valid", row.get("validated", 0)))
            row["validated"] = row["reference_valid"]
            row["support_status"] = row.get("support_status") or "supports"
        return rows

    def delete_evidence(self, investigation_id: str) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM evidence WHERE investigation_id = ?", [investigation_id])

    # ---- reports ----
    def upsert_report(
        self,
        investigation_id: str,
        content: Dict[str, Any],
        markdown: str,
        validation_status: str,
        notes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        rid = _new_id("rep")
        now = _utcnow_iso()
        with self.transaction() as conn:
            conn.execute("DELETE FROM reports WHERE investigation_id = ?", [investigation_id])
            conn.execute(
                """
                INSERT INTO reports
                    (id, investigation_id, content_json, markdown, validation_status,
                     validation_notes_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    rid,
                    investigation_id,
                    self._dumps(content),
                    markdown,
                    validation_status,
                    self._dumps(notes or []),
                    now,
                ],
            )
        return self.get_report(investigation_id)  # type: ignore[return-value]

    def get_report(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        row = self._row_to_dict(
            self.execute("SELECT * FROM reports WHERE investigation_id = ?", [investigation_id]).fetchone()
        )
        if row is None:
            return None
        row["content"] = self._loads(row.pop("content_json"))
        row["validation_notes"] = self._loads(row.pop("validation_notes_json")) or []
        return row


# Global DB accessor. The application owns a single instance per process.
_db: Optional[Database] = None


def get_db() -> Database:
    from app.core.config import get_settings

    global _db
    if _db is None:
        settings = get_settings()
        # Allow ``sqlite:///./evidex.db`` style URLs.
        url = settings.database_url
        if url.startswith("sqlite:///"):
            db_path = Path(url[len("sqlite:///") :])
        elif url.startswith("sqlite://"):
            db_path = Path(url[len("sqlite://") :])
        else:
            db_path = Path(url)
        if not db_path.is_absolute():
            db_path = (BACKEND_ROOT / db_path).resolve()
        _db = Database(db_path)
    return _db


def reset_db_for_tests() -> Database:
    """Recreate the global database; tests only."""
    global _db
    if _db is not None:
        try:
            _db.close()
        except Exception:  # noqa: BLE001
            pass
    _db = None
    return get_db()

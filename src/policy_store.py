"""정책 후보와 티스토리 패키지 상태를 관리하는 SQLite 저장소."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import DATA_DIR

DB_PATH = DATA_DIR / "policy_workspace.sqlite3"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _connect(path: Path | None = None) -> sqlite3.Connection:
    db = path or DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init(conn)
    return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            external_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            agency TEXT NOT NULL DEFAULT '',
            region TEXT NOT NULL DEFAULT '전국',
            source_url TEXT NOT NULL,
            official INTEGER NOT NULL DEFAULT 0,
            facts_json TEXT NOT NULL,
            source_updated_at TEXT NOT NULL DEFAULT '',
            checked_at TEXT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ready',
            last_error TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS packages (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL REFERENCES candidates(id),
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            published_at TEXT NOT NULL DEFAULT '',
            tistory_url TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_candidates_score
            ON candidates(status, score DESC, checked_at DESC);
        CREATE INDEX IF NOT EXISTS idx_packages_created
            ON packages(created_at DESC);
        CREATE TABLE IF NOT EXISTS workspace_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    conn.commit()


def upsert_candidate(candidate: dict, path: Path | None = None) -> None:
    facts = candidate.get("facts", {})
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO candidates (
                id, source_type, external_id, title, category, agency, region,
                source_url, official, facts_json, source_updated_at, checked_at,
                score, status, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_type=excluded.source_type,
                external_id=excluded.external_id,
                title=excluded.title,
                category=excluded.category,
                agency=excluded.agency,
                region=excluded.region,
                source_url=excluded.source_url,
                official=excluded.official,
                facts_json=excluded.facts_json,
                source_updated_at=excluded.source_updated_at,
                checked_at=excluded.checked_at,
                score=excluded.score,
                status=CASE
                    WHEN candidates.status IN ('generated', 'generating')
                    THEN candidates.status ELSE excluded.status END,
                last_error=excluded.last_error
            """,
            (
                candidate["id"], candidate["source_type"], candidate.get("external_id", ""),
                candidate["title"], candidate["category"], candidate.get("agency", ""),
                candidate.get("region", "전국"), candidate["source_url"],
                int(bool(candidate.get("official"))),
                json.dumps(facts, ensure_ascii=False), candidate.get("source_updated_at", ""),
                candidate.get("checked_at", now_iso()), int(candidate.get("score", 0)),
                candidate.get("status", "ready"), candidate.get("last_error", ""),
            ),
        )


def _candidate(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["official"] = bool(item["official"])
    item["facts"] = json.loads(item.pop("facts_json") or "{}")
    return item


def get_candidate(candidate_id: str, path: Path | None = None) -> dict | None:
    with _connect(path) as conn:
        return _candidate(conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone())


def list_candidates(
    *, status: str | None = None, category: str | None = None,
    region: str | None = None, limit: int = 200, path: Path | None = None,
) -> list[dict]:
    where, params = [], []
    if status:
        where.append("status=?")
        params.append(status)
    if category:
        where.append("category=?")
        params.append(category)
    if region:
        where.append("region=?")
        params.append(region)
    sql = "SELECT * FROM candidates"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score DESC, checked_at DESC LIMIT ?"
    params.append(limit)
    with _connect(path) as conn:
        return [_candidate(row) for row in conn.execute(sql, params).fetchall()]


def hide_gov24_candidates(path: Path | None = None) -> None:
    """새 추천 수집 전 기존 미생성 보조금24 후보를 기본 목록에서 숨긴다."""
    with _connect(path) as conn:
        conn.execute(
            "UPDATE candidates SET status='filtered_out', "
            "last_error='현재 30~50대 생활밀착 추천 기준에서 제외됨' "
            "WHERE source_type='gov24' AND status IN ('ready', 'failed')"
        )


def set_candidate_status(
    candidate_id: str, status: str, error: str = "", path: Path | None = None
) -> None:
    with _connect(path) as conn:
        conn.execute(
            "UPDATE candidates SET status=?, last_error=? WHERE id=?",
            (status, error, candidate_id),
        )


def save_package(package: dict, path: Path | None = None) -> None:
    created = package.get("created_at", now_iso())
    updated = package.get("updated_at", created)
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO packages (
                id, candidate_id, title, category, path, status, created_at,
                updated_at, published_at, tistory_url, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, category=excluded.category, path=excluded.path,
                status=excluded.status, updated_at=excluded.updated_at,
                published_at=excluded.published_at, tistory_url=excluded.tistory_url,
                error=excluded.error
            """,
            (
                package["id"], package["candidate_id"], package["title"], package["category"],
                package["path"], package.get("status", "ready"), created, updated,
                package.get("published_at", ""), package.get("tistory_url", ""),
                package.get("error", ""),
            ),
        )


def get_package(package_id: str, path: Path | None = None) -> dict | None:
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM packages WHERE id=?", (package_id,)).fetchone()
        return dict(row) if row else None


def list_packages(status: str | None = None, limit: int = 100, path: Path | None = None) -> list[dict]:
    sql, params = "SELECT * FROM packages", []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connect(path) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def mark_published(package_id: str, url: str = "", path: Path | None = None) -> dict:
    published = now_iso()
    with _connect(path) as conn:
        conn.execute(
            "UPDATE packages SET status='published', published_at=?, tistory_url=?, updated_at=? WHERE id=?",
            (published, url, published, package_id),
        )
    package = get_package(package_id, path)
    if not package:
        raise KeyError(f"패키지를 찾을 수 없습니다: {package_id}")
    return package


def set_regions(regions: Iterable[str], path: Path | None = None) -> None:
    cleaned = [r.strip() for r in regions if r and r.strip()]
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO workspace_settings(key, value) VALUES('regions', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(cleaned, ensure_ascii=False),),
        )


def get_regions(path: Path | None = None) -> list[str]:
    with _connect(path) as conn:
        row = conn.execute("SELECT value FROM workspace_settings WHERE key='regions'").fetchone()
    return json.loads(row["value"]) if row else []

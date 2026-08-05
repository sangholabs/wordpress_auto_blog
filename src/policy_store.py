"""정책 후보와 티스토리 패키지 상태를 관리하는 SQLite 저장소."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
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
            last_error TEXT NOT NULL DEFAULT '',
            generation_started_at TEXT NOT NULL DEFAULT ''
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
        CREATE TABLE IF NOT EXISTS automation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_type TEXT NOT NULL DEFAULT 'scheduled',
            status TEXT NOT NULL DEFAULT 'running',
            requested_count INTEGER NOT NULL DEFAULT 0,
            generated_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL DEFAULT '',
            errors_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS seo_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id TEXT NOT NULL REFERENCES packages(id),
            phase TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            score INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            result_json TEXT NOT NULL,
            checked_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_automation_runs_started
            ON automation_runs(started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_seo_audits_package
            ON seo_audits(package_id, phase, checked_at DESC);
        """
    )
    package_columns = {row[1] for row in conn.execute("PRAGMA table_info(packages)")}
    if "generation_mode" not in package_columns:
        conn.execute("ALTER TABLE packages ADD COLUMN generation_mode TEXT NOT NULL DEFAULT 'manual'")
    if "automation_run_id" not in package_columns:
        conn.execute("ALTER TABLE packages ADD COLUMN automation_run_id INTEGER")
    candidate_columns = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
    if "generation_started_at" not in candidate_columns:
        conn.execute(
            "ALTER TABLE candidates ADD COLUMN generation_started_at TEXT NOT NULL DEFAULT ''"
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
                score, status, last_error, generation_started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                last_error=excluded.last_error,
                generation_started_at=CASE
                    WHEN candidates.status='generating' THEN candidates.generation_started_at
                    ELSE excluded.generation_started_at END
            """,
            (
                candidate["id"], candidate["source_type"], candidate.get("external_id", ""),
                candidate["title"], candidate["category"], candidate.get("agency", ""),
                candidate.get("region", "전국"), candidate["source_url"],
                int(bool(candidate.get("official"))),
                json.dumps(facts, ensure_ascii=False), candidate.get("source_updated_at", ""),
                candidate.get("checked_at", now_iso()), int(candidate.get("score", 0)),
                candidate.get("status", "ready"), candidate.get("last_error", ""),
                candidate.get("generation_started_at", ""),
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
        started_at = now_iso() if status == "generating" else ""
        conn.execute(
            "UPDATE candidates SET status=?, last_error=?, generation_started_at=? WHERE id=?",
            (status, error, started_at, candidate_id),
        )


def recover_stale_generating(
    stale_minutes: int = 60, path: Path | None = None,
) -> list[dict]:
    """중단된 생성 상태를 다시 선택 가능한 ready 상태로 안전하게 복구한다."""
    threshold = datetime.now(timezone.utc) - timedelta(minutes=max(1, stale_minutes))
    recovered: list[dict] = []
    with _connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT id, title, generation_started_at FROM candidates WHERE status='generating'"
        ).fetchall()
        for row in rows:
            started = _parse_iso(row["generation_started_at"])
            if started and started.astimezone(timezone.utc) > threshold:
                continue
            message = (
                "이전 글 생성 작업이 정상 종료되지 않아 자동 복구됨"
                + (f" (시작: {row['generation_started_at']})" if row["generation_started_at"] else "")
            )
            conn.execute(
                "UPDATE candidates SET status='ready', last_error=?, generation_started_at='' "
                "WHERE id=? AND status='generating'",
                (message, row["id"]),
            )
            recovered.append({"id": row["id"], "title": row["title"], "message": message})
        conn.commit()
    return recovered


def save_package(package: dict, path: Path | None = None) -> None:
    created = package.get("created_at", now_iso())
    updated = package.get("updated_at", created)
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT INTO packages (
                id, candidate_id, title, category, path, status, created_at,
                updated_at, published_at, tistory_url, error, generation_mode,
                automation_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, category=excluded.category, path=excluded.path,
                status=excluded.status, updated_at=excluded.updated_at,
                published_at=excluded.published_at, tistory_url=excluded.tistory_url,
                error=excluded.error, generation_mode=excluded.generation_mode,
                automation_run_id=excluded.automation_run_id
            """,
            (
                package["id"], package["candidate_id"], package["title"], package["category"],
                package["path"], package.get("status", "ready"), created, updated,
                package.get("published_at", ""), package.get("tistory_url", ""),
                package.get("error", ""),
                package.get("generation_mode", "manual"), package.get("automation_run_id"),
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


def set_workspace_setting(key: str, value: object, path: Path | None = None) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO workspace_settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )


def get_workspace_setting(key: str, default: object = None, path: Path | None = None) -> object:
    with _connect(path) as conn:
        row = conn.execute("SELECT value FROM workspace_settings WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return row["value"]


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def begin_automation_run(
    requested_count: int, trigger_type: str = "scheduled", path: Path | None = None,
    stale_hours: int = 6,
) -> int | None:
    """동시에 하나의 자동 실행만 허용하고 새 실행 ID를 반환한다."""
    started = now_iso()
    stale_before = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
    with _connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT id, started_at FROM automation_runs WHERE status='running' ORDER BY id DESC"
        ).fetchall()
        for row in rows:
            timestamp = _parse_iso(row["started_at"])
            if timestamp and timestamp.astimezone(timezone.utc) >= stale_before:
                conn.rollback()
                return None
            conn.execute(
                "UPDATE automation_runs SET status='failed', finished_at=?, "
                "errors_json=? WHERE id=?",
                (started, json.dumps(["이전 자동 실행 잠금이 만료되어 종료 처리됨"], ensure_ascii=False), row["id"]),
            )
        cursor = conn.execute(
            "INSERT INTO automation_runs(trigger_type, status, requested_count, started_at) "
            "VALUES(?, 'running', ?, ?)",
            (trigger_type, requested_count, started),
        )
        conn.commit()
        return int(cursor.lastrowid)


def finish_automation_run(
    run_id: int, *, generated_count: int, failed_count: int,
    errors: list[str] | None = None, status: str = "completed", path: Path | None = None,
) -> None:
    with _connect(path) as conn:
        conn.execute(
            "UPDATE automation_runs SET status=?, generated_count=?, failed_count=?, "
            "finished_at=?, errors_json=? WHERE id=?",
            (status, generated_count, failed_count, now_iso(),
             json.dumps(errors or [], ensure_ascii=False), run_id),
        )


def get_automation_run(run_id: int, path: Path | None = None) -> dict | None:
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM automation_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["errors"] = json.loads(item.pop("errors_json") or "[]")
    return item


def list_automation_runs(limit: int = 20, path: Path | None = None) -> list[dict]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM automation_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["errors"] = json.loads(item.pop("errors_json") or "[]")
        result.append(item)
    return result


def auto_packages_on(date_value: str, path: Path | None = None) -> int:
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM packages "
            "WHERE generation_mode='auto' AND substr(created_at, 1, 10)=?",
            (date_value,),
        ).fetchone()
    return int(row["count"])


def save_seo_audit(
    package_id: str, phase: str, result: dict, url: str = "", path: Path | None = None,
) -> int:
    with _connect(path) as conn:
        cursor = conn.execute(
            "INSERT INTO seo_audits(package_id, phase, url, score, status, result_json, checked_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (package_id, phase, url, int(result.get("score", 0)), result.get("status", "error"),
             json.dumps(result, ensure_ascii=False), result.get("checked_at", now_iso())),
        )
        return int(cursor.lastrowid)


def latest_seo_audit(
    package_id: str, phase: str = "local", path: Path | None = None,
) -> dict | None:
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM seo_audits WHERE package_id=? AND phase=? "
            "ORDER BY id DESC LIMIT 1", (package_id, phase),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["result"] = json.loads(item.pop("result_json"))
    return item

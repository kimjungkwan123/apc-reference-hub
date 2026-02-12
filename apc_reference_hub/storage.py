from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from capture import TAG_COLUMNS


BASE_COLUMNS = [
    "id",
    "brand",
    "season",
    "item",
    "source_url",
    "image_path",
    "captured_at",
    *TAG_COLUMNS,
    "fit_key",
    "apc_fit_score",
    "notes",
    "status",
    "error_message",
    "created_at",
    "updated_at",
]


@dataclass
class RefRow:
    brand: str
    season: str
    item: str
    source_url: str


def db_conn(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reference_items (
          id TEXT PRIMARY KEY,
          brand TEXT NOT NULL,
          season TEXT NOT NULL,
          item TEXT NOT NULL,
          source_url TEXT NOT NULL,
          image_path TEXT NOT NULL DEFAULT '',
          captured_at TEXT NOT NULL DEFAULT '',
          SILHOUETTE TEXT NOT NULL DEFAULT '',
          COLOR TEXT NOT NULL DEFAULT '',
          DETAIL TEXT NOT NULL DEFAULT '',
          MATERIAL TEXT NOT NULL DEFAULT '',
          MOOD TEXT NOT NULL DEFAULT '',
          FUNCTION TEXT NOT NULL DEFAULT '',
          USE_CASE TEXT NOT NULL DEFAULT '',
          fit_key TEXT NOT NULL DEFAULT '',
          apc_fit_score INTEGER,
          notes TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'PENDING',
          error_message TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_references_source_key
        ON reference_items (brand, season, item, source_url)
        """
    )
    conn.commit()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def enqueue_urls(conn: sqlite3.Connection, rows: list[RefRow]) -> tuple[int, int]:
    inserted = 0
    duplicated = 0
    for row in rows:
        ts = now_iso()
        try:
            conn.execute(
                """
                INSERT INTO reference_items (
                  id, brand, season, item, source_url, created_at, updated_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')
                """,
                (
                    f"{row.brand}_{row.season}_{row.item}_{uuid4().hex[:16]}",
                    row.brand,
                    row.season,
                    row.item,
                    row.source_url,
                    ts,
                    ts,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            duplicated += 1
    conn.commit()
    return inserted, duplicated


def list_references(
    conn: sqlite3.Connection,
    brand: str = "",
    season: str = "",
    item: str = "",
    status: str = "ALL",
    limit: int = 5000,
) -> pd.DataFrame:
    conds = []
    params: list[Any] = []
    if brand.strip():
        conds.append("brand LIKE ?")
        params.append(f"%{brand.strip()}%")
    if season.strip():
        conds.append("season LIKE ?")
        params.append(f"%{season.strip()}%")
    if item.strip():
        conds.append("item LIKE ?")
        params.append(f"%{item.strip()}%")
    if status != "ALL":
        conds.append("status = ?")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(conds)) if conds else ""
    query = f"""
        SELECT {", ".join(BASE_COLUMNS)}
        FROM reference_items
        {where_sql}
        ORDER BY updated_at DESC
        LIMIT ?
    """
    params.append(limit)
    return pd.read_sql_query(query, conn, params=params)


def list_pending(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT id, brand, season, item, source_url
        FROM reference_items
        WHERE status = 'PENDING'
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in cur.fetchall()]


def list_failed(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT id, brand, season, item, source_url
        FROM reference_items
        WHERE status = 'FAILED'
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in cur.fetchall()]


def mark_processing(conn: sqlite3.Connection, ids: list[str]) -> None:
    if not ids:
        return
    ts = now_iso()
    q = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE reference_items SET status='PROCESSING', updated_at=? WHERE id IN ({q})",
        (ts, *ids),
    )
    conn.commit()


def apply_capture_result(conn: sqlite3.Connection, source_id: str, result: dict[str, Any]) -> None:
    ts = now_iso()
    score = None
    try:
        score = int(result.get("apc_fit_score")) if result.get("apc_fit_score") else None
    except Exception:
        score = None
    conn.execute(
        """
        UPDATE reference_items
        SET image_path = COALESCE(?, ''),
            captured_at = COALESCE(?, ''),
            status = ?,
            error_message = COALESCE(?, ''),
            apc_fit_score = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            result.get("image_path", ""),
            result.get("captured_at", ""),
            result.get("status", "FAILED"),
            result.get("error_message", ""),
            score,
            ts,
            source_id,
        ),
    )
    conn.commit()


def reset_to_pending(conn: sqlite3.Connection, ids: list[str]) -> int:
    if not ids:
        return 0
    q = ",".join("?" for _ in ids)
    ts = now_iso()
    cur = conn.execute(
        f"""
        UPDATE reference_items
        SET status='PENDING', error_message='', updated_at=?
        WHERE id IN ({q})
        """,
        (ts, *ids),
    )
    conn.commit()
    return cur.rowcount


def update_edited_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    updated = 0
    for row in rows:
        if not row.get("id"):
            continue
        ts = now_iso()
        values = [
            str(row.get("SILHOUETTE", "")),
            str(row.get("COLOR", "")),
            str(row.get("DETAIL", "")),
            str(row.get("MATERIAL", "")),
            str(row.get("MOOD", "")),
            str(row.get("FUNCTION", "")),
            str(row.get("USE_CASE", "")),
            str(row.get("fit_key", "")),
            int(row["apc_fit_score"]) if str(row.get("apc_fit_score", "")).strip().isdigit() else None,
            str(row.get("notes", "")),
            str(row.get("status", "")) or "SUCCESS",
            ts,
            str(row["id"]),
        ]
        conn.execute(
            """
            UPDATE reference_items
            SET SILHOUETTE=?,
                COLOR=?,
                DETAIL=?,
                MATERIAL=?,
                MOOD=?,
                FUNCTION=?,
                USE_CASE=?,
                fit_key=?,
                apc_fit_score=?,
                notes=?,
                status=?,
                updated_at=?
            WHERE id=?
            """,
            tuple(values),
        )
        updated += 1
    conn.commit()
    return updated


def save_uploaded_asset(
    conn: sqlite3.Connection,
    *,
    brand: str,
    season: str,
    item: str,
    source_url: str,
    image_path: str,
) -> str:
    ts = now_iso()
    rid = f"{brand}_{season}_{item}_{uuid4().hex[:16]}"
    conn.execute(
        """
        INSERT OR IGNORE INTO reference_items (
          id, brand, season, item, source_url, image_path, captured_at,
          status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'SUCCESS', ?, ?)
        """,
        (rid, brand, season, item, source_url, image_path, ts, ts, ts),
    )
    conn.commit()
    return rid


def export_csv(conn: sqlite3.Connection, target_csv: Path) -> Path:
    df = pd.read_sql_query(f"SELECT {', '.join(BASE_COLUMNS)} FROM reference_items ORDER BY updated_at DESC", conn)
    target_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target_csv, index=False)
    return target_csv


def stats(conn: sqlite3.Connection) -> dict[str, int]:
    data: dict[str, int] = {}
    for status in ["PENDING", "PROCESSING", "SUCCESS", "FAILED"]:
        c = conn.execute("SELECT COUNT(1) FROM reference_items WHERE status = ?", (status,)).fetchone()[0]
        data[status] = int(c or 0)
    total = conn.execute("SELECT COUNT(1) FROM reference_items").fetchone()[0]
    data["TOTAL"] = int(total or 0)
    return data

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from pathlib import Path

from capture import CaptureConfig, capture_urls
from storage import (
    apply_capture_result,
    db_conn,
    init_db,
    list_pending,
    mark_processing,
)


def run_worker(db_path: Path, output_root: Path, limit: int, width: int, height: int, timeout_ms: int, retries: int) -> tuple[int, int]:
    conn = db_conn(db_path)
    init_db(conn)
    pending = list_pending(conn, limit=limit)
    if not pending:
        return 0, 0

    grouped = defaultdict(list)
    for row in pending:
        grouped[(row["brand"], row["season"], row["item"])].append(row)

    ids = [r["id"] for r in pending]
    mark_processing(conn, ids)

    ok_count = 0
    fail_count = 0
    for (brand, season, item), rows in grouped.items():
        cfg = CaptureConfig(
            output_root=output_root,
            brand=brand,
            season=season,
            item=item,
            width=width,
            height=height,
            timeout_ms=timeout_ms,
            max_retries=retries,
        )
        urls = [r["source_url"] for r in rows]
        try:
            results = capture_urls(urls, cfg, start_index=1)
            for source_row, result in zip(rows, results):
                apply_capture_result(conn, source_row["id"], result)
                if result.get("status") == "SUCCESS":
                    ok_count += 1
                else:
                    fail_count += 1
        except Exception as e:  # noqa: BLE001
            for source_row in rows:
                apply_capture_result(
                    conn,
                    source_row["id"],
                    {"status": "FAILED", "error_message": str(e), "image_path": "", "captured_at": ""},
                )
                fail_count += 1

    return ok_count, fail_count


def main() -> None:
    app_dir = Path(__file__).resolve().parent
    data_root = Path(os.environ.get("APC_HUB_DATA_DIR", str(app_dir))).expanduser().resolve()
    parser = argparse.ArgumentParser(description="APC Reference Hub capture worker")
    parser.add_argument("--db-path", default=str(data_root / "data" / "references.db"))
    parser.add_argument("--output-root", default=str(data_root / "output"))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=2200)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    ok, fail = run_worker(
        db_path=Path(args.db_path).expanduser().resolve(),
        output_root=Path(args.output_root).expanduser().resolve(),
        limit=args.limit,
        width=args.width,
        height=args.height,
        timeout_ms=args.timeout_ms,
        retries=args.retries,
    )
    print(f"worker_done success={ok} failed={fail}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


TAG_COLUMNS = [
    "SILHOUETTE",
    "COLOR",
    "DETAIL",
    "MATERIAL",
    "MOOD",
    "FUNCTION",
    "USE_CASE",
]

INDEX_COLUMNS = [
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
]


@dataclass
class CaptureConfig:
    output_root: Path
    brand: str
    season: str
    item: str
    width: int = 1600
    height: int = 2200
    timeout_ms: int = 30000
    jpeg_quality: int = 85
    max_retries: int = 2


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "unknown"


def read_urls(raw_text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for line in raw_text.splitlines():
        v = line.strip()
        if not v:
            continue
        if v in seen:
            continue
        seen.add(v)
        urls.append(v)
    return urls


def build_capture_path(cfg: CaptureConfig, index: int) -> tuple[str, Path]:
    brand = _slug(cfg.brand)
    season = _slug(cfg.season)
    item = _slug(cfg.item)
    item_dir = cfg.output_root / brand / season / item
    item_dir.mkdir(parents=True, exist_ok=True)
    capture_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{capture_stamp}_{index:03d}.jpg"
    file_path = item_dir / file_name
    return capture_stamp, file_path


def capture_urls(urls: list[str], cfg: CaptureConfig, start_index: int = 1) -> list[dict[str, Any]]:
    brand = _slug(cfg.brand)
    season = _slug(cfg.season)
    item = _slug(cfg.item)
    results: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": cfg.width, "height": cfg.height})
        page = context.new_page()
        for i, url in enumerate(urls, start=start_index):
            capture_stamp, file_path = build_capture_path(cfg, i)
            row_id = f"{brand}_{season}_{item}_{capture_stamp}_{i:03d}"
            captured_at = datetime.now().isoformat(timespec="seconds")
            ok = False
            error = ""

            for _ in range(cfg.max_retries + 1):
                try:
                    page.goto(url, wait_until="networkidle", timeout=cfg.timeout_ms)
                    page.screenshot(
                        path=str(file_path),
                        full_page=True,
                        type="jpeg",
                        quality=cfg.jpeg_quality,
                    )
                    ok = True
                    error = ""
                    break
                except Exception as e:  # noqa: BLE001
                    ok = False
                    error = str(e)

            results.append(
                {
                    "id": row_id,
                    "brand": brand,
                    "season": season,
                    "item": item,
                    "source_url": url,
                    "image_path": str(file_path) if ok else "",
                    "captured_at": captured_at,
                    "status": "SUCCESS" if ok else "FAILED",
                    "error_message": error,
                }
            )

        context.close()
        browser.close()

    return results

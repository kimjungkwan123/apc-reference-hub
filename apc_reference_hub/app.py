from __future__ import annotations

import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

from capture import CaptureConfig, capture_urls, read_urls
from storage import (
    RefRow,
    db_conn,
    export_csv,
    init_db,
    list_failed,
    list_pending,
    list_references,
    mark_processing,
    reset_to_pending,
    save_uploaded_asset,
    stats,
    update_edited_rows,
    enqueue_urls,
    apply_capture_result,
)


APP_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("APC_HUB_DATA_DIR", str(APP_DIR))).expanduser().resolve()
DEFAULT_OUTPUT_ROOT = DATA_ROOT / "output"
DEFAULT_DB_PATH = DATA_ROOT / "data" / "references.db"
DEFAULT_EXPORT_CSV = DATA_ROOT / "index.csv"


def get_conn(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = db_conn(path)
    init_db(conn)
    return conn


def _slug(v: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in v.strip()).strip("-") or "unknown"


def save_uploaded_files(files: list[Any], target_dir: Path) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for f in files:
        out = target_dir / os.path.basename(f.name)
        with out.open("wb") as w:
            w.write(f.read())
        saved.append(str(out.resolve()))
    return saved


def require_password_if_needed() -> None:
    password = os.environ.get("APC_HUB_PASSWORD", "").strip()
    if not password:
        return
    typed = st.sidebar.text_input("App Password", type="password")
    if typed != password:
        st.warning("비밀번호가 필요합니다.")
        st.stop()


def process_queue(conn, pending_rows: list[dict], output_root: Path, width: int, height: int, timeout_ms: int, retries: int):
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in pending_rows:
        grouped[(row["brand"], row["season"], row["item"])].append(row)

    ids = [r["id"] for r in pending_rows]
    mark_processing(conn, ids)

    processed = 0
    failed = 0
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
                    processed += 1
                else:
                    failed += 1
        except Exception as e:  # noqa: BLE001
            for source_row in rows:
                apply_capture_result(
                    conn,
                    source_row["id"],
                    {"status": "FAILED", "error_message": str(e), "image_path": "", "captured_at": ""},
                )
                failed += 1

    return processed, failed


st.set_page_config(page_title="APC GOLF Reference Hub", layout="wide")
st.title("APC GOLF Reference Hub v1")

with st.sidebar:
    st.header("System")
    db_path = Path(st.text_input("DB Path", value=str(DEFAULT_DB_PATH))).expanduser().resolve()
    output_root = Path(st.text_input("Output Root", value=str(DEFAULT_OUTPUT_ROOT))).expanduser().resolve()
    export_csv_path = Path(st.text_input("Export CSV Path", value=str(DEFAULT_EXPORT_CSV))).expanduser().resolve()
    width = int(st.number_input("Viewport Width", min_value=800, max_value=3000, value=1600))
    height = int(st.number_input("Viewport Height", min_value=1000, max_value=4000, value=2200))
    timeout_ms = int(st.number_input("Timeout (ms)", min_value=5000, max_value=120000, value=30000, step=1000))
    retries = int(st.number_input("Retries", min_value=0, max_value=5, value=2))

require_password_if_needed()
conn = get_conn(db_path)
metric = stats(conn)

top1, top2, top3, top4, top5 = st.columns(5)
top1.metric("TOTAL", metric["TOTAL"])
top2.metric("PENDING", metric["PENDING"])
top3.metric("PROCESSING", metric["PROCESSING"])
top4.metric("SUCCESS", metric["SUCCESS"])
top5.metric("FAILED", metric["FAILED"])

st.divider()
st.subheader("1) 원클릭 수집 (추천)")
quick_col1, quick_col2, quick_col3 = st.columns(3)
quick_brand = _slug(quick_col1.text_input("Quick Brand", value="apc-golf"))
quick_season = _slug(quick_col2.text_input("Quick Season", value="2026-ss"))
quick_item = _slug(quick_col3.selectbox("Quick Item", ["tee", "pants", "outer", "knit", "other"], index=0))
quick_urls = st.text_area(
    "URL 붙여넣기 (한 줄 하나)",
    placeholder="https://www.vogue.com/fashion-shows/...\nhttps://brand.com/lookbook/...",
    height=120,
)
if st.button("원클릭 수집 실행 (등록+캡처)", type="primary", use_container_width=True):
    urls = read_urls(quick_urls)
    if not urls:
        st.warning("최소 1개 URL이 필요합니다.")
    else:
        rows = [RefRow(brand=quick_brand, season=quick_season, item=quick_item, source_url=u) for u in urls]
        inserted, duplicated = enqueue_urls(conn, rows)
        pending_rows = list_pending(conn, limit=300)
        success_n = 0
        failed_n = 0
        if pending_rows:
            with st.spinner(f"수집 실행 중 ({len(pending_rows)}건)"):
                success_n, failed_n = process_queue(conn, pending_rows, output_root, width, height, timeout_ms, retries)
        st.success(
            f"등록 {inserted}건 / 중복 {duplicated}건 / 캡처성공 {success_n}건 / 실패 {failed_n}건"
        )

st.divider()
st.subheader("2) URL 큐 등록 (고급)")
form_col1, form_col2, form_col3 = st.columns(3)
brand = _slug(form_col1.text_input("Brand", value="apc-golf"))
season = _slug(form_col2.text_input("Season", value="2026-ss"))
item = _slug(form_col3.selectbox("Item", ["tee", "pants", "outer", "knit", "other"], index=0))
url_text = st.text_area("URL 리스트(한 줄 하나)", placeholder="https://...", height=160)

queue_col1, queue_col2, queue_col3 = st.columns(3)
if queue_col1.button("큐 등록", type="primary", use_container_width=True):
    urls = read_urls(url_text)
    rows = [RefRow(brand=brand, season=season, item=item, source_url=u) for u in urls]
    inserted, duplicated = enqueue_urls(conn, rows)
    st.success(f"등록 {inserted}건, 중복 {duplicated}건")

if queue_col2.button("PENDING 처리 실행", use_container_width=True):
    pending_rows = list_pending(conn, limit=300)
    if not pending_rows:
        st.info("처리할 PENDING 항목이 없습니다.")
    else:
        with st.spinner(f"캡처 처리 중 ({len(pending_rows)}건)"):
            success_n, failed_n = process_queue(conn, pending_rows, output_root, width, height, timeout_ms, retries)
        st.success(f"완료: 성공 {success_n}건 / 실패 {failed_n}건")

if queue_col3.button("FAILED -> PENDING 재시도", use_container_width=True):
    failed_rows = list_failed(conn, limit=300)
    cnt = reset_to_pending(conn, [r["id"] for r in failed_rows])
    st.success(f"{cnt}건을 재시도 대기 상태로 변경")

st.subheader("3) 파일 업로드 (로컬 이미지/리포트)")
uploaded_assets = st.file_uploader(
    "이미지/리포트 업로드",
    type=["png", "jpg", "jpeg", "webp", "pdf", "csv", "txt"],
    accept_multiple_files=True,
)
if st.button("업로드 저장 및 레코드 등록", use_container_width=True):
    if not uploaded_assets:
        st.warning("업로드 파일이 없습니다.")
    else:
        raw_dir = output_root / brand / season / item / "raw"
        saved_paths = save_uploaded_files(uploaded_assets, raw_dir)
        for p in saved_paths:
            save_uploaded_asset(
                conn,
                brand=brand,
                season=season,
                item=item,
                source_url=f"local://{Path(p).name}",
                image_path=p,
            )
        st.success(f"{len(saved_paths)}건 저장 및 인덱싱 완료")

st.divider()
st.subheader("4) 인덱스 조회/태깅")
flt1, flt2, flt3, flt4, flt5 = st.columns(5)
f_brand = flt1.text_input("Filter brand", "")
f_season = flt2.text_input("Filter season", "")
f_item = flt3.text_input("Filter item", "")
f_status = flt4.selectbox("Filter status", ["ALL", "PENDING", "PROCESSING", "SUCCESS", "FAILED"], index=0)
limit = int(flt5.number_input("Limit", min_value=50, max_value=10000, value=1000, step=50))

df = list_references(conn, brand=f_brand, season=f_season, item=f_item, status=f_status, limit=limit)
if df.empty:
    st.info("조회 결과가 없습니다.")
else:
    editable_cols = [
        "id",
        "brand",
        "season",
        "item",
        "source_url",
        "image_path",
        "captured_at",
        "SILHOUETTE",
        "COLOR",
        "DETAIL",
        "MATERIAL",
        "MOOD",
        "FUNCTION",
        "USE_CASE",
        "fit_key",
        "apc_fit_score",
        "notes",
        "status",
        "error_message",
        "updated_at",
    ]
    edited = st.data_editor(
        df[editable_cols],
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="references_editor",
    )
    save1, save2 = st.columns(2)
    if save1.button("태그/메모 저장", type="primary", use_container_width=True):
        count = update_edited_rows(conn, edited.to_dict("records"))
        st.success(f"{count}건 저장")
    if save2.button("DB -> index.csv 내보내기", use_container_width=True):
        out_csv = export_csv(conn, export_csv_path)
        st.success(f"내보내기 완료: {out_csv}")

    st.subheader("5) 미리보기")
    preview_n = st.slider("미리보기 수", min_value=1, max_value=30, value=8)
    for _, row in edited.head(preview_n).iterrows():
        st.caption(f"{row.get('brand', '')}/{row.get('season', '')}/{row.get('item', '')} | {row.get('status', '')}")
        st.caption(str(row.get("source_url", "")))
        image_path = str(row.get("image_path", "")).strip()
        if image_path:
            p = Path(image_path)
            if p.exists() and p.is_file():
                st.image(str(p), use_container_width=True)
            else:
                st.warning(f"이미지 없음: {p}")
        else:
            st.warning("이미지 경로 없음")
        if str(row.get("error_message", "")).strip():
            st.error(str(row.get("error_message")))

st.divider()
st.subheader("6) 아카이브")
zip_col1, zip_col2 = st.columns(2)
if zip_col1.button("출력 폴더 ZIP 생성", use_container_width=True):
    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = shutil.make_archive(str(output_root), "zip", str(output_root))
    st.success(f"압축 생성: {zip_path}")
if zip_col2.button("새로고침", use_container_width=True):
    st.rerun()

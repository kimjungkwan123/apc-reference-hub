from __future__ import annotations

import os
import shutil
import base64
import zipfile
import json
import time
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from PIL import Image, ImageEnhance, ImageOps

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

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    PDF_AVAILABLE = True
except Exception:  # noqa: BLE001
    PDF_AVAILABLE = False

APP_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("APC_HUB_DATA_DIR", str(APP_DIR))).expanduser().resolve()
DEFAULT_OUTPUT_ROOT = DATA_ROOT / "output"
DEFAULT_DB_PATH = DATA_ROOT / "data" / "references.db"
DEFAULT_EXPORT_CSV = DATA_ROOT / "index.csv"
MAX_FACE_UPLOAD_MB = 15
MAX_STORY_PAGES = 6
STORYBOOK_TEMPLATES: dict[str, list[str]] = {
    "별빛 모험": [
        "오늘 밤, {child}는 반짝이는 별지도를 따라 숲으로 떠났어요.",
        "{child}의 미소를 본 반딧불이들이 길을 밝혀 주었어요.",
        "달빛 호수에서 만난 부엉이 선생님이 용기의 주문을 알려 주었어요.",
        "{child}는 별조각 퍼즐을 맞춰 잃어버린 길을 되찾았어요.",
        "새벽이 오기 전, {child}는 친구들과 별다리를 건넜어요.",
        "집에 돌아온 {child}는 내일 또 새로운 모험을 꿈꿨어요.",
    ],
    "바다 친구": [
        "{child}는 파도 소리를 따라 푸른 바다 마을에 도착했어요.",
        "작은 해마 친구가 {child}에게 산호 지도를 건네주었어요.",
        "바닷속 동굴에서 길을 잃은 거북이를 함께 찾아 나섰어요.",
        "{child}는 반짝이는 조개로 길표시를 만들어 친구들을 이끌었어요.",
        "커다란 고래가 등장해 모두를 안전한 항구로 데려다주었어요.",
        "{child}는 바다 친구들과 약속했어요. 다시 만나 모험하기로요.",
    ],
    "공룡 탐험": [
        "{child}는 시간문을 지나 공룡 섬에 도착했어요.",
        "초식공룡 친구가 {child}에게 숲길 안내를 부탁했어요.",
        "화산이 흔들리자 {child}는 모두를 넓은 평원으로 이끌었어요.",
        "작은 티라노가 겁을 먹자 {child}가 손을 잡아 주었어요.",
        "위험이 지나가고 공룡들은 {child}를 용감한 대장으로 불렀어요.",
        "집으로 돌아온 {child}는 탐험 일기에 오늘의 용기를 적었어요.",
    ],
}


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


def _safe_slug(v: str) -> str:
    return _slug(v or "child")


def build_story_pages(child_name: str, template_name: str, custom_story: str) -> list[str]:
    custom_lines = [line.strip() for line in (custom_story or "").splitlines() if line.strip()]
    template_pages = STORYBOOK_TEMPLATES.get(template_name, STORYBOOK_TEMPLATES["별빛 모험"])
    if custom_lines:
        pages = custom_lines[:MAX_STORY_PAGES]
        if len(pages) < MAX_STORY_PAGES:
            pages.extend(p.format(child=child_name) for p in template_pages[len(pages):MAX_STORY_PAGES])
        return pages
    return [p.format(child=child_name) for p in template_pages[:MAX_STORY_PAGES]]


def normalize_face_image(face_upload: Any, out_dir: Path) -> Path:
    raw = face_upload.getvalue()
    if not raw:
        raise ValueError("업로드된 이미지가 비어 있습니다.")
    try:
        with Image.open(BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            # Normalize size for faster downstream generation and predictable output.
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            out = out_dir / "face.png"
            img.save(out, format="PNG", optimize=True)
            return out
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"지원하지 않는 이미지이거나 손상된 파일입니다: {e}") from e


def create_page_variant_images(face_path: Path, out_dir: Path, page_count: int, keep_existing: bool = False) -> list[Path]:
    with Image.open(face_path) as base_img:
        base = ImageOps.exif_transpose(base_img).convert("RGB")
    variants: list[Path] = []
    # Deterministic per-page transforms: angle/zoom/color/light changes.
    presets = [
        {"angle": -8, "zoom": 1.10, "sat": 1.15, "con": 1.05, "bri": 1.00},
        {"angle": 7, "zoom": 1.05, "sat": 1.00, "con": 1.10, "bri": 1.05},
        {"angle": -4, "zoom": 1.18, "sat": 1.20, "con": 1.00, "bri": 0.98},
        {"angle": 11, "zoom": 1.08, "sat": 0.95, "con": 1.08, "bri": 1.08},
        {"angle": -12, "zoom": 1.12, "sat": 1.10, "con": 0.98, "bri": 1.02},
        {"angle": 3, "zoom": 1.00, "sat": 1.05, "con": 1.03, "bri": 1.00},
    ]
    for i in range(page_count):
        out = out_dir / f"page_{i + 1:02d}.png"
        if keep_existing and out.exists():
            variants.append(out)
            continue
        p = presets[i % len(presets)]
        img = base.copy()
        img = img.rotate(p["angle"], expand=True, resample=Image.Resampling.BICUBIC, fillcolor=(20, 20, 20))

        w, h = img.size
        crop_w = int(w / p["zoom"])
        crop_h = int(h / p["zoom"])
        left = (w - crop_w) // 2
        top = (h - crop_h) // 2
        img = img.crop((left, top, left + crop_w, top + crop_h))

        img = ImageEnhance.Color(img).enhance(p["sat"])
        img = ImageEnhance.Contrast(img).enhance(p["con"])
        img = ImageEnhance.Brightness(img).enhance(p["bri"])
        img = img.resize((1024, 1024), Image.Resampling.LANCZOS)

        img.save(out, format="PNG")
        variants.append(out)
    return variants


def create_ai_scene_images(
    face_path: Path,
    out_dir: Path,
    pages: list[str],
    child_name: str,
    theme: str,
    tone: str,
    template_name: str,
) -> tuple[list[Path], list[str]]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return [], ["OPENAI_API_KEY가 없어 빠른 변형 모드로 대체합니다."]

    headers = {"Authorization": f"Bearer {api_key}"}
    endpoint = "https://api.openai.com/v1/images/edits"
    warnings: list[str] = []
    generated: list[Path] = []

    style_prefix = (
        "Children's storybook illustration, soft lighting, friendly mood, high detail, "
        "the same child identity as the reference face image."
    )
    for i, page_text in enumerate(pages, start=1):
        prompt = (
            f"{style_prefix} Theme: {theme}. Tone: {tone}. Template: {template_name}. "
            f"Child name: {child_name}. Scene for page {i}: {page_text}. "
            "Keep child age-appropriate and positive."
        )
        with face_path.open("rb") as image_fp:
            data = {
                "model": "gpt-image-1",
                "prompt": prompt,
                "size": "1024x1024",
            }
            try:
                resp = None
                for retry in range(3):
                    image_fp.seek(0)
                    files = {
                        "image": (face_path.name, image_fp, "application/octet-stream"),
                    }
                    resp = requests.post(endpoint, headers=headers, files=files, data=data, timeout=120)
                    if resp.status_code < 500:
                        break
                    time.sleep(1.2 * (retry + 1))
                if resp is None:
                    warnings.append(f"AI 이미지 {i}페이지 생성 실패: 응답 없음")
                    continue
                if resp.status_code >= 400:
                    detail = (resp.text or "").strip().replace("\n", " ")[:140]
                    warnings.append(f"AI 이미지 {i}페이지 생성 실패: {resp.status_code} {detail}")
                    continue
                payload = resp.json()
                items = payload.get("data", [])
                if not items:
                    warnings.append(f"AI 이미지 {i}페이지 응답이 비어있어 스킵했습니다.")
                    continue
                out = out_dir / f"page_{i:02d}.png"
                b64 = items[0].get("b64_json")
                url = items[0].get("url")
                if b64:
                    out.write_bytes(base64.b64decode(b64))
                    generated.append(out)
                elif url:
                    img_resp = requests.get(url, timeout=60)
                    if img_resp.status_code < 400:
                        out.write_bytes(img_resp.content)
                        generated.append(out)
                    else:
                        warnings.append(f"AI 이미지 {i}페이지 다운로드 실패")
                else:
                    warnings.append(f"AI 이미지 {i}페이지 결과 형식을 인식하지 못했습니다.")
            except Exception as e:  # noqa: BLE001
                warnings.append(f"AI 이미지 {i}페이지 생성 중 오류: {e}")
    return generated, warnings


def create_storybook_from_face(
    face_upload: Any,
    child_name: str,
    theme: str,
    tone: str,
    template_name: str,
    custom_story: str,
    output_root: Path,
    image_mode: str,
) -> tuple[Path, Path, Path, list[Path], list[str], str, list[str]]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    child_slug = _safe_slug(child_name)
    out_dir = output_root / "storybook" / child_slug / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    face_path = normalize_face_image(face_upload, out_dir)

    title = f"{child_name}의 {template_name}"
    pages = build_story_pages(child_name, template_name, custom_story)
    warnings: list[str] = []
    page_images: list[Path] = []
    if image_mode == "AI 장면 생성 (Beta)":
        page_images, warnings = create_ai_scene_images(
            face_path=face_path,
            out_dir=out_dir,
            pages=pages,
            child_name=child_name,
            theme=theme,
            tone=tone,
            template_name=template_name,
        )
    if len(page_images) < len(pages):
        page_images = create_page_variant_images(face_path, out_dir, len(pages), keep_existing=True)
        if image_mode == "AI 장면 생성 (Beta)":
            warnings.append("AI 생성이 일부/전체 실패하여 빠른 변형 모드 결과로 대체했습니다.")

    story_path = out_dir / "storybook.md"
    lines = [
        f"# {title}",
        "",
        f"- 아이 이름: {child_name}",
        f"- 테마: {theme}",
        f"- 분위기: {tone}",
        f"- 동화책 종류: {template_name}",
        "",
    ]
    for i, page in enumerate(pages, start=1):
        page_img = page_images[i - 1]
        lines.append(f"## {i}페이지")
        lines.append(f"![{child_name} 페이지 이미지]({page_img.name})")
        lines.append("")
        lines.append(page)
        lines.append("")
    lines.extend(
        [
            "## 얼굴 참조 이미지",
            f"![face]({face_path.name})",
            "",
        ]
    )
    story_path.write_text("\n".join(lines), encoding="utf-8")
    manifest = {
        "title": title,
        "child_name": child_name,
        "theme": theme,
        "tone": tone,
        "template_name": template_name,
        "image_mode": image_mode,
        "created_at": datetime.now().isoformat(),
        "pages": pages,
        "page_images": [p.name for p in page_images],
        "warnings": warnings,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir, story_path, face_path, page_images, pages, title, warnings


def build_storybook_bundle_bytes(story_dir: Path) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(story_dir.iterdir()):
            if p.is_file():
                zf.write(p, arcname=p.name)
    buf.seek(0)
    return buf.getvalue()


def create_storybook_pdf_bytes(
    title: str,
    child_name: str,
    theme: str,
    tone: str,
    template_name: str,
    pages: list[str],
    page_image_paths: list[str] | None = None,
) -> bytes:
    if not PDF_AVAILABLE:
        return b""

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    font_name = "Helvetica"
    try:
        font_name = "HYSMyeongJo-Medium"
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:  # noqa: BLE001
        font_name = "Helvetica"

    cover_y = height - 50
    c.setFont(font_name, 16)
    c.drawString(40, cover_y, title)
    cover_y -= 28
    c.setFont(font_name, 11)
    c.drawString(40, cover_y, f"Child: {child_name}")
    cover_y -= 16
    c.drawString(40, cover_y, f"Theme: {theme}")
    cover_y -= 16
    c.drawString(40, cover_y, f"Tone: {tone}")
    cover_y -= 16
    c.drawString(40, cover_y, f"Template: {template_name}")

    for idx, page in enumerate(pages, start=1):
        c.showPage()
        y = height - 50
        c.setFont(font_name, 14)
        c.drawString(40, y, f"Page {idx}")
        y -= 20

        current_image = ""
        if page_image_paths and idx - 1 < len(page_image_paths):
            current_image = page_image_paths[idx - 1]

        if current_image:
            p = Path(current_image)
            if p.exists():
                try:
                    img = ImageReader(str(p))
                    img_w, img_h = img.getSize()
                    target_w = width - 80
                    target_h = 260
                    scale = min(target_w / img_w, target_h / img_h)
                    draw_w = img_w * scale
                    draw_h = img_h * scale
                    x = 40 + (target_w - draw_w) / 2
                    c.drawImage(img, x, y - draw_h, width=draw_w, height=draw_h, preserveAspectRatio=True, mask="auto")
                    y -= draw_h + 20
                except Exception:  # noqa: BLE001
                    pass

        c.setFont(font_name, 11)
        for line in page.splitlines() or [""]:
            if y < 70:
                c.showPage()
                c.setFont(font_name, 11)
                y = height - 50
            c.drawString(50, y, line[:90])
            y -= 15

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


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
if st.button("원클릭 수집 실행 (등록+캡처)", type="primary", width="stretch"):
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
if queue_col1.button("큐 등록", type="primary", width="stretch"):
    urls = read_urls(url_text)
    rows = [RefRow(brand=brand, season=season, item=item, source_url=u) for u in urls]
    inserted, duplicated = enqueue_urls(conn, rows)
    st.success(f"등록 {inserted}건, 중복 {duplicated}건")

if queue_col2.button("PENDING 처리 실행", width="stretch"):
    pending_rows = list_pending(conn, limit=300)
    if not pending_rows:
        st.info("처리할 PENDING 항목이 없습니다.")
    else:
        with st.spinner(f"캡처 처리 중 ({len(pending_rows)}건)"):
            success_n, failed_n = process_queue(conn, pending_rows, output_root, width, height, timeout_ms, retries)
        st.success(f"완료: 성공 {success_n}건 / 실패 {failed_n}건")

if queue_col3.button("FAILED -> PENDING 재시도", width="stretch"):
    failed_rows = list_failed(conn, limit=300)
    cnt = reset_to_pending(conn, [r["id"] for r in failed_rows])
    st.success(f"{cnt}건을 재시도 대기 상태로 변경")

st.subheader("3) 파일 업로드 (로컬 이미지/리포트)")
uploaded_assets = st.file_uploader(
    "이미지/리포트 업로드",
    type=["png", "jpg", "jpeg", "webp", "pdf", "csv", "txt"],
    accept_multiple_files=True,
)
if st.button("업로드 저장 및 레코드 등록", width="stretch"):
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

st.subheader("3-1) 아이 얼굴로 즉시 동화책 만들기")
sb_col1, sb_col2 = st.columns(2)
child_name = sb_col1.text_input("아이 이름", value="하린")
storybook_theme = sb_col2.text_input("동화 테마", value="용기와 우정")
tone = st.selectbox("분위기", ["따뜻함", "신나는", "잔잔한", "유쾌한"], index=0)
storybook_kind = st.selectbox("동화책 종류", list(STORYBOOK_TEMPLATES.keys()), index=0)
image_mode = st.selectbox("이미지 생성 모드", ["빠른 변형", "AI 장면 생성 (Beta)"], index=0)
if image_mode == "AI 장면 생성 (Beta)" and not os.environ.get("OPENAI_API_KEY", "").strip():
    st.warning("OPENAI_API_KEY가 없어 AI 모드 대신 빠른 변형 결과로 대체됩니다.")
custom_story = st.text_area(
    "스토리 직접 수정 (선택, 한 줄=한 페이지, 최대 6줄)",
    placeholder="1페이지 내용\n2페이지 내용\n...",
    height=120,
)
custom_story_lines = [line for line in custom_story.splitlines() if line.strip()]
if len(custom_story_lines) > MAX_STORY_PAGES:
    st.warning(f"스토리 {MAX_STORY_PAGES}줄까지만 반영됩니다.")
elif 0 < len(custom_story_lines) < MAX_STORY_PAGES:
    st.info(f"입력한 {len(custom_story_lines)}줄 뒤 페이지는 선택한 템플릿으로 자동 채워집니다.")
face_upload = st.file_uploader("아이 얼굴 사진 업로드", type=["png", "jpg", "jpeg", "webp"], key="face_storybook_upload")
regenerate = st.button("이미지 다시 생성", width="stretch", key="regen_storybook")

if "face_storybook_sig" not in st.session_state:
    st.session_state["face_storybook_sig"] = ""
if "face_storybook_result" not in st.session_state:
    st.session_state["face_storybook_result"] = None

if face_upload is None:
    st.info("얼굴 이미지를 업로드하면 자동으로 동화책이 생성됩니다.")
else:
    max_bytes = MAX_FACE_UPLOAD_MB * 1024 * 1024
    if int(face_upload.size or 0) > max_bytes:
        st.error(f"파일이 너무 큽니다. {MAX_FACE_UPLOAD_MB}MB 이하 이미지를 업로드해 주세요.")
        st.stop()
    sig = "|".join(
        [
            face_upload.name,
            str(face_upload.size),
            child_name.strip(),
            storybook_theme.strip(),
            tone.strip(),
            storybook_kind.strip(),
            image_mode.strip(),
            custom_story.strip(),
            str(st.session_state.get("face_storybook_nonce", 0)),
        ]
    )
    if regenerate:
        st.session_state["face_storybook_nonce"] = int(st.session_state.get("face_storybook_nonce", 0)) + 1
        sig = sig + f"|regen:{st.session_state['face_storybook_nonce']}"
    if sig != st.session_state["face_storybook_sig"]:
        clean_child_name = child_name.strip() or "아이"
        clean_theme = storybook_theme.strip() or "즐거운 모험"
        clean_child_name = clean_child_name[:24]
        clean_theme = clean_theme[:80]
        with st.spinner("동화책 이미지 생성 중..."):
            try:
                out_dir, story_path, face_path, page_images, pages, title, warnings = create_storybook_from_face(
                    face_upload=face_upload,
                    child_name=clean_child_name,
                    theme=clean_theme,
                    tone=tone,
                    template_name=storybook_kind,
                    custom_story=custom_story,
                    output_root=output_root,
                    image_mode=image_mode,
                )
                st.session_state["face_storybook_sig"] = sig
                st.session_state["face_storybook_result"] = {
                    "dir": str(out_dir),
                    "story_path": str(story_path),
                    "face_path": str(face_path),
                    "page_image_paths": [str(p) for p in page_images],
                    "title": title,
                    "child_name": clean_child_name,
                    "theme": clean_theme,
                    "tone": tone,
                    "template_name": storybook_kind,
                    "image_mode": image_mode,
                    "pages": pages,
                    "warnings": warnings,
                }
            except Exception as e:  # noqa: BLE001
                st.error(f"동화책 생성 실패: {e}")
                st.session_state["face_storybook_result"] = None

    result = st.session_state["face_storybook_result"]
    if result:
        story_path = Path(result["story_path"])
        st.success("동화책 생성 완료")
        st.caption(f"생성 경로: {result['dir']}")
        st.caption(f"생성 모드: {result.get('image_mode', '빠른 변형')}")
        for w in result.get("warnings", []):
            st.warning(w)
        with st.expander("동화책 미리보기", expanded=True):
            st.markdown(f"### {result.get('title', '동화책')}")
            page_image_paths = [Path(p) for p in result.get("page_image_paths", [])]
            for i, page in enumerate(result.get("pages", []), start=1):
                st.markdown(f"**{i}페이지**")
                if i - 1 < len(page_image_paths) and page_image_paths[i - 1].exists():
                    st.image(str(page_image_paths[i - 1]), width="stretch")
                st.write(page)

        if story_path.exists():
            st.download_button(
                "동화책 마크다운 다운로드",
                data=story_path.read_bytes(),
                file_name="storybook.md",
                mime="text/markdown",
                width="stretch",
                key="download_storybook_md",
            )
            if PDF_AVAILABLE:
                pdf_bytes = create_storybook_pdf_bytes(
                    title=result.get("title", "Storybook"),
                    child_name=result.get("child_name", ""),
                    theme=result.get("theme", ""),
                    tone=result.get("tone", ""),
                    template_name=result.get("template_name", ""),
                    pages=result.get("pages", []),
                    page_image_paths=result.get("page_image_paths", []),
                )
                if pdf_bytes:
                    pdf_path = Path(result["dir"]) / "storybook.pdf"
                    pdf_path.write_bytes(pdf_bytes)
                    st.download_button(
                        "동화책 PDF 다운로드",
                        data=pdf_bytes,
                        file_name="storybook.pdf",
                        mime="application/pdf",
                        width="stretch",
                        key="download_storybook_pdf",
                    )
            else:
                st.info("PDF 다운로드를 쓰려면 reportlab 설치가 필요합니다.")
            story_dir = Path(result["dir"])
            if story_dir.exists():
                zip_bytes = build_storybook_bundle_bytes(story_dir)
                st.download_button(
                    "동화책 전체 ZIP 다운로드 (md+pdf+이미지)",
                    data=zip_bytes,
                    file_name=f"{story_dir.name}_storybook_bundle.zip",
                    mime="application/zip",
                    width="stretch",
                    key="download_storybook_zip",
                )

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
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        key="references_editor",
    )
    save1, save2 = st.columns(2)
    if save1.button("태그/메모 저장", type="primary", width="stretch"):
        count = update_edited_rows(conn, edited.to_dict("records"))
        st.success(f"{count}건 저장")
    if save2.button("DB -> index.csv 내보내기", width="stretch"):
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
                st.image(str(p), width="stretch")
            else:
                st.warning(f"이미지 없음: {p}")
        else:
            st.warning("이미지 경로 없음")
        if str(row.get("error_message", "")).strip():
            st.error(str(row.get("error_message")))

st.divider()
st.subheader("6) 아카이브")
zip_col1, zip_col2 = st.columns(2)
if zip_col1.button("출력 폴더 ZIP 생성", width="stretch"):
    output_root.mkdir(parents=True, exist_ok=True)
    zip_path = shutil.make_archive(str(output_root), "zip", str(output_root))
    st.success(f"압축 생성: {zip_path}")
if zip_col2.button("새로고침", width="stretch"):
    st.rerun()

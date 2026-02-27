# APC Reference Hub v1 (Share URL Ready)

실운영 가능한 A.P.C. GOLF 레퍼런스 수집/태깅 웹앱입니다.

## 터미널 없이 웹앱으로 쓰기 (권장)
- 이 프로젝트는 브라우저 URL로 바로 접속 가능한 웹앱 배포를 지원합니다.
- 운영자는 Render에 1회 배포만 하면 되고, 사용자는 **터미널 없이 링크 클릭만**으로 사용할 수 있습니다.
- 저장소에 `render.yaml`, `Dockerfile`, `run_web.sh`가 포함되어 있어 배포 준비가 되어 있습니다.
- Render 배포 시 `APC_HUB_DATA_DIR=/var/data`와 디스크 마운트가 자동 적용되어 데이터가 유지됩니다.

### 가장 쉬운 운영 방식
1. GitHub에 이 저장소를 push
2. Render에서 `New +` → `Blueprint`
3. 저장소 연결 후 배포
4. Render가 발급한 URL을 사용자에게 공유

## 기능
- URL 큐 등록 (`PENDING`)
- 캡처 워커 실행 (`PENDING -> PROCESSING -> SUCCESS/FAILED`)
- 실패건 재시도 (`FAILED -> PENDING`)
- 업로드 파일 인덱싱
- 아이 얼굴 업로드 즉시 자동 동화책 생성 (종류 선택/스토리 수정 가능, 얼굴 기준 이미지 포함)
- 태그/점수/노트 편집
- DB -> `index.csv` 내보내기
- 결과 폴더 zip 압축
- 비밀번호 보호 옵션 (`APC_HUB_PASSWORD`)

## 설치
```bash
cd "/Users/a/Documents/New project/apc_reference_hub"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 웹앱 실행
```bash
cd "/Users/a/Documents/New project/apc_reference_hub"
source .venv/bin/activate
streamlit run app.py
```
실행 후 터미널에 표시되는 `Network URL` 또는 `External URL`을 그대로 공유하면 됩니다.

## 링크만 공유하려면 (권장: Render)
명령 없이 사용하려면 클라우드 배포가 필요합니다. 이 프로젝트는 Render용 설정이 이미 포함되어 있습니다.

준비된 파일:
- `render.yaml`
- `Dockerfile`
- `run_web.sh`

배포 순서(클릭 위주):
1. 이 폴더를 GitHub 저장소로 올림
2. Render에서 `New +` -> `Blueprint` 선택
3. 해당 GitHub 저장소 연결 후 배포
4. 배포 완료 후 Render가 발급한 URL 공유

참고:
- 데이터는 Render 디스크(`/var/data`)에 저장됩니다.
- 서버가 꺼져도 DB/이미지 유지됩니다.

## 캡처 워커 실행 (무인/스케줄러용)
```bash
cd "/Users/a/Documents/New project/apc_reference_hub"
source .venv/bin/activate
python worker.py --limit 200
```

## 비밀번호 보호 (선택)
```bash
export APC_HUB_PASSWORD='your-password'
streamlit run app.py
```

## 공유 방법
- 같은 네트워크: Streamlit 실행 PC의 IP와 포트를 공유
- 외부 공유: Streamlit Community Cloud 또는 Render/Fly.io 배포

## 기본 저장소
- DB: `/Users/a/Documents/New project/apc_reference_hub/data/references.db`
- 이미지: `/Users/a/Documents/New project/apc_reference_hub/output/...`
- CSV Export: `/Users/a/Documents/New project/apc_reference_hub/index.csv`

## 태그 컬럼
- `SILHOUETTE`
- `COLOR`
- `DETAIL`
- `MATERIAL`
- `MOOD`
- `FUNCTION`
- `USE_CASE`
- `fit_key`
- `apc_fit_score`
- `notes`

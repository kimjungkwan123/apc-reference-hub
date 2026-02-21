# APC Reference Hub v1 (Share URL Ready)

실운영 가능한 A.P.C. GOLF 레퍼런스 수집/태깅 웹앱입니다.

## 기능
- URL 큐 등록 (`PENDING`)
- 캡처 워커 실행 (`PENDING -> PROCESSING -> SUCCESS/FAILED`)
- 실패건 재시도 (`FAILED -> PENDING`)
- 업로드 파일 인덱싱
- 아이 얼굴 업로드 후 즉시 동화책 생성 (화면 미리보기 + `storybook.md`/`PDF` 다운로드)
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

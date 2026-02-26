# APC Reference Hub v1 (Share URL Ready)

실운영 가능한 A.P.C. GOLF 레퍼런스 수집/태깅 웹앱입니다.

## 기능
- URL 큐 등록 (`PENDING`)
- 캡처 워커 실행 (`PENDING -> PROCESSING -> SUCCESS/FAILED`)
- 실패건 재시도 (`FAILED -> PENDING`)
- 업로드 파일 인덱싱
- 아이 얼굴 업로드 후 즉시 동화책 생성 (페이지별 각도/색감 변형 이미지 + 미리보기 + `storybook.md`/`PDF` 다운로드)
- 이미지 생성 모드 선택: `빠른 변형` 또는 `AI 장면 생성(Beta, OPENAI_API_KEY 필요)`
- 생성 결과를 `ZIP(md+pdf+페이지이미지)`로 한 번에 다운로드
- 대용량 업로드 보호(얼굴 이미지 15MB 제한) + `이미지 다시 생성` 버튼 제공
- 이미지 정규화/검증(PNG 변환) + 결과 메타데이터(`manifest.json`) 저장
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


## 카드뉴스 스튜디오 (독립 앱)
기존 `app.py`(APC GOLF 레퍼런스 허브)와 분리된 카드뉴스 전용 앱입니다.

### 그냥 URL만 치고 사용하려면 (권장)
Render 배포를 하면 **앱 실행 명령 없이** URL만 입력해서 바로 접속할 수 있습니다.

배포 후 접속:
- `https://cardnews-studio.onrender.com` (실제 URL은 Render가 발급)

설정:
- 루트 `render.yaml`에 `cardnews-studio` 서비스가 추가되어 있어 Blueprint 배포 시 자동 생성됩니다.
- `APC_APP=cardnews` 환경변수로 카드뉴스 앱(`cardnews_app.py`)이 실행됩니다.

### 로컬에서 쓸 때(보조)
- macOS: `start_cardnews.command` 더블클릭
- Windows: `start_cardnews.bat` 더블클릭

기능:
- 시장조사 에이전트
- 10장 카드뉴스 구성 에이전트
- HTML 디자인 미리보기
- ZIP 다운로드(요약/JSON/HTML 포함)

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

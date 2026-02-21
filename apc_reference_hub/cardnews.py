from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
import json
import re
import zipfile


CARD_COUNT = 10


@dataclass
class Card:
    index: int
    title: str
    subtitle: str
    bullets: list[str]
    insight: str


STYLE_PRESETS: dict[str, dict[str, str]] = {
    "모던 미니멀": {
        "bg": "#F6F7FB",
        "card_bg": "#FFFFFF",
        "title": "#1B1F3B",
        "body": "#2F365F",
        "accent": "#5B7CFA",
    },
    "강한 임팩트": {
        "bg": "#0E0E12",
        "card_bg": "#1A1B24",
        "title": "#FFFFFF",
        "body": "#D7DBF4",
        "accent": "#FF6B6B",
    },
    "비즈니스 클래식": {
        "bg": "#F2F5F7",
        "card_bg": "#FFFFFF",
        "title": "#1F2937",
        "body": "#374151",
        "accent": "#0EA5E9",
    },
}


def _topic_slug(topic: str) -> str:
    lowered = topic.strip().lower()
    slug = re.sub(r"[^a-z0-9가-힣]+", "-", lowered).strip("-")
    return slug or "cardnews"


def market_research_agent(topic: str, direction: str) -> dict[str, list[str] | str]:
    trend = [
        f"{topic} 관련 검색량/커뮤니티 언급은 '가성비'와 '즉시성' 키워드로 모이는 경향",
        "초기 진입자는 차별화 포인트보다 메시지 명확성이 성과를 좌우",
        "콘텐츠형 마케팅(짧은 카드·릴스)에서 전환이 자주 발생",
    ]
    if direction == "too_new":
        pain = [
            "고객이 문제를 명확히 인식하지 못해 교육형 메시지가 필수",
            "비교 대상이 없어 가격 저항이 크게 나타날 수 있음",
            "신뢰 확보를 위한 사례·리뷰·데모 자산이 중요",
        ]
        opportunity = [
            "선점 브랜드로 카테고리 표준을 정의할 수 있음",
            "초기 타깃을 세분화하면 높은 충성도 확보 가능",
            "파트너십/커뮤니티 기반 확산이 빠르게 일어날 수 있음",
        ]
    else:
        pain = [
            "시장이 포화되어 고객에게 새로움이 부족",
            "가격 경쟁으로 마진이 얇아지기 쉬움",
            "브랜드 전환 장벽이 낮아 재구매 관리가 핵심",
        ]
        opportunity = [
            "기존 프로세스 개선형 제안은 도입 저항이 낮음",
            "작은 불편 해결(속도, 신뢰, 개인화)만으로도 차별화 가능",
            "니치 세그먼트 공략 시 CAC를 안정적으로 낮출 수 있음",
        ]
    return {
        "audience": "20~40대 실무자/창업자 + 문제 인식이 있는 얼리어답터",
        "trend": trend,
        "pain_points": pain,
        "opportunities": opportunity,
    }


def card_planning_agent(topic: str, direction: str, research: dict[str, list[str] | str]) -> list[Card]:
    hook = "너무 지루한 시장" if direction == "boring" else "너무 새로운 시장"
    cards = [
        Card(1, f"{topic} 카드뉴스", f"{hook}를 기회로 바꾸는 10장 전략", ["문제 정의", "타깃 정의", "실행 프레임"], "끝까지 읽으면 바로 실행할 수 있습니다."),
        Card(2, "시장 진단", "왜 지금 이 시장을 봐야 할까?", list(research["trend"][:3]), "트렌드 해석이 첫 번째 경쟁력입니다."),
        Card(3, "타깃 고객", "누구의 어떤 문제를 풀 것인가", [str(research["audience"]), "상황 중심 세그먼트 설계", "즉시 행동을 부르는 문장 정의"], "대상을 좁힐수록 메시지가 강해집니다."),
        Card(4, "핵심 페인포인트", "고객이 실제로 불편한 지점", list(research["pain_points"][:3]), "페인포인트를 복사해 광고 카피로 활용하세요."),
        Card(5, "기회 포인트", "작지만 확실한 우위 만들기", list(research["opportunities"][:3]), "작은 차이가 결국 선택의 이유가 됩니다."),
        Card(6, "포지셔닝", "한 줄 가치제안 만들기", [f"{topic} = 빠르고 이해 쉬운 솔루션", "기존 대안 대비 Before/After 제시", "가격이 아닌 결과 중심 메시지"], "포지셔닝은 한 문장으로 끝나야 합니다."),
        Card(7, "콘텐츠 전략", "어떤 형식으로 설득할까", ["카드뉴스: 문제→해결 구조", "짧은 영상: 사용 장면 시각화", "후기/사례: 신뢰 자산 축적"], "설명보다 증명이 더 빠르게 전환을 만듭니다."),
        Card(8, "수익 모델", "작게 시작해 확장하는 방법", ["입문형 상품으로 진입", "상위 플랜/옵션으로 업셀", "반복 구매 루프 설계"], "초기엔 복잡함보다 단순한 요금제가 유리합니다."),
        Card(9, "실행 로드맵", "30일 안에 검증하기", ["1주차: 메시지/랜딩 제작", "2주차: 콘텐츠 10개 배포", "3~4주차: 광고/제휴로 실험"], "완벽함보다 빠른 검증이 중요합니다."),
        Card(10, "CTA", "다음 액션", ["이 카드뉴스 템플릿 복사", "우리 브랜드 사례로 치환", "오늘 첫 게시물 업로드"], "지금 시작하면 다음 달 데이터가 쌓입니다."),
    ]
    return cards


def design_agent(cards: list[Card], style_name: str) -> str:
    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS["모던 미니멀"])
    blocks = []
    for card in cards:
        bullets = "".join(f"<li>{b}</li>" for b in card.bullets)
        blocks.append(
            f"""
            <section class='card'>
              <div class='index'>#{card.index:02d}</div>
              <h2>{card.title}</h2>
              <h3>{card.subtitle}</h3>
              <ul>{bullets}</ul>
              <p class='insight'>{card.insight}</p>
            </section>
            """
        )

    return f"""
<!doctype html>
<html lang='ko'>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width, initial-scale=1'/>
<title>Cardnews Preview</title>
<style>
body {{font-family: 'Pretendard', 'Noto Sans KR', sans-serif; background:{style['bg']}; margin:0; padding:40px; color:{style['body']};}}
.grid {{display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:18px; max-width:1200px; margin:0 auto;}}
.card {{background:{style['card_bg']}; border-radius:18px; padding:20px; box-shadow:0 8px 22px rgba(0,0,0,.08); min-height:320px;}}
.index {{color:{style['accent']}; font-weight:700; margin-bottom:6px;}}
h2 {{margin:0; color:{style['title']}; font-size:24px;}}
h3 {{margin:8px 0 14px 0; font-size:16px; color:{style['body']};}}
ul {{padding-left:18px; line-height:1.5;}}
.insight {{margin-top:16px; border-left:4px solid {style['accent']}; padding-left:10px; font-weight:600;}}
</style>
</head>
<body>
<div class='grid'>
{''.join(blocks)}
</div>
</body>
</html>
""".strip()


def delivery_agent(topic: str, research: dict[str, list[str] | str], cards: list[Card], html: str) -> tuple[bytes, str]:
    slug = _topic_slug(topic)
    day = date.today().isoformat()
    payload = {
        "topic": topic,
        "generated_at": day,
        "market_research": research,
        "cards": [card.__dict__ for card in cards],
    }

    summary_lines = [
        f"# {topic} 카드뉴스 패키지",
        "",
        "## 1) 시장 리서치",
        f"- 타깃: {research['audience']}",
    ]
    for k in ["trend", "pain_points", "opportunities"]:
        summary_lines.append(f"- {k}:")
        for line in research[k]:
            summary_lines.append(f"  - {line}")

    summary_lines.append("\n## 2) 10장 카드 구성")
    for c in cards:
        summary_lines.append(f"- {c.index}. {c.title} | {c.subtitle}")
        for b in c.bullets:
            summary_lines.append(f"  - {b}")

    memory = BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug}_{day}/market_and_cards.json", json.dumps(payload, ensure_ascii=False, indent=2))
        zf.writestr(f"{slug}_{day}/cardnews_preview.html", html)
        zf.writestr(f"{slug}_{day}/cardnews_summary.md", "\n".join(summary_lines))

    memory.seek(0)
    return memory.read(), f"{slug}_cardnews_{day}.zip"

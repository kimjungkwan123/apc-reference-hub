from __future__ import annotations

import streamlit as st

from cardnews import card_planning_agent, delivery_agent, design_agent, market_research_agent


st.set_page_config(page_title="Cardnews Studio", layout="wide")
st.title("카드뉴스 스튜디오")
st.caption("기존 APC GOLF 레퍼런스 허브와 분리된 독립 생성기입니다.")

input_col1, input_col2, input_col3 = st.columns([2, 1, 1])
card_topic = input_col1.text_input("주제", value="아주 지루하고 뻔한 비즈니스")
market_direction = input_col2.selectbox(
    "시장 타입",
    ["boring", "too_new"],
    format_func=lambda v: "지루하고 뻔함" if v == "boring" else "너무 새로움",
)
design_preset = input_col3.selectbox("디자인 프리셋", ["모던 미니멀", "강한 임팩트", "비즈니스 클래식"])

if st.button("카드뉴스 10장 자동 생성", type="primary", use_container_width=True):
    if not card_topic.strip():
        st.warning("주제를 입력해주세요.")
    else:
        with st.spinner("4개 에이전트 실행 중..."):
            research = market_research_agent(card_topic, market_direction)
            cards = card_planning_agent(card_topic, market_direction, research)
            html_preview = design_agent(cards, design_preset)
            zip_bytes, zip_name = delivery_agent(card_topic, research, cards, html_preview)

        st.success("완료! 1)리서치 2)10장 구성 3)디자인 4)다운로드까지 생성됐어요.")

        block1, block2 = st.columns([1, 1])
        with block1:
            st.markdown("### 1) 시장조사 에이전트")
            st.json(research)
        with block2:
            st.markdown("### 2) 카드 구성 에이전트")
            for card in cards:
                st.markdown(f"**{card.index}. {card.title}**")
                st.caption(card.subtitle)
                st.markdown("\n".join([f"- {bullet}" for bullet in card.bullets]))

        st.markdown("### 3) 디자인 에이전트 (HTML 미리보기)")
        st.components.v1.html(html_preview, height=760, scrolling=True)

        st.markdown("### 4) 다운로드 에이전트")
        st.download_button(
            label="카드뉴스 패키지 ZIP 다운로드",
            data=zip_bytes,
            file_name=zip_name,
            mime="application/zip",
            use_container_width=True,
        )

st.divider()
st.markdown("#### 실행 방법")
st.code("streamlit run apc_reference_hub/cardnews_app.py")

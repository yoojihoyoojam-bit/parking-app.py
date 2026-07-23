import streamlit as st
import time

# Page configuration
st.set_page_config(page_title="광산 채굴 타이쿤", page_icon="⛏️", layout="centered")

# --- Session State Initialization ---
if "gold" not in st.session_state:
    st.session_state.gold = 0
if "mined_ores" not in st.session_state:
    st.session_state.mined_ores = 0
if "pickaxe_level" not in st.session_state:
    st.session_state.pickaxe_level = 1
if "auto_miner_level" not in st.session_state:
    st.session_state.auto_miner_level = 0
if "last_time" not in st.session_state:
    st.session_state.last_time = time.time()

# --- Auto Mining Logic ---
current_time = time.time()
elapsed_time = current_time - st.session_state.last_time

if st.session_state.auto_miner_level > 0:
    # Generates ore based on auto miner level and elapsed seconds
    auto_gained = int(elapsed_time * st.session_state.auto_miner_level)
    if auto_gained > 0:
        st.session_state.mined_ores += auto_gained
        st.session_state.last_time = current_time
else:
    st.session_state.last_time = current_time

# --- UI & Layout ---
st.title("⛏️ 광산 채굴 타이쿤")
st.caption("Streamlit 기반의 간단한 클릭/방치형 게임")

# Stats Summary
col1, col2, col3 = st.columns(3)
col1.metric("보유 골드", f"{st.session_state.gold} G")
col2.metric("보유 광석", f"{st.session_state.mined_ores} 개")
col3.metric("곡괭이 레벨", f"Lv.{st.session_state.pickaxe_level}")

st.divider()

# Game Tabs
tab1, tab2, tab3 = st.tabs(["⛏️ 채굴하기", "💰 상점 / 판매", "⚙️ 설명서"])

with tab1:
    st.subheader("광산 작업장")
    st.write(f"현재 클릭당 채굴량: **{st.session_state.pickaxe_level} 개**")
    
    if st.button("⛏️ 광석 채굴하기!", use_container_width=True):
        st.session_state.mined_ores += st.session_state.pickaxe_level
        st.success(f"광석 {st.session_state.pickaxe_level}개를 채굴했습니다!")
        st.rerun()

    if st.session_state.auto_miner_level > 0:
        st.info(f"🤖 자동 채굴기가 작동 중입니다 (초당 {st.session_state.auto_miner_level}개 자동 생성)")
        if st.button("🔄 자동 채굴 결과 새로고침"):
            st.rerun()

with tab2:
    st.subheader("1. 광석 판매")
    ore_price = 10  # 개당 10골드
    st.write(f"광석 판매가: 개당 **{ore_price} G**")
    
    col_sell1, col_sell2 = st.columns(2)
    with col_sell1:
        if st.button("광석 10개 판매", use_container_width=True):
            if st.session_state.mined_ores >= 10:
                st.session_state.mined_ores -= 10
                st.session_state.gold += 10 * ore_price
                st.rerun()
            else:
                st.error("광석이 부족합니다!")
                
    with col_sell2:
        if st.button("전체 광석 판매", use_container_width=True):
            if st.session_state.mined_ores > 0:
                gained_gold = st.session_state.mined_ores * ore_price
                st.session_state.gold += gained_gold
                st.session_state.mined_ores = 0
                st.rerun()
            else:
                st.error("판매할 광석이 없습니다!")

    st.divider()

    st.subheader("2. 장비 업그레이드")
    
    # Pickaxe Upgrade
    pickaxe_cost = st.session_state.pickaxe_level * 50
    st.write(f"**곡괭이 강화** (현재 Lv.{st.session_state.pickaxe_level}) → 강화 비용: **{pickaxe_cost} G**")
    if st.button(f"곡괭이 강화하기 ({pickaxe_cost} G)", use_container_width=True):
        if st.session_state.gold >= pickaxe_cost:
            st.session_state.gold -= pickaxe_cost
            st.session_state.pickaxe_level += 1
            st.success("곡괭이가 강화되었습니다!")
            st.rerun()
        else:
            st.error("골드가 부족합니다!")

    # Auto Miner Upgrade
    auto_cost = (st.session_state.auto_miner_level + 1) * 150
    st.write(f"**자동 채굴기 매입/강화** (현재 Lv.{st.session_state.auto_miner_level}) → 비용: **{auto_cost} G**")
    if st.button(f"자동 채굴기 구매/강화 ({auto_cost} G)", use_container_width=True):
        if st.session_state.gold >= auto_cost:
            st.session_state.gold -= auto_cost
            st.session_state.auto_miner_level += 1
            st.success("자동 채굴기가 업그레이드되었습니다!")
            st.rerun()
        else:
            st.error("골드가 부족합니다!")

with tab3:
    st.subheader("게임 정보")
    st.markdown("""
    - **채굴**: 버튼을 누를 때마다 곡괭이 레벨만큼 광석을 획득합니다.
    - **자동 채굴기**: 구매 시 시간에 따라 자동으로 광석을 생성합니다. (화면을 새로고침하거나 버튼을 누르면 정산)
    - **판매 및 강화**: 광석을 팔아 얻은 골드로 곡괭이와 자동 채굴기를 강화해 보세요!
    """)
    if st.button("⚠️ 게임 데이터 초기화"):
        st.session_state.gold = 0
        st.session_state.mined_ores = 0
        st.session_state.pickaxe_level = 1
        st.session_state.auto_miner_level = 0
        st.rerun()

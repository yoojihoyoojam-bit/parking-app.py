import streamlit as st
import time
import random

# Page configuration
st.set_page_config(page_title="심해 채굴 타이쿤", page_icon="🦑", layout="centered")

# --- 게임 데이터 정의 (재질 및 확률) ---

# 곡괭이 등급 정보 (재질, 구매비용, 채굴력)
PICKAXE_TIERS = {
    1: {"name": "돌 곡괭이", "cost": 0, "power": 1},
    2: {"name": "철 곡괭이", "cost": 500, "power": 3},
    3: {"name": "금 곡괭이", "cost": 2500, "power": 8},
    4: {"name": "다이아몬드 곡괭이", "cost": 10000, "power": 20},
    5: {"name": "네더라이트 곡괭이", "cost": 50000, "power": 50},
}

# 광석 종류 및 채굴 확률/가치 (확률 합계는 100이어야 함)
# 가치는 기본 채굴력에 곱해지는 배수입니다.
ORE_TYPES = [
    {"name": "돌덩이", "chance": 60, "value_multiplier": 1, "icon": "🪨"},
    {"name": "석탄", "chance": 25, "value_multiplier": 2, "icon": "⚫"},
    {"name": "철광석", "chance": 10, "value_multiplier": 5, "icon": "⛓️"},
    {"name": "금광석", "chance": 4, "value_multiplier": 15, "icon": "💰"},
    {"name": "다이아몬드", "chance": 1, "value_multiplier": 100, "icon": "💎"},
]

def get_random_ore():
    """확률에 따라 광석을 무작위로 추첨합니다."""
    rand = random.randint(1, 100)
    cumulative_chance = 0
    for ore in ORE_TYPES:
        cumulative_chance += ore["chance"]
        if rand <= cumulative_chance:
            return ore
    return ORE_TYPES[0] # 예외 처리용

# --- Session State Initialization ---
if "gold" not in st.session_state:
    st.session_state.gold = 0
if "ores" not in st.session_state:
    # 각 광석별 보유량 저장
    st.session_state.ores = {ore["name"]: 0 for ore in ORE_TYPES}
if "pickaxe_tier" not in st.session_state:
    st.session_state.pickaxe_tier = 1
if "auto_miner_level" not in st.session_state:
    st.session_state.auto_miner_level = 0
if "last_time" not in st.session_state:
    st.session_state.last_time = time.time()
# 최근 채굴 결과 저장용
if "last_mine_result" not in st.session_state:
    st.session_state.last_mine_result = None

# --- Auto Mining Logic (간소화) ---
# 방치형 요소를 위해 간단한 자동 골드 수급으로 변경
current_time = time.time()
elapsed_time = current_time - st.session_state.last_time

if st.session_state.auto_miner_level > 0:
    # 자동 채굴기는 초당 (레벨 * 2) 골드를 생성
    auto_gained_gold = int(elapsed_time * st.session_state.auto_miner_level * 2)
    if auto_gained_gold > 0:
        st.session_state.gold += auto_gained_gold
        # 세션 새로고침 시 골드 획득 메시지를 띄우면 너무 자주 뜨므로 생략
st.session_state.last_time = current_time

# --- UI & Layout ---
st.title("🦑 심해 채굴 타이쿤")
st.caption("확률형 채굴과 다양한 곡괭이 업그레이드!")

# Stats Summary
current_pickaxe = PICKAXE_TIERS[st.session_state.pickaxe_tier]
col1, col2 = st.columns(2)
col1.metric("보유 골드", f"{st.session_state.gold} G")
col2.metric("현재 곡괭이", f"{current_pickaxe['name']} (Lv.{st.session_state.pickaxe_tier})")

st.divider()

# Game Tabs
tab1, tab2, tab3 = st.tabs(["⛏️ 해저 채굴", "🛍️ 인벤토리 & 상점", "⚙️ 설정"])

with tab1:
    st.subheader("심해 작업장")
    st.write(f"현재 곡괭이 채굴력: **{current_pickaxe['power']}**")
    
    if st.button("⛏️ 바닥 깨기!", use_container_width=True):
        mined_ore = get_random_ore()
        
        # 실제 획득 골드 계산: 곡괭이 파워 * 광석 가치 배수
        gained_gold = current_pickaxe['power'] * mined_ore['value_multiplier']
        
        # 데이터 업데이트
        st.session_state.ores[mined_ore["name"]] += 1
        st.session_state.gold += gained_gold
        
        # 결과 메시지 저장
        st.session_state.last_mine_result = {
            "ore_name": mined_ore['name'],
            "icon": mined_ore['icon'],
            "gained_gold": gained_gold
        }
        st.rerun()

    # 최근 채굴 결과 표시
    if st.session_state.last_mine_result:
        result = st.session_state.last_mine_result
        st.success(f"{result['icon']} **{result['ore_name']}** 발견! (+{result['gained_gold']} G)")
        # 메시지를 한 번 보여준 후에는 지우지 않음 (다음 클릭 시 갱신됨)

    if st.session_state.auto_miner_level > 0:
        st.info(f"🤖 자동 드론 작동 중 (초당 {st.session_state.auto_miner_level * 2} G 자동 생성)")
        if st.button("🔄 화면 새로고침 (골드 정산)"):
            st.rerun()

with tab2:
    col_inv, col_shop = st.columns([1, 1.5])
    
    with col_inv:
        st.subheader("🎒 인벤토리")
        for ore in ORE_TYPES:
            count = st.session_state.ores[ore["name"]]
            if count > 0:
                st.write(f"{ore['icon']} {ore['name']}: {count}개")
        if sum(st.session_state.ores.values()) == 0:
            st.write("비어 있음")

    with col_shop:
        st.subheader("🛒 상점")
        
        # 1. 곡괭이 업그레이드
        st.markdown("#### **곡괭이 재질 변경**")
        next_tier = st.session_state.pickaxe_tier + 1
        if next_tier in PICKAXE_TIERS:
            next_pickaxe = PICKAXE_TIERS[next_tier]
            st.write(f"**{next_pickaxe['name']}**으로 업그레이드")
            st.write(f"- 채굴력: {next_pickaxe['power']}")
            st.write(f"- 비용: **{next_pickaxe['cost']} G**")
            
            if st.button(f"{next_pickaxe['name']} 구매", use_container_width=True):
                if st.session_state.gold >= next_pickaxe['cost']:
                    st.session_state.gold -= next_pickaxe['cost']
                    st.session_state.pickaxe_tier = next_tier
                    st.success(f"{next_pickaxe['name']}를 구매했습니다!")
                    st.rerun()
                else:
                    st.error("골드가 부족합니다!")
        else:
            st.write("✅ 최고 등급 곡괭이를 보유 중입니다.")

        st.divider()

        # 2. 자동 채굴기 업그레이드
        st.markdown("#### **자동 드론 고용**")
        auto_cost = (st.session_state.auto_miner_level + 1) * 1000
        st.write(f"현재 레벨: Lv.{st.session_state.auto_miner_level}")
        st.write(f"다음 레벨 비용: **{auto_cost} G**")
        if st.button(f"자동 드론 강화 ({auto_cost} G)", use_container_width=True):
            if st.session_state.gold >= auto_cost:
                st.session_state.gold -= auto_cost
                st.session_state.auto_miner_level += 1
                st.success("자동 드론이 강화되었습니다!")
                st.rerun()
            else:
                st.error("골드가 부족합니다!")

with tab3:
    st.subheader("게임 정보 및 설정")
    
    # 확률표 표시
    st.markdown("#### **광석 채굴 확률 및 가치**")
    prob_data = []
    for ore in ORE_TYPES:
        prob_data.append({
            "광석": f"{ore['icon']} {ore['name']}",
            "확률": f"{ore['chance']}%",
            "가치 배수": f"x{ore['value_multiplier']}"
        })
    st.table(prob_data)
    
    st.divider()
    
    if st.button("⚠️ 게임 데이터 초기화", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

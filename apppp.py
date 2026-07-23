import streamlit as st
import random

st.set_page_config(page_title="Mine Clicker", page_icon="⛏️", layout="centered")

# -----------------------
# 초기값
# -----------------------
if "money" not in st.session_state:
    st.session_state.money = 0
    st.session_state.progress = 0
    st.session_state.pickaxe = "맨손"
    st.session_state.power = 10

    st.session_state.inventory = {
        "🪨 돌": 0,
        "🪵 석탄": 0,
        "🩶 철": 0,
        "🥇 금": 0,
        "💎 다이아": 0,
    }

# -----------------------
# 광물 정보
# -----------------------
minerals = [
    ("🪨 돌", 60, 5),
    ("🪵 석탄", 25, 15),
    ("🩶 철", 10, 40),
    ("🥇 금", 4, 120),
    ("💎 다이아", 1, 500),
]

# -----------------------
# 화면
# -----------------------
st.title("⛏️ Mine Clicker")

col1, col2 = st.columns(2)

with col1:
    st.metric("💰 돈", f"{st.session_state.money}원")

with col2:
    st.metric("⛏️ 곡괭이", st.session_state.pickaxe)

st.divider()

st.markdown("## 🪨 바위")

if st.button("⛏️ 채굴하기", use_container_width=True):

    st.session_state.progress += st.session_state.power

    if st.session_state.progress >= 100:

        st.session_state.progress = 0

        rand = random.randint(1,100)

        total = 0

        for name, chance, price in minerals:

            total += chance

            if rand <= total:

                st.session_state.inventory[name] += 1

                st.success(f"{name} 획득!")

                break

st.progress(st.session_state.progress)

st.write(f"진행도 : {st.session_state.progress}%")

st.divider()

st.subheader("🎒 인벤토리")

prices = {}

for name, chance, price in minerals:

    prices[name] = price

    c1, c2, c3 = st.columns([4,2,2])

    with c1:
        st.write(name)

    with c2:
        st.write(st.session_state.inventory[name])

    with c3:

        if st.button(f"판매 {name}"):

            if st.session_state.inventory[name] > 0:

                st.session_state.inventory[name] -= 1

                st.session_state.money += price

                st.rerun()

st.divider()

st.subheader("🛒 곡괭이 상점")

if st.button("🪓 나무 곡괭이 (300원)"):

    if st.session_state.money >= 300:

        st.session_state.money -= 300

        st.session_state.pickaxe = "나무 곡괭이"

        st.session_state.power = 20

        st.success("업그레이드 완료!")

        st.rerun()

    else:

        st.error("돈이 부족합니다.")

if st.button("⛏️ 철 곡괭이 (1500원)"):

    if st.session_state.money >= 1500:

        st.session_state.money -= 1500

        st.session_state.pickaxe = "철 곡괭이"

        st.session_state.power = 35

        st.success("업그레이드 완료!")

        st.rerun()

    else:

        st.error("돈이 부족합니다.")

if st.button("💎 다이아 곡괭이 (6000원)"):

    if st.session_state.money >= 6000:

        st.session_state.money -= 6000

        st.session_state.pickaxe = "다이아 곡괭이"

        st.session_state.power = 60

        st.success("업그레이드 완료!")

        st.balloons()

        st.rerun()

    else:

        st.error("돈이 부족합니다.")

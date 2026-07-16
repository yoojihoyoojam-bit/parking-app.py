import streamlit as st
import pandas as pd
import pydeck as pdk

# 페이지 설정
st.set_page_config(
    page_title="서울시 공영주차장 정보 안내",
    page_icon="🅿️",
    layout="wide"
)

# ---------------------------------------------------------
# 데이터 전처리 및 로드 함수
# ---------------------------------------------------------
@st.cache_data
def load_data(file):
    # CSV 읽기 (인코딩 문제 방지를 위해 utf-8 또는 cp949 적용)
    try:
        df = pd.read_csv(file, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(file, encoding='cp949')

    # 숫자 데이터 형변환 및 기본 처리
    numeric_cols = ['위도', '경도', '기본 주차 요금', '기본 주차 시간(분 단위)', '추가 단위 요금', '추가 단위 시간(분 단위)', '월 정기권 금액']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 주소에서 자치구(예: 강북구, 성동구 등) 추출
    if '주소' in df.columns:
        df['자치구'] = df['주소'].astype(str).apply(
            lambda x: x.split()[0] if len(x.split()) > 0 and x.split()[0].endswith(('구', '군', '시'))
            else (x.split()[1] if len(x.split()) > 1 and x.split()[1].endswith(('구', '군', '시')) else '기타')
        )
    else:
        df['자치구'] = '기타'

    # 기본 요금 정보 가공 (예: 10분당 xxx원 형태로 표시용 컬럼 추가)
    df['요금정보'] = df.apply(
        lambda r: f"기본 {int(r['기본 주차 시간(분 단위)'])}분 / {int(r['기본 주차 요금']):,}원" 
        if r['기본 주차 요금'] > 0 else "무료 또는 정보 없음", axis=1
    )

    return df

# ---------------------------------------------------------
# 사이드바: 파일 업로드 및 필터 옵션
# ---------------------------------------------------------
st.sidebar.title("⚙️ 설정 및 데이터 업로드")

uploaded_file = st.sidebar.file_uploader("CSV 파일 업로드", type=["csv"])

# 파일 업로드가 없으면 기본 로컬 파일 로드 시도
if uploaded_file is not None:
    data = load_data(uploaded_file)
else:
    try:
        data = load_data("서울시 공영주차장 안내 정보.csv")
        st.sidebar.info("기본 파일(서울시 공영주차장 안내 정보.csv)을 사용 중입니다.")
    except Exception as e:
        st.sidebar.warning("CSV 파일을 업로드해주세요.")
        st.stop()

# ---------------------------------------------------------
# 데이터 필터링 세션
# ---------------------------------------------------------
st.title("🅿️ 서울시 공영주차장 스마트 안내 시스템")

# 자치구 목록 가져오기
gu_list = ["전체"] + sorted([g for g in data['자치구'].unique() if g != '기타'])
selected_gu = st.sidebar.selectbox("자치구 선택", gu_list)

# 추천 기능 필터: 주말 무료 여부
free_weekend = st.sidebar.checkbox("주말(토/공휴일) 무료 개방 주차장만 보기")

# 필터링 적용
filtered_df = data.copy()

if selected_gu != "전체":
    filtered_df = filtered_df[filtered_df['자치구'] == selected_gu]

if free_weekend:
    filtered_df = filtered_df[
        (filtered_df['토요일 유,무료 구분명'] == '무료') | 
        (filtered_df['공휴일 유,무료 구분명'] == '무료')
    ]

# 위도/경도가 유효한 데이터만 지도에 표기
map_df = filtered_df[(filtered_df['위도'] > 0) & (filtered_df['경도'] > 0)].copy()

# ---------------------------------------------------------
# 상단 요약 정보 및 가장 저렴한 주차장 추천 (추천 기능 1)
# ---------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="조회된 주차장 수", value=f"{len(filtered_df):,} 개")

with col2:
    if not filtered_df.empty and (filtered_df['기본 주차 요금'] > 0).any():
        avg_price = filtered_df[filtered_df['기본 주차 요금'] > 0]['기본 주차 요금'].mean()
        st.metric(label="평균 기본 요금", value=f"{int(avg_price):,} 원")
    else:
        st.metric(label="평균 기본 요금", value="0 원")

with col3:
    # 가장 요금이 싼 주차장 찾기
    valid_price_df = filtered_df[filtered_df['기본 주차 요금'] >= 0]
    if not valid_price_df.empty:
        cheapest = valid_price_df.sort_values(by=['기본 주차 요금', '기본 주차 시간(분 단위)'], ascending=[True, False]).iloc[0]
        st.metric(label="💡 최저가 주차장", value=cheapest['주차장명'], delta=f"{int(cheapest['기본 주차 요금'])}원 ({int(cheapest['기본 주차 시간(분 단위)'])}분)")

st.markdown("---")

# ---------------------------------------------------------
# Pydeck 기반 지도 시각화 (호버 기능 포함)
# ---------------------------------------------------------
st.subheader("🗺️ 주차장 위치 지도")

if not map_df.empty:
    # 중심 좌표 설정
    center_lat = map_df['위도'].mean()
    center_lon = map_df['경도'].mean()

    # Pydeck 마커 (ScatterplotLayer) 생성
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["경도", "위도"],
        get_fill_color="[255, 75, 75, 180]",  # 마커 색상 (RGB, 알파)
        get_radius=80,                        # 마커 크기(m)
        pickable=True,                        # 호버/클릭 가능 여부
        auto_highlight=True,
    )

    # 시점(View) 설정
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=13,
        pitch=0,
    )

    # 툴팁(마우스 호버 시 보일 정보) 디자인
    tooltip = {
        "html": """
            <b>🅿️ {주차장명}</b><br/>
            📍 <b>주소:</b> {주소}<br/>
            💰 <b>요금:</b> {요금정보}<br/>
            📅 <b>토요일:</b> {토요일 유,무료 구분명} | <b>공휴일:</b> {공휴일 유,무료 구분명}<br/>
            🎟️ <b>월 정기권:</b> {월 정기권 금액}원
        """,
        "style": {
            "backgroundColor": "rgba(0, 0, 0, 0.8)",
            "color": "white",
            "fontSize": "13px",
            "padding": "10px",
            "borderRadius": "8px"
        }
    }

    # 지도 출력
    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="mapbox://styles/mapbox/light-v10"
    )
    st.pydeck_chart(r)
else:
    st.warning("조건에 맞는 지도 데이터(위도/경도)가 없습니다.")

st.markdown("---")

# ---------------------------------------------------------
# 추천 기능 2: 키워드 검색 및 상세 목록 테이블
# ---------------------------------------------------------
st.subheader("📋 주차장 상세 목록 및 검색")

search_kw = st.text_input("주차장명 또는 상세 주소를 검색하세요:", "")

display_df = filtered_df.copy()
if search_kw:
    display_df = display_df[
        display_df['주차장명'].str.contains(search_kw, case=False, na=False) | 
        display_df['주소'].str.contains(search_kw, case=False, na=False)
    ]

# 주요 정보 컬럼만 가독성 좋게 출력
cols_to_show = [
    '주차장명', '주소', '기본 주차 요금', '기본 주차 시간(분 단위)', 
    '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '월 정기권 금액', '전화번호'
]
existing_cols = [c for c in cols_to_show if c in display_df.columns]

st.dataframe(
    display_df[existing_cols],
    use_container_width=True,
    hide_index=True
)

import streamlit as st
import pandas as pd
import pydeck as pdk

# 페이지 기본 설정
st.set_page_config(
    page_title="서울시 공영주차장 정보 안내",
    page_icon="🅿️",
    layout="wide"
)

# ---------------------------------------------------------
# 데이터 전처리 및 로드 함수 (KeyError 방지 완벽 보장)
# ---------------------------------------------------------
@st.cache_data
def load_data(file):
    # 1. UTF-8 또는 CP949 인코딩으로 데이터 읽기
    try:
        df = pd.read_csv(file, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(file, encoding='cp949')

    # 2. 열(Column) 이름 양끝의 숨은 공백 제거 (KeyError 예방 핵심)
    df.columns = df.columns.str.strip()

    # 3. 주요 수치형 컬럼 보장 및 숫자형 변환
    numeric_cols = [
        '위도', '경도', '기본 주차 요금', '기본 주차 시간(분 단위)', 
        '추가 단위 요금', '추가 단위 시간(분 단위)', '월 정기권 금액'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    # 4. 자치구(구/군/시) 안전 추출
    if '주소' in df.columns:
        df['자치구'] = df['주소'].astype(str).apply(
            lambda x: x.split()[0] if len(x.split()) > 0 and x.split()[0].endswith(('구', '군', '시'))
            else (x.split()[1] if len(x.split()) > 1 and x.split()[1].endswith(('구', '군', '시')) else '기타')
        )
    else:
        df['자치구'] = '기타'

    # 5. 마커 툴팁용 요금 정보 문구 가공
    def make_fee_info(r):
        fee = r.get('기본 주차 요금', 0)
        time_min = r.get('기본 주차 시간(분 단위)', 0)
        if fee > 0:
            return f"기본 {int(time_min)}분 / {int(fee):,}원"
        return "무료 또는 정보 없음"

    df['요금정보'] = df.apply(make_fee_info, axis=1)

    # 6. 유무료 및 문자열 컬럼 안전 예외 처리
    for col in ['주차장명', '주소', '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '전화번호']:
        if col not in df.columns:
            df[col] = '정보없음'
        else:
            df[col] = df[col].fillna('정보없음')

    return df

# ---------------------------------------------------------
# 사이드바: 파일 업로드 및 데이터 로드
# ---------------------------------------------------------
st.sidebar.title("⚙️ 설정 및 파일 업로드")

uploaded_file = st.sidebar.file_uploader("CSV 파일 업로드", type=["csv"])

# 파일 업로드가 있으면 적용, 없으면 로컬 기본 파일 읽기 시도
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
# 사이드바 필터 옵션
# ---------------------------------------------------------
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

# 지도 표시용 (위도/경도가 올바른 데이터만 사용)
map_df = filtered_df[(filtered_df['위도'] > 0) & (filtered_df['경도'] > 0)].copy()

# ---------------------------------------------------------
# 메인 화면 UI
# ---------------------------------------------------------
st.title("🅿️ 서울시 공영주차장 스마트 안내 시스템")

# 요약 지표 카드
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="조회된 주차장 수", value=f"{len(filtered_df):,} 개")

with col2:
    valid_paid = filtered_df[filtered_df['기본 주차 요금'] > 0]
    if not valid_paid.empty:
        avg_price = valid_paid['기본 주차 요금'].mean()
        st.metric(label="평균 기본 요금", value=f"{int(avg_price):,} 원")
    else:
        st.metric(label="평균 기본 요금", value="0 원")

with col3:
    # 가장 요금이 싼 곳 추천 (시간 대비 단가 또는 기본요금 기준)
    if not filtered_df.empty:
        cheapest = filtered_df.sort_values(by=['기본 주차 요금', '기본 주차 시간(분 단위)'], ascending=[True, False]).iloc[0]
        fee_val = int(cheapest['기본 주차 요금'])
        time_val = int(cheapest['기본 주차 시간(분 단위)'])
        fee_text = f"{fee_val:,}원 ({time_val}분)" if fee_val > 0 else "무료"
        st.metric(label="💡 최저가 주차장", value=cheapest['주차장명'], delta=fee_text)

st.markdown("---")

# ---------------------------------------------------------
# 지도 시각화 (Pydeck 툴팁/호버 적용)
# ---------------------------------------------------------
st.subheader("🗺️ 주차장 위치 지도")

if not map_df.empty:
    center_lat = map_df['위도'].mean()
    center_lon = map_df['경도'].mean()

    # Pydeck 레이어 생성
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["경도", "위도"],
        get_fill_color="[255, 75, 75, 180]",  # 주황 빨강 핀
        get_radius=80,                        # 마커 반지름(m)
        pickable=True,                        # 마우스 호버 감지 활성화
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=12,
        pitch=0,
    )

    # 마우스 오버 시 보일 툴팁 설정
    tooltip = {
        "html": """
            <div style="font-family: sans-serif;">
                <b>🅿️ {주차장명}</b><br/>
                📍 <b>주소:</b> {주소}<br/>
                💰 <b>요금:</b> {요금정보}<br/>
                📅 <b>토요일:</b> {토요일 유,무료 구분명} | <b>공휴일:</b> {공휴일 유,무료 구분명}<br/>
                🎟️ <b>월 정기권:</b> {월 정기권 금액}원
            </div>
        """,
        "style": {
            "backgroundColor": "rgba(0, 0, 0, 0.85)",
            "color": "white",
            "fontSize": "13px",
            "padding": "10px",
            "borderRadius": "8px"
        }
    }

    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="mapbox://styles/mapbox/light-v10"
    )
    st.pydeck_chart(r)
else:
    st.warning("조건에 맞는 지도 데이터가 없습니다.")

st.markdown("---")

# ---------------------------------------------------------
# 주차장 목록 및 검색 테이블
# ---------------------------------------------------------
st.subheader("📋 주차장 상세 목록 및 검색")

search_kw = st.text_input("주차장명 또는 상세 주소를 입력하세요:", "")

display_df = filtered_df.copy()
if search_kw:
    display_df = display_df[
        display_df['주차장명'].str.contains(search_kw, case=False, na=False) | 
        display_df['주소'].str.contains(search_kw, case=False, na=False)
    ]

# 화면에 표시할 주요 열
show_cols = [
    '주차장명', '주소', '기본 주차 요금', '기본 주차 시간(분 단위)', 
    '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '월 정기권 금액', '전화번호'
]

st.dataframe(
    display_df[show_cols],
    use_container_width=True,
    hide_index=True
)

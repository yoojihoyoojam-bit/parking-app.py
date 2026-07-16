import streamlit as st
import pandas as pd
import pydeck as pdk
import chardet
import io
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# 1. 페이지 설정
st.set_page_config(page_title="서울시 공영주차장 스마트 안내", page_icon="🅿️", layout="wide")

# ---------------------------------------------------------
# 2. 데이터 로드 및 초강력 전처리 (KeyError 방지)
# ---------------------------------------------------------
@st.cache_data
def load_and_clean_data(file):
    if hasattr(file, 'getvalue'):
        raw_bytes = file.getvalue()
    elif isinstance(file, str):
        with open(file, 'rb') as f:
            raw_bytes = f.read()
    else:
        raw_bytes = file.read()

    # 인코딩 감지
    detected = chardet.detect(raw_bytes)
    enc = detected.get('encoding') if detected.get('encoding') else 'utf-8-sig'

    try:
        df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, quotechar='"')
    except Exception:
        df = pd.read_csv(io.BytesIO(raw_bytes), encoding='cp949', quotechar='"')

    # 컬럼명의 따옴표 및 공백 완벽 제거 ("위도" -> 위도)
    df.columns = df.columns.astype(str).str.replace('"', '').str.strip()

    # 셀 내부 따옴표 제거
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.replace('"', '').str.strip()

    # 수치형 컬럼 강제 생성 및 예외 처리 (KeyError 방지 핵심)
    num_cols = ['위도', '경도', '기본 주차 요금', '기본 주차 시간(분 단위)', '월 정기권 금액']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0

    # 자치구 추출 (주소 첫 단어)
    if '주소' in df.columns:
        df['자치구'] = df['주소'].apply(lambda x: str(x).split()[0] if len(str(x).split()) > 0 else "기타")
    else:
        df['자치구'] = "기타"

    # 요금 텍스트 가공
    def format_fee(r):
        fee = r.get('기본 주차 요금', 0)
        time_m = r.get('기본 주차 시간(분 단위)', 0)
        if fee > 0:
            return f"기본 {int(time_m)}분 / {int(fee):,}원"
        return "무료 또는 정보 없음"

    df['요금정보'] = df.apply(format_fee, axis=1)

    # 누락된 텍스트 컬럼 안전 처리
    for col in ['주차장명', '주소', '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '전화번호']:
        if col not in df.columns:
            df[col] = '정보없음'
        else:
            df[col] = df[col].replace({'nan': '정보없음', '': '정보없음'}).fillna('정보없음')

    return df

# ---------------------------------------------------------
# 3. 비어있는 위도/경도를 주소 기반으로 자동 변환 (지오코딩)
# ---------------------------------------------------------
@st.cache_data
def fill_missing_coordinates(df):
    # 위도/경도가 0이거나 서울 지역을 벗어난 경우 좌표 변환 대상
    missing_mask = (df['위도'] < 33) | (df['경도'] < 124)
    if not missing_mask.any():
        return df

    geolocator = Nominatim(user_agent="seoul_parking_app_v3")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=0.05)

    # 상위 60개 항목 좌표 변환 (속도 방어)
    targets = df[missing_mask].head(60)
    for idx, row in targets.iterrows():
        addr = row.get('주소', '')
        if addr and addr != '정보없음':
            try:
                location = geocode(f"서울 {addr}")
                if location:
                    df.at[idx, '위도'] = location.latitude
                    df.at[idx, '경도'] = location.longitude
            except Exception:
                continue
    return df

# ---------------------------------------------------------
# 4. 사이드바 - 파일 업로드 & 필터링
# ---------------------------------------------------------
st.sidebar.title("⚙️ 설정 및 파일 업로드")
uploaded_file = st.sidebar.file_uploader("CSV 파일을 업로드하세요", type=["csv"])

if uploaded_file is not None:
    data = load_and_clean_data(uploaded_file)
else:
    try:
        data = load_and_clean_data("서울시 공영주차장 안내 정보.csv")
        st.sidebar.info("기본 파일(서울시 공영주차장 안내 정보.csv)을 읽었습니다.")
    except Exception:
        st.sidebar.warning("왼쪽 사이드바에서 CSV 파일을 업로드해주세요.")
        st.stop()

# 좌표가 없으면 주소 기반으로 지오코딩 실행
data = fill_missing_coordinates(data)

# 필터 옵션
gu_list = ["전체"] + sorted([g for g in data['자치구'].unique() if g != '기타'])
selected_gu = st.sidebar.selectbox("자치구 선택", gu_list)
free_weekend = st.sidebar.checkbox("주말(토/공휴일) 무료 주차장만 보기")

filtered_df = data.copy()

if selected_gu != "전체":
    filtered_df = filtered_df[filtered_df['자치구'] == selected_gu]

if free_weekend:
    filtered_df = filtered_df[
        (filtered_df['토요일 유,무료 구분명'] == '무료') | 
        (filtered_df['공휴일 유,무료 구분명'] == '무료')
    ]

# 정상 좌표만 지도로 전송
map_df = filtered_df[(filtered_df['위도'] > 33) & (filtered_df['경도'] > 124)].copy()

# ---------------------------------------------------------
# 5. 메인 UI
# ---------------------------------------------------------
st.title("🅿️ 서울시 공영주차장 스마트 안내 시스템")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="조회된 주차장", value=f"{len(filtered_df):,} 개")

with col2:
    valid_paid = filtered_df[filtered_df['기본 주차 요금'] > 0]
    if not valid_paid.empty:
        avg_price = valid_paid['기본 주차 요금'].mean()
        st.metric(label="평균 기본 요금", value=f"{int(avg_price):,} 원")
    else:
        st.metric(label="평균 기본 요금", value="0 원")

with col3:
    if not filtered_df.empty:
        cheapest = filtered_df.sort_values(by=['기본 주차 요금', '기본 주차 시간(분 단위)'], ascending=[True, False]).iloc[0]
        fee_val = int(cheapest['기본 주차 요금'])
        time_val = int(cheapest['기본 주차 시간(분 단위)'])
        fee_text = f"{fee_val:,}원 ({time_val}분)" if fee_val > 0 else "무료"
        st.metric(label="💡 최저가 주차장", value=cheapest['주차장명'], delta=fee_text)

st.markdown("---")

# ---------------------------------------------------------
# 6. 지도 시각화 (Pydeck)
# ---------------------------------------------------------
st.subheader("🗺️ 주차장 위치 지도")

if not map_df.empty:
    center_lat = map_df['위도'].mean()
    center_lon = map_df['경도'].mean()

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["경도", "위도"],
        get_fill_color="[255, 75, 75, 200]",
        get_radius=80,
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=13,
        pitch=0,
    )

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
    st.warning("선택된 주차장의 위도/경도를 찾는 중입니다. 잠시만 기다리시거나 아래 표 목록에서 확인하세요.")

st.markdown("---")

# ---------------------------------------------------------
# 7. 주차장 상세 목록 테이블 및 검색
# ---------------------------------------------------------
st.subheader("📋 주차장 상세 목록 및 검색")

search_kw = st.text_input("주차장명 또는 상세 주소를 검색하세요:", "")

display_df = filtered_df.copy()
if search_kw:
    display_df = display_df[
        display_df['주차장명'].str.contains(search_kw, case=False, na=False) | 
        display_df['주소'].str.contains(search_kw, case=False, na=False)
    ]

show_cols = [
    '주차장명', '주소', '기본 주차 요금', '기본 주차 시간(분 단위)', 
    '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '월 정기권 금액', '전화번호'
]

st.dataframe(
    display_df[show_cols],
    use_container_width=True,
    hide_index=True
)

import streamlit as st
import pandas as pd
import pydeck as pdk
import io

# 1. 페이지 설정
st.set_page_config(
    page_title="서울시 공영주차장 스마트 안내",
    page_icon="🅿️",
    layout="wide"
)

# ---------------------------------------------------------
# 2. 데이터 로드 및 최적화 함수
# ---------------------------------------------------------
@st.cache_data
def load_data(uploaded_file):
    if uploaded_file is None:
        return None

    # 파일 읽기 전 포인터 초기화
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    
    raw_data = uploaded_file.read()

    # 인코딩 순차 시도 (서울시 공영주차장 데이터 맞춤)
    df = None
    for enc in ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']:
        try:
            df = pd.read_csv(io.BytesIO(raw_data), encoding=enc, engine='c')
            if len(df.columns) > 5 and len(df) > 0:
                break
        except Exception:
            try:
                df = pd.read_csv(io.BytesIO(raw_data), encoding=enc, engine='python', on_bad_lines='skip')
                if len(df.columns) > 5 and len(df) > 0:
                    break
            except Exception:
                continue

    if df is None or len(df) == 0:
        st.error("CSV 데이터를 읽을 수 없거나 내용이 비어있습니다.")
        return None

    # 컬럼명 앞뒤 따옴표 및 공백 제거
    df.columns = df.columns.astype(str).str.replace('"', '').str.strip()

    # 데이터 내부 따옴표 및 공백 제거
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.replace('"', '').str.strip()

    # 수치형 데이터 보장 (위도, 경도, 요금 등)
    num_cols = ['위도', '경도', '기본 주차 요금', '기본 주차 시간(분 단위)', '월 정기권 금액']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    # 자치구 컬럼 자동 생성 (주소 첫 단어)
    if '주소' in df.columns:
        df['자치구'] = df['주소'].apply(
            lambda x: str(x).split()[0] if len(str(x).split()) > 0 and str(x) != 'nan' else '기타'
        )
    else:
        df['자치구'] = '기타'

    # 요금 표시 텍스트 생성
    def make_fee_text(r):
        fee = r.get('기본 주차 요금', 0)
        time_m = r.get('기본 주차 시간(분 단위)', 0)
        if fee > 0:
            return f"기본 {int(time_m)}분 / {int(fee):,}원"
        return "무료 또는 정보없음"

    df['요금정보'] = df.apply(make_fee_text, axis=1)

    # 누락된 텍스트 데이터 보정
    text_cols = ['주차장명', '주소', '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '전화번호']
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].replace({'nan': '-', '': '-', 'None': '-'}).fillna('-')
        else:
            df[col] = '-'

    return df


# ---------------------------------------------------------
# 3. 사이드바 - 파일 업로드 & 필터
# ---------------------------------------------------------
st.sidebar.title("⚙️ 설정 및 CSV 업로드")

uploaded_file = st.sidebar.file_uploader("서울시 공영주차장 CSV 업로드", type=["csv"])

if uploaded_file is not None:
    data = load_data(uploaded_file)
else:
    # 로컬 경로 시도
    try:
        with open("서울시 공영주차장 안내 정보.csv", "rb") as f:
            data = load_data(f)
        st.sidebar.info("기본 파일(서울시 공영주차장 안내 정보.csv)을 불러왔습니다.")
    except Exception:
        st.sidebar.warning("왼쪽 사이드바에서 CSV 파일을 업로드해주세요.")
        st.stop()

if data is None or len(data) == 0:
    st.warning("데이터를 불러오지 못했습니다. 올바른 CSV 파일인지 확인해주세요.")
    st.stop()

# 필터 설정
gu_list = ["전체"] + sorted([g for g in data['자치구'].unique() if g not in ['기타', '-']])
selected_gu = st.sidebar.selectbox("자치구 선택", gu_list)
free_weekend = st.sidebar.checkbox("주말(토요일) 무료 주차장만 보기")

# 필터링 적용
filtered_df = data.copy()

if selected_gu != "전체":
    filtered_df = filtered_df[filtered_df['자치구'] == selected_gu]

if free_weekend:
    filtered_df = filtered_df[filtered_df['토요일 유,무료 구분명'] == '무료']

# 지도용 데이터 (위도/경도가 0이 아닌 유효 좌표만)
map_df = filtered_df[(filtered_df['위도'] > 30) & (filtered_df['경도'] > 120)].copy()


# ---------------------------------------------------------
# 4. 메인 UI 및 통계
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
    if not filtered_df.empty and (filtered_df['기본 주차 요금'] > 0).any():
        cheapest = filtered_df[filtered_df['기본 주차 요금'] > 0].sort_values(
            by=['기본 주차 요금', '기본 주차 시간(분 단위)'], ascending=[True, False]
        ).iloc[0]
        fee_val = int(cheapest['기본 주차 요금'])
        time_val = int(cheapest['기본 주차 시간(분 단위)'])
        st.metric(label="💡 최저가 주차장", value=cheapest['주차장명'], delta=f"{fee_val:,}원({time_val}분)")
    else:
        st.metric(label="💡 최저가 주차장", value="정보없음", delta="0원")

st.markdown("---")


# ---------------------------------------------------------
# 5. 지도 시각화 (Pydeck)
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
        get_radius=100,
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
            <div style="font-family: sans-serif; padding: 5px;">
                <b>🅿️ {주차장명}</b><br/>
                📍 <b>주소:</b> {주소}<br/>
                💰 <b>요금:</b> {요금정보}<br/>
                📅 <b>토요일:</b> {토요일 유,무료 구분명} | <b>공휴일:</b> {공휴일 유,무료 구분명}<br/>
                📞 <b>전화:</b> {전화번호}
            </div>
        """,
        "style": {
            "backgroundColor": "rgba(0, 0, 0, 0.85)",
            "color": "white",
            "fontSize": "13px",
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
    st.warning("선택하신 주차장 데이터 중 지도의 좌표(위도/경도) 데이터가 비어 있는 항목이 많습니다. 아래 표에서 전체 정보를 확인해주세요.")

st.markdown("---")


# ---------------------------------------------------------
# 6. 상세 테이블 및 실시간 검색
# ---------------------------------------------------------
st.subheader("📋 주차장 상세 목록 및 검색")

search_kw = st.text_input("주차장명 또는 주소 검색:", "")

display_df = filtered_df.copy()
if search_kw:
    display_df = display_df[
        display_df['주차장명'].astype(str).str.contains(search_kw, case=False, na=False) | 
        display_df['주소'].astype(str).str.contains(search_kw, case=False, na=False)
    ]

# 표에 표시할 주요 컬럼 (존재하는 컬럼만 선택)
cols_to_show = [
    '주차장명', '주소', '기본 주차 요금', '기본 주차 시간(분 단위)', 
    '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '월 정기권 금액', '전화번호'
]
actual_cols = [c for c in cols_to_show if c in display_df.columns]

st.dataframe(
    display_df[actual_cols],
    use_container_width=True,
    hide_index=True
)

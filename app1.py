import streamlit as st
import pandas as pd
import pydeck as pdk
import io
import chardet

# 페이지 기본 설정
st.set_page_config(
    page_title="서울시 공영주차장 스마트 안내",
    page_icon="🅿️",
    layout="wide"
)

# ---------------------------------------------------------
# CSV 파일 안전하게 읽기 및 데이터 정제 함수
# ---------------------------------------------------------
@st.cache_data
def load_data(file):
    # 1. 파일 바이너리 데이터 읽기
    if hasattr(file, 'getvalue'):
        raw_data = file.getvalue()
    elif isinstance(file, str):
        with open(file, 'rb') as f:
            raw_data = f.read()
    else:
        raw_data = file.read()

    # chardet으로 인코딩 자동 감지
    detected = chardet.detect(raw_data)
    detected_enc = detected.get('encoding')

    # 시도할 인코딩 후보 목록
    encodings_to_try = [detected_enc, 'utf-8-sig', 'cp949', 'euc-kr', 'utf-8']
    
    df = None
    for enc in encodings_to_try:
        if not enc:
            continue
        try:
            # engine='python', on_bad_lines='skip'으로 파싱 에러 방지
            df = pd.read_csv(io.BytesIO(raw_data), encoding=enc, engine='python', on_bad_lines='skip')
            if len(df.columns) > 1: # 정상 파싱 체크
                break
        except Exception:
            continue

    if df is None:
        raise ValueError("파일 인코딩을 읽을 수 없습니다. (UTF-8 또는 CP949 변환 필요)")

    # 컬럼명 정리 (따옴표 및 공백 제거)
    df.columns = df.columns.str.replace('"', '').str.strip()

    # 모든 셀 데이터의 앞뒤 따옴표 및 공백 제거
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.replace('"', '').str.strip()

    # 주요 숫자형 컬럼 존재 여부 확인 후 형변환 및 예외 처리
    numeric_cols = ['위도', '경도', '기본 주차 요금', '기본 주차 시간(분 단위)', '월 정기권 금액']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0 # 컬럼이 없으면 0.0으로 새 컬럼 생성

    # 자치구 추출 (주소 정보가 있는 경우)
    if '주소' in df.columns:
        # 주소 앞단어 추출 (예: 성동구 마장동 ... -> 성동구)
        df['자치구'] = df['주소'].astype(str).apply(lambda x: x.split()[0] if len(x.split()) > 0 else '기타')
    else:
        # '주소' 컬럼이 없으면 전체 주차장 이름 정보를 통해 유추하거나 '기타'로 처리
        df['자치구'] = '기타'

    # 요금 정보 문구 가공 (툴팁용)
    def make_fee_info(r):
        fee = r.get('기본 주차 요금', 0)
        time_min = r.get('기본 주차 시간(분 단위)', 0)
        if fee > 0:
            return f"기본 {int(time_min)}분 / {int(fee):,}원"
        else:
            return "무료 또는 정보 없음"

    df['요금정보'] = df.apply(make_fee_info, axis=1)

    # 데이터 유실 방지: 표에 표시할 주요 문자열 컬럼 안전 처리
    cols_to_fill = ['주차장명', '주소', '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '전화번호']
    for col in cols_to_fill:
        if col not in df.columns:
            df[col] = '정보없음' # 컬럼이 없으면 '정보없음'으로 컬럼 생성
        else:
            df[col] = df[col].replace({'nan': '정보없음', '': '정보없음'}).fillna('정보없음')

    return df

# ---------------------------------------------------------
# 사이드바: 데이터 업로드 및 필터링
# ---------------------------------------------------------
st.sidebar.title("⚙️ 설정 및 파일 업로드")

uploaded_file = st.sidebar.file_uploader("CSV 파일 업로드", type=["csv"])

if uploaded_file is not None:
    data = load_data(uploaded_file)
else:
    # 기본 로컬 파일 로딩 시도 (배포 전 파일 경로 확인 필요)
    try:
        data = load_data("서울시 공영주차장 안내 정보.csv")
        st.sidebar.info("기본 데이터를 로드했습니다.")
    except Exception:
        st.sidebar.warning("CSV 파일을 사이드바에서 업로드해주세요.")
        st.stop()

# 자치구 목록 가져오기 및 필터 선택
gu_list = ["전체"] + sorted(list(data['자치구'].unique()))
selected_gu = st.sidebar.selectbox("자치구 선택", gu_list)

# 추천 기능: 주말 무료 여부 체크박스
free_weekend = st.sidebar.checkbox("주말(토/공휴일) 무료 개방 주차장만 보기")

# 데이터 필터링 적용
filtered_df = data.copy()

if selected_gu != "전체":
    filtered_df = filtered_df[filtered_df['자치구'] == selected_gu]

if free_weekend:
    filtered_df = filtered_df[
        (filtered_df['토요일 유,무료 구분명'] == '무료') | 
        (filtered_df['공휴일 유,무료 구분명'] == '무료')
    ]

# 좌표가 유효한 데이터만 지도에 표기 (위도 33~39, 경도 124~132 서울 부근 범위)
map_df = filtered_df[
    (filtered_df['위도'] > 33) & (filtered_df['위도'] < 39) &
    (filtered_df['경도'] > 124) & (filtered_df['경도'] < 132)
].copy()

# ---------------------------------------------------------
# 메인 화면 UI
# ---------------------------------------------------------
st.title("🅿️ 서울시 공영주차장 스마트 안내 시스템")

# 상단 요약 정보 카드
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="조회된 주차장 수", value=f"{len(filtered_df):,} 개")

with col2:
    if not filtered_df.empty:
        avg_price = filtered_df[filtered_df['기본 주차 요금'] > 0]['기본 주차 요금'].mean()
        st.metric(label="평균 기본 요금", value=f"{int(avg_price) if not pd.isna(avg_price) else 0:,} 원")
    else:
        st.metric(label="평균 기본 요금", value="0 원")

with col3:
    # 가장 요금이 싼 곳 추천 (0원 초과)
    valid_paid = filtered_df[filtered_df['기본 주차 요금'] > 0]
    if not valid_paid.empty:
        cheapest = valid_paid.sort_values(by=['기본 주차 요금', '기본 주차 시간(분 단위)'], ascending=[True, False]).iloc[0]
        st.metric(label="💡 최저가 주차장", value=cheapest['주차장명'], delta=f"{int(cheapest['기본 주차 요금'])}원/{int(cheapest['기본 주차 시간(분 단위)'])}분")

st.markdown("---")

# ---------------------------------------------------------
# 지도 시각화 (Pydeck)
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
    st.warning("조건에 맞는 좌표 정보를 가진 주차장이 없습니다. 아래 목록에서 주소 정보를 확인해주세요.")

st.markdown("---")

# ---------------------------------------------------------
# 추천 기능: 데이터 표 및 키워드 검색
# ---------------------------------------------------------
st.subheader("📋 주차장 상세 목록 및 검색")

search_kw = st.text_input("주차장명 또는 주소 검색:", "")

display_df = filtered_df.copy()
if search_kw:
    display_df = display_df[
        display_df['주차장명'].str.contains(search_kw, case=False, na=False) | 
        display_df['주소'].str.contains(search_kw, case)

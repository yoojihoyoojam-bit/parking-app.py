import streamlit as st
import pandas as pd
import pydeck as pdk
import chardet
import io

# 1. 페이지 설정
st.set_page_config(page_title="서울시 공영주차장 안내", page_icon="🅿️", layout="wide")

# ---------------------------------------------------------
# 2. 데이터 로드 및 초강력 정제 함수
# ---------------------------------------------------------
@st.cache_data
def load_and_clean_data(file):
    # 가. 인코딩 감지 및 읽기
    raw_bytes = file.read()
    detected = chardet.detect(raw_bytes)
    encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
    
    # 나. 데이터 읽기 (따옴표 처리)
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding, quotechar='"')
    except:
        df = pd.read_csv(io.BytesIO(raw_bytes), encoding='cp949', quotechar='"')

    # 다. 컬럼명 정제 (따옴표 및 공백 제거)
    df.columns = df.columns.str.replace('"', '').str.strip()
    
    # 라. 모든 데이터 내의 따옴표 제거 (데이터가 ""마장동"" 처럼 된 경우 대비)
    df = df.apply(lambda x: x.str.replace('"', '').str.strip() if x.dtype == "object" else x)

    # 마. 숫자형 변환 (위도, 경도, 요금 등)
    num_cols = ['위도', '경도', '기본 주차 요금', '기본 주차 시간(분 단위)', '월 정기권 금액']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 바. 자치구 추출 (주소의 첫 단어)
    if '주소' in df.columns:
        df['자치구'] = df['주소'].apply(lambda x: str(x).split()[0] if len(str(x).split()) > 0 else "기타")
    else:
        df['자치구'] = "미분류"

    # 사. 툴팁용 요금 정보 생성
    df['요금표시'] = df.apply(lambda x: f"{int(x['기본 주차 요금'])}원/{int(x['기본 주차 시간(분 단위)'])}분" 
                            if x['기본 주차 요금'] > 0 else "무료/정보없음", axis=1)
    
    return df

# ---------------------------------------------------------
# 3. 사이드바 - 파일 업로드 및 필터
# ---------------------------------------------------------
st.sidebar.title("🅿️ 데이터 설정")
uploaded_file = st.sidebar.file_uploader("주차장 CSV 파일을 업로드하세요", type=['csv'])

if uploaded_file:
    df = load_and_clean_data(uploaded_file)
else:
    st.info("왼쪽 사이드바에서 CSV 파일을 업로드해주세요. (제공해주신 데이터를 넣으시면 됩니다)")
    st.stop()

# 자치구 필터
gu_list = ["전체"] + sorted(list(df['자치구'].unique()))
selected_gu = st.sidebar.selectbox("자치구 선택", gu_list)

# 운영 필터
filter_free = st.sidebar.checkbox("주말(토요일) 무료만 보기")

# 데이터 필터링 적용
view_df = df.copy()
if selected_gu != "전체":
    view_df = view_df[view_df['자치구'] == selected_gu]
if filter_free:
    view_df = view_df[view_df['토요일 유,무료 구분명'] == '무료']

# ---------------------------------------------------------
# 4. 메인 화면 - 요약 정보
# ---------------------------------------------------------
st.title(f"🚗 {selected_gu if selected_gu != '전체' else '서울시'} 공영주차장 찾기")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("검색된 주차장", f"{len(view_df)} 곳")
with col2:
    avg_fee = view_df[view_df['기본 주차 요금'] > 0]['기본 주차 요금'].mean()
    st.metric("평균 기본요금", f"{int(avg_fee) if not pd.isna(avg_fee) else 0} 원")
with col3:
    # 가장 싼 주차장 찾기 (요금이 0보다 큰 것 중 최저가)
    cheapest_df = view_df[view_df['기본 주차 요금'] > 0].sort_values('기본 주차 요금')
    if not cheapest_df.empty:
        cheapest = cheapest_df.iloc[0]
        st.success(f"가장 싼 곳: {cheapest['주차장명']} ({int(cheapest['기본 주차 요금'])}원)")

# ---------------------------------------------------------
# 5. 지도 시각화 (Pydeck)
# ---------------------------------------------------------
st.subheader("📍 주차장 위치 (마우스를 올리면 상세정보가 보입니다)")

# 위도/경도가 0인 데이터 제거 (지도 오류 방지)
map_data = view_df[(view_df['위도'] > 30) & (view_df['경도'] > 120)]

if not map_data.empty:
    # 지도 레이어
    layer = pdk.Layer(
        "ScatterplotLayer",
        map_data,
        get_position="[경도, 위도]",
        get_fill_color="[255, 100, 0, 160]",
        get_radius=100,
        pickable=True,
        auto_highlight=True,
    )

    # 중심점 계산
    center_lat = map_data['위도'].mean()
    center_lon = map_data['경도'].mean()

    # 지도 출력
    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/light-v9',
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=12,
            pitch=0
        ),
        layers=[layer],
        tooltip={
            "html": "<b>주차장명:</b> {주차장명}<br/>"
                    "<b>주소:</b> {주소}<br/>"
                    "<b>요금:</b> {요금표시}<br/>"
                    "<b>토요일:</b> {토요일 유,무료 구분명}<br/>"
                    "<b>공휴일:</b> {공휴일 유,무료 구분명}",
            "style": {"color": "white", "backgroundColor": "black"}
        }
    ))
else:
    st.warning("지도에 표시할 위치 정보(위도, 경도)가 데이터에 없습니다.")

# ---------------------------------------------------------
# 6. 상세 데이터 표
# ---------------------------------------------------------
st.subheader("📋 주차장 상세 목록")

# 필요한 컬럼만 보기 좋게 정리
show_cols = ['주차장명', '주소', '요금표시', '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '전화번호']
st.dataframe(view_df[show_cols], use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# 7. 추가 추천 기능: 월 정기권 분석
# ---------------------------------------------------------
if not view_df.empty:
    st.markdown("---")
    st.subheader("💡 분석 추천: 월 정기권이 저렴한 곳")
    monthly_df = view_df[view_df['월 정기권 금액'] > 0].sort_values('월 정기권 금액').head(5)
    if not monthly_df.empty:
        st.write("해당 지역에서 월 정기권이 가장 저렴한 TOP 5입니다.")
        st.table(monthly_df[['주차장명', '월 정기권 금액', '전화번호']])

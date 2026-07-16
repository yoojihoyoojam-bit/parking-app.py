import streamlit as st
import pandas as pd
import pydeck as pdk
import io
import chardet

# 페이지 기본 설정
st.set_page_config(
    page_title="서울시 공영주차장 정보 안내",
    page_icon="🅿️",
    layout="wide"
)

# ---------------------------------------------------------
# CSV 파일 안전하게 읽기 (따옴표 및 인코딩 완전 처리)
# ---------------------------------------------------------
@st.cache_data
def load_data(file):
    # 1. 파일 바이트 읽기
    if hasattr(file, 'getvalue'):
        raw_data = file.getvalue()
    elif isinstance(file, str):
        with open(file, 'rb') as f:
            raw_data = f.read()
    else:
        raw_data = file.read()

    # 인코딩 감지
    detected = chardet.detect(raw_data)
    detected_enc = detected.get('encoding')

    encodings_to_try = [detected_enc, 'utf-8-sig', 'cp949', 'euc-kr', 'utf-8']
    
    df = None
    for enc in encodings_to_try:
        if not enc:
            continue
        try:
            # engine='python' 및 on_bad_lines 옵션으로 파싱 에러 방지
            df = pd.read_csv(
                io.BytesIO(raw_data), 
                encoding=enc, 
                engine='python', 
                on_bad_lines='skip'
            )
            if len(df.columns) > 1: # 정상 파싱 체크
                break
        except Exception:
            continue

    if df is None or len(df.columns) <= 1:
        # C엔진으로 다시 시도
        for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
            try:
                df = pd.read_csv(io.BytesIO(raw_data), encoding=enc)
                if len(df.columns) > 1:
                    break
            except Exception:
                continue

    # 컬럼명 앞뒤 따옴표 및 공백 제거
    df.columns = df.columns.str.replace('"', '').str.strip()

    # 모든 셀 데이터의 앞뒤 따옴표 및 공백 제거
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.replace('"', '').str.strip()

    # 수치형 컬럼 변환
    numeric_cols = [
        '위도', '경도', '기본 주차 요금', '기본 주차 시간(분 단위)', 
        '추가 단위 요금', '추가 단위 시간(분 단위)', '월 정기권 금액'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    # 자치구 추출 (주소 예: "강북구 미아동 791-1364" -> "강북구")
    if '주소' in df.columns:
        def extract_gu(addr):
            parts = str(addr).split()
            for p in parts:
                if p.endswith(('구', '군', '시')):
                    return p
            return '기타'
        df['자치구'] = df['주소'].apply(extract_gu)
    else:
        df['자치구'] = '기타'

    # 요금 정보 텍스트 가공
    def make_fee_info(r):
        fee = r.get('기본 주차 요금', 0)
        time_min = r.get('기본 주차 시간(분 단위)', 0)
        if fee > 0:
            return f"기본 {int(time_min)}분 / {int(fee):,}원"
        return "무료 또는 정보 없음"

    df['요금정보'] = df.apply(make_fee_info, axis=1)

    # 누락 데이터 안전 처리
    for col in ['주차장명', '주소', '토요일 유,무료 구분명', '공휴일 유,무료 구분명', '전화번호']:
        if col not in df.columns:
            df[col] = '정보없음'
        else:
            df[col] = df[col].replace({'nan': '정보없음', 'None': '정보없음', '': '정보없음'}).fillna('정보없음')

    return df

# ---------------------------------------------------------
# 사이드바: 데이터 업로드 및 필터
# ---------------------------------------------------------
st.sidebar.title("⚙️ 설정 및 파일 업로드")

uploaded_file = st.sidebar.file_uploader("CSV 파일 업로드", type=["csv"])

if uploaded_file is not None:
    data = load_data(uploaded_file)
else:
    try:
        data = load_data("서울시 공영주차장 안내 정보.csv")
        st.sidebar.info("기본 CSV 파일을 로드했습니다.")
    except Exception as e:
        st.sidebar.warning("CSV 파일을 사이드바에서 업로드해주세요.")
        st.stop()

gu_list = ["전체"] + sorted([g for g in data['자치구'].unique() if g != '기타'])
selected_gu = st.sidebar.selectbox("자치구 선택", gu_list)

free_weekend = st.sidebar.checkbox("주말(토/공휴일) 무료 개방 주차장만 보기")

# 필터링
filtered_df = data.copy()

if selected_gu != "전체":
    filtered_df = filtered_df[filtered_df['자치구'] == selected_gu]

if free_weekend:
    filtered_df = filtered_df[
        (filtered_df['토요일 유,무료 구분명'] == '무료') | 
        (filtered_df['공휴일 유,무료 구분명'] == '무료')
    ]

# 위도, 경도 좌표가 유효한(서울 지역범위 33~39, 124~132) 데이터만 지도에 표기
map_df = filtered_df[
    (filtered_df['위도'] > 30) & (filtered_df['위도'] < 45) &
    (filtered_df['경도'] > 120) & (filtered_df['경도'] < 135)
].copy()

# ---------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------
st.title("🅿️ 서울시 공영주차장 스마트 안내 시스템")

# 상단 요약 카드
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
    if not filtered_df.empty:
        cheapest = filtered_df.sort_values(by=['기본 주차 요금', '기본 주차 시간(분 단위)'], ascending=[True, False]).iloc[0]
        fee_val = int(cheapest['기본 주차 요금'])
        time_val = int(cheapest['기본 주차 시간(분 단위)'])
        fee_text = f"{fee_val:,}원 ({time_val}분)" if fee_val > 0 else "무료"
        st.metric(label="💡 최저가 주차장", value=cheapest['주차장명'], delta=fee_text)

st.markdown("---")

# ---------------------------------------------------------
# 지도 시각화 (Pydeck)
# ---------------------------------------------------------
st.subheader("🗺️ 주차장 위치 지도")

if not map_df.empty:
    center_lat = map_df['위도'].mean()
    center_lon = map_df['경도'].mean()

    layer = pdk.

st.dataframe(
    display_df[show_cols],
    use_container_width=True,
    hide_index=True
)

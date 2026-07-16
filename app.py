import streamlit as st
import pandas as pd
import io
import folium
from streamlit_folium import st_folium

# 1. 페이지 설정
st.set_page_config(
    page_title="서울시 공영주차장 스마트 안내",
    page_icon="🅿️",
    layout="wide"
)

# ---------------------------------------------------------
# 2. 데이터 로드 및 전처리
# ---------------------------------------------------------
@st.cache_data
def load_data(uploaded_file):
    if uploaded_file is None:
        return None

    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    
    raw_data = uploaded_file.read()

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
        return None

    # 컬럼 및 셀 정제
    df.columns = df.columns.astype(str).str.replace('"', '').str.strip()
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.replace('"', '').str.strip()

    # 숫자형 변환
    num_cols = ['위도', '경도', '기본 주차 요금', '기본 주차 시간(분 단위)', '월 정기권 금액']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0

    # 자치구 컬럼 생성
    if '주소' in df.columns:
        df['자치구'] = df['주소'].apply(
            lambda x: str(x).split()[0] if len(str(x).split()) > 0 and str(x) != 'nan' else '기타'
        )
    else:
        df['자치구'] = '기타'

    # 요금 텍스트 가공
    def make_fee_text(r):
        fee = r.get('기본 주차 요금', 0)
        time_m = r.get('기본 주차 시간(분 단위)', 0)
        if fee > 0:
            return f"기본 {int(time_m)}분 / {int(fee):,}원"
        return "무료 또는 정보없음"

    df['요금정보'] = df.apply(make_fee_text, axis=1)

    # 문자열 누락 보정
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

# 필터 옵션
gu_list = ["전체"] + sorted([g for g in data['자치구'].unique() if g not in ['기타', '-']])
selected_gu = st.sidebar.selectbox("자치구 선택", gu_list)
free_weekend = st.sidebar.checkbox("주말(토요일) 무료 주차장만 보기")

filtered_df = data.copy()

if selected_gu != "전체":
    filtered_df = filtered_df[filtered_df['자치구'] == selected_gu]

if free_weekend:
    filtered_df = filtered_df[filtered_df['토요일 유,무료 구분명'] == '무료']

# 유효한 한국 위치 좌표만 필터링 (서울 위도 약 37.5, 경도 약 126.9)
map_df = filtered_df[(filtered_df['위도'] > 33) & (filtered_df['위도'] < 39) & 
                    (filtered_df['경도'] > 124) & (filtered_df['경도'] < 130)].copy()


# ---------------------------------------------------------
# 4. 메인 UI
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
# 5. 진짜 지도 시각화 (Folium / OpenStreetMap)
# ---------------------------------------------------------
st.subheader("🗺️ 실제 서울시 지도로 위치 확인하기")

if not map_df.empty:
    # 중심 좌표 설정
    center_lat = map_df['위도'].mean()
    center_lon = map_df['경도'].mean()

    # Folium 타일 지도로 '진짜 배경 지도' 로드
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="OpenStreetMap" # 실제 도로와 지명이 표시되는 배경 타일
    )

    # 성능을 위해 지도 표시 마커 수를 최대 100개로 제한 (너무 많으면 느려짐)
    display_map_df = map_df.head(100)

    for idx, row in display_map_df.iterrows():
        popup_html = f"""
        <div style="font-family: sans-serif; width: 220px;">
            <h4 style="margin-bottom: 5px;">🅿️ {row['주차장명']}</h4>
            <b>📍 주소:</b> {row['주소']}<br/>
            <b>💰 요금:</b> {row['요금정보']}<br/>
            <b>📅 토요일:</b> {row['토요일 유,무료 구분명']}<br/>
            <b>📞 전화:</b> {row['전화번호']}
        </div>
        """
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row['주차장명'],
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)

    # Streamlit 화면에 진짜 지도 출력
    st_folium(m, width="100%", height=500)
    
    if len(map_df) > 100:
        st.caption(f"💡 지도 속도 최적화를 위해 좌표가 있는 {len(map_df)}개 중 상위 100개 주차장을 지도에 표시했습니다.")
else:
    st.warning("선택하신 데이터 중 실제 지도에 핀을 찍을 좌표(위도/경도) 값이 없습니다. 아래 상세 목록을 이용해 주세요.")

st.markdown("---")


# ---------------------------------------------------------
# 6. 상세 목록 테이블
# ---------------------------------------------------------
st.subheader("📋 주차장 상세 목록 및 검색")

search_kw = st.text_input("주차장명 또는 주소 검색:", "")

display_df = filtered_df.copy()
if search_kw:
    display_df = display_df[
        display_df['주차장명'].astype(str).str.contains(search_kw, case=False, na=False) | 
        display_df['주소'].astype(str).str.contains(search_kw, case=False, na=False)
    ]

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

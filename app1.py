import streamlit as st
import pandas as pd
import folium

from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

st.set_page_config(
    page_title="서울시 공영주차장",
    page_icon="🅿️",
    layout="wide"
)

st.title("🅿️ 서울시 공영주차장 안내")

###########################################
# CSV 불러오기
###########################################

uploaded = st.sidebar.file_uploader(
    "CSV 업로드",
    type="csv"
)

if uploaded is not None:
    df = pd.read_csv(uploaded, encoding="utf-8")
else:
    df = pd.read_csv(
        "서울시 공영주차장 안내 정보.csv",
        encoding="utf-8"
    )

###########################################
# 컬럼명 정리
###########################################

df.columns = df.columns.str.strip()

st.sidebar.success(f"데이터 : {len(df)}건")

st.write(df.head())

###########################################
# 주소 컬럼 찾기
###########################################

address_candidates = [
    "주소",
    "소재지",
    "도로명주소",
    "주차장주소"
]

address_col = None

for c in address_candidates:
    if c in df.columns:
        address_col = c
        break

if address_col is None:
    st.error("주소 컬럼을 찾지 못했습니다.")
    st.stop()

###########################################
# 좌표 변환
###########################################

geolocator = Nominatim(user_agent="parking_app")
geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1
)

@st.cache_data
def geocode_dataframe(data):

    lat_list = []
    lon_list = []

    for addr in data[address_col]:

        try:

            location = geocode(addr)

            if location:

                lat_list.append(location.latitude)
                lon_list.append(location.longitude)

            else:

                lat_list.append(None)
                lon_list.append(None)

        except:

            lat_list.append(None)
            lon_list.append(None)

    data["위도"] = lat_list
    data["경도"] = lon_list

    return data

if "위도" not in df.columns:

    with st.spinner("주소를 좌표로 변환 중..."):

        df = geocode_dataframe(df)

###########################################
# 검색
###########################################

keyword = st.sidebar.text_input("검색")

if keyword:

    mask = df.apply(
        lambda row:
        row.astype(str).str.contains(
            keyword,
            case=False
        ).any(),
        axis=1
    )

    df = df[mask]

###########################################
# 지도
###########################################

m = folium.Map(
    location=[37.5665,126.9780],
    zoom_start=11
)

cluster = MarkerCluster().add_to(m)

###########################################
# 이름 컬럼
###########################################

name_candidates = [
    "주차장명",
    "주차장 이름",
    "시설명"
]

name_col = None

for c in name_candidates:

    if c in df.columns:

        name_col = c
        break

###########################################
# 마커 표시
###########################################

for _, row in df.iterrows():

    if pd.isna(row["위도"]):
        continue

    if name_col:

        popup = f"""
        <b>{row[name_col]}</b><br>
        {row[address_col]}
        """

    else:

        popup = row[address_col]

    folium.Marker(

        location=[
            row["위도"],
            row["경도"]
        ],

        popup=popup,

        tooltip=popup

    ).add_to(cluster)

###########################################
# 지도 출력
###########################################

st.subheader("지도")

st_folium(
    m,
    width=1200,
    height=700
)

###########################################
# 데이터
###########################################

st.subheader("데이터")

st.dataframe(
    df,
    use_container_width=True
)
##################################################
# 자치구 컬럼 찾기
##################################################

gu_candidates = [
    "자치구",
    "구",
    "행정구"
]

gu_col = None

for c in gu_candidates:
    if c in df.columns:
        gu_col = c
        break

if gu_col:

    gu_list = sorted(df[gu_col].dropna().unique())

    selected_gu = st.sidebar.selectbox(
        "자치구 선택",
        ["전체"] + list(gu_list)
    )

    if selected_gu != "전체":
        df = df[df[gu_col] == selected_gu]

fee_candidates = [
    "요금",
    "기본요금",
    "주차요금",
    "요금정보"
]

fee_col = None

for c in fee_candidates:

    if c in df.columns:

        fee_col = c
        break

time_candidates = [
    "운영시간",
    "운영시간정보",
    "운영"
]

time_col = None

for c in time_candidates:

    if c in df.columns:

        time_col = c
        break

week_candidates = [
    "주말운영",
    "토요일운영",
    "운영요일"
]

week_col = None

for c in week_candidates:

    if c in df.columns:

        week_col = c
        break

free_candidates = [
    "무료",
    "무료여부",
    "요금구분"
]

free_col = None

for c in free_candidates:

    if c in df.columns:

        free_col = c
        break


st.subheader("🏆 추천 주차장")

if fee_col:

    temp = df.copy()

    temp["fee_num"] = (
        temp[fee_col]
        .astype(str)
        .str.replace(",", "")
        .str.extract("(\d+)")
        .fillna(999999)
        .astype(int)
    )

    cheapest = temp.sort_values("fee_num").iloc[0]

    col1,col2,col3 = st.columns(3)

    if name_col:
        col1.metric("추천", cheapest[name_col])

    col2.metric("요금", cheapest[fee_col])

    if gu_col:
        col3.metric("자치구", cheapest[gu_col])

st.subheader("📊 통계")

c1,c2,c3,c4 = st.columns(4)

c1.metric("주차장 수", len(df))

if fee_col:

    temp = (
        df[fee_col]
        .astype(str)
        .str.replace(",","")
        .str.extract("(\d+)")
        .fillna(0)
        .astype(int)
    )

    c2.metric(
        "평균요금",
        f"{int(temp.mean())}원"
    )

if free_col:

    free_count = (
        df[free_col]
        .astype(str)
        .str.contains("무료")
        .sum()
    )

    c3.metric(
        "무료",
        free_count
    )

    c4.metric(
        "유료",
        len(df)-free_count
    )
icon_color = "blue"

if fee_col:

    text = str(row[fee_col])

    if "무료" in text:

        icon_color = "green"

    else:

        try:

            fee = int(
                ''.join(
                    filter(str.isdigit,text)
                )
            )

            if fee <= 1000:

                icon_color = "blue"

            elif fee <= 3000:

                icon_color = "orange"

            else:

                icon_color = "red"

        except:

            pass

icon=folium.Icon(color=icon_color)
popup = f"""
<b>{row[name_col] if name_col else ''}</b><br>

📍 주소 : {row[address_col]}<br>

💰 요금 : {row[fee_col] if fee_col else '-'}<br>

🆓 무료 :
{row[free_col] if free_col else '-'}<br>

📅 주말 :
{row[week_col] if week_col else '-'}<br>

🕒 운영 :
{row[time_col] if time_col else '-'}
"""

csv = df.to_csv(
    index=False
).encode("utf-8-sig")

st.download_button(

    "📥 결과 CSV 다운로드",

    csv,

    "parking_result.csv",

    "text/csv"
)




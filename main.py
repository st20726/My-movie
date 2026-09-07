
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.write("원하는 날짜를 선택하면 그날의 박스오피스를 확인할 수 있습니다.")


# --------------------------------------------------
# 한국 시간 기준 날짜 계산
# --------------------------------------------------

kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()
yesterday = today_kst - timedelta(days=1)


# --------------------------------------------------
# 날짜 선택
# --------------------------------------------------

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday
)

target_dt = selected_date.strftime("%Y%m%d")

st.caption(
    f"선택한 날짜: {selected_date.strftime('%Y년 %m월 %d일')}"
)


# --------------------------------------------------
# KOBIS API에서 박스오피스 데이터 가져오기
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    # Streamlit Secrets에서 API 키 가져오기
    try:
        api_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "error_type": "secret",
            "error": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 Secrets에 "
                "KOBIS_KEY가 등록되어 있는지 확인하세요."
            )
        }

    # KOBIS 일일 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    # API 요청
    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        return {
            "success": False,
            "error_type": "request",
            "error": f"API 요청에 실패했습니다.\n\n{e}"
        }

    # KOBIS API 오류 확인
    if "faultInfo" in data:

        fault = data["faultInfo"]

        return {
            "success": False,
            "error_type": "fault",
            "error": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault.get('faultCode', '확인 불가')}\n"
                f"오류 내용: {fault.get('message', '확인 불가')}"
            )
        }

    # 박스오피스 결과 확인
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "error_type": "empty",
            "error": "박스오피스 결과가 없습니다."
        }

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )

    # 데이터가 없으면 안내
    if not movie_list:
        return {
            "success": False,
            "error_type": "no_data",
            "error": "그날은 아직 집계 전입니다."
        }

    return {
        "success": True,
        "data": movie_list
    }


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------

result = get_boxoffice(target_dt)


# --------------------------------------------------
# 오류 처리
# --------------------------------------------------

if not result["success"]:

    if result["error_type"] == "no_data":

        st.info(
            "📭 그날은 아직 집계 전입니다.\n\n"
            "다른 날짜를 선택해 주세요."
        )

    else:

        st.error(
            "❌ 박스오피스 정보를 가져오지 못했습니다."
        )

        st.warning(
            "다음 내용을 확인해 주세요.\n\n"
            "① Streamlit Cloud의 Secrets에 "
            "KOBIS_KEY가 등록되어 있는지 확인하세요.\n\n"
            "② KOBIS 인증키가 정확한지 확인하세요.\n\n"
            "③ KOBIS API가 정상적으로 작동하는지 확인하세요.\n\n"
            "④ 선택한 날짜의 박스오피스 데이터가 존재하는지 "
            "확인하세요.\n\n"
            f"상세 오류:\n{result['error']}"
        )

    st.stop()


# --------------------------------------------------
# DataFrame 만들기
# --------------------------------------------------

df = pd.DataFrame(result["data"])


# --------------------------------------------------
# 숫자 데이터 숫자형으로 변환
# --------------------------------------------------

number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in number_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).astype(int)


# --------------------------------------------------
# 관객수 기준으로 정렬
# --------------------------------------------------

df = (
    df.sort_values(
        by="audiCnt",
        ascending=False
    )
    .reset_index(drop=True)
)


# --------------------------------------------------
# 영화 이름 만들기
# 누적 관객수가 100만 명을 넘으면 트로피 표시
# --------------------------------------------------

def make_movie_name(row):

    movie_name = row["movieNm"]

    if row["audiAcc"] > 1_000_000:
        movie_name += " 🏆"

    return movie_name


df["display_movie_name"] = df.apply(
    make_movie_name,
    axis=1
)


# --------------------------------------------------
# 순위 변화 표시
# rankInten
# 양수 = 순위 상승
# 음수 = 순위 하락
# --------------------------------------------------

def make_rank_display(row):

    rank = row["rank"]
    change = row["rankInten"]

    if change > 0:

        return f"{rank} 🔴⬆️"

    elif change < 0:

        return f"{rank} 🔵⬇️"

    else:

        return f"{rank} ➖"


df["display_rank"] = df.apply(
    make_rank_display,
    axis=1
)


# --------------------------------------------------
# 관객수 기준 1위 영화
# --------------------------------------------------

first_movie = df.iloc[0]


st.subheader("🏆 관객수 기준 1위")

st.markdown(
    f"## {first_movie['display_movie_name']}"
)


# --------------------------------------------------
# 1위 영화 정보 3개 카드
# --------------------------------------------------

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "관객수",
        f"{first_movie['audiCnt']:,}명"
    )


with col2:

    st.metric(
        "누적관객",
        f"{first_movie['audiAcc']:,}명"
    )


with col3:

    st.metric(
        "스크린수",
        f"{first_movie['scrnCnt']:,}개"
    )


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------

st.subheader("📋 전체 박스오피스")


display_df = df[
    [
        "display_rank",
        "display_movie_name",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


display_df = display_df.sort_values(
    by="관객수",
    ascending=False
).reset_index(drop=True)


st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 관객수 상위 5편 표
# --------------------------------------------------

st.subheader("🔥 관객수 상위 5편")


top5_table = df.head(5).copy()


top5_table["상위순위"] = range(
    1,
    len(top5_table) + 1
)


top5_table = top5_table[
    [
        "상위순위",
        "display_movie_name",
        "audiCnt"
    ]
].copy()


top5_table.columns = [
    "순위",
    "영화명",
    "관객수"
]


top5_table["관객수"] = (
    top5_table["관객수"]
    .astype(int)
)


st.dataframe(
    top5_table,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 관객수 상위 5편 그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편 그래프")


# 상위 5편만 가져오기
top5_chart = (
    df[
        [
            "display_movie_name",
            "audiCnt"
        ]
    ]
    .head(5)
    .copy()
)


# 가장 적은 관객수를 위쪽에 배치해서
# 가장 많은 영화가 그래프 위에 나오도록 정렬
top5_chart = top5_chart.sort_values(
    by="audiCnt",
    ascending=True
)


# Plotly 막대그래프 생성
fig = px.bar(
    top5_chart,
    x="audiCnt",
    y="display_movie_name",
    orientation="h",
    labels={
        "audiCnt": "관객수",
        "display_movie_name": "영화"
    },
    text="audiCnt"
)


# 막대 끝에 관객수 표시
fig.update_traces(
    texttemplate="%{text:,}명",
    textposition="outside"
)


# 그래프 크기 및 제목 설정
fig.update_layout(
    xaxis_title="관객수",
    yaxis_title="영화",
    height=400,
    margin=dict(
        l=20,
        r=80,
        t=30,
        b=20
    )
)


# Streamlit에 그래프 표시
st.plotly_chart(
    fig,
    use_container_width=True
)


# --------------------------------------------------
# 마지막 안내
# --------------------------------------------------

st.divider()

st.caption(
    "데이터 출처: KOBIS 영화관입장권통합전산망 "
    "(Korean Box Office Information System)"
)


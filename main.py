import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# -----------------------------------------
# 1. 기본 화면 설정
# -----------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.write("KOBIS 영화관입장권통합전산망의 일일 박스오피스 정보를 보여줍니다.")


# -----------------------------------------
# 2. 한국 시간 기준으로 '어제' 계산하기
# -----------------------------------------
# 배포 서버의 시간이 한국 시간이 아닐 수 있기 때문에
# 반드시 한국 시간(KST)을 기준으로 날짜를 계산합니다.
kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()
yesterday = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_dt = yesterday.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} "
    f"(한국 시간 기준)"
)


# -----------------------------------------
# 3. KOBIS API에서 데이터 가져오기
# -----------------------------------------
# st.cache_data를 사용하면 같은 날짜의 데이터를
# 약 1시간 동안 저장해 두어 API를 계속 호출하지 않습니다.
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # 인증키는 Streamlit secrets에서 가져옵니다.
    # 실제 인증키를 코드에 직접 작성하지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생했는지 확인합니다.
        response.raise_for_status()

        # JSON 형태의 응답을 가져옵니다.
        data = response.json()

    except Exception as e:
        return {
            "success": False,
            "error": f"API 요청에 실패했습니다: {e}"
        }

    # -----------------------------------------
    # 4. 인증키 오류 등 faultInfo 확인
    # -----------------------------------------
    if "faultInfo" in data:
        fault = data["faultInfo"]

        return {
            "success": False,
            "error": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault.get('faultCode', '확인 불가')}\n"
                f"오류 내용: {fault.get('message', '확인 불가')}"
            )
        }

    # -----------------------------------------
    # 5. 정상적인 박스오피스 데이터 확인
    # -----------------------------------------
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "error": (
                "박스오피스 결과가 없습니다.\n\n"
                "KOBIS API 응답 형식을 확인해 주세요."
            )
        }

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    if not movie_list:
        return {
            "success": False,
            "error": (
                "해당 날짜의 영화 목록이 없습니다.\n\n"
                "조회 날짜에 박스오피스 데이터가 집계되었는지 "
                "또는 KOBIS API가 정상적으로 응답했는지 확인해 주세요."
            )
        }

    return {
        "success": True,
        "data": movie_list
    }


# -----------------------------------------
# 6. API 호출
# -----------------------------------------
result = get_boxoffice(target_dt)


# -----------------------------------------
# 7. API 오류가 발생했을 때 안내
# -----------------------------------------
if not result["success"]:
    st.error("박스오피스 정보를 가져오지 못했습니다.")

    st.warning(
        "다음 내용을 확인해 주세요.\n\n"
        "1. Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지 확인하세요.\n"
        "2. KOBIS 인증키가 정확한지 확인하세요.\n"
        "3. 인터넷 연결 및 KOBIS API 상태를 확인하세요.\n"
        "4. 해당 날짜의 박스오피스 데이터가 존재하는지 확인하세요.\n\n"
        f"상세 내용: {result['error']}"
    )

    st.stop()


# -----------------------------------------
# 8. 데이터를 표 형태로 변환
# -----------------------------------------
movies = result["data"]

df = pd.DataFrame(movies)


# -----------------------------------------
# 9. 숫자로 변환하기
# -----------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달되므로
# 정렬과 그래프에 사용할 수 있도록 숫자로 변환합니다.

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


# -----------------------------------------
# 10. 순위순으로 정렬
# -----------------------------------------
df = df.sort_values("rank")


# -----------------------------------------
# 11. 1위 영화 정보 보여주기
# -----------------------------------------
first_movie = df.iloc[0]

st.subheader("🏆 오늘의 1위")

st.markdown(
    f"## {first_movie['movieNm']}"
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "오늘 관객수",
        f"{first_movie['audiCnt']:,}명"
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_movie['audiAcc']:,}명"
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['scrnCnt']:,}개"
    )


# -----------------------------------------
# 12. 전체 영화 목록을 표로 보여주기
# -----------------------------------------
st.subheader("📋 전체 박스오피스")

# 사용자에게 보여줄 열만 선택합니다.
display_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 열 이름을 한국어로 바꿉니다.
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# -----------------------------------------
# 13. 관객수 상위 5편 막대그래프
# -----------------------------------------
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 영화명을 인덱스로 설정하고 관객수를 그래프로 표시합니다.
chart_data = top5.set_index("movieNm")[["audiCnt"]]

st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수"
)


# -----------------------------------------
# 14. 데이터 출처 안내
# -----------------------------------------
st.divider()

st.caption(
    "데이터 출처: KOBIS 영화관입장권통합전산망 "
    "(Korean Box Office Information System)"
)

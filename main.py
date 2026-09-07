
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================
# 1. 화면 설정
# =========================================
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")


# =========================================
# 2. 한국 시간 기준으로 어제 날짜 계산
# =========================================
# 서버가 한국 시간이 아닐 수도 있기 때문에
# Asia/Seoul을 사용해서 한국 시간을 가져옵니다.

kst = ZoneInfo("Asia/Seoul")

today = datetime.now(kst).date()
yesterday = today - timedelta(days=1)

# KOBIS가 요구하는 날짜 형식
target_dt = yesterday.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} "
    "(한국 시간 기준)"
)


# =========================================
# 3. KOBIS API에서 데이터 가져오기
# =========================================
# 같은 날짜를 다시 조회하면 1시간 동안
# 저장된 결과를 사용합니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
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

        response.raise_for_status()

        data = response.json()

    except Exception as e:

        return {
            "success": False,
            "error": f"API 요청에 실패했습니다.\n{e}"
        }


    # =========================================
    # 4. KOBIS faultInfo 확인
    # =========================================
    # 인증키가 잘못되어도 HTTP 상태코드는 200일 수 있으므로
    # faultInfo가 있는지 반드시 확인합니다.

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


    # =========================================
    # 5. 박스오피스 결과 확인
    # =========================================
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:

        return {
            "success": False,
            "error": (
                "박스오피스 결과가 없습니다.\n\n"
                "KOBIS API 응답을 확인해 주세요."
            )
        }


    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )


    # 영화 목록이 비어 있는 경우
    if not movie_list:

        return {
            "success": False,
            "error": (
                "해당 날짜의 영화 목록이 없습니다.\n\n"
                "해당 날짜에 박스오피스 데이터가 집계되었는지 "
                "확인해 주세요."
            )
        }


    return {
        "success": True,
        "data": movie_list
    }


# =========================================
# 6. API 실행
# =========================================
result = get_boxoffice(target_dt)


# =========================================
# 7. 오류가 발생한 경우
# =========================================
if not result["success"]:

    st.error("❌ 박스오피스 정보를 가져오지 못했습니다.")

    st.warning(
        "다음 내용을 확인해 주세요.\n\n"
        "① Streamlit Cloud의 Secrets에 KOBIS_KEY가 있는지 확인\n\n"
        "② KOBIS 인증키가 정확한지 확인\n\n"
        "③ 인터넷 연결 및 KOBIS API 상태 확인\n\n"
        "④ 해당 날짜의 박스오피스 데이터가 존재하는지 확인\n\n"
        f"상세 오류:\n{result['error']}"
    )

    st.stop()


# =========================================
# 8. 데이터프레임 만들기
# =========================================
df = pd.DataFrame(result["data"])


# =========================================
# 9. 숫자 데이터를 숫자로 변환
# =========================================
# KOBIS API에서는 숫자도 문자열로 보내므로
# 관객수 등을 실제 숫자로 변환합니다.

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
        ).fillna(0)


# =========================================
# 10. ★ 관객수 기준으로 정렬 ★
# =========================================
# 가장 중요한 부분입니다.
#
# audiCnt = 해당 날짜의 관객수
#
# ascending=False는 큰 숫자가 위로 오도록 합니다.
#
# 따라서 관객수가 가장 많은 영화가 첫 번째에 옵니다.

df = df.sort_values(
    by="audiCnt",
    ascending=False
).reset_index(drop=True)


# =========================================
# 11. 관객수 기준으로 새로운 순위 만들기
# =========================================
# 정렬된 순서대로 1위, 2위, 3위...를 부여합니다.

df["new_rank"] = range(1, len(df) + 1)


# =========================================
# 12. 1위 영화
# =========================================
# 정렬된 데이터의 첫 번째 영화가
# 관객수가 가장 많은 영화입니다.

first_movie = df.iloc[0]

st.subheader("🏆 관객수 기준 1위")

st.markdown(
    f"## {first_movie['movieNm']}"
)


# 지표 카드 3개
col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "관객수",
        f"{int(first_movie['audiCnt']):,}명"
    )


with col2:

    st.metric(
        "누적관객",
        f"{int(first_movie['audiAcc']):,}명"
    )


with col3:

    st.metric(
        "스크린수",
        f"{int(first_movie['scrnCnt']):,}개"
    )


# =========================================
# 13. 전체 박스오피스 표
# =========================================
st.subheader("📋 박스오피스")

# 화면에 보여줄 데이터를 새로 만듭니다.
# 여기서 new_rank를 사용하기 때문에
# 표의 순서와 순위가 정확히 일치합니다.

display_df = df[
    [
        "new_rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 열 이름을 한국어로 변경
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자를 보기 편하게 표시
display_df["관객수"] = display_df["관객수"].astype(int)
display_df["누적관객"] = display_df["누적관객"].astype(int)
display_df["스크린수"] = display_df["스크린수"].astype(int)


# -----------------------------------------
# ★ 관객수 내림차순으로 한 번 더 정렬 ★
# -----------------------------------------
# 혹시 모를 정렬 문제를 방지하기 위해
# 표를 만들기 직전에 다시 관객수 기준으로 정렬합니다.

display_df = display_df.sort_values(
    by="관객수",
    ascending=False
).reset_index(drop=True)


# 순위도 다시 1위부터 표시
display_df["순위"] = range(
    1,
    len(display_df) + 1
)


# 표 표시
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# =========================================
# 14. 관객수 상위 5편 그래프
# =========================================
st.subheader("📊 관객수 상위 5편")


# 이미 관객수순으로 정렬되어 있으므로
# 앞에서 5개만 가져옵니다.

top5 = df.head(5).copy()


# 그래프용 데이터
chart_data = top5[
    ["movieNm", "audiCnt"]
].copy()

chart_data = chart_data.set_index("movieNm")


# 막대그래프
st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수"
)


# =========================================
# 15. 데이터 출처
# =========================================
st.divider()

st.caption(
    "데이터 출처: KOBIS 영화관입장권통합전산망 "
    "(Korean Box Office Information System)"
)




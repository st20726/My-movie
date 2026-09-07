
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================
# 1. 화면 설정
# =========================================
st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.write("원하는 날짜를 선택하면 그날의 박스오피스를 보여줍니다.")


# =========================================
# 2. 한국 시간 기준 날짜 계산
# =========================================
# 서버가 한국 시간이 아닐 수도 있기 때문에
# 반드시 한국 시간(Asia/Seoul)을 사용합니다.

kst = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(kst).date()

# 오늘 영화 데이터는 아직 집계 전이므로
# 가장 최근에 선택할 수 있는 날짜는 어제입니다.
yesterday = today_kst - timedelta(days=1)


# =========================================
# 3. 날짜 선택
# =========================================
selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday
)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환
target_dt = selected_date.strftime("%Y%m%d")

st.caption(
    f"선택한 날짜: {selected_date.strftime('%Y년 %m월 %d일')}"
)


# =========================================
# 4. KOBIS API에서 데이터 가져오기
# =========================================
# 같은 날짜를 다시 조회하면 1시간 동안
# 저장해 둔 데이터를 사용합니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    # Streamlit Secrets에서 KOBIS 인증키를 가져옵니다.
    # 실제 인증키는 코드에 적지 않습니다.
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


    # =========================================
    # 5. faultInfo 확인
    # =========================================
    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가
    # 200으로 올 수 있으므로 faultInfo를 확인합니다.

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


    # =========================================
    # 6. 박스오피스 결과 확인
    # =========================================
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


    # 영화 목록이 비어 있으면
    # 선택한 날짜에 아직 집계되지 않은 것으로 안내합니다.
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


# =========================================
# 7. API 실행
# =========================================
result = get_boxoffice(target_dt)


# =========================================
# 8. 오류 처리
# =========================================
if not result["success"]:

    if result["error_type"] == "no_data":

        st.info(
            "📭 그날은 아직 집계 전입니다.\n\n"
            "다른 날짜를 선택해 주세요."
        )

    else:

        st.error("❌ 박스오피스 정보를 가져오지 못했습니다.")

        st.warning(
            "다음 내용을 확인해 주세요.\n\n"
            "① Streamlit Cloud의 Secrets에 KOBIS_KEY가 "
            "등록되어 있는지 확인하세요.\n\n"
            "② KOBIS 인증키가 정확한지 확인하세요.\n\n"
            "③ KOBIS API가 정상적으로 작동하는지 확인하세요.\n\n"
            "④ 선택한 날짜의 박스오피스 데이터가 존재하는지 "
            "확인하세요.\n\n"
            f"상세 내용:\n{result['error']}"
        )

    st.stop()


# =========================================
# 9. 데이터프레임 만들기
# =========================================
df = pd.DataFrame(result["data"])


# =========================================
# 10. 숫자 데이터를 실제 숫자로 변환
# =========================================
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 정렬과 그래프를 위해 숫자로 변환합니다.

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


# =========================================
# 11. 관객수가 많은 순서로 정렬
# =========================================
# KOBIS 원래 순위와 관계없이
# 관객수가 많은 영화부터 보여줍니다.

df = (
    df.sort_values(
        by="audiCnt",
        ascending=False
    )
    .reset_index(drop=True)
)


# =========================================
# 12. 영화명에 트로피 붙이기
# =========================================
# 누적관객이 100만 명을 넘은 영화는
# 영화명 뒤에 🏆를 붙입니다.

def make_movie_name(row):

    movie_name = row["movieNm"]

    if row["audiAcc"] > 1_000_000:
        movie_name += " 🏆"

    return movie_name


df["display_movie_name"] = df.apply(
    make_movie_name,
    axis=1
)


# =========================================
# 13. 순위 변동 표시
# =========================================
# rankInten의 의미
#
# 양수 = 순위 상승
# 음수 = 순위 하락
# 0 = 변동 없음
#
# 상승은 빨간색 계열의 🔴⬆️
# 하락은 파란색 계열의 🔵⬇️로 표시합니다.

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


# =========================================
# 14. 1위 영화
# =========================================
# 현재 데이터는 관객수가 많은 순서로 정렬되어 있으므로
# 첫 번째 영화가 관객수 기준 1위입니다.

first_movie = df.iloc[0]

st.subheader("🏆 관객수 기준 1위")

st.markdown(
    f"## {first_movie['display_movie_name']}"
)


# =========================================
# 15. 1위 영화 지표 카드
# =========================================
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


# =========================================
# 16. 전체 박스오피스 표
# =========================================
st.subheader("📋 박스오피스")


# 화면에 보여줄 열을 선택합니다.
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


# 열 이름을 한국어로 변경합니다.
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 표를 표시합니다.
# 이미 관객수가 많은 순서로 정렬되어 있습니다.

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# =========================================
# 17. 관객수 상위 5편 그래프
# =========================================
st.subheader("📊 관객수 상위 5편")


# 관객수가 많은 영화 5편을 선택합니다.
top5 = (
    df[
        [
            "display_movie_name",
            "audiCnt"
        ]
    ]
    .head(5)
    .copy()
)


# -----------------------------------------
# 중요!
# -----------------------------------------
# 가로 막대그래프에서는 데이터를
# 관객수가 적은 순서로 뒤집어 주면
# 화면에서는 위쪽부터
#
# 1위
# 2위
# 3위
# 4위
# 5위
#
# 순서로 표시됩니다.

top5 = top5.sort_values(
    by="audiCnt",
    ascending=True
)


# 영화명을 인덱스로 설정합니다.
top5 = top5.set_index(
    "display_movie_name"
)


# 가로 막대그래프를 표시합니다.
st.bar_chart(
    top5,
    horizontal=True,
    x="audiCnt",
    x_label="관객수",
    y_label="영화"
)


# =========================================
# 18. 데이터 출처
# =========================================
st.divider()

st.caption(
    "데이터 출처: KOBIS 영화관입장권통합전산망 "
    "(Korean Box Office Information System)"
)


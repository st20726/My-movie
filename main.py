# =========================================
# 14. 관객수 상위 5편 그래프
# =========================================
st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 영화 5편을 가져옵니다.
top5 = (
    df.sort_values(
        by="audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 가로 막대그래프에서
# 관객수가 많은 영화가 위쪽에 오도록
# 데이터를 관객수가 적은 순서로 뒤집습니다.
chart_data = (
    top5[
        ["movieNm", "audiCnt"]
    ]
    .sort_values(
        by="audiCnt",
        ascending=True
    )
    .set_index("movieNm")
)

# 가로 막대그래프를 표시합니다.
st.bar_chart(
    chart_data,
    horizontal=True,
    x="audiCnt",
    y=chart_data.index,
    x_label="관객수",
    y_label="영화"
)

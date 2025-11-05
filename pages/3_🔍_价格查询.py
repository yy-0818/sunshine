import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta
from core.database import get_connection

# ==============================
# ⚙️ 页面配置
# ==============================
st.set_page_config(page_title="价格查询中心", layout="wide")
st.title("🔍 价格查询中心")

# ==============================
# ⏱️ 获取数据库日期范围
# ==============================
def get_date_range():
    with get_connection() as conn:
        res = pd.read_sql_query("""
            SELECT MIN(record_date) AS min_date, MAX(record_date) AS max_date 
            FROM sales_records WHERE record_date IS NOT NULL
        """, conn)
        if not res.empty:
            return pd.to_datetime(res.min_date[0]), pd.to_datetime(res.max_date[0])
    return datetime.now() - timedelta(days=30), datetime.now()
min_date, max_date = get_date_range()

# ==============================
# 📋 最新价格数据（独立表）
# ==============================
with st.container():
    st.markdown("### 📋 最新价格数据")
    st.caption("展示每个客户及产品组合的最新成交价格")

    @st.cache_data(ttl=6000)
    def get_latest_prices():
        with get_connection() as conn:
            df = pd.read_sql_query("""
                WITH Latest AS (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY customer_name, finance_id, sub_customer_name, color, grade
                               ORDER BY record_date DESC
                           ) rn
                    FROM sales_records
                    WHERE unit_price > 0
                )
                SELECT 
                    customer_name AS 客户名称,
                    finance_id AS 财务编号,
                    COALESCE(NULLIF(sub_customer_name, ''), '主客户') AS 子客户,
                    color AS 产品颜色,
                    COALESCE(grade, '无等级') AS 等级,
                    ROUND(unit_price, 2) AS 单价,
                    quantity AS 数量,
                    ROUND(amount, 2) AS 金额,
                    record_date AS 记录日期
                FROM Latest WHERE rn = 1
                ORDER BY customer_name, color;
            """, conn)
            for c in ['单价', '数量', '金额']:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).round(2)
            return df

    latest_df = get_latest_prices()

    st.dataframe(latest_df, width="stretch", height=500, column_config={
        # "客户名称": {"width": 1},
        "财务编号": {"width": 1},
        "数量": {"width": 1},
        "等级": {"width": 1},
        "记录日期": {"width": 1},
        '单价':st.column_config.NumberColumn(format="￥ %2f",width=1),
        '金额':st.column_config.NumberColumn(format="￥ %2f",width=1),
    })
    csv_latest = latest_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📥 导出最新价格数据 (CSV)", csv_latest, "最新价格数据.csv", "text/csv", width="stretch")

# ==============================
# 🎛️ 高级查询模块
# ==============================
st.markdown("----")
st.markdown("### 🎛️ 高级数据查询")
st.caption("在此根据客户、产品、时间范围等条件筛选所有历史销售记录。")

# ---- 查询条件卡 ----
with st.container():
    # 第一行：客户、颜色、等级、时间段
    col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])
    with col1:
        customer_filter = st.text_input("客户名称", placeholder="支持模糊匹配")
    with col2:
        color_filter = st.text_input("产品颜色", placeholder="支持模糊匹配")
    with col3:
        grade_filter = st.selectbox("产品等级", ["全部", "优", "壹", "(空)"])
    with col4:
        quick_select = st.selectbox("时间范围", ["最近30天", "最近90天", "全部时间", "自定义"])

    # 时间筛选
    if quick_select == "自定义":
        col5, col6 = st.columns(2)
        with col5:
            start_date = st.date_input("开始日期", min_date, min_value=min_date, max_value=max_date)
        with col6:
            end_date = st.date_input("结束日期", max_date, min_value=min_date, max_value=max_date)
    else:
        end_date = datetime.now().date()
        if quick_select == "最近30天":
            start_date = end_date - timedelta(days=30)
        elif quick_select == "最近90天":
            start_date = end_date - timedelta(days=90)
        elif quick_select == "全部时间":
            start_date, end_date = min_date.date(), max_date.date()

# ==============================
# 🧩 查询逻辑
# ==============================
@st.cache_data(ttl=6000)
def query_sales_records(customer=None, color=None, grade=None, start=None, end=None):
    query = """
        SELECT 
            customer_name AS 客户名称,
            finance_id AS 财务编号,
            COALESCE(NULLIF(sub_customer_name,''),'主客户') AS 子客户,
            color AS 产品颜色,
            COALESCE(grade,'无等级') AS 等级,
            quantity AS 数量,
            ROUND(unit_price, 2) AS 单价,
            ROUND(amount, 2) AS 金额,
            record_date AS 记录日期
        FROM sales_records
        WHERE unit_price > 0
    """
    params, conditions = [], []
    if customer:
        conditions.append("(customer_name LIKE ? OR sub_customer_name LIKE ?)")
        params.extend([f'%{customer}%', f'%{customer}%'])
    if color:
        conditions.append("color LIKE ?")
        params.append(f'%{color}%')
    if grade and grade != "全部":
        if grade == "(空)":
            conditions.append("(grade IS NULL OR grade = '')")
        else:
            conditions.append("grade = ?")
            params.append(grade)
    if start and end:
        conditions.append("record_date BETWEEN ? AND ?")
        params.extend([str(start), str(end)])
    if conditions:
        query += " AND " + " AND ".join(conditions)
    query += " ORDER BY record_date DESC"

    with get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
        for c in ['数量', '单价', '金额']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).round(2)
        return df

# ==============================
# 🔍 查询执行（自动加载）
# ==============================
df = query_sales_records(customer_filter, color_filter, grade_filter, start_date, end_date)
st.markdown(f"#### 📋 查询结果（共 {len(df):,} 条记录）")

# ==============================
# 🔎 搜索 + 分页美化
# ==============================
search_term = st.text_input("🔎 快速搜索（输入关键词过滤结果）", placeholder="输入客户、颜色、等级等进行模糊筛选")

if search_term:
    df_filtered = df[df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]
else:
    df_filtered = df

page_size = 100
total_pages = max(1, math.ceil(len(df_filtered) / page_size))
page = st.session_state.get("page", 1)
page = min(page, total_pages)

start_idx = (page - 1) * page_size
end_idx = start_idx + page_size
page_data = df_filtered.iloc[start_idx:end_idx]

if page_data.empty:
    st.warning("⚠️ 当前条件下无匹配数据。")
else:
    st.dataframe(page_data, height=500,column_config={
        "财务编号": {"width": 1},
        "等级": {"width": 1},
        # '颜色':st.column_config.Column(width=1),
        "数量": {"width": 1},
        '单价':st.column_config.NumberColumn(format="￥ %2f",width=1),
        '金额':st.column_config.NumberColumn(format="￥ %2f",width=1)
        }  
    )

# 页码控制栏（底部右侧）
col_left, col_right = st.columns([4, .5])
with col_left:
    st.caption(f"第 {page} / {total_pages} 页")

with col_right:
    new_page = st.number_input("页码跳转", min_value=1, max_value=total_pages, value=page, step=1, label_visibility="collapsed")
    if new_page != page:
        st.session_state["page"] = new_page
        st.rerun()

# ==============================
# 📊 汇总与导出
# ==============================
st.markdown("#### 📊 汇总指标")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("平均单价", f"¥{df_filtered['单价'].mean():.2f}" if not df_filtered.empty else "¥0.00")
with col2:
    st.metric("总金额", f"¥{df_filtered['金额'].sum():,.2f}" if not df_filtered.empty else "¥0.00")
with col3:
    st.metric("总数量", f"{df_filtered['数量'].sum():,.0f}" if not df_filtered.empty else "0")
with col4:
    st.metric("客户数量", df_filtered['客户名称'].nunique() if not df_filtered.empty else "0")

if not df_filtered.empty:
    export_df = df_filtered.copy()
    for col in ['单价', '金额']:
        export_df[col] = export_df[col].apply(lambda x: f"{x:.2f}")
    csv_filtered = export_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📥 导出筛选结果 (CSV)", csv_filtered, "销售记录查询结果.csv", "text/csv", width="stretch")

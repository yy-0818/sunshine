import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta
from core.database import get_connection

# ==============================
# ⚙️ 页面配置
# ==============================
st.logo(
    image='https://doc-logo.streamlit.app/~/+/media/5bbeb2aa8dae615df2081a396b47e30bb710e10dd2f4f3f2e7b06c81.png',
    icon_image='https://doc-logo.streamlit.app/~/+/media/5bbeb2aa8dae615df2081a396b47e30bb710e10dd2f4f3f2e7b06c81.png',
)

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
                    product_name AS 产品名称,
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

    st.dataframe(latest_df, width="stretch", height=550, column_config={
        "财务编号": {"width": 'small'},
        "颜色": {"width": 'small'},
        "数量": {"width": 'small'},
        "等级": {"width": 'small'},
        "记录日期": {"width": 'small'},
        '单价':st.column_config.NumberColumn(format="¥%2f",width='samll'),
        '金额':st.column_config.NumberColumn(format="¥%2f",width='small'),
    })
    st.markdown(f"#### （共 {len(latest_df):,} 条记录）")
    csv_latest = latest_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📥 导出最新价格数据 (CSV)", csv_latest, "最新价格数据.csv", "text/csv", width="stretch")

# ==============================
# 🎛️ 高级查询模块
# ==============================
st.markdown("----")
st.markdown("### 🎛️ 高级数据查询")
st.caption("在此根据客户、产品、时间范围等条件筛选所有历史销售记录。")

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
            product_name AS 产品名称,
            color AS 产品颜色,
            COALESCE(NULLIF(grade,''), '(空)') AS 等级,
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
        placeholders = ','.join(['?'] * len(color))
        conditions.append(f"color IN ({placeholders})")
        params.extend(color)

    if grade:
        grade_conditions = []
        grade_params = []
        for g in grade:
            if g == '(空)':
                grade_conditions.append("(grade IS NULL OR grade = '')")
            else:
                grade_conditions.append("grade = ?")
                grade_params.append(g)
        
        if grade_conditions:
            conditions.append("(" + " OR ".join(grade_conditions) + ")")
            params.extend(grade_params)

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

def get_unique_colors():
    """获取所有唯一的颜色选项"""
    query = "SELECT DISTINCT color FROM sales_records WHERE color IS NOT NULL AND color != '' ORDER BY color"
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)
        return df['color'].tolist()

def get_unique_grades():
    """获取所有唯一的产品等级选项"""
    query = """
        SELECT DISTINCT 
            CASE 
                WHEN grade IS NULL OR grade = '' THEN '(空)'
                ELSE grade 
            END as grade_display
        FROM sales_records 
        ORDER BY grade_display
    """
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)
        return df['grade_display'].tolist() 
    
# ---- 查询条件卡 ----
with st.container():
    # 第一行：客户、颜色、等级、时间段
    col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])
    with col1:
        customer_filter = st.text_input("客户名称", placeholder="支持模糊匹配")
    with col2:
        # 获取所有颜色选项
        color_options = get_unique_colors()
        color_filter = st.multiselect(
            "产品颜色",
            options=color_options,
            placeholder="选择颜色（可多选）"
        )
    with col3:
        # 获取所有等级选项
        grade_options = get_unique_grades()
        grade_filter = st.multiselect(
            "产品等级",
            options=grade_options,
            placeholder="选择等级（可多选）"
        )
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
# 🔍 查询执行（自动加载）
# ==============================
df = query_sales_records(
    customer=customer_filter if customer_filter else None,
    color=color_filter if color_filter else None,
    grade=grade_filter if grade_filter else None,
    start=start_date,
    end=end_date
)
# 显示查询结果统计
if color_filter:
    color_text = "、".join(color_filter)
else:
    color_text = "全部颜色"

if grade_filter:
    grade_text = "、".join(grade_filter)
else:
    grade_text = "全部等级"
st.markdown(f"#### 📋 查询结果（共 {len(df):,} 条记录）")

# ==============================
# 🔎 搜索 + 分页美化
# ==============================
search_term = st.text_input("🔎 快速搜索（输入关键词过滤结果）", placeholder="输入客户、产品名称、颜色等进行模糊筛选")

if search_term:
    df_filtered = df[df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]
else:
    df_filtered = df

# 分页控制
page_size = 100
total_pages = max(1, math.ceil(len(df_filtered) / page_size))
# 初始化页码
if "page" not in st.session_state:
    st.session_state.page = 1
# 确保页码在有效范围内
page = min(st.session_state.page, total_pages)
if page < 1:
    page = 1

start_idx = (page - 1) * page_size
end_idx = start_idx + page_size
page_data = df_filtered.iloc[start_idx:end_idx]

if page_data.empty:
    st.warning("⚠️ 当前条件下无匹配数据。")
else:
    st.dataframe(page_data, height='auto', column_config={
        "财务编号": {"width": 'small'},
        "等级": {"width": 'small'},
        '颜色':{"width": 'small'},
        "数量": {"width": 'small'},
        '单价':st.column_config.NumberColumn(format="¥%.2f",width='small'),
        '金额':st.column_config.NumberColumn(format="¥%.2f",width='small')
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

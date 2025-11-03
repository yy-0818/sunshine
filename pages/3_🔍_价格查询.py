import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.database import get_connection

# ==============================
# ⚙️ 页面配置
# ==============================
st.set_page_config(page_title="价格查询中心", layout="wide")
st.title("🔍 价格查询中心")

# ==============================
# 🎨 自定义样式
# ==============================
st.markdown("""
<style>
.metric-card {
    background-color: #f9fafb;
    padding: 1rem;
    border-radius: 12px;
    border-left: 5px solid #3b82f6;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    margin-bottom: 1rem;
}
.filter-box {
    background-color: #f0f4f8;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 1.5rem;
}
</style>
""", unsafe_allow_html=True)

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
# 📋 最新价格数据
# ==============================
st.subheader("📋 最新价格数据")

@st.cache_data(ttl=600)
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
            SELECT customer_name AS 客户名称,
                   finance_id AS 财务编号,
                   COALESCE(NULLIF(sub_customer_name, ''), '主客户') AS 子客户,
                   color AS 产品颜色,
                   COALESCE(grade, '无等级') AS 等级,
                   unit_price AS 单价,
                   quantity AS 数量,
                   amount AS 金额,
                   record_date AS 记录日期
            FROM Latest WHERE rn = 1
            ORDER BY customer_name, color;
        """, conn)
        for c in ['单价', '数量', '金额']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).round(2)
        return df
latest_df = get_latest_prices()
if not latest_df.empty:
    st.dataframe(latest_df, use_container_width=True, height=350)
    csv = latest_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 导出最新价格数据", csv, "latest_prices.csv", "text/csv", use_container_width=True)
else:
    st.info("暂无最新价格数据")

# ==============================
# 🎛️ 高级查询模块
# ==============================
# st.markdown("---")
st.markdown('<div class="filter-box">', unsafe_allow_html=True)

st.subheader("🎛️ 高级查询")

# ---- 筛选面板 ----
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        customer_filter = st.text_input("客户名称", placeholder="输入客户名称关键词")
    with col2:
        color_filter = st.text_input("产品颜色", placeholder="输入产品颜色关键词")
    with col3:
        grade_filter = st.selectbox("产品等级", ["全部", "优", "壹", "(空)"])
    with col4:
        quick_select = st.selectbox("时间范围", ["最近30天", "最近90天", "全部时间", "自定义"])
    
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
st.markdown('</div>', unsafe_allow_html=True)

# ==============================
# 🧩 查询逻辑（默认加载所有数据）
# ==============================
@st.cache_data(ttl=600)
def query_sales_records(customer=None, color=None, grade=None, start=None, end=None):
    query = """
        SELECT 
            customer_name AS 客户名称,
            finance_id AS 财务编号,
            COALESCE(NULLIF(sub_customer_name,''),'主客户') AS 子客户,
            color AS 产品颜色,
            COALESCE(grade,'无等级') AS 等级,
            quantity AS 数量,
            unit_price AS 单价,
            amount AS 金额,
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
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df

# ==============================
# 🔍 执行查询（默认加载）
# ==============================
try:
    df = query_sales_records(customer_filter, color_filter, grade_filter, start_date, end_date)

    if df.empty:
        st.warning("⚠️ 当前筛选条件无匹配结果，显示空表结构")
        empty_columns = ['客户名称', '财务编号', '子客户', '产品颜色', '等级', '数量', '单价', '金额', '记录日期']
        df = pd.DataFrame(columns=empty_columns)

    st.subheader(f"📋 查询结果（共 {len(df):,} 条记录）")
    st.dataframe(df, use_container_width=True, height=450)

    # 汇总统计
    st.markdown("#### 📊 查询汇总指标")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("平均单价", f"¥{df['单价'].mean():.2f}" if not df.empty else "¥0.00")
    with col2:
        st.metric("总金额", f"¥{df['金额'].sum():,.0f}" if not df.empty else "¥0")
    with col3:
        st.metric("总数量", f"{df['数量'].sum():,.0f}" if not df.empty else "0")
    with col4:
        st.metric("客户数量", df['客户名称'].nunique() if not df.empty else "0")

    # 导出按钮
    csv_filtered = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 导出查询结果", csv_filtered, "filtered_sales_records.csv", "text/csv", use_container_width=True)
except Exception as e:
    st.error(f"❌ 查询出错: {e}")

# ==============================
# 📘 使用说明
# ==============================
with st.expander("📘 使用说明", expanded=False):
    st.markdown("""
    ### 页面说明
    - **最新价格数据**：展示每个客户与产品的最新价格，独立存在，不受筛选影响。
    - **高级查询**：默认展示所有销售记录，可通过客户、颜色、等级和时间范围进行筛选。
    - **等级选项**：仅支持“优”、“壹”、“(空)” 三类或全部。
    - **查询结果**：若无数据，将显示空表结构而非报错。
    
    ### 使用建议
    - 若要查看最新行情，请关注上方独立表；
    - 若要分析历史销售记录，请在筛选区选择客户或时间范围；
    - 导出数据支持 Excel、BI 报表分析。
    """)

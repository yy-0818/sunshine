import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta
from core.database import get_connection

# ==============================
# ⚙️ 页面配置
# ==============================
st.set_page_config(page_title="价格查询中心", layout="wide")
st.logo(image='./assets/logo.png', icon_image='./assets/logo.png')
st.title("🔍 价格查询中心")

# ==============================
# ⚙️ 全局常量与缓存配置
# ==============================
PAGE_SIZE = 100
CACHE_TTL = 600  # 缓存时间（秒）

# ==============================
# 🔧 工具函数
# ==============================
def format_numeric_columns(df, cols):
    """统一格式化数值列"""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
    return df


# ==============================
# 📊 数据查询函数
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def get_date_range():
    with get_connection() as conn:
        res = pd.read_sql_query(
            "SELECT MIN(record_date) AS min_date, MAX(record_date) AS max_date FROM sales_records WHERE record_date IS NOT NULL",
            conn
        )
        if not res.empty and res.min_date[0] and res.max_date[0]:
            return pd.to_datetime(res.min_date[0]), pd.to_datetime(res.max_date[0])
    return datetime.now() - timedelta(days=30), datetime.now()


@st.cache_data(ttl=CACHE_TTL)
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
            )
            SELECT 
                customer_name AS 客户名称,
                finance_id AS 财务编号,
                COALESCE(NULLIF(sub_customer_name, ''), '主客户') AS 子客户,
                product_name AS 产品名称,
                color AS 产品颜色,
                COALESCE(NULLIF(grade, ''), '无等级') AS 等级,
                quantity AS 数量,
                ROUND(unit_price, 2) AS 单价,
                ROUND(amount, 2) AS 金额,
                COALESCE(NULLIF(ticket_number, ''), '无票号') AS 票据号,
                COALESCE(NULLIF(remark, ''), '无备注') AS 备注,
                production_line AS 生产线,
                record_date AS 记录日期
            FROM Latest WHERE rn = 1
            ORDER BY customer_name, color, record_date DESC
        """, conn)
        return format_numeric_columns(df, ['数量', '单价', '金额'])


@st.cache_data(ttl=CACHE_TTL)
def get_unique_values(column):
    query = f"""
        SELECT DISTINCT 
            CASE WHEN {column} IS NULL OR {column} = '' THEN '(空)' ELSE {column} END AS val
        FROM sales_records ORDER BY val
    """
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)
    return df['val'].tolist()


@st.cache_data(ttl=CACHE_TTL)
def query_sales_records(filters):
    """根据筛选条件查询完整数据"""
    query = """
        SELECT 
            customer_name AS 客户名称,
            finance_id AS 财务编号,
            COALESCE(NULLIF(sub_customer_name,''), '主客户') AS 子客户,
            product_name AS 产品名称,
            color AS 产品颜色,
            COALESCE(NULLIF(grade,''), '(空)') AS 等级,
            quantity AS 数量,
            ROUND(unit_price, 2) AS 单价,
            ROUND(amount, 2) AS 金额,
            COALESCE(NULLIF(ticket_number,''), '无票号') AS 票据号,
            COALESCE(NULLIF(remark,''), '无备注') AS 备注,
            COALESCE(NULLIF(production_line,''), '(空)') AS 生产线,
            record_date AS 记录日期
        FROM sales_records
        WHERE 1=1
    """
    params, conditions = [], []

    if filters['customer']:
        conditions.append("(customer_name LIKE ? OR sub_customer_name LIKE ? OR product_name LIKE ?)")
        params += [f"%{filters['customer']}%"] * 3

    if filters['colors']:
        placeholders = ','.join(['?'] * len(filters['colors']))
        conditions.append(f"color IN ({placeholders})")
        params += filters['colors']

    if filters['grades']:
        grade_conds = []
        for g in filters['grades']:
            if g == '(空)':
                grade_conds.append("(grade IS NULL OR grade='')")
            else:
                grade_conds.append("grade=?")
                params.append(g)
        conditions.append("(" + " OR ".join(grade_conds) + ")")

    if filters['production_lines']:
        line_conds = []
        for l in filters['production_lines']:
            if l == '(空)':
                line_conds.append("(production_line IS NULL OR production_line='')")
            else:
                line_conds.append("production_line=?")
                params.append(l)
        conditions.append("(" + " OR ".join(line_conds) + ")")

    if filters['start_date'] and filters['end_date']:
        conditions.append("record_date BETWEEN ? AND ?")
        params += [filters['start_date'].strftime('%Y-%m-%d'), filters['end_date'].strftime('%Y-%m-%d')]

    if conditions:
        query += " AND " + " AND ".join(conditions)
    query += " ORDER BY record_date DESC, customer_name, color"

    with get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
        return format_numeric_columns(df, ['数量', '单价', '金额'])


# ==============================
# 🎛️ UI 部分
# ==============================
def render_filters():
    """筛选区"""
    with st.expander("🎛️ 高级筛选条件", expanded=False):
        color_opts = get_unique_values("color")
        grade_opts = get_unique_values("grade")
        line_opts = get_unique_values("production_line")
        min_date, max_date = get_date_range()

        col1, col2, col3 = st.columns([2, 2, 1.5])
        with col1:
            customer = st.text_input("客户/产品名称", placeholder="支持模糊匹配")
        with col2:
            colors = st.multiselect("产品颜色", color_opts, placeholder="支持颜色多选")
        with col3:
            grades = st.multiselect("产品等级", grade_opts, placeholder="支持等级多选")

        col4, col5 = st.columns([2, 1])
        with col4:
            lines = st.multiselect("生产线", line_opts, placeholder="支持生产线多选")
        with col5:
            range_choice = st.selectbox(
                "时间范围",
                ["最近30天", "最近90天", "最近半年", "全部时间", "自定义"],
            )

        start_date, end_date = min_date.date(), max_date.date()
        if range_choice == "自定义":
            start_date = st.date_input("开始日期", min_value=min_date.date(), max_value=max_date.date())
            end_date = st.date_input("结束日期", min_value=min_date.date(), max_value=max_date.date())
        elif range_choice == "最近30天":
            start_date = (datetime.now() - timedelta(days=30)).date()
        elif range_choice == "最近90天":
            start_date = (datetime.now() - timedelta(days=90)).date()
        elif range_choice == "最近半年":
            start_date = (datetime.now() - timedelta(days=180)).date()

        return dict(
            customer=customer.strip() if customer else None,
            colors=colors or None,
            grades=grades or None,
            production_lines=lines or None,
            start_date=start_date,
            end_date=end_date
        )


def render_pagination_controls(current_page, total_pages, total_records):
    """分页样式"""
    col1, col2 = st.columns([2.5, 0.3])
    with col1:
        st.caption(f"第 {current_page} / {total_pages} 页，共 {total_records:,} 条记录")
    with col2:
        new_page = st.number_input(
            "页码",
            min_value=1,
            max_value=total_pages,
            value=current_page,
            step=1,
            label_visibility="collapsed"
        )
        if new_page != current_page:
            st.session_state.current_page = new_page
            st.rerun()


def render_results(df):
    """结果展示与分页"""
    if df.empty:
        st.info("📭 未找到匹配记录")
        return

    search_term = st.text_input("🔍 快速搜索", placeholder="输入客户、颜色、备注等关键字筛选")
    if search_term:
        df = df[df.apply(lambda r: search_term.lower() in ' '.join(r.astype(str).values).lower(), axis=1)]

    total_pages = max(1, math.ceil(len(df) / PAGE_SIZE))
    current_page = st.session_state.get("current_page", 1)
    current_page = max(1, min(current_page, total_pages))

    start_idx, end_idx = (current_page - 1) * PAGE_SIZE, current_page * PAGE_SIZE
    page_data = df.iloc[start_idx:end_idx]

    st.markdown(f"#### 📋 查询结果（共 {len(df):,} 条记录）")
    st.dataframe(page_data, width='stretch')

    render_pagination_controls(current_page, total_pages, len(df))

    csv_data = df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📥 导出查询结果", csv_data, "销售记录查询结果.csv", "text/csv", width='stretch')


# ==============================
# 🚀 主程序
# ==============================
def main():
    st.subheader("📋 最新价格数据")
    latest_df = get_latest_prices()
    st.dataframe(latest_df, width='stretch')

    # 统计和导出 
    col1, col2 = st.columns([4, .75]) 
    with col1: 
        st.caption(f"共 {len(latest_df):,} 条记录")

    with col2: 
        csv_data = latest_df.to_csv(index=False, encoding='utf-8-sig') 
        st.download_button( "📥 导出最新价格数据", csv_data, "最新价格数据.csv", "text/csv", width='stretch')

    st.divider()

    filters = render_filters()
    df = query_sales_records(filters)
    render_results(df)


if __name__ == "__main__":
    main()

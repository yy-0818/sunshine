import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta
from core.database import get_connection

# ==============================
# ⚙️ 页面配置
# ==============================
st.logo(image='./assets/logo.png', icon_image='./assets/logo.png')
st.set_page_config(page_title="价格查询中心", layout="wide")
st.title("🔍 价格查询中心")

# ==============================
# 🔧 配置常量
# ==============================
PAGE_SIZE = 100
CACHE_TTL = 600  # 缓存时间（秒）

# ==============================
# 📊 数据获取函数
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def get_date_range():
    """获取数据库中的日期范围"""
    with get_connection() as conn:
        res = pd.read_sql_query("""
            SELECT MIN(record_date) AS min_date, MAX(record_date) AS max_date 
            FROM sales_records WHERE record_date IS NOT NULL
        """, conn)
        if not res.empty and res.min_date[0] and res.max_date[0]:
            return pd.to_datetime(res.min_date[0]), pd.to_datetime(res.max_date[0])
    return datetime.now() - timedelta(days=30), datetime.now()

@st.cache_data(ttl=CACHE_TTL)
def get_latest_prices():
    """获取最新价格数据"""
    with get_connection() as conn:
        df = pd.read_sql_query("""
            WITH Latest AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY customer_name, finance_id, sub_customer_name, color, grade
                           ORDER BY record_date DESC
                       ) rn
                FROM sales_records
                WHERE unit_price > 0 AND quantity > 0
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
                record_date AS 记录日期
            FROM Latest 
            WHERE rn = 1
            ORDER BY customer_name, color, record_date DESC
        """, conn)
        
        # 数值列处理
        numeric_columns = ['数量', '单价', '金额']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
        return df

@st.cache_data(ttl=CACHE_TTL)
def get_unique_colors():
    """获取所有唯一的颜色选项"""
    query = """
        SELECT DISTINCT color 
        FROM sales_records 
        WHERE color IS NOT NULL AND color != '' 
        ORDER BY color
    """
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)
        return df['color'].tolist()

@st.cache_data(ttl=CACHE_TTL)
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

@st.cache_data(ttl=CACHE_TTL)
def query_sales_records(customer=None, colors=None, grades=None, start_date=None, end_date=None):
    """查询销售记录"""
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
            record_date AS 记录日期
        FROM sales_records
        WHERE unit_price > 0 AND quantity > 0
    """
    
    params = []
    conditions = []
    
    # 客户名称筛选
    if customer and customer.strip():
        conditions.append("(customer_name LIKE ? OR sub_customer_name LIKE ?)")
        params.extend([f'%{customer.strip()}%', f'%{customer.strip()}%'])
    
    # 颜色筛选
    if colors:
        placeholders = ','.join(['?'] * len(colors))
        conditions.append(f"color IN ({placeholders})")
        params.extend(colors)
    
    # 等级筛选
    if grades:
        grade_conditions = []
        grade_params = []
        for grade in grades:
            if grade == '(空)':
                grade_conditions.append("(grade IS NULL OR grade = '')")
            else:
                grade_conditions.append("grade = ?")
                grade_params.append(grade)
        
        if grade_conditions:
            conditions.append("(" + " OR ".join(grade_conditions) + ")")
            params.extend(grade_params)
    
    # 日期筛选
    if start_date and end_date:
        conditions.append("record_date BETWEEN ? AND ?")
        params.extend([start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')])
    
    # 构建完整查询
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    query += " ORDER BY record_date DESC, customer_name, color"
    
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
        
        # 数值列处理
        numeric_columns = ['数量', '单价', '金额']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
        
        return df

# ==============================
# 🎛️ 界面组件函数
# ==============================
def render_latest_prices_section():
    """渲染最新价格数据部分"""
    st.markdown("### 📋 最新价格数据")
    st.caption("展示每个客户及产品组合的最新成交价格")
    
    latest_df = get_latest_prices()
    
    if latest_df.empty:
        st.info("暂无价格数据")
        return
    
    # 显示数据表格
    st.dataframe(
        latest_df, 
        use_container_width=True, 
        height=400,
        column_config={
            "财务编号": st.column_config.TextColumn(width="small"),
            "产品颜色": st.column_config.TextColumn(width="small"),
            "数量": st.column_config.NumberColumn(width="small"),
            "等级": st.column_config.TextColumn(width="small"),
            "记录日期": st.column_config.DateColumn(width="small"),
            "单价": st.column_config.NumberColumn(format="¥%.2f", width="small"),
            "金额": st.column_config.NumberColumn(format="¥%.2f", width="small"),
        }
    )
    
    # 统计和导出
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**共 {len(latest_df):,} 条记录**")
    with col2:
        csv_data = latest_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 导出最新价格数据",
            csv_data,
            "最新价格数据.csv",
            "text/csv",
            use_container_width=True
        )

def render_query_filters():
    """渲染查询筛选条件"""
    st.markdown("### 🎛️ 高级数据查询")
    st.caption("根据客户、产品、时间范围等条件筛选历史销售记录")
    
    # 获取筛选选项
    color_options = get_unique_colors()
    grade_options = get_unique_grades()
    min_date, max_date = get_date_range()
    
    # 筛选条件布局
    col1, col2, col3, col4 = st.columns([2, 2, 1.5, 1.5])
    
    with col1:
        customer_filter = st.text_input(
            "客户名称", 
            placeholder="输入客户名称（支持模糊匹配）",
            help="可以输入客户名称或子客户名称进行搜索"
        )
    
    with col2:
        color_filter = st.multiselect(
            "产品颜色",
            options=color_options,
            placeholder="选择颜色（可多选）",
            help="可多选，不选表示所有颜色"
        )
    
    with col3:
        grade_filter = st.multiselect(
            "产品等级", 
            options=grade_options,
            placeholder="选择等级（可多选）",
            help="可多选，不选表示所有等级"
        )
    
    with col4:
        time_range = st.selectbox(
            "时间范围",
            options=["最近30天", "最近90天", "最近半年", "全部时间", "自定义"],
            help="选择查询的时间范围"
        )
    
    # 日期选择
    start_date, end_date = min_date.date(), max_date.date()
    
    if time_range == "自定义":
        col5, col6 = st.columns(2)
        with col5:
            start_date = st.date_input(
                "开始日期", 
                min_date.date(), 
                min_value=min_date.date(), 
                max_value=max_date.date()
            )
        with col6:
            end_date = st.date_input(
                "结束日期", 
                max_date.date(), 
                min_value=min_date.date(), 
                max_value=max_date.date()
            )
    elif time_range == "最近30天":
        start_date = (datetime.now() - timedelta(days=30)).date()
    elif time_range == "最近90天":
        start_date = (datetime.now() - timedelta(days=90)).date()
    elif time_range == "最近半年":
        start_date = (datetime.now() - timedelta(days=180)).date()
    
    return {
        'customer': customer_filter.strip() if customer_filter else None,
        'colors': color_filter if color_filter else None,
        'grades': grade_filter if grade_filter else None,
        'start_date': start_date,
        'end_date': end_date
    }

def render_query_results(df):
    """渲染查询结果"""
    if df.empty:
        st.info("📭 未找到匹配的销售记录")
        return
    
    # 搜索过滤
    search_term = st.text_input(
        "🔍 快速搜索", 
        placeholder="输入关键词过滤结果（客户、产品、颜色等）",
        help="在所有列中进行模糊搜索"
    )
    
    if search_term:
        df_filtered = df[df.astype(str).apply(
            lambda row: row.str.contains(search_term, case=False, na=False).any(), 
            axis=1
        )]
    else:
        df_filtered = df
    
    # 分页控制
    total_pages = max(1, math.ceil(len(df_filtered) / PAGE_SIZE))
    
    # 初始化页码
    if "current_page" not in st.session_state:
        st.session_state.current_page = 1
    
    # 确保页码有效
    current_page = min(st.session_state.current_page, total_pages)
    if current_page < 1:
        current_page = 1
    
    # 分页数据
    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_data = df_filtered.iloc[start_idx:end_idx]
    
    # 显示结果统计
    st.markdown(f"#### 📋 查询结果（共 {len(df_filtered):,} 条记录）")
    
    if page_data.empty:
        st.warning("当前页面无数据")
    else:
        # 显示数据表格
        st.dataframe(
            page_data,
            use_container_width=True,
            height=400,
            column_config={
                "财务编号": st.column_config.TextColumn(width="small"),
                "产品颜色": st.column_config.TextColumn(width="small"),
                "数量": st.column_config.NumberColumn(width="small"),
                "等级": st.column_config.TextColumn(width="small"),
                "记录日期": st.column_config.DateColumn(width="small"),
                "单价": st.column_config.NumberColumn(format="¥%.2f", width="small"),
                "金额": st.column_config.NumberColumn(format="¥%.2f", width="small"),
            }
        )
    
    # 分页控制器
    render_pagination_controls(current_page, total_pages, len(df_filtered))
    
    # 汇总统计
    render_summary_stats(df_filtered)
    
    # 导出功能
    if not df_filtered.empty:
        csv_data = df_filtered.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 导出筛选结果",
            csv_data,
            "销售记录查询结果.csv",
            "text/csv",
            use_container_width=True
        )

def render_pagination_controls(current_page, total_pages, total_records):
    """渲染分页控制器"""
    col1, col2 = st.columns([2, .5])
    
    with col1:
        st.caption(f"第 {current_page} / {total_pages} 页，共 {total_records:,} 条记录")
    
    with col2:
        # 页码跳转
        new_page = st.number_input(
            "跳转到",
            min_value=1,
            max_value=total_pages,
            value=current_page,
            step=1,
            label_visibility="collapsed"
        )
        if new_page != current_page:
            st.session_state.current_page = new_page
            st.rerun()

def render_summary_stats(df):
    """渲染汇总统计"""
    if df.empty:
        return
    
    st.markdown("#### 📊 汇总指标")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_price = df['单价'].mean()
        st.metric("平均单价", f"¥{avg_price:.2f}" if not pd.isna(avg_price) else "¥0.00")
    
    with col2:
        total_amount = df['金额'].sum()
        st.metric("总金额", f"¥{total_amount:,.2f}" if total_amount > 0 else "¥0.00")
    
    with col3:
        total_quantity = df['数量'].sum()
        st.metric("总数量", f"{total_quantity:,.0f}" if total_quantity > 0 else "0")
    
    with col4:
        unique_customers = df['客户名称'].nunique()
        st.metric("客户数量", f"{unique_customers}")

# ==============================
# 🚀 主程序
# ==============================
def main():
    # 最新价格数据部分
    render_latest_prices_section()
    
    st.markdown("---")
    
    # 高级查询部分
    filters = render_query_filters()
    
    # 执行查询（自动）
    df = query_sales_records(
        customer=filters['customer'],
        colors=filters['colors'], 
        grades=filters['grades'],
        start_date=filters['start_date'],
        end_date=filters['end_date']
    )
    
    # 显示查询结果
    render_query_results(df)

if __name__ == "__main__":
    main()
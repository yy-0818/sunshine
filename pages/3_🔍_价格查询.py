import streamlit as st
import pandas as pd
from core.analysis_service import AnalysisService
from core.database import get_connection

st.set_page_config(page_title="价格查询", layout="wide")
st.title("🔍 价格查询")

analysis_service = AnalysisService()

# 默认展示所有去重后的最新数据
st.subheader("📊 所有客户最新价格数据")

# 获取所有最新价格数据
@st.cache_data(ttl=300)  # 缓存5分钟
def get_all_latest_prices():
    """获取所有客户的最新价格数据"""
    with get_connection() as conn:
        query = '''
            WITH LatestSales AS (
                SELECT 
                    customer_name,
                    finance_id,
                    sub_customer_name,
                    color,
                    grade,
                    unit_price,
                    quantity,
                    amount,
                    record_date,
                    ROW_NUMBER() OVER (
                        PARTITION BY customer_name, finance_id, sub_customer_name, color, grade 
                        ORDER BY record_date DESC
                    ) as rn
                FROM sales_records
                WHERE unit_price > 0
            )
            SELECT 
                customer_name as 客户名称,
                finance_id as 编号,
                COALESCE(NULLIF(sub_customer_name, ''), '主客户') as 子客户,
                color as 产品颜色,
                grade as 等级,
                unit_price as 单价,
                quantity as 数量,
                amount as 金额,
                record_date as 记录日期
            FROM LatestSales
            WHERE rn = 1
            ORDER BY customer_name, sub_customer_name, color, grade
        '''
        
        df = pd.read_sql_query(query, conn)
        
        # 处理数值列
        numeric_columns = ['单价', '数量', '金额']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
        
        return df

# 显示所有数据表
try:
    all_prices_df = get_all_latest_prices()
    
    if not all_prices_df.empty:
        st.info(f"📈 共找到 {len(all_prices_df)} 条最新价格记录")
        
        # 显示数据表
        st.dataframe(all_prices_df, use_container_width=True)
        
        # 简单统计
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            avg_price = all_prices_df['单价'].mean()
            st.metric("平均价格", f"¥{avg_price:.2f}")
        with col2:
            total_amount = all_prices_df['金额'].sum()
            st.metric("总金额", f"¥{total_amount:,.2f}")
        with col3:
            total_quantity = all_prices_df['数量'].sum()
            st.metric("总数量", f"{total_quantity:,.0f}")
        with col4:
            unique_customers = all_prices_df['客户名称'].nunique()
            st.metric("客户数量", unique_customers)
        
        # 导出功能
        csv_data = all_prices_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 导出所有价格数据(CSV)",
            csv_data,
            "all_ceramic_prices.csv",
            "text/csv",
            key='download-all-csv',
            use_container_width=True
        )
    else:
        st.warning("暂无价格数据")
except Exception as e:
    st.error(f"加载数据时出错: {str(e)}")

st.markdown("---")

# 条件查询功能
st.subheader("🔎 条件查询")

# 查询条件
col1, col2, col3 = st.columns(3)
with col1:
    customer_filter = st.text_input("客户名称", placeholder="输入客户名称关键词", key="customer_filter")
with col2:
    color_filter = st.text_input("产品颜色", placeholder="输入产品颜色关键词", key="color_filter")
with col3:
    grade_filter = st.text_input("产品等级", placeholder="输入产品等级", key="grade_filter")

# 查询按钮
if st.button("🔍 开始条件查询", type="primary", use_container_width=True):
    with st.spinner("正在查询中..."):
        df = analysis_service.get_latest_prices(customer_filter, color_filter, grade_filter)
    
    if not df.empty:
        st.subheader(f"📋 条件查询结果 ({len(df)} 条记录)")
        
        # 格式化显示列名
        display_df = df.rename(columns={
            'customer_name': '客户名称',
            'finance_id': '财务编号',
            'sub_customer_name': '子客户名称',
            'color': '产品颜色',
            'grade': '产品等级',
            'unit_price': '单价',
            'quantity': '数量',
            'amount': '金额',
            'record_date': '记录日期'
        })
        
        # 处理子客户名称显示
        display_df['子客户名称'] = display_df['子客户名称'].apply(lambda x: x if x and x != '' else '主客户')
        
        st.dataframe(display_df, use_container_width=True)
        
        # 导出功能
        csv_data = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 导出查询结果(CSV)",
            csv_data,
            "filtered_ceramic_prices.csv",
            "text/csv",
            key='download-filtered-csv',
            use_container_width=True
        )
        
        # 简单统计
        st.subheader("📊 查询统计")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("平均单价", f"¥{df['unit_price'].mean():.2f}")
        with col2:
            st.metric("总金额", f"¥{df['amount'].sum():.2f}")
        with col3:
            st.metric("总数量", f"{df['quantity'].sum():.0f}")
            
    else:
        st.warning("⚠️ 未找到匹配的记录")

# 快速查询提示
with st.expander("💡 查询技巧"):
    st.markdown("""
    ### 默认数据表说明
    - 📊 **上方表格**: 默认展示所有客户的最新价格数据，已按客户-子客户-产品去重
    - 🔍 **条件查询**: 下方可根据条件筛选特定数据
    
    ### 查询技巧
    - 🔍 **模糊查询**: 输入部分关键词即可匹配
    - 🎯 **精确查询**: 输入完整名称进行精确匹配  
    - 📊 **组合查询**: 可同时使用多个条件进行筛选
    - 💾 **数据导出**: 查询结果可导出为CSV文件
    
    ### 数据说明
    - **客户名称**: 大客户名称
    - **编号**: 财务唯一编号
    - **子客户**: 挂靠在大客户下的小客户，显示"主客户"表示无子客户
    - **产品颜色**: 产品颜色名称
    - **单价**: 产品单价
    - **数量**: 销售数量
    - **金额**: 销售金额
    """)
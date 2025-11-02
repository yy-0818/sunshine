import streamlit as st
import pandas as pd
from core.analysis_service import AnalysisService
from core.database import get_connection

st.set_page_config(page_title="价格趋势", layout="wide")
st.title("📈 价格趋势分析")

analysis_service = AnalysisService()

# 获取基础数据
customers_df = analysis_service.get_customers()
products_df = analysis_service.get_products()

if customers_df.empty or products_df.empty:
    st.warning("⚠️ 请先导入数据")
else:
    # 选择条件
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_customer = st.selectbox("选择客户", customers_df['customer_name'].unique())
        # 获取财务编号
        finance_id = customers_df[customers_df['customer_name'] == selected_customer]['finance_id'].iloc[0]
    
    with col2:
        # 根据选择的客户筛选可用的产品颜色
        with get_connection() as conn:
            customer_colors = pd.read_sql_query('''
                SELECT DISTINCT color 
                FROM sales_records 
                WHERE finance_id = ? 
                ORDER BY color
            ''', conn, params=[finance_id])['color'].tolist()
        
        if customer_colors:
            selected_color = st.selectbox("选择产品颜色", customer_colors)
        else:
            selected_color = st.selectbox("选择产品颜色", products_df['color'].unique())
            st.warning("该客户暂无产品数据")
    
    with col3:
        # 获取该客户该颜色的所有等级
        with get_connection() as conn:
            grade_options = pd.read_sql_query('''
                SELECT DISTINCT COALESCE(grade, '') as grade 
                FROM sales_records 
                WHERE finance_id = ? AND color = ?
                ORDER BY grade
            ''', conn, params=[finance_id, selected_color])['grade'].tolist()
        
        # 处理空等级显示
        grade_display_options = [g if g != '' else '无等级' for g in grade_options]
        selected_grade_display = st.selectbox("选择等级", grade_display_options)
        selected_grade = '' if selected_grade_display == '无等级' else selected_grade_display
    
    # 获取子客户选项
    with get_connection() as conn:
        sub_customers = pd.read_sql_query('''
            SELECT DISTINCT COALESCE(sub_customer_name, '') as sub_customer 
            FROM sales_records 
            WHERE finance_id = ? AND color = ? AND (grade = ? OR (grade IS NULL AND ? = ''))
            ORDER BY sub_customer
        ''', conn, params=[finance_id, selected_color, selected_grade, selected_grade])['sub_customer'].tolist()
    
    sub_customer_display = [sc if sc != '' else '主客户' for sc in sub_customers]
    selected_sub_customer_display = st.selectbox("选择子客户", sub_customer_display)
    selected_sub_customer = '' if selected_sub_customer_display == '主客户' else selected_sub_customer_display
    
    if selected_customer and selected_color:
        # 获取趋势数据
        with st.spinner("正在获取趋势数据..."):
            trend_data = analysis_service.get_price_trend(
                finance_id, selected_color, selected_grade, selected_sub_customer
            )
        
        if not trend_data.empty and len(trend_data) > 0:
            st.subheader(f"📈 {selected_customer} - {selected_color} - {selected_grade_display} 价格趋势")
            
            # 确保数据格式正确
            trend_data['month'] = pd.to_datetime(trend_data['month'] + '-01', format='%Y-%m-%d')
            trend_data = trend_data.sort_values('month')
            
            # 价格趋势图表
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 💰 价格趋势")
                if len(trend_data) > 1:
                    # 创建价格趋势图
                    price_chart_data = trend_data[['month', 'avg_price']].set_index('month')
                    st.line_chart(price_chart_data)
                else:
                    st.info("📅 数据点不足，无法显示趋势图")
                    st.write(f"当前价格: ¥{trend_data.iloc[0]['avg_price']:.2f}")
            
            with col2:
                st.markdown("#### 📦 数量趋势")
                if len(trend_data) > 1:
                    quantity_chart_data = trend_data[['month', 'total_quantity']].set_index('month')
                    st.bar_chart(quantity_chart_data)
                else:
                    st.info("📅 数据点不足，无法显示趋势图")
                    st.write(f"总数量: {trend_data.iloc[0]['total_quantity']:.0f}")
            
            # 金额对比
            st.markdown("#### 💸 金额分析")
            col3, col4 = st.columns(2)
            
            with col3:
                if len(trend_data) > 1:
                    amount_data = trend_data[['month', 'total_amount']].set_index('month')
                    st.area_chart(amount_data)
                else:
                    st.info("📅 数据点不足，无法显示趋势图")
            
            with col4:
                # 关键指标
                st.metric("最新均价", f"¥{trend_data.iloc[-1]['avg_price']:.2f}")
                st.metric("总交易量", f"{trend_data['total_quantity'].sum():.0f}")
                st.metric("总金额", f"¥{trend_data['total_amount'].sum():.2f}")
                st.metric("交易次数", f"{trend_data['transaction_count'].sum():.0f}")
            
            # 详细数据表
            st.markdown("#### 📊 详细数据")
            display_trend = trend_data.copy()
            display_trend['month'] = display_trend['month'].dt.strftime('%Y-%m')
            display_trend = display_trend.rename(columns={
                'month': '月份',
                'avg_price': '平均价格',
                'total_quantity': '总数量',
                'total_amount': '总金额',
                'transaction_count': '交易次数'
            })
            
            # 格式化数值列
            numeric_cols = ['平均价格', '总数量', '总金额']
            for col in numeric_cols:
                if col in display_trend.columns:
                    display_trend[col] = display_trend[col].round(2)
            
            st.dataframe(display_trend, use_container_width=True)
            
            # 导出功能
            csv_data = display_trend.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 导出趋势数据",
                csv_data,
                f"price_trend_{selected_customer}_{selected_color}.csv",
                "text/csv",
                use_container_width=True
            )
            
        else:
            st.info("📭 暂无历史价格数据")
            st.write("可能的原因：")
            st.write("- 该客户/产品组合没有足够的历史数据")
            st.write("- 数据的时间跨度不足")
            st.write("- 请检查数据导入是否包含时间信息")

# 使用说明
with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    ### 价格趋势分析说明
    
    **功能用途**
    - 分析特定客户、产品在不同时间段的价格变化
    - 跟踪销售数量和金额的趋势
    - 辅助价格决策和客户管理
    
    **数据要求**
    - 需要导入包含时间信息的Excel数据
    - 数据应包含月份或日期字段
    - 建议导入至少3个月的数据以观察趋势
    
    **使用技巧**
    - 选择具体的客户和产品组合获得更精确的趋势
    - 通过子客户筛选可以分析具体业务线的价格变化
    - 导出数据可用于进一步分析和报告
    """)
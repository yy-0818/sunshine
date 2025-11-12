import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from core.analysis_service import AnalysisService
from core.database import get_connection

st.logo(image='./assets/logo.png', icon_image='./assets/logo.png')
st.set_page_config(page_title="价格趋势", layout="wide")
st.title("📈 价格趋势分析")

analysis_service = AnalysisService()

# 获取基础数据
@st.cache_data(ttl=300)
def load_base_data():
    customers_df = analysis_service.get_customers()
    return customers_df

customers_df = load_base_data()

if customers_df.empty:
    st.warning("⚠️ 请先导入数据")
    st.stop()

# 数据查询函数
def get_customer_products_analysis(finance_id):
    """获取客户所有产品的分析数据"""
    with get_connection() as conn:
        products_data = pd.read_sql_query('''
            SELECT 
                product_name,
                color,
                COUNT(*) as transaction_count,
                SUM(quantity) as total_quantity,
                SUM(amount) as total_amount,
                AVG(unit_price) as avg_price,
                MIN(record_date) as first_date,
                MAX(record_date) as last_date
            FROM sales_records 
            WHERE finance_id = ? 
            AND product_name IS NOT NULL 
            AND product_name != ''
            GROUP BY product_name, color
            ORDER BY total_amount DESC
        ''', conn, params=[finance_id])
    return products_data

def get_product_price_trend(finance_id, product_name, color):
    """获取单个产品的价格趋势"""
    with get_connection() as conn:
        trend_data = pd.read_sql_query('''
            SELECT 
                strftime('%Y-%m', record_date) as month,
                AVG(unit_price) as avg_price,
                SUM(quantity) as total_quantity,
                SUM(amount) as total_amount,
                COUNT(*) as transaction_count
            FROM sales_records
            WHERE finance_id = ? AND product_name = ? AND color = ?
            GROUP BY strftime('%Y-%m', record_date) 
            ORDER BY month
        ''', conn, params=[finance_id, product_name, color])
    return trend_data

def get_product_transactions(finance_id, product_name, color):
    """获取产品的完整销售数据列表"""
    with get_connection() as conn:
        transactions = pd.read_sql_query('''
            SELECT 
                customer_name,
                finance_id,
                sub_customer_name,
                year,
                month,
                day,
                product_name,
                color,
                grade,
                quantity,
                unit_price,
                amount,
                ticket_number,
                remark,
                production_line
            FROM sales_records
            WHERE finance_id = ? AND product_name = ? AND color = ?
            ORDER BY record_date DESC, ticket_number
        ''', conn, params=[finance_id, product_name, color])
    return transactions

# 客户选择
st.markdown("### 🔍 选择客户")

# 按财务编号分组显示客户
customer_options = []
for finance_id in customers_df['finance_id'].unique():
    customer_names = customers_df[customers_df['finance_id'] == finance_id]['customer_name'].unique()
    display_name = f"{customer_names[0]} - {finance_id}" if len(customer_names) == 1 else f"{', '.join(customer_names)} - {finance_id}"
    customer_options.append((display_name, finance_id))

selected_customer_display = st.selectbox(
    "选择客户",
    [opt[0] for opt in customer_options],
    help="选择要分析的客户（按财务编号合并）"
)

# 获取选中的财务编号
selected_finance_id = None
for display_name, finance_id in customer_options:
    if display_name == selected_customer_display:
        selected_finance_id = finance_id
        break

if selected_finance_id:
    # 获取客户的所有产品分析数据
    with st.spinner("正在获取产品数据..."):
        products_analysis = get_customer_products_analysis(selected_finance_id)
    
    if products_analysis.empty:
        st.info("📭 该客户暂无产品购买记录")
        st.stop()
    
    # 显示客户信息
    customer_name = selected_customer_display.split(' - ')[0]
    st.subheader(f"📊 {customer_name} - 产品购买汇总")
    
    # 总体统计
    total_products = len(products_analysis)
    total_amount = products_analysis['total_amount'].sum()
    total_quantity = products_analysis['total_quantity'].sum()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("产品种类", f"{total_products}种")
    with col2:
        st.metric("总销售额", f"¥{total_amount:,.2f}")
    with col3:
        st.metric("总销量", f"{total_quantity:,.0f}")
    
    # 产品汇总表格
    st.markdown("### 📋 产品汇总")
    
    # 格式化显示数据
    display_data = products_analysis.copy()
    display_data = display_data.rename(columns={
        'product_name': '产品名称',
        'color': '颜色',
        'transaction_count': '交易次数',
        'total_quantity': '总销量',
        'total_amount': '总销售额',
        'avg_price': '平均价格',
        'first_date': '首次购买',
        'last_date': '最近购买'
    })
    
    # 格式化数值
    display_data['总销售额'] = display_data['总销售额'].round(2)
    display_data['平均价格'] = display_data['平均价格'].round(2)
    display_data['首次购买'] = pd.to_datetime(display_data['首次购买']).dt.strftime('%Y-%m-%d')
    display_data['最近购买'] = pd.to_datetime(display_data['最近购买']).dt.strftime('%Y-%m-%d')
    
    st.dataframe(display_data, use_container_width=True, height=500)
    
    # 产品选择详细分析
    st.markdown("### 🔍 产品详细分析")
    
    # 创建产品选择选项
    product_options = []
    for _, row in products_analysis.iterrows():
        option_text = f"{row['product_name']} - {row['color']} (¥{row['avg_price']:.2f})"
        product_options.append((option_text, row['product_name'], row['color']))
    
    selected_option = st.selectbox(
        "选择产品查看完整销售数据",
        [opt[0] for opt in product_options],
        help="选择产品和颜色查看完整销售数据列表"
    )
    
    # 获取选中的产品
    selected_product = None
    selected_color = None
    for option_text, product, color in product_options:
        if option_text == selected_option:
            selected_product = product
            selected_color = color
            break
    
    if selected_product and selected_color:
        st.markdown("---")
        st.subheader(f"📋 {selected_product} - {selected_color} 完整销售数据")
        
        # 获取完整销售数据
        with st.spinner("正在获取销售数据..."):
            transactions = get_product_transactions(selected_finance_id, selected_product, selected_color)
        
        # 显示产品基本信息
        product_info = products_analysis[
            (products_analysis['product_name'] == selected_product) & 
            (products_analysis['color'] == selected_color)
        ].iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("平均价格", f"¥{product_info['avg_price']:.2f}")
        with col2:
            st.metric("总销量", f"{product_info['total_quantity']:,}")
        with col3:
            st.metric("总销售额", f"¥{product_info['total_amount']:,.2f}")
        with col4:
            st.metric("交易次数", f"{product_info['transaction_count']}")
        
        # 只有当有足够数据时才显示趋势图
        trend_data = get_product_price_trend(selected_finance_id, selected_product, selected_color)
        if not trend_data.empty and len(trend_data) >= 3:
            st.markdown("### 📈 价格趋势")
            
            # 处理趋势数据
            trend_data['month'] = pd.to_datetime(trend_data['month'] + '-01', format='%Y-%m-%d')
            trend_data = trend_data.sort_values('month')
            
            # 价格趋势图
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trend_data['month'], 
                y=trend_data['avg_price'],
                mode='lines+markers',
                name='平均价格',
                line=dict(color='#1f77b4', width=3, shape='spline', smoothing=0.8),
                marker=dict(size=6),
                hovertemplate='<b>%{x|%Y-%m}</b><br>价格: ¥%{y:.2f}<extra></extra>'
            ))
            fig.update_layout(
                title='价格趋势',
                xaxis_title='月份',
                yaxis_title='价格 (元)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📊 数据点不足，无法显示价格趋势图")
        
        # 完整销售数据列表
        st.markdown("### 📝 完整销售数据列表")
        
        if not transactions.empty:
            # 格式化完整销售数据
            transactions_display = transactions.copy()
            
            # 重命名列以符合要求
            transactions_display = transactions_display.rename(columns={
                'customer_name': '客户名称',
                'finance_id': '编号',
                'sub_customer_name': '子客户名称',
                'year': '年',
                'month': '月', 
                'day': '日',
                'product_name': '产品名称',
                'color': '颜色',
                'grade': '等级',
                'quantity': '数量',
                'unit_price': '单价',
                'amount': '金额',
                'ticket_number': '票号',
                'remark': '备注',
                'production_line': '生产线'
            })
            
            # 处理空值
            transactions_display['子客户名称'] = transactions_display['子客户名称'].fillna('-')
            transactions_display['等级'] = transactions_display['等级'].fillna('-')
            transactions_display['备注'] = transactions_display['备注'].fillna('-')
            transactions_display['生产线'] = transactions_display['生产线'].fillna('-')
            
            # 格式化数值
            transactions_display['单价'] = transactions_display['单价'].round(2)
            transactions_display['金额'] = transactions_display['金额'].round(2)
            
            # 添加余额列（如果需要计算，这里暂时设为0）
            transactions_display['余额'] = 0
            
            # 重新排列列的顺序
            column_order = [
                '客户名称', '编号', '子客户名称', '年', '月', '日', 
                '产品名称', '颜色', '等级', '数量', '单价', '金额', 
                '余额', '票号', '备注', '生产线'
            ]
            
            # 确保所有列都存在
            for col in column_order:
                if col not in transactions_display.columns:
                    transactions_display[col] = '-'
            
            transactions_display = transactions_display[column_order]
            
            # 显示完整数据表格
            st.dataframe(transactions_display, use_container_width=True, height=600)
            
            # 导出功能
            st.markdown("### 📤 导出数据")
            csv_transactions = transactions_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 导出完整销售数据",
                csv_transactions,
                f"销售数据_{customer_name}_{selected_product}_{selected_color}.csv",
                "text/csv",
                use_container_width=True
            )
        else:
            st.info("暂无销售数据记录")

# 使用说明
with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **功能说明**
    - 选择客户后，展示该客户购买的所有产品汇总
    - 从产品列表中选择具体产品查看完整销售数据
    
    **数据展示**
    - **产品汇总**: 显示客户购买的所有产品、销量、销售额等
    - **完整销售数据**: 展示选定产品的所有销售记录，包含：
      - 客户名称、编号、子客户名称
      - 年、月、日
      - 产品名称、颜色、等级
      - 数量、单价、金额
      - 票号、备注、生产线
    
    **使用技巧**
    - 通过产品汇总表了解客户的产品购买情况
    - 选择感兴趣的产品查看完整销售数据
    - 当数据量足够时自动显示价格趋势图
    - 导出完整销售数据用于进一步分析
    """)
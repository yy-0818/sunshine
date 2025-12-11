import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from core.analysis_service import AnalysisService
from core.database import get_connection
from utils.auth import require_login

st.logo(image='./assets/logo.png', icon_image='./assets/logo.png')
st.set_page_config(page_title="价格趋势", layout="wide")
st.title("📈 价格趋势分析")

require_login()

analysis_service = AnalysisService()

# 获取基础数据
@st.cache_data(ttl=300)
def load_base_data():
    """加载基础数据"""
    with get_connection() as conn:
        # 获取所有部门数据
        departments_df = pd.read_sql_query('''
            SELECT DISTINCT 
                department,
                COUNT(*) as record_count,
                SUM(amount) as total_amount
            FROM sales_records
            WHERE department IS NOT NULL 
                AND department != ''
            GROUP BY department
            HAVING record_count > 0
            ORDER BY total_amount DESC
        ''', conn)
        
        return departments_df

@st.cache_data(ttl=300)
def get_department_customers(department):
    """获取指定部门下的所有客户"""
    with get_connection() as conn:
        customers_df = pd.read_sql_query('''
            SELECT DISTINCT 
                customer_name,
                finance_id,
                COUNT(*) as record_count,
                SUM(amount) as total_amount
            FROM sales_records
            WHERE department = ?
                AND customer_name IS NOT NULL 
                AND finance_id IS NOT NULL
            GROUP BY customer_name, finance_id
            HAVING record_count > 0
            ORDER BY total_amount DESC
        ''', conn, params=[department])
        
        return customers_df

@st.cache_data(ttl=300)
def get_customer_products_analysis(finance_id, department):
    """获取客户所有产品的分析数据（按部门）- 处理颜色为空的情况"""
    with get_connection() as conn:
        query = '''
            SELECT 
                product_name,
                COALESCE(color, '') as color,
                COUNT(*) as transaction_count,
                SUM(quantity) as total_quantity,
                SUM(amount) as total_amount,
                AVG(unit_price) as avg_price,
                MIN(record_date) as first_date,
                MAX(record_date) as last_date
            FROM sales_records 
            WHERE finance_id = ? 
                AND department = ?
                AND product_name IS NOT NULL 
                AND product_name != ''
            GROUP BY product_name, COALESCE(color, '')
            ORDER BY total_amount DESC
        '''
        products_data = pd.read_sql_query(query, conn, params=[finance_id, department])
    return products_data

def get_product_price_trend(finance_id, product_name, color, department):
    """获取单个产品的价格趋势（按部门）- 处理颜色为空的情况"""
    with get_connection() as conn:
        # 处理颜色条件：如果颜色是""，则查询color IS NULL或空字符串
        if color == '':
            query = '''
                SELECT 
                    strftime('%Y-%m', record_date) as month,
                    AVG(unit_price) as avg_price,
                    SUM(quantity) as total_quantity,
                    SUM(amount) as total_amount,
                    COUNT(*) as transaction_count
                FROM sales_records
                WHERE finance_id = ? 
                    AND product_name = ? 
                    AND (color IS NULL OR color = '')
                    AND department = ?
                GROUP BY strftime('%Y-%m', record_date) 
                ORDER BY month
            '''
            params = [finance_id, product_name, department]
        else:
            query = '''
                SELECT 
                    strftime('%Y-%m', record_date) as month,
                    AVG(unit_price) as avg_price,
                    SUM(quantity) as total_quantity,
                    SUM(amount) as total_amount,
                    COUNT(*) as transaction_count
                FROM sales_records
                WHERE finance_id = ? 
                    AND product_name = ? 
                    AND color = ?
                    AND department = ?
                GROUP BY strftime('%Y-%m', record_date) 
                ORDER BY month
            '''
            params = [finance_id, product_name, color, department]
        
        trend_data = pd.read_sql_query(query, conn, params=params)
    return trend_data

def get_complete_sales_records(finance_id, department, product_name=None, color=None):
    """获取完整的销售数据列表（按部门）- 处理颜色为空的情况"""
    with get_connection() as conn:
        if product_name:
            if color == '':
                query = '''
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
                        production_line,
                        department,
                        record_date
                    FROM sales_records
                    WHERE finance_id = ?
                        AND department = ?
                        AND product_name = ?
                        AND (color IS NULL OR color = '')
                '''
                params = [finance_id, department, product_name]
            else:
                query = '''
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
                        production_line,
                        department,
                        record_date
                    FROM sales_records
                    WHERE finance_id = ?
                        AND department = ?
                        AND product_name = ?
                        AND color = ?
                '''
                params = [finance_id, department, product_name, color]
        else:
            query = '''
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
                    production_line,
                    department,
                    record_date
                FROM sales_records
                WHERE finance_id = ?
                    AND department = ?
            '''
            params = [finance_id, department]
        
        query += " ORDER BY record_date DESC"
        
        transactions = pd.read_sql_query(query, conn, params=params)
    return transactions

# 加载部门数据
departments_df = load_base_data()

if departments_df.empty:
    st.warning("⚠️ 请先导入数据")
    st.stop()

# 创建两个选择框的布局 - 先选部门，再选客户
st.markdown("### 🔍 选择部门与客户")

col1, col2 = st.columns(2)

with col1:
    # 部门选择框
    if not departments_df.empty:
        # 创建部门选择选项
        department_options = []
        for _, row in departments_df.iterrows():
            dept_name = row['department']
            record_count = row['record_count']
            total_amount = row['total_amount']
            
            # 格式化显示
            if total_amount > 0:
                display_text = f"{dept_name} ({record_count:,}条记录, ¥{total_amount:,.2f})"
            else:
                display_text = f"{dept_name} ({record_count:,}条记录)"
            
            department_options.append({
                'display': display_text,
                'department': dept_name,
                'record_count': record_count,
                'total_amount': total_amount
            })
    
    # 按部门名称排序
    department_options = sorted(department_options, key=lambda x: x['department'])
    
    # 创建下拉框
    selected_dept_display = st.selectbox(
        "选择部门",
        [opt['display'] for opt in department_options],
        help="选择要分析的部门，显示该部门的记录数和总金额"
    )
    
    # 获取选中的部门信息
    selected_department = None
    for opt in department_options:
        if opt['display'] == selected_dept_display:
            selected_department = opt
            break

with col2:
    # 客户选择框 - 根据选择的部门动态加载
    if selected_department:
        # 获取该部门下的客户
        with st.spinner(f"正在加载 {selected_department['department']} 部门的客户列表..."):
            customers_df = get_department_customers(selected_department['department'])
        
        if not customers_df.empty:
            # 创建客户选择选项
            customer_options = []
            for _, row in customers_df.iterrows():
                if row['record_count'] > 0:
                    display_text = f"{row['customer_name']} ({row['finance_id']}) - {row['record_count']}笔订单"
                else:
                    display_text = f"{row['customer_name']} ({row['finance_id']})"
                
                customer_options.append({
                    'display': display_text,
                    'customer_name': row['customer_name'],
                    'finance_id': row['finance_id'],
                    'record_count': row['record_count'],
                    'total_amount': row['total_amount']
                })
            
            # 按客户名称排序
            customer_options = sorted(customer_options, key=lambda x: x['customer_name'])
            
            # 创建下拉框
            selected_customer_display = st.selectbox(
                "选择客户",
                [opt['display'] for opt in customer_options],
                help=f"选择 {selected_department['department']} 部门的客户进行分析"
            )
            
            # 获取选中的客户信息
            selected_customer = None
            for opt in customer_options:
                if opt['display'] == selected_customer_display:
                    selected_customer = opt
                    break
        else:
            st.warning(f"⚠️ {selected_department['department']} 部门暂无客户数据")
            selected_customer = None
    else:
        selected_customer = None
        st.selectbox(
            "选择客户",
            ["请先选择部门"],
            help="请先选择部门"
        )

# 如果部门和客户都已选择，开始分析
if selected_department and selected_customer:
    department_name = selected_department['department']
    customer_name = selected_customer['customer_name']
    finance_id = selected_customer['finance_id']
    
    # 显示当前选择的信息
    st.success(f"**已选择**: {department_name}部门 - {customer_name} ({finance_id})")
    
    # 获取该客户在选定部门的所有产品分析数据
    with st.spinner(f"正在获取 {customer_name} 在 {department_name} 部门的产品数据..."):
        products_analysis = get_customer_products_analysis(finance_id, department_name)
    
    if products_analysis.empty:
        # 尝试更宽松的查询，检查是否有数据
        with get_connection() as conn:
            # 检查是否有该客户在该部门的任何记录
            record_check = pd.read_sql_query('''
                SELECT COUNT(*) as record_count
                FROM sales_records
                WHERE finance_id = ? 
                    AND department = ?
                    AND customer_name = ?
            ''', conn, params=[finance_id, department_name, customer_name])
            
            if record_check.iloc[0]['record_count'] > 0:
                # 有记录但没有产品数据，可能是产品名称为空
                st.warning(f"⚠️ 该客户在 {department_name} 部门有 {record_check.iloc[0]['record_count']} 条记录，但产品数据不完整")
            else:
                st.error(f"❌ 错误：找不到 {customer_name} 在 {department_name} 部门的记录")
        
        st.stop()
    
    # 显示客户部门信息汇总
    st.subheader(f"📊 {customer_name} - {department_name}部门 产品购买汇总")
    
    # 总体统计
    total_products = len(products_analysis)
    total_amount = products_analysis['total_amount'].sum()
    total_quantity = products_analysis['total_quantity'].sum()
    avg_price = products_analysis['avg_price'].mean() if not products_analysis.empty else 0
    
    col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)
    with col_stat1:
        st.metric("产品种类", f"{total_products}种")
    with col_stat2:
        st.metric("总销售额", f"¥{total_amount:,.2f}")
    with col_stat3:
        st.metric("总销量", f"{total_quantity:,.0f}")
    with col_stat4:
        st.metric("平均单价", f"¥{avg_price:.2f}")
    with col_stat5:
        st.metric("所属部门", department_name)
    
    # 产品汇总表格
    st.markdown("### 📋 产品汇总")
    
    # 格式化显示数据
    display_data = products_analysis.copy()
    
    # 检查数据完整性
    if display_data.empty:
        st.warning("没有产品数据")
        st.stop()
    
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
    
    # 确保数值类型正确
    try:
        display_data['总销售额'] = pd.to_numeric(display_data['总销售额'], errors='coerce').round(2)
        display_data['平均价格'] = pd.to_numeric(display_data['平均价格'], errors='coerce').round(2)
        display_data['总销量'] = pd.to_numeric(display_data['总销量'], errors='coerce').astype(int)
        display_data['交易次数'] = pd.to_numeric(display_data['交易次数'], errors='coerce').astype(int)
    except Exception as e:
        st.error(f"数据处理错误: {str(e)}")
        st.write("原始数据:", display_data)
        st.stop()
    
    # 格式化日期
    if '首次购买' in display_data.columns:
        try:
            display_data['首次购买'] = pd.to_datetime(display_data['首次购买']).dt.strftime('%Y-%m-%d')
        except:
            pass
    
    if '最近购买' in display_data.columns:
        try:
            display_data['最近购买'] = pd.to_datetime(display_data['最近购买']).dt.strftime('%Y-%m-%d')
        except:
            pass
    
    # 设置列宽配置
    column_config = {
        '产品名称': st.column_config.TextColumn(width="small"),
        '颜色': st.column_config.TextColumn(width="small"),
        '交易次数': st.column_config.NumberColumn(format="%d", width="small"),
        '总销量': st.column_config.NumberColumn(format="%d", width="small"),
        '总销售额': st.column_config.NumberColumn(format="¥%.2f", width="small"),
        '平均价格': st.column_config.NumberColumn(format="¥%.2f", width="small"),
        '首次购买': st.column_config.TextColumn(width="small"),
        '最近购买': st.column_config.TextColumn(width="small")
    }
    
    st.dataframe(display_data, width='stretch', height='auto', hide_index=True, column_config=column_config)
    
    # 产品选择详细分析
    st.markdown("### 🔍 产品详细分析")
    
    # 创建产品选择选项
    product_options = []
    for _, row in products_analysis.iterrows():
        product_name = str(row['product_name']) if pd.notna(row['product_name']) else "未命名产品"
        color = str(row['color']) if pd.notna(row['color']) else ""
        avg_price = float(row['avg_price']) if pd.notna(row['avg_price']) else 0
        
        # 如果有颜色信息且不是空字符串，则显示颜色
        if color and color != "" and color != "nan":
            option_text = f"{product_name} - {color} (¥{avg_price:.2f})"
        else:
            option_text = f"{product_name} (¥{avg_price:.2f})"
        
        product_options.append((option_text, product_name, color, avg_price))
    
    # 添加"全部产品"选项
    if product_options:
        product_options.insert(0, ("全部产品 - 查看所有订单", None, None, None))
    
    if product_options:
        selected_option = st.selectbox(
            "选择产品查看详细订单",
            [opt[0] for opt in product_options],
            help="选择产品和颜色查看详细订单信息，或选择'全部产品'查看所有订单"
        )
        
        # 获取选中的产品
        selected_product = None
        selected_color = None
        for option_text, product, color, price in product_options:
            if option_text == selected_option:
                selected_product = product
                selected_color = color
                break
        
        # 如果是"全部产品"，设置为None
        if selected_option == "全部产品 - 查看所有订单":
            selected_product = None
            selected_color = None
        
        # 获取完整的销售数据
        with st.spinner("正在获取订单数据..."):
            try:
                complete_records = get_complete_sales_records(finance_id, department_name, selected_product, selected_color)
            except Exception as e:
                st.error(f"获取订单数据失败: {str(e)}")
                complete_records = pd.DataFrame()
        
        if selected_option == "全部产品 - 查看所有订单":
            st.subheader(f"📋 {customer_name} - {department_name}部门 所有订单记录")
            
            if not complete_records.empty:
                # 显示总体统计
                total_records = len(complete_records)
                st.metric("总订单数", f"{total_records}笔")
                
                # 格式化完整销售数据
                records_display = complete_records.copy()
                records_display = records_display.rename(columns={
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
                    'production_line': '生产线',
                    'department': '部门'
                })
                
                # 重新排序列顺序
                column_order = ['客户名称', '编号', '子客户名称', '部门', '年', '月', '日', 
                              '产品名称', '颜色', '等级', '数量', '单价', '金额', 
                              '票号', '备注', '生产线', 'record_date']
                available_columns = [col for col in column_order if col in records_display.columns]
                records_display = records_display[available_columns]
                
                st.dataframe(records_display, width='stretch', hide_index=True, height='auto', 
                            column_config={
                                '单价': st.column_config.NumberColumn(format="¥%.2f", width='small'),
                                '金额': st.column_config.NumberColumn(format="¥%.2f", width='small'),
                                'record_date': st.column_config.DatetimeColumn(format="YYYY-MM-DD", width='medium')
                            })
                
                # 导出功能
                st.markdown("### 📤 导出数据")
                csv_data = records_display.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    "📥 导出所有订单记录",
                    csv_data,
                    f"{customer_name}_{department_name}_所有订单记录.csv",
                    "text/csv",
                    width='stretch'
                )
            else:
                st.info("暂无订单记录")
        
        # 修复这里：当选择了具体产品时，无论颜色是否为空，都应该进入详细分析
        elif selected_product is not None:
            st.markdown("---")
            
            # 显示产品标题
            if selected_color and selected_color != "" and selected_color != "nan":
                st.subheader(f"📋 {selected_product} - {selected_color} 订单详情 ({department_name}部门)")
            else:
                st.subheader(f"📋 {selected_product} 订单详情 ({department_name}部门)")
            
            # 找到对应的产品信息
            product_info = None
            for _, row in products_analysis.iterrows():
                # 修复产品匹配逻辑：正确处理颜色为空的情况
                if row['product_name'] == selected_product:
                    # 检查颜色是否匹配
                    row_color = str(row['color']) if pd.notna(row['color']) else ""
                    if (selected_color == "" and row_color == "") or (selected_color == row_color):
                        product_info = row
                        break
            
            if product_info is not None:
                # 获取价格趋势数据
                with st.spinner("正在获取价格趋势..."):
                    trend_data = get_product_price_trend(finance_id, selected_product, selected_color, department_name)
                
                # 产品关键指标
                col_metrics1, col_metrics2, col_metrics3, col_metrics4, col_metrics5 = st.columns(5)
                with col_metrics1:
                    st.metric("平均价格", f"¥{product_info['avg_price']:.2f}")
                with col_metrics2:
                    st.metric("总销量", f"{product_info['total_quantity']:,}")
                with col_metrics3:
                    st.metric("总销售额", f"¥{product_info['total_amount']:,.2f}")
                with col_metrics4:
                    st.metric("交易次数", f"{product_info['transaction_count']}")
                with col_metrics5:
                    st.metric("所属部门", department_name)
                
                # 显示价格趋势图表
                if not trend_data.empty:
                    st.markdown("### 📈 价格趋势")
                    
                    try:
                        # 处理趋势数据
                        trend_data['month'] = pd.to_datetime(trend_data['month'] + '-01', format='%Y-%m-%d')
                        trend_data = trend_data.sort_values('month')
                        
                        # 创建多图表布局
                        fig = go.Figure()
                        
                        # 价格趋势线
                        fig.add_trace(go.Scatter(
                            x=trend_data['month'], 
                            y=trend_data['avg_price'],
                            mode='lines+markers',
                            name='平均价格',
                            line=dict(color='#1f77b4', width=3, shape='spline', smoothing=0.8),
                            marker=dict(size=6),
                            hovertemplate='<b>%{x|%Y-%m}</b><br>价格: ¥%{y:.2f}<extra></extra>'
                        ))
                        
                        # 添加交易数量柱状图（次坐标轴）
                        fig.add_trace(go.Bar(
                            x=trend_data['month'],
                            y=trend_data['transaction_count'],
                            name='交易次数',
                            yaxis='y2',
                            marker_color='rgba(255, 127, 14, 0.6)',
                            hovertemplate='<b>%{x|%Y-%m}</b><br>交易次数: %{y}<extra></extra>'
                        ))
                        
                        # 优化图表布局
                        if selected_color and selected_color != "" and selected_color != "nan":
                            chart_title = f'{selected_product} - {selected_color} 价格趋势 ({department_name}部门)'
                        else:
                            chart_title = f'{selected_product} 价格趋势 ({department_name}部门)'
                        
                        fig.update_layout(
                            title=chart_title,
                            xaxis_title='月份',
                            yaxis_title='价格 (元)',
                            yaxis=dict(
                                title='价格 (元)',
                                showgrid=True,
                                gridcolor='rgba(128, 128, 128, 0.1)',
                                gridwidth=1
                            ),
                            yaxis2=dict(
                                title='交易次数',
                                overlaying='y',
                                side='right',
                                showgrid=False
                            ),
                            xaxis=dict(
                                showgrid=True,
                                gridcolor='rgba(128, 128, 128, 0.1)',
                                gridwidth=1
                            ),
                            hovermode='x unified',
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1
                            )
                        )
                        
                        st.plotly_chart(fig, width='stretch', use_container_width=True)
                        
                        # 添加价格统计信息
                        st.markdown("#### 📊 价格统计")
                        col_stats1, col_stats2, col_stats3 = st.columns(3)
                        with col_stats1:
                            if len(trend_data) >= 2:
                                price_change = ((trend_data['avg_price'].iloc[-1] - trend_data['avg_price'].iloc[0]) / 
                                               trend_data['avg_price'].iloc[0] * 100)
                                delta_color = "inverse" if price_change < 0 else "normal"
                                st.metric(
                                    "价格变化", 
                                    f"¥{trend_data['avg_price'].iloc[-1]:.2f}", 
                                    delta=f"{price_change:.1f}%" if price_change != 0 else None,
                                    delta_color=delta_color
                                )
                            else:
                                st.metric("当前价格", f"¥{trend_data['avg_price'].iloc[-1]:.2f}")
                        with col_stats2:
                            st.metric("最高价格", f"¥{trend_data['avg_price'].max():.2f}")
                        with col_stats3:
                            st.metric("最低价格", f"¥{trend_data['avg_price'].min():.2f}")
                    except Exception as e:
                        st.error(f"生成趋势图失败: {str(e)}")
                        st.info("📊 无法显示价格趋势图")
                else:
                    st.info("📊 没有价格趋势数据")
                
                # 详细交易记录
                st.markdown("### 📝 详细订单记录")
                
                if not complete_records.empty:
                    # 格式化完整销售数据
                    records_display = complete_records.copy()
                    records_display = records_display.rename(columns={
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
                        'production_line': '生产线',
                        'department': '部门'
                    })
                    
                    # 处理颜色显示
                    records_display['颜色'] = records_display['颜色'].apply(lambda x: '' if pd.isna(x) or x == '' else x)
                    
                    # 重新排序列顺序
                    column_order = ['客户名称', '编号', '子客户名称', '部门', '年', '月', '日', 
                                  '产品名称', '颜色', '等级', '数量', '单价', '金额', 
                                  '票号', '备注', '生产线', 'record_date']
                    available_columns = [col for col in column_order if col in records_display.columns]
                    records_display = records_display[available_columns]
                    
                    st.dataframe(records_display, width='stretch', height='auto',
                                column_config={
                                    '单价': st.column_config.NumberColumn(format="¥%.2f", width='small'),
                                    '金额': st.column_config.NumberColumn(format="¥%.2f", width='small'),
                                    'record_date': st.column_config.DatetimeColumn(format="YYYY-MM-DD", width='medium')
                                })
                    
                    # 导出功能
                    st.markdown("### 📤 导出数据")
                    csv_data = records_display.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        "📥 导出订单记录",
                        csv_data,
                        f"{customer_name}_{selected_product}_{department_name}_订单记录.csv",
                        "text/csv",
                        width='stretch'
                    )
                else:
                    st.info("暂无订单记录")
            else:
                st.warning("未找到产品信息")
    else:
        st.info("没有可供选择的产品")

# 使用说明
with st.expander("💡 使用说明", expanded=False):
    st.markdown("""
    **功能说明**
    - **先选部门，再选客户**：首先选择要分析的部门，然后选择该部门下的客户
    - **支持无颜色数据**：二期数据中很多产品没有颜色信息，系统会自动处理
    - **优化图表显示**：去除多余的网格线，优化视觉效果
    
    **操作流程**
    1. **选择部门**：从部门下拉框中选择要分析的部门，可以看到部门的记录数和总金额
    2. **选择客户**：系统会自动加载选定部门的所有客户，选择要分析的客户
    3. **查看产品汇总**：系统显示该客户在选定部门的产品购买汇总
    4. **选择产品**：从产品列表中选择具体产品或选择"全部产品"查看所有订单
    
    **数据处理**
    - **颜色字段处理**：对于没有颜色信息的产品，系统会显示""
    - **数据查询优化**：针对无颜色数据的查询进行了特殊处理
    - **数据完整性检查**：确保数据正确显示
    
    **数据展示**
    - **产品汇总**: 显示客户在选定部门购买的所有产品、销量、销售额、平均价格等
    - **完整订单记录**: 包含客户名称、编号、子客户、年月日、产品名称、颜色、等级、数量、单价、金额、票号、备注、生产线、部门等完整信息
    - **价格趋势**: 显示选定产品的价格变化趋势和交易次数
    
    **使用技巧**
    - 部门选择框显示每个部门的记录数和总金额，帮助选择重点部门
    - 客户选择框显示每个客户的订单数量，帮助选择重要客户
    - 选择"全部产品"可以查看客户在选定部门的所有订单记录
    - 选择具体产品可以查看该产品的详细信息和价格趋势
    - 导出数据用于进一步分析
    
    **注意**
    - 同一客户在不同部门的数据是分开的
    - 确保导入数据时填写正确的部门信息
    - 产品数据不完整可能会影响分析结果
    """)
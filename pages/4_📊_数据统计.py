import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.analysis_service import AnalysisService
from core.database import get_connection
from utils.auth import require_login

# 页面配置
st.logo(
    image='./assets/logo.png',
    icon_image='./assets/logo.png',
)

st.set_page_config(page_title="数据统计", layout="wide")
st.title("📊 数据统计分析")

require_login()

# 初始化服务
analysis_service = AnalysisService()

# ==================== 通用组件函数优化 ====================

def create_metric_card(label, value, delta=None, delta_color="normal"):
    """创建统一的指标卡片"""
    st.metric(label, value, delta=delta, delta_color=delta_color)

def create_pie_chart(df, values_col, names_col, title, color_map=None):
    """创建饼图"""
    if df.empty:
        st.info("暂无数据")
        return None
        
    fig = px.pie(
        df, 
        values=values_col, 
        names=names_col,
        title=title,
        color=names_col,
        color_discrete_map=color_map
    )
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>记录数: %{value}<br>占比: %{percent}'
    )
    fig.update_layout(
        template="plotly_white",
        showlegend=False,
    )
    return fig

def create_bar_chart(df, x_col, y_col, title, color_col=None, color_scale="Viridis", x_label=None, y_label=None):
    """创建柱状图"""
    if df.empty:
        st.info("暂无数据")
        return None
    
    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        title=title,
        color=color_col if color_col else y_col,
        color_continuous_scale=color_scale
    )
    
    x_label = x_label or x_col
    y_label = y_label or y_col
    
    fig.update_layout(
        template="plotly_white",
        xaxis_title=x_label,
        yaxis_title=y_label,
        xaxis_tickangle=-45,
    )
    return fig

def format_chinese_month(month_str):
    """将YYYY-MM格式转换为中文月份格式"""
    try:
        year, month = month_str.split('-')
        month_names = ['一月', '二月', '三月', '四月', '五月', '六月', 
                      '七月', '八月', '九月', '十月', '十一月', '十二月']
        return f"{year}年{month_names[int(month)-1]}"
    except:
        return month_str

def create_trend_comparison_chart(monthly_data, primary_col, secondary_col, title, 
                                primary_name="销售额", secondary_name="交易次数",
                                primary_color='#2563EB', secondary_color='rgba(16,185,129,0.4)'):
    """创建趋势对比图 - 优化中文月份显示"""
    if monthly_data.empty or len(monthly_data) <= 1:
        st.info("暂无足够的时间趋势数据")
        return None
        
    # 转换月份为中文格式
    monthly_data = monthly_data.copy()
    monthly_data['month_chinese'] = monthly_data['month'].apply(format_chinese_month)
    
    fig = go.Figure()
    
    # 主Y轴数据（折线图）
    fig.add_trace(go.Scatter(
        x=monthly_data['month_chinese'],
        y=monthly_data[primary_col],
        name=primary_name,
        line=dict(color=primary_color, width=3),
        line_shape='spline',
        marker=dict(size=6),
        hovertemplate=f'{primary_name}: %{{y:,.2f}}<extra></extra>'
    ))
    
    # 次Y轴数据（柱状图）
    fig.add_trace(go.Bar(
        x=monthly_data['month_chinese'],
        y=monthly_data[secondary_col],
        name=secondary_name,
        marker_color=secondary_color,
        yaxis='y2',
        hovertemplate=f'{secondary_name}: %{{y:,}}<extra></extra>'
    ))
    
    fig.update_layout(
        title=title,
        template="plotly_white",
        xaxis_title="月份",
        yaxis_title=primary_name,
        yaxis=dict(side='left', showgrid=False),
        yaxis2=dict(title=secondary_name, overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='x unified',
    )
    return fig

# ==================== 部门概览优化 ====================

@st.cache_data(ttl=60)
def get_cached_department_stats():
    """缓存部门统计数据"""
    with get_connection() as conn:
        # 部门记录统计
        dept_stats = pd.read_sql_query('''
            SELECT 
                CASE 
                    WHEN department IS NULL OR department = '' THEN '未分类'
                    ELSE department 
                END as department,
                COUNT(*) as record_count,
                SUM(amount) as total_amount,
                SUM(quantity) as total_quantity,
                AVG(unit_price) as avg_price
            FROM sales_records
            GROUP BY department
            ORDER BY record_count DESC
        ''', conn)
        
        # 获取示例数据
        unclassified_samples = pd.read_sql_query('''
            SELECT 
                production_line,
                COUNT(*) as record_count
            FROM sales_records
            WHERE department IS NULL OR department = ''
            GROUP BY production_line
            ORDER BY record_count DESC
            LIMIT 10
        ''', conn)
        
        return {
            'department_stats': dept_stats.to_dict('records'),
            'unclassified_samples': unclassified_samples.to_dict('records'),
            'total_records': dept_stats['record_count'].sum() if not dept_stats.empty else 0,
            'classified_records': dept_stats[dept_stats['department'] != '未分类']['record_count'].sum() 
                                 if not dept_stats.empty else 0,
            'unclassified_records': dept_stats[dept_stats['department'] == '未分类']['record_count'].sum() 
                                   if not dept_stats.empty else 0
        }

# ==================== 部门分析 ====================

@st.cache_data(ttl=60)
def get_cached_department_data(department):
    """缓存部门数据"""
    with get_connection() as conn:
        query = '''
            SELECT 
                customer_name,
                finance_id,
                sub_customer_name,
                product_name,
                color,
                grade,
                quantity,
                unit_price,
                amount,
                ticket_number,
                remark,
                production_line,
                record_date
            FROM sales_records
            WHERE department = ?
            ORDER BY record_date DESC
        '''
        df = pd.read_sql_query(query, conn, params=(department,))
        return df

@st.cache_data(ttl=60)
def get_cached_department_stats(department):
    """缓存部门统计数据"""
    with get_connection() as conn:
        stats = pd.read_sql_query('''
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT customer_name) as customer_count,
                COUNT(DISTINCT product_name) as product_count,
                COUNT(DISTINCT color) as color_count,
                SUM(amount) as total_amount,
                SUM(quantity) as total_quantity,
                AVG(unit_price) as avg_price,
                MIN(record_date) as start_date,
                MAX(record_date) as end_date
            FROM sales_records
            WHERE department = ?
        ''', conn, params=(department,))
        
        return {
            'total_records': int(stats.iloc[0]['total_records']) if not stats.empty else 0,
            'customer_count': int(stats.iloc[0]['customer_count']) if not stats.empty else 0,
            'product_count': int(stats.iloc[0]['product_count']) if not stats.empty else 0,
            'color_count': int(stats.iloc[0]['color_count']) if not stats.empty else 0,
            'total_amount': float(stats.iloc[0]['total_amount']) if not stats.empty else 0,
            'total_quantity': float(stats.iloc[0]['total_quantity']) if not stats.empty else 0,
            'avg_price': float(stats.iloc[0]['avg_price']) if not stats.empty else 0,
            'date_range': {
                'start': str(stats.iloc[0]['start_date']) if not stats.empty and stats.iloc[0]['start_date'] else None,
                'end': str(stats.iloc[0]['end_date']) if not stats.empty and stats.iloc[0]['end_date'] else None
            }
        }

def render_department_metrics(dept_stats, department):
    """渲染部门指标 - 优化布局"""
    # 优化指标卡片布局
    cols1 = st.columns(4)
    metrics1 = [
        ("总记录数", f"{dept_stats['total_records']:,}"),
        ("客户数量", f"{dept_stats['customer_count']:,}"),
        ("产品数量", f"{dept_stats['product_count']:,}"),
        ("颜色种类", f"{dept_stats['color_count']:,}")
    ]
    
    for col, (label, value) in zip(cols1, metrics1):
        with col:
            st.metric(label, value)
    
    cols2 = st.columns(4)
    
    # 优化时间范围显示
    date_range_text = "暂无数据"
    if dept_stats['date_range'] and dept_stats['date_range']['start']:
        start_date = dept_stats['date_range']['start'][:10] if dept_stats['date_range']['start'] else "未知"
        end_date = dept_stats['date_range']['end'][:10] if dept_stats['date_range']['end'] else "未知"
        date_range_text = f"{start_date} 至 {end_date}"
    
    metrics2 = [
        ("总金额", f"¥{dept_stats['total_amount']:,.2f}"),
        ("总数量", f"{dept_stats['total_quantity']:,.0f}"),
        ("平均价格", f"¥{dept_stats['avg_price']:.2f}"),
        ("数据时间范围", date_range_text)
    ]
    
    for col, (label, value) in zip(cols2, metrics2):
        with col:
            if label == "数据时间范围":
                # 对于长文本字段，使用更简洁的显示方式
                st.metric(label, value)
            else:
                create_metric_card(label, value)

def render_production_line_analysis_by_dept(department):
    """渲染部门生产线分析"""
    with get_connection() as conn:
        lines_df = pd.read_sql_query('''
            SELECT 
                production_line,
                COUNT(*) as record_count,
                SUM(amount) as total_amount,
                SUM(quantity) as total_quantity,
                AVG(unit_price) as avg_price
            FROM sales_records
            WHERE department = ?
            GROUP BY production_line
            HAVING record_count > 0
            ORDER BY record_count DESC
        ''', conn, params=(department,))
    
    if lines_df.empty:
        st.info(f"{department}暂无生产线详细数据")
        return
        
    col1, col2 = st.columns(2)
    
    with col1:
        fig_lines = create_bar_chart(
            lines_df.nlargest(10, 'record_count'),
            'production_line', 'record_count',
            f"{department}生产线记录数TOP10",
            x_label="生产线", y_label="记录数"
        )
        fig_lines.update_traces(
            hovertemplate='<b>%{x}</b><br>记录数: %{y:,.2f}<extra></extra>'
        )
        if fig_lines:
            st.plotly_chart(fig_lines, width='stretch')
    
    with col2:
        if not lines_df.empty:
            fig_amount = px.pie(
                lines_df,
                values='total_amount',
                names='production_line',
                title=f"{department}生产线销售额分布",
                hole=0.4
            )
            fig_amount.update_traces(
                textposition='inside', 
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>销售额: ¥%{value:,.2f}<br>占比: %{percent}<extra></extra>'
            )
            fig_amount.update_layout(
                template="plotly_white", 
                showlegend=False, 
            )
            st.plotly_chart(fig_amount, width='stretch')
    
    # 生产线详细数据表
    st.subheader("📋 生产线详细数据")
    display_lines = lines_df.copy()
    display_lines['平均价格'] = display_lines['avg_price'].round(2)
    display_lines['总金额'] = display_lines['total_amount'].round(2)
    display_lines['总数量'] = display_lines['total_quantity'].round(0)
    
    st.dataframe(
        display_lines[['production_line', 'record_count', '总数量', '平均价格', '总金额']],
        column_config={
            'production_line': st.column_config.TextColumn('生产线', width="medium"),
            'record_count': st.column_config.NumberColumn('记录数', format="%d"),
            '总数量': st.column_config.NumberColumn('总数量', format="%d"),
            '平均价格': st.column_config.NumberColumn('平均价格', format="¥%.2f"),
            '总金额': st.column_config.NumberColumn('总金额', format="¥%.2f")
        },
        width='stretch',
        hide_index=True
    )

def render_department_trend_analysis(department):
    """渲染部门趋势分析 - 优化中文月份显示"""
    with get_connection() as conn:
        monthly_trend = pd.read_sql_query('''
            SELECT 
                strftime('%Y-%m', record_date) as month,
                COUNT(*) as transaction_count,
                SUM(amount) as total_amount,
                AVG(unit_price) as avg_price,
                SUM(quantity) as total_quantity
            FROM sales_records
            WHERE department = ?
            GROUP BY strftime('%Y-%m', record_date)
            ORDER BY month
        ''', conn, params=(department,))

    if not monthly_trend.empty and len(monthly_trend) > 1:
        col1, col2 = st.columns(2)
        
        with col1:
            fig_trend = create_trend_comparison_chart(
                monthly_trend, 'total_amount', 'transaction_count',
                f"📊 {department}销售额 vs 交易量 时间对比趋势",
                "销售额", "交易次数",
                primary_color="rgba(138, 92, 246, .85)", secondary_color='rgba(6, 214, 160, .7)'
            )
            if fig_trend:
                st.plotly_chart(fig_trend, width='stretch')
        
        with col2:
            fig_price_qty = create_trend_comparison_chart(
                monthly_trend, 'avg_price', 'total_quantity',
                f"📦 {department}平均单价 vs 销售数量 趋势变化",
                "平均单价", "销售数量",
                primary_color='rgba(239, 71, 111, .85)', secondary_color='rgba(17, 138, 178, .7)'
            )
            if fig_price_qty:
                st.plotly_chart(fig_price_qty, width='stretch')
        
        # 月度详细数据
        with st.expander("📈 查看月度详细数据"):
            display_monthly = monthly_trend.copy()
            display_monthly['月份'] = display_monthly['month'].apply(format_chinese_month)
            display_monthly['交易次数'] = display_monthly['transaction_count']
            display_monthly['总金额'] = display_monthly['total_amount'].round(2)
            display_monthly['平均价格'] = display_monthly['avg_price'].round(2)
            display_monthly['总数量'] = display_monthly['total_quantity']
            
            st.dataframe(
                display_monthly[['月份', '交易次数', '总金额', '平均价格', '总数量']],
                width='stretch',
                hide_index=True
            )
    else:
        st.info(f"{department}暂无足够的时间趋势数据")

def create_department_analysis_tab(department):
    """创建部门分析选项卡内容"""
    try:
        # 获取部门数据
        dept_data = get_cached_department_data(department)
        dept_stats = get_cached_department_stats(department)
        
        if dept_data.empty:
            st.warning(f"⚠️ {department}暂无数据")
            return
        
        # 部门概览指标
        st.subheader(f"📈 {department}关键指标")
        render_department_metrics(dept_stats, department)
        
        # 生产线详细分析
        st.markdown("---")
        st.subheader("🏭 生产线详细分析")
        render_production_line_analysis_by_dept(department)
        
        # 时间趋势分析
        st.markdown("---")
        st.subheader("📅 时间趋势分析")
        render_department_trend_analysis(department)
        
        # 产品分析
        st.markdown("---")
        st.subheader("🏺 产品分析")
        
        if not dept_data.empty:
            # 产品统计
            product_stats = dept_data.groupby(['product_name', 'color']).agg({
                'amount': 'sum',
                'quantity': 'sum',
                'unit_price': 'mean',
                'customer_name': 'count'
            }).reset_index()
            product_stats.columns = ['product_name', 'color', 'total_amount', 'total_quantity', 'avg_price', 'transaction_count']
            product_stats = product_stats.sort_values('total_amount', ascending=False)
            
            if not product_stats.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    # 热销产品TOP10
                    top_products = product_stats.head(10)
                    fig_top_products = px.bar(
                        top_products,
                        x='product_name',
                        y='total_amount',
                        color='color',
                        title=f"{department}热销产品TOP10",
                        labels={
                            'product_name': '产品名称', 
                            'total_amount': '销售额 (¥)',
                            'color': '颜色'
                        }
                    )
                    fig_top_products.update_traces(
                        hovertemplate='<b>%{x}</b><br>销售额: ¥%{y:,.2f}<extra></extra>'
                    )
                    fig_top_products.update_layout(
                        template="plotly_white",
                        xaxis_title="产品名称",
                        yaxis_title="销售额 (¥)",
                        xaxis_tickangle=-45,
                        showlegend=True,
                    )
                    st.plotly_chart(fig_top_products, width='stretch')
                
                with col2:
                    # 产品价格分布
                    fig_price_dist = px.box(
                        product_stats,
                        x='product_name',
                        y='avg_price',
                        title=f"{department}产品价格分布",
                        points="all",
                        labels={
                            'product_name': '产品名称',
                            'avg_price': '平均价格 (¥)'
                        }
                    )
                    fig_price_dist.update_traces(
                        hovertemplate='<b>%{x}</b><br>平均价格: ¥%{y:.2f}<extra></extra>'
                    )
                    fig_price_dist.update_layout(
                        template="plotly_white",
                        xaxis_title="产品名称",
                        yaxis_title="平均价格 (¥)",
                        xaxis_tickangle=-45,
                        showlegend=False,
                    )
                    st.plotly_chart(fig_price_dist, width='stretch')
        
        # 数据导出
        st.markdown("---")
        st.subheader("💾 数据导出")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 导出部门数据（中文表头）
            export_data = dept_data.copy()
            export_data = export_data.rename(columns={
                'customer_name': '客户名称',
                'finance_id': '财务编号',
                'sub_customer_name': '子客户名称',
                'product_name': '产品名称',
                'color': '颜色',
                'grade': '等级',
                'quantity': '数量',
                'unit_price': '单价',
                'amount': '金额',
                'ticket_number': '票据号码',
                'remark': '备注',
                'production_line': '生产线',
                'record_date': '记录日期'
            })
            csv_data = export_data.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                f"📥 导出{department}数据",
                csv_data,
                f"{department}_数据.csv",
                "text/csv",
                width='stretch'
            )
        
        with col2:
            if not dept_data.empty:
                product_stats = dept_data.groupby(['product_name', 'color']).agg({
                    'amount': 'sum', 'quantity': 'sum', 'unit_price': 'mean', 'customer_name': 'count'
                }).reset_index()
                # 导出产品统计（中文表头）
                export_products = product_stats.copy()
                export_products = export_products.rename(columns={
                    'product_name': '产品名称',
                    'color': '颜色',
                    'amount': '总金额',
                    'quantity': '总数量',
                    'unit_price': '平均价格',
                    'customer_name': '交易次数'
                })
                csv_products = export_products.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    f"📥 导出{department}产品统计",
                    csv_products,
                    f"{department}_产品统计.csv",
                    "text/csv",
                    width='stretch'
                )
                
    except Exception as e:
        st.error(f"分析{department}数据时出错: {str(e)}")

# ==================== 总数分析优化 ====================

@st.cache_data(ttl=60)
def get_cached_total_stats():
    """缓存总数统计数据"""
    return analysis_service.get_statistics()

def render_total_metrics(stats):
    """渲染总数分析指标 - 优化布局"""
    # 第一行指标
    cols1 = st.columns(4)
    metrics1 = [
        ("总记录数", f"{stats['total_records']:,}"),
        ("主客户", f"{stats['main_customers']:,}"),
        ("子客户数", f"{stats['sub_customers']:,}"),
        ("产品颜色数", f"{stats['unique_colors']:,}")
    ]
    
    for col, (label, value) in zip(cols1, metrics1):
        with col:
            st.metric(label, value)
    
    # 第二行指标
    cols2 = st.columns(4)
    metrics2 = [
        ("产品等级数", f"{stats['unique_grades']:,}"),
        ("最低价格", f"¥{stats.get('min_price', 0):.2f}"),
        ("最高价格", f"¥{stats.get('max_price', 0):.2f}"),
        ("平均价格", f"¥{stats.get('avg_price', 0):.2f}")
    ]
    
    for col, (label, value) in zip(cols2, metrics2):
        with col:
            create_metric_card(label, value)
    
    # 第三行指标
    cols3 = st.columns(4)
    total_quantity = stats.get('total_quantity', 0)
    total_amount = stats.get('total_amount', 0)
    avg_amount = total_amount / stats['total_records'] if stats['total_records'] > 0 else 0
    avg_customer_amount = total_amount / stats['sub_customers'] if stats['sub_customers'] > 0 else 0
    
    metrics3 = [
        ("总数量", f"{total_quantity:,.0f}"),
        ("总金额", f"¥{total_amount:,.2f}"),
        ("平均交易金额", f"¥{avg_amount:,.2f}"),
        ("客单价", f"¥{avg_customer_amount:,.2f}")
    ]
    
    for col, (label, value) in zip(cols3, metrics3):
        with col:
            create_metric_card(label, value)

def render_customer_analysis():
    """渲染客户分析"""
    st.subheader("👥 客户分析")
    
    with get_connection() as conn:
        # 客户交易统计
        customer_stats = pd.read_sql_query('''
            SELECT 
                customer_name,
                COUNT(DISTINCT color) as product_colors,
                COUNT(*) as transaction_count,
                SUM(amount) as total_amount,
                AVG(unit_price) as avg_price
            FROM sales_records
            GROUP BY customer_name
            HAVING total_amount > 0
            ORDER BY total_amount DESC
            LIMIT 20
        ''', conn)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not customer_stats.empty:
            fig_customer_sales = px.bar(
                customer_stats.head(10), 
                x='customer_name', 
                y='total_amount',
                title="🏆 TOP10 客户销售额",
                color='total_amount', 
                color_continuous_scale="Tealgrn",
                labels={
                    'customer_name': '客户名称',
                    'total_amount': '销售额（￥）'
                }
            )
            fig_customer_sales.update_traces(
                hovertemplate='<b>%{x}</b><br>销售额: ¥%{y:,.2f}<extra></extra>'
            )
            fig_customer_sales.update_layout(
                template="plotly_white",
                xaxis_title="客户名称",
                yaxis_title="销售额（￥）",
                xaxis_tickangle=-30,
            )
            st.plotly_chart(fig_customer_sales, width='stretch')
        else:
            st.info("暂无客户交易数据")
    
    with col2:
        if not customer_stats.empty:
            fig_customer_products = px.scatter(
                customer_stats,
                x='total_amount', 
                y='product_colors',
                size='transaction_count', 
                color='avg_price',
                hover_name='customer_name',
                title='💬 客户销售额 vs 产品多样性',
                color_continuous_scale='Viridis',
                size_max=35,
                labels={
                    'total_amount': '销售额（￥）',
                    'product_colors': '产品颜色数',
                    'transaction_count': '交易次数',
                    'avg_price': '平均价格（￥）'
                }
            )
            fig_customer_products.update_layout(
                template="plotly_white",
                xaxis_title="销售额（￥）",
                yaxis_title="产品颜色数",
            )
            fig_customer_products.update_traces(
                hovertemplate='<b>%{hovertext}</b><br>' +
                            '销售额：¥%{x:,.2f}<br>' +
                            '产品颜色数：%{y}<br>' +
                            '交易次数：%{marker.size}<br>' +
                            '平均价格：¥%{marker.color:,.2f}<extra></extra>',
            )
            st.plotly_chart(fig_customer_products, width='stretch')
        else:
            st.info("暂无客户交易数据")
    
    return customer_stats

def render_product_analysis():
    """渲染产品分析"""
    st.subheader("🏺 产品分析")
    
    with get_connection() as conn:
        # 产品统计
        product_stats = pd.read_sql_query('''
            SELECT 
                CONCAT(product_name, ' - ', color) as product_info,
                product_name,
                color,
                CASE 
                    WHEN grade IS NULL OR grade = '' THEN '无等级'
                    ELSE grade 
                END as grade,
                COUNT(*) as transaction_count,
                AVG(unit_price) as avg_price,
                SUM(quantity) as total_quantity,
                SUM(amount) as total_amount
            FROM sales_records 
            GROUP BY product_name, color, grade
            HAVING total_amount > 0
            ORDER BY total_amount DESC
        ''', conn)

    if not product_stats.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            top_products = product_stats.nlargest(10, 'total_amount')
            fig_top_products = px.bar(
                top_products, 
                x='product_info',
                y='total_amount',
                color='grade', 
                title='🔥 热销产品TOP10 (按销售额)',
                labels={
                    'product_info': '产品名称 - 颜色',
                    'total_amount': '销售额（￥）',
                    'grade': '产品等级'
                },
            )
            fig_top_products.update_traces(
                hovertemplate='<b>%{x}</b><br>销售额: ¥%{y:,.2f}<extra></extra>'
            )
            fig_top_products.update_layout(
                template="plotly_white",
                xaxis_title="产品名称 - 颜色",
                yaxis_title="销售额（￥）",
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig_top_products, width='stretch')
        
        with col2:
            # 产品价格分布
            fig_product_price = px.box(
                product_stats, 
                x='product_info',
                y='avg_price',
                color='grade',
                title='📊 各产品价格分布',
                labels={
                    'product_info': '产品名称 - 颜色',
                    'avg_price': '平均价格（元）',
                    'grade': '产品等级'
                }
            )
            fig_product_price.update_traces(
                hovertemplate='<b>%{x}</b><br>平均价格: ¥%{y:.2f}<extra></extra>'
            )
            fig_product_price.update_layout(
                template="plotly_white",
                xaxis_title="产品名称 - 颜色",
                yaxis_title="平均价格（元）",
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig_product_price, width='stretch')
    
    return product_stats

def render_time_trend_analysis():
    """渲染时间趋势分析 - 优化中文月份显示"""
    st.subheader("📅 时间趋势分析")
    
    with get_connection() as conn:
        # 月度趋势
        monthly_trend = pd.read_sql_query('''
            SELECT 
                strftime('%Y-%m', record_date) as month,
                COUNT(*) as transaction_count,
                SUM(amount) as total_amount,
                AVG(unit_price) as avg_price,
                SUM(quantity) as total_quantity
            FROM sales_records
            GROUP BY strftime('%Y-%m', record_date)
            ORDER BY month
        ''', conn)
    
    if not monthly_trend.empty and len(monthly_trend) > 1:
        col1, col2 = st.columns(2)
        
        with col1:
            fig_trend = create_trend_comparison_chart(
                monthly_trend, 'total_amount', 'transaction_count',
                "📊 销售额 vs 交易量 时间对比趋势",
                primary_color="rgba(138, 92, 246, .85)", secondary_color='rgba(6, 214, 160, .7)'
            )
            if fig_trend:
                st.plotly_chart(fig_trend, width='stretch')
        
        with col2:
            fig_price_qty = create_trend_comparison_chart(
                monthly_trend, 'avg_price', 'total_quantity',
                "📦 平均单价 vs 销售数量 趋势变化",
                primary_color='rgba(239, 71, 111, .85)', secondary_color='rgba(17, 138, 178, .7)'
            )
            if fig_price_qty:
                st.plotly_chart(fig_price_qty, width='stretch')
        
        # 月度详细数据表格
        st.subheader("📈 月度详细数据")
        display_monthly = monthly_trend.copy()
        display_monthly['月份'] = display_monthly['month'].apply(format_chinese_month)
        display_monthly['交易次数'] = display_monthly['transaction_count']
        display_monthly['总金额'] = display_monthly['total_amount'].round(2)
        display_monthly['平均价格'] = display_monthly['avg_price'].round(2)
        display_monthly['总数量'] = display_monthly['total_quantity']
        
        st.dataframe(
            display_monthly[['月份', '交易次数', '总金额', '平均价格', '总数量']],
            width='stretch',
            hide_index=True
        )
        
        return monthly_trend
    else:
        st.info("暂无足够的时间趋势数据")
        return pd.DataFrame()

def render_total_analysis():
    """渲染总数分析选项卡"""
    try:
        stats = get_cached_total_stats()
        
        if stats['total_records'] == 0:
            st.warning("⚠️ 暂无数据，请先导入Excel文件")
            return
        
        # 关键指标概览
        st.subheader("📈 关键指标概览")
        render_total_metrics(stats)
        
        # 部门销售额分析
        st.markdown("---")
        st.subheader("🏢 部门销售额分析")
        
        with get_connection() as conn:
            dept_sales = pd.read_sql_query('''
                SELECT 
                    CASE 
                        WHEN department IS NULL OR department = '' THEN '未分类'
                        ELSE department 
                    END as department,
                    SUM(amount) as total_amount,
                    COUNT(*) as transaction_count,
                    AVG(unit_price) as avg_price
                FROM sales_records
                GROUP BY department
                ORDER BY total_amount DESC
            ''', conn)
        
        if not dept_sales.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig_dept_sales = create_bar_chart(
                    dept_sales, 'department', 'total_amount',
                    "🏢 各部门销售额对比",
                    x_label="部门", y_label="销售额"
                )
                fig_dept_sales.update_traces(
                    hovertemplate="部门：%{x}<br>销售额: ¥%{y:,.2f}<extra></extra>"
                )
                if fig_dept_sales:
                    st.plotly_chart(fig_dept_sales, width='stretch')
            
            with col2:
                fig_dept_pie = create_pie_chart(
                    dept_sales[dept_sales['department'] != '未分类'], 
                    'total_amount', 'department', "部门销售额占比"
                )
                if fig_dept_pie:
                    st.plotly_chart(fig_dept_pie, width='stretch')
        
        # 金额分析
        st.markdown("---")
        st.subheader("💰 金额分析")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with get_connection() as conn:
                monthly_amount = pd.read_sql_query('''
                    SELECT 
                        strftime('%Y-%m', record_date) as month,
                        SUM(amount) as total_amount,
                        COUNT(*) as transaction_count
                    FROM sales_records
                    WHERE amount > 0
                    GROUP BY strftime('%Y-%m', record_date)
                    ORDER BY month
                ''', conn)
            
            if not monthly_amount.empty:
                # 转换为中文月份
                monthly_amount = monthly_amount.copy()
                monthly_amount['month_chinese'] = monthly_amount['month'].apply(format_chinese_month)
                
                fig_monthly = px.line(
                    monthly_amount, x="month_chinese", y="total_amount",
                    title="📈 月度销售额趋势",
                    line_shape='spline', markers=True,
                    color_discrete_sequence=["#2563EB"]
                )
                fig_monthly.update_traces(
                    hovertemplate="月份: %{x}<br>销售额: ¥%{y:,.2f}<extra></extra>"
                )
                fig_monthly.update_layout(
                    template="plotly_white",
                    xaxis_title="月份",
                    yaxis_title="销售额 (¥)",
                )
                st.plotly_chart(fig_monthly, width='stretch')
            else:
                st.info("暂无月度趋势数据")
        
        with col2:
            with get_connection() as conn:
                color_sales = pd.read_sql_query('''
                    SELECT 
                        color,
                        SUM(amount) as total_amount,
                        COUNT(*) as transaction_count
                    FROM sales_records
                    WHERE amount > 0 AND color IS NOT NULL AND color != ''
                    GROUP BY color
                    ORDER BY total_amount DESC
                    LIMIT 10
                ''', conn)
            
            if not color_sales.empty:
                fig_color = create_bar_chart(
                    color_sales, 'color', 'total_amount',
                    "🎨 TOP10 产品颜色销售额",
                    x_label="产品颜色", y_label="销售额"
                )
                fig_color.update_traces(
                    hovertemplate="产品颜色：%{x}<br>销售额: ¥%{y:,.2f}<extra></extra>"
                )
                if fig_color:
                    st.plotly_chart(fig_color, width='stretch')
            else:
                st.info("暂无产品颜色销售数据")
        
        # 价格分布分析
        st.markdown("---")
        st.subheader("💎 价格区间分析")
        
        with get_connection() as conn:
            price_distribution = pd.read_sql_query('''
                SELECT 
                    CASE 
                        WHEN unit_price <= 0.5 THEN '0-0.5'
                        WHEN unit_price <= 1 THEN '0.5-1'
                        WHEN unit_price <= 1.5 THEN '1-1.5'
                        WHEN unit_price <= 2 THEN '1.5-2'
                        WHEN unit_price <= 3 THEN '2-3'
                        WHEN unit_price <= 5 THEN '3-5'
                        WHEN unit_price <= 10 THEN '5-10'
                        ELSE '10+'
                    END as price_range,
                    COUNT(*) as count,
                    AVG(unit_price) as avg_price,
                    SUM(amount) as total_amount
                FROM sales_records 
                WHERE unit_price > 0
                GROUP BY price_range
                ORDER BY MIN(unit_price)
            ''', conn)
        
        if not price_distribution.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig_price_dist = create_bar_chart(
                    price_distribution, 'price_range', 'count',
                    "📦 价格区间交易分布",
                    x_label="价格区间", y_label="交易数量"
                )
                fig_price_dist.update_traces(
                    hovertemplate="价格区间: %{x}<br>交易数量: %{y}<br>"
                )
                if fig_price_dist:
                    st.plotly_chart(fig_price_dist, width='stretch')
                    
                # 核心价格区间统计
                total_transactions = price_distribution['count'].sum()
                main_range_count = price_distribution[
                    price_distribution['price_range'].isin(['1-1.5', '1.5-2'])
                ]['count'].sum()
                main_range_percentage = (main_range_count / total_transactions) * 100
                
                st.metric("核心价格区间(1-2元)占比", f"{main_range_percentage:.1f}%", 
                         delta=f"{main_range_count}笔交易")
            
            with col2:
                # 组合图表
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=price_distribution['price_range'], 
                    y=price_distribution['count'],
                    name="交易数量",
                    marker_color='#1f77b4',
                    opacity=0.85,
                    hovertemplate='价格区间: %{x}<br>交易数量: %{y}<extra></extra>',
                ))
                fig.add_trace(go.Scatter(
                    x=price_distribution['price_range'], 
                    y=price_distribution['avg_price'],
                    name="平均价格",
                    line_shape='spline', 
                    mode='lines+markers',
                    line=dict(color='#ff7f0e', width=3),
                    yaxis='y2',
                    hovertemplate='价格区间: %{x}<br>平均价格: ¥%{y:.2f}<extra></extra>'
                ))
                fig.update_layout(
                    title="📈 价格分布与平均价格趋势",
                    template="plotly_white",
                    xaxis_title='价格区间',
                    yaxis=dict(title="交易数量"),
                    yaxis2=dict(title="平均价格（￥）", overlaying='y', side='right', showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig, width='stretch')
                # 添加价格集中度分析
                st.markdown("**价格集中度分析**")
                
                # 计算价格分布的统计指标
                max_count_range = price_distribution.loc[price_distribution['count'].idxmax()]
                col_21, col_22 = st.columns(2)
                with col_21:
                    st.write(f"• **最密集区间**: ￥{max_count_range['price_range']} ({max_count_range['count']}笔)")
        
        # 客户分析
        st.markdown("---")
        customer_stats = render_customer_analysis()
        
        # 产品分析
        st.markdown("---")
        product_stats = render_product_analysis()
        
        # 时间趋势分析
        st.markdown("---")
        monthly_trend = render_time_trend_analysis()
        
        # 数据导出
        st.markdown("---")
        st.subheader("💾 数据导出")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 导出客户统计（中文表头）
            if not customer_stats.empty:
                export_customer = customer_stats.copy()
                export_customer = export_customer.rename(columns={
                    'customer_name': '客户名称',
                    'product_colors': '产品颜色数',
                    'transaction_count': '交易次数',
                    'total_amount': '总金额',
                    'avg_price': '平均价格'
                })
                csv_customer = export_customer.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    "📥 导出客户统计",
                    csv_customer,
                    "客户统计.csv",
                    "text/csv",
                    width='stretch'
                )
            else:
                st.info("暂无客户数据")
        
        with col2:
            # 导出产品统计（中文表头）
            if not product_stats.empty:
                export_product = product_stats.copy()
                export_product = export_product.rename(columns={
                    'product_info': '产品信息',
                    'product_name': '产品名称',
                    'color': '颜色',
                    'grade': '等级',
                    'transaction_count': '交易次数',
                    'avg_price': '平均价格',
                    'total_quantity': '总数量',
                    'total_amount': '总金额'
                })
                csv_product = export_product.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    "📥 导出产品统计", 
                    csv_product,
                    "产品统计.csv",
                    "text/csv",
                    width='stretch'
                )
            else:
                st.info("暂无产品数据")
        
        with col3:
            # 导出月度趋势（中文表头）
            if not monthly_trend.empty:
                export_monthly = monthly_trend.copy()
                export_monthly = export_monthly.rename(columns={
                    'month': '月份',
                    'transaction_count': '交易次数',
                    'total_amount': '总金额',
                    'avg_price': '平均价格',
                    'total_quantity': '总数量'
                })
                csv_monthly = export_monthly.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    "📥 导出月度趋势",
                    csv_monthly,
                    "月度趋势.csv",
                    "text/csv", 
                    width='stretch'
                )
            else:
                st.info("暂无月度数据")
                
    except Exception as e:
        st.error(f"获取统计数据时出错: {str(e)}")
        st.info("请确保已正确导入数据并初始化数据库")

# ==================== 主页面布局 ====================

# 获取部门列表用于动态生成选项卡
@st.cache_data(ttl=60)
def get_department_list():
    """获取所有部门列表"""
    with get_connection() as conn:
        dept_list = pd.read_sql_query('''
            SELECT DISTINCT department
            FROM sales_records
            WHERE department IS NOT NULL AND department != ''
            ORDER BY department
        ''', conn)
        return dept_list['department'].tolist() if not dept_list.empty else []

# 创建选项卡
departments = get_department_list()
tab_names = ["总数分析"] + departments
tabs = st.tabs(tab_names)

with tabs[0]:
    render_total_analysis()

# 为每个部门创建分析选项卡
for i, department in enumerate(departments, 1):
    if i < len(tabs):  # 确保索引不越界
        with tabs[i]:
            create_department_analysis_tab(department)

# 使用说明
with st.expander("📚 使用说明", expanded=False):
    st.markdown("""
    ### 数据统计页面说明
    
    **功能概述**
    - 提供全面的数据分析和可视化
    - 从多个维度分析业务数据
    - 支持数据导出和深入分析
    
    **分析维度**
    1. **部门概览** - 基于department字段的部门分类统计
    2. **总数分析** - 整体业务数据概览
    3. **部门分析** - 各部门的详细数据分析
    
    **时间维度分析**
    - 月度销售额趋势分析
    - 交易量与销售额对比
    - 平均单价与销售数量趋势
    - 时间序列数据导出
    
    **使用技巧**
    - 关注关键指标的异常变化
    - 通过图表识别业务模式和趋势
    - 导出数据用于进一步分析和报告制作
    - 定期查看时间趋势了解业务发展
    
    **数据说明**
    - 部门字段(department)已替代原有的生产线分类逻辑
    - 确保导入数据时填写正确的部门信息
    - 未分类的数据会单独显示，便于数据清理
    """)
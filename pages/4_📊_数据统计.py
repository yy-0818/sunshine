import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.analysis_service import AnalysisService
from core.database import get_connection

st.set_page_config(page_title="数据统计", layout="wide")
st.title("📊 数据统计分析")

analysis_service = AnalysisService()

# 获取基础统计数据
try:
    stats = analysis_service.get_statistics()
    
    if stats['total_records'] == 0:
        st.warning("⚠️ 暂无数据，请先导入Excel文件")
    else:
        # 关键指标概览
        st.subheader("📈 关键指标概览")
        
        # 第一行指标
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总记录数", stats['total_records'])
        with col2:
            st.metric("唯一客户", stats['unique_customers'])
        with col3:
            st.metric("子客户数", stats['sub_customers'])
        with col4:
            st.metric("产品颜色数", stats['unique_colors'])
        
        # 第二行指标
        col5, col6, col7, col8 = st.columns(4)
        with col5:
            st.metric("产品等级数", stats['unique_grades'])
        with col6:
            min_price = stats.get('min_price', 0)
            st.metric("最低价格", f"¥{min_price:.2f}")
        with col7:
            max_price = stats.get('max_price', 0)
            st.metric("最高价格", f"¥{max_price:.2f}")
        with col8:
            avg_price = stats.get('avg_price', 0)
            st.metric("平均价格", f"¥{avg_price:.2f}")
        
        # 第三行指标
        col9, col10, col11, col12 = st.columns(4)
        with col9:
            total_quantity = stats.get('total_quantity', 0)
            st.metric("总数量", f"{total_quantity:,.0f}")
        with col10:
            total_amount = stats.get('total_amount', 0)
            st.metric("总金额", f"¥{total_amount:,.2f}")
        with col11:
            # 计算平均交易金额
            avg_amount = total_amount / stats['total_records'] if stats['total_records'] > 0 else 0
            st.metric("平均交易金额", f"¥{avg_amount:,.2f}")
        with col12:
            # 计算客单价
            avg_customer_amount = total_amount / stats['unique_customers'] if stats['unique_customers'] > 0 else 0
            st.metric("客单价", f"¥{avg_customer_amount:,.2f}")
        
        # 金额分析
        st.markdown("---")
        st.subheader("💰 金额分析")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 月度金额趋势
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
                fig_monthly = px.line(
                    monthly_amount, x="month", y="total_amount",
                    title="📈 月度销售额趋势",
                    line_shape='spline', 
                    markers=True,
                    color_discrete_sequence=["#2563EB"]
                )
                fig_monthly.update_traces(hovertemplate="月份: %{x}<br>销售额: ¥%{y:,.2f}")
                fig_monthly.update_layout(
                    template="plotly_white",
                    yaxis_title="销售额 (¥)",
                    xaxis_title="月份",
                    title_font=dict(size=18)
                )
                st.plotly_chart(fig_monthly, use_container_width=True)
            else:
                st.info("暂无月度趋势数据")
        
        with col2:
            # 产品颜色销售额分布
            with get_connection() as conn:
                color_sales = pd.read_sql_query('''
                    SELECT 
                        color,
                        SUM(amount) as total_amount,
                        COUNT(*) as transaction_count
                    FROM sales_records
                    WHERE amount > 0
                    GROUP BY color
                    ORDER BY total_amount DESC
                    LIMIT 10
                ''', conn)
            
            if not color_sales.empty:
                fig_color = px.bar(
                    color_sales, x='color', y='total_amount',
                    title="🎨 TOP10 产品颜色销售额",
                    color='total_amount',
                    labels={
                        'color': '产品颜色',
                        'total_amount': '销售额（￥）'
                    }
                )
                fig_color.update_layout(template="plotly_white", xaxis_tickangle=-30,xaxis_title='产品颜色',yaxis_title='销售额（元）')
                st.plotly_chart(fig_color, use_container_width=True)
            else:
                st.info("暂无产品颜色销售数据")
        
        # 价格分布分析
        st.markdown("---")
        st.subheader("💎 价格区间分析")
        
        # 获取价格分布数据
        with get_connection() as conn:
            price_distribution = pd.read_sql_query('''
                SELECT 
                    CASE 
                        WHEN unit_price <= 1 THEN '0-1'
                        WHEN unit_price <= 2 THEN '1-2'
                        WHEN unit_price <= 5 THEN '2-5'
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
        
        col1, col2 = st.columns(2)
        
        with col1:
            if not price_distribution.empty:
                fig_price_dist = px.bar(
                    price_distribution, x='price_range', y='count',
                    title="📦 价格区间交易分布",
                    color='count', color_continuous_scale="Viridis",
                    labels={
                        'price_range': '价格区间',
                        'count': '交易数量'
                    }
                )
                fig_price_dist.update_layout(template="plotly_white",xaxis_title='价格区间',yaxis_title='交易数量')
                st.plotly_chart(fig_price_dist, use_container_width=True)
            else:
                st.info("暂无价格分布数据")
        
        with col2:
            if not price_distribution.empty:
                fig_price_avg = px.line(price_distribution,x='price_range',y='avg_price',title='📈各价格区间平均价格',markers=True,
                    labels={
                        'price_range': '价格区间',
                        'avg_price': '平均价格（元）'
                    }
                )
                fig_price_avg.update_traces(line=dict(color='#FFA726', width=3), marker=dict(size=8, symbol='circle'))
                fig_price_avg.update_layout(template="plotly_white", xaxis_title='价格区间', yaxis_title='平均价格（元）', hovermode='x unified', showlegend=False
                )
                st.plotly_chart(fig_price_avg, use_container_width=True)
            else:
                st.info("暂无价格分布数据")
        
        # 客户分析
        st.markdown("---")
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
                fig_customer_sales.update_layout(
                    template="plotly_white",
                    xaxis_tickangle=-30,
                    xaxis_title='客户名称',
                    yaxis_title='销售额（￥）',
                    # hovermode='x',
                )
                fig_customer_sales.update_traces(
                    hovertemplate='<b>%{x}</b><br>销售额：¥%{y:,.2f}<extra></extra>',
                    marker_line_width=1,
                )
                st.plotly_chart(fig_customer_sales, use_container_width=True)

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
                    size_max=30,
                    labels={
                        'total_amount': '销售额（￥）',
                        'product_colors': '产品颜色数',
                        'transaction_count': '交易次数',
                        'avg_price': '平均价格（￥）'
                    }
                )
                fig_customer_products.update_layout(
                    template="plotly_white",
                    xaxis_title='销售额（￥）',
                    yaxis_title='产品颜色数',
                )
                fig_customer_products.update_traces(
                    hovertemplate='<b>%{hovertext}</b><br>' +
                                '销售额：¥%{x:,.2f}<br>' +
                                '产品颜色数：%{y}<br>' +
                                '交易次数：%{marker.size}<br>' +
                                '平均价格：¥%{marker.color:,.2f}<extra></extra>',
                )
                st.plotly_chart(fig_customer_products, use_container_width=True)

            else:
                st.info("暂无客户交易数据")
        
        # 产品分析
        st.markdown("---")
        st.subheader("🏺 产品分析")
        
        with get_connection() as conn:
            # 产品统计
            product_stats = pd.read_sql_query('''
                SELECT 
                    color,
                    COALESCE(grade, '无等级') as grade,
                    COUNT(*) as transaction_count,
                    AVG(unit_price) as avg_price,
                    SUM(quantity) as total_quantity,
                    SUM(amount) as total_amount
                FROM sales_records 
                GROUP BY color, grade
                HAVING total_amount > 0
                ORDER BY total_amount DESC
            ''', conn)
        
        if not product_stats.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                top_products = product_stats.nlargest(10, 'total_amount')
                fig_top_products = px.bar(
                    top_products, 
                    x='color', 
                    y='total_amount',
                    color='grade', 
                    title='🔥 热销产品TOP10 (按销售额)',
                    labels={
                        'color': '产品颜色',
                        'total_amount': '销售额（￥）',
                        'grade': '产品等级'
                    },
                )
                fig_top_products.update_layout(
                    template="plotly_white",
                    xaxis_tickangle=-45,
                    xaxis_title='产品颜色',
                    yaxis_title='销售额（￥）',
                    showlegend=True,
                    legend=dict(
                        title="产品等级",
                        yanchor="top",
                        y=0.99,
                        xanchor="right",
                        x=0.99
                    ),
                    margin=dict(l=50, r=50, t=50, b=100),
                )
                fig_top_products.update_traces(
                    hovertemplate='<b>%{x}</b><br>销售额：¥%{y:,.2f}<br>等级：%{fullData.name}<extra></extra>'
                )
                st.plotly_chart(fig_top_products, use_container_width=True)
            
            with col2:
                # 产品价格分布
                fig_product_price = px.box(
                    product_stats, 
                    x='color', 
                    y='avg_price',
                    title='📊 各产品颜色价格分布',
                    labels={
                        'color': '产品颜色',
                        'avg_price': '平均价格（元）'
                    }
                )

                # 完全重写悬停信息
                fig_product_price.update_traces(
                    hoverinfo='none',  # 禁用默认悬停信息
                    selector=dict(type='box')
                )

                # 添加自定义悬停文本
                fig_product_price.add_trace(
                    go.Scatter(
                        x=product_stats['color'],
                        y=product_stats['avg_price'],
                        mode='markers',
                        marker=dict(
                            opacity=0,
                            size=0
                        ),
                        hovertemplate='<b>%{x}</b><br>平均价格：¥%{y:,.2f}<extra></extra>'
                    )
                )

                fig_product_price.update_layout(
                    template="plotly_white",
                    xaxis_tickangle=-45,
                    xaxis_title='产品颜色',
                    yaxis_title='平均价格（元）',
                    showlegend=False,
                    margin=dict(l=50, r=50, t=50, b=100),
                    plot_bgcolor='rgba(0,0,0,0)'
                )

                st.plotly_chart(fig_product_price, use_container_width=True)

        
        # 时间趋势分析
        st.markdown("---")
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
                # 月度销售额趋势
                st.markdown("#### 📈 销售额、交易量、均价多维趋势")
                fig_trend = go.Figure()

                # 销售额趋势（主轴）
                fig_trend.add_trace(go.Scatter(
                    x=monthly_trend['month'],
                    y=monthly_trend['total_amount'],
                    name='销售额 (¥)',
                    line=dict(color='#2563EB', width=3),
                    line_shape='spline',
                    marker=dict(size=6),
                    fill='tozeroy',
                    fillcolor='rgba(37,99,235,0.1)',
                    hovertemplate='月份: %{x}<br>销售额: ¥%{y:,.2f}'
                ))

                # 交易次数趋势（次轴）
                fig_trend.add_trace(go.Bar(
                    x=monthly_trend['month'],
                    y=monthly_trend['transaction_count'],
                    name='交易次数',
                    marker_color='rgba(16,185,129,0.6)',
                    yaxis='y2',
                    hovertemplate='<br>月份: %{x}</br><br>交易次数: %{y:,}<extra></extra>'
                ))

                # 图表布局
                fig_trend.update_layout(
                    title="📊 销售额 vs 交易量 时间对比趋势",
                    template="plotly_white",
                    xaxis=dict(title="月份"),
                    yaxis=dict(title="销售额 (¥)", side='left', showgrid=False),
                    yaxis2=dict(title="交易次数", overlaying='y', side='right', showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )

                st.plotly_chart(fig_trend, use_container_width=True)
            
            with col2:
                # 月度交易量趋势
                st.markdown("#### 💹 平均单价与销售数量趋势")
                fig_price_qty = go.Figure()

                fig_price_qty.add_trace(go.Scatter(
                    x=monthly_trend['month'],
                    y=monthly_trend['avg_price'],
                    name='平均单价 (¥)',
                    line_shape='spline',
                    line=dict(color='#F97316', width=3, dash='dot'),
                    marker=dict(size=7, symbol='circle'),
                    hovertemplate='月份: %{x}<br>平均单价: ¥%{y:,.2f}'
                ))

                fig_price_qty.add_trace(go.Bar(
                    x=monthly_trend['month'],
                    y=monthly_trend['total_quantity'],
                    name='销售数量',
                    marker_color='rgba(59,130,246,0.3)',
                    yaxis='y2',
                    hovertemplate='<b>月份: %{x}</b><br>销售数量: %{y:,}<extra></extra>'
                ))

                fig_price_qty.update_layout(
                    title="📦 平均单价 vs 销售数量 趋势变化",
                    template="plotly_white",
                    xaxis_title="月份",
                    yaxis=dict(title="平均单价 (¥)"),
                    yaxis2=dict(title="销售数量", overlaying='y', side='right', showgrid=False),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )

                st.plotly_chart(fig_price_qty, use_container_width=True)
            
            # 月度详细数据
            st.markdown("#### 📈 月度详细数据")
            display_monthly = monthly_trend.rename(columns={
                'month': '月份',
                'transaction_count': '交易次数',
                'total_amount': '总金额',
                'avg_price': '平均价格',
                'total_quantity': '总数量'
            })
            st.dataframe(display_monthly.round(2), use_container_width=True)
        else:
            st.info("暂无足够的时间趋势数据")

        # 计算最近三个月变化
        if len(monthly_trend) >= 3:
            recent = monthly_trend.tail(3)
            diff_amount = recent.iloc[-1]['total_amount'] - recent.iloc[0]['total_amount']
            pct_change = (diff_amount / recent.iloc[0]['total_amount']) * 100 if recent.iloc[0]['total_amount'] else 0

            if pct_change > 10:
                trend_text = f"📈 最近三个月销售额持续上升，增长约 **{pct_change:.1f}%**，业务保持良好增长态势。"
            elif pct_change < -10:
                trend_text = f"📉 最近三个月销售额下降约 **{abs(pct_change):.1f}%**，建议关注市场变化或客户流失。"
            else:
                trend_text = f"⚖️ 最近三个月销售额波动较小，整体保持稳定。"
        else:
            trend_text = "📊 当前数据不足以进行趋势对比分析。"

        st.info(trend_text)
        
        # 数据导出
        st.markdown("---")
        st.subheader("💾 数据导出")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 导出客户统计
            if not customer_stats.empty:
                csv_customer = customer_stats.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 导出客户统计",
                    csv_customer,
                    "customer_statistics.csv",
                    "text/csv",
                    use_container_width=True
                )
        
        with col2:
            # 导出产品统计
            if not product_stats.empty:
                csv_product = product_stats.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 导出产品统计", 
                    csv_product,
                    "product_statistics.csv",
                    "text/csv",
                    use_container_width=True
                )
        
        with col3:
            # 导出月度趋势
            if not monthly_trend.empty:
                csv_monthly = monthly_trend.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 导出月度趋势",
                    csv_monthly,
                    "monthly_trend.csv",
                    "text/csv", 
                    use_container_width=True
                )

except Exception as e:
    st.error(f"获取统计数据时出错: {str(e)}")
    st.info("请确保已正确导入数据并初始化数据库")

# 使用说明
with st.expander("📚 使用说明", expanded=False):
    st.markdown("""
    ### 数据统计页面说明
    
    **功能概述**
    - 提供全面的数据分析和可视化
    - 从多个维度分析业务数据
    - 支持数据导出和深入分析
    
    **分析维度**
    1. **关键指标** - 核心业务指标概览
    2. **金额分析** - 销售趋势和产品分布
    3. **价格分布** - 产品价格区间分析
    4. **客户分析** - 客户交易行为和价值分析
    5. **产品分析** - 产品销售和价格分析
    6. **时间趋势** - 业务发展时间趋势分析
    
    **数据要求**
    - 需要导入包含完整交易记录的Excel数据
    - 数据应包含金额、数量、价格等数值字段
    - 建议数据量足够大以获得有意义的分析结果
    
    **使用技巧**
    - 关注关键指标的异常变化
    - 通过图表识别业务模式和趋势
    - 导出数据用于进一步分析和报告制作
    - 定期查看时间趋势了解业务发展
    """)
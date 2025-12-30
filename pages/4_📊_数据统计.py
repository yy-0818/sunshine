import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
from core.database import get_connection
from utils.auth import require_login

# 页面配置
st.logo(
    image='./assets/logo.png',
    icon_image='./assets/logo.png',
)

st.set_page_config(
    page_title="数据统计仪表板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 数据统计分析仪表板")

require_login()

# 现代商业配色方案
COLOR_SCHEME = {
    'primary': ['#4f46e5', '#7c3aed', '#a855f7', '#d946ef'],  # 紫色系
    'success': ['#10b981', '#34d399', '#6ee7b7', '#a7f3d0'],  # 绿色系
    'warning': ['#f59e0b', '#fbbf24', '#fcd34d', '#fde68a'],  # 橙色系
    'danger': ['#ef4444', '#f87171', '#fca5a5', '#fecaca'],   # 红色系
    'neutral': ['#6b7280', '#9ca3af', '#d1d5db', '#e5e7eb'],  # 灰色系
    'sequential': ['#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe']  # 蓝色渐变
}

# ==================== 优化的缓存函数 ====================
@st.cache_data(ttl=300)
def get_available_years():
    """获取数据中存在的年份列表"""
    try:
        with get_connection() as conn:
            df = pd.read_sql_query('''
                SELECT year
                FROM (
                    SELECT DISTINCT CAST(strftime('%Y', record_date) as INTEGER) as year
                    FROM sales_records
                    WHERE record_date IS NOT NULL
                    AND record_date != ''
                )
                ORDER BY year DESC
            ''', conn)
        years = df['year'].dropna().astype(int).tolist()
        return ['全部年份'] + [str(year) for year in years]
    except Exception as e:
        st.error(f"获取年份列表失败: {str(e)}")
        return ['全部年份']

@st.cache_data(ttl=300)
def get_department_list(year_filter):
    """获取部门列表"""
    try:
        with get_connection() as conn:
            if year_filter != "全部年份":
                query = '''
                    SELECT DISTINCT department
                    FROM sales_records
                    WHERE strftime('%Y', record_date) = ? 
                        AND department IS NOT NULL 
                        AND department != ''
                    ORDER BY department
                '''
                params = [year_filter]
            else:
                query = '''
                    SELECT DISTINCT department
                    FROM sales_records
                    WHERE department IS NOT NULL AND department != ''
                    ORDER BY department
                '''
                params = []
            
            dept_list = pd.read_sql_query(query, conn, params=params)
            return dept_list['department'].tolist() if not dept_list.empty else []
    except Exception as e:
        st.error(f"获取部门列表失败: {str(e)}")
        return []

@st.cache_data(ttl=300, show_spinner="正在加载统计数据...")
def get_cached_total_stats(year_filter):
    """缓存总数统计数据"""
    try:
        with get_connection() as conn:
            year_condition = ""
            params = []
            
            if year_filter != "全部年份":
                year_condition = "WHERE strftime('%Y', record_date) = ?"
                params = [year_filter]
            
            # 使用单个查询获取所有统计数据
            base_query = f'''
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT customer_name) as unique_customers,
                    COUNT(DISTINCT product_name) as unique_products,
                    COUNT(DISTINCT color) as unique_colors,
                    COUNT(DISTINCT grade) as unique_grades,
                    COALESCE(SUM(quantity), 0) as total_quantity,
                    COALESCE(SUM(amount), 0) as total_amount,
                    COALESCE(MIN(unit_price), 0) as min_price,
                    COALESCE(MAX(unit_price), 0) as max_price,
                    COALESCE(AVG(unit_price), 0) as avg_price,
                    MIN(record_date) as earliest_date,
                    MAX(record_date) as latest_date
                FROM sales_records
                {year_condition}
            '''
            
            stats_df = pd.read_sql_query(base_query, conn, params=params)
            
            if stats_df.empty:
                return get_default_stats()
            
            stats = stats_df.iloc[0].to_dict()
            
            # 添加日期范围
            stats['date_range'] = {
                'start': stats.get('earliest_date'),
                'end': stats.get('latest_date')
            }
            
            # 计算衍生指标
            total_records = stats['total_records'] or 0
            total_amount = stats['total_amount'] or 0
            
            # 只保留交易均额
            stats['avg_transaction_amount'] = total_amount / total_records if total_records > 0 else 0
            
            return stats
    except Exception as e:
        st.error(f"加载总数统计失败: {str(e)}")
        return get_default_stats()

def get_default_stats():
    """返回默认统计数据"""
    return {
        'total_records': 0,
        'unique_customers': 0,
        'unique_products': 0,
        'unique_colors': 0,
        'unique_grades': 0,
        'total_quantity': 0,
        'total_amount': 0,
        'min_price': 0,
        'max_price': 0,
        'avg_price': 0,
        'avg_transaction_amount': 0,
        'date_range': {'start': None, 'end': None}
    }

@st.cache_data(ttl=300)
def get_cached_department_stats(year_filter):
    """缓存部门统计数据"""
    try:
        with get_connection() as conn:
            year_condition = ""
            params = []
            if year_filter != "全部年份":
                year_condition = "WHERE strftime('%Y', record_date) = ?"
                params = [year_filter]
            
            dept_stats_query = f'''
                SELECT 
                    COALESCE(NULLIF(department, ''), '未分类') as department,
                    COUNT(*) as record_count,
                    ROUND(SUM(amount), 2) as total_amount,
                    SUM(quantity) as total_quantity,
                    ROUND(AVG(unit_price), 2) as avg_price
                FROM sales_records
                {year_condition}
                GROUP BY COALESCE(NULLIF(department, ''), '未分类')
                ORDER BY total_amount DESC
            '''
            dept_stats = pd.read_sql_query(dept_stats_query, conn, params=params)
            
            return {
                'department_stats': dept_stats.to_dict('records'),
                'total_records': int(dept_stats['record_count'].sum()) if not dept_stats.empty else 0,
                'classified_records': int(dept_stats[dept_stats['department'] != '未分类']['record_count'].sum()) 
                                     if not dept_stats.empty else 0,
                'unclassified_records': int(dept_stats[dept_stats['department'] == '未分类']['record_count'].sum()) 
                                       if not dept_stats.empty else 0
            }
    except Exception as e:
        st.error(f"加载部门统计失败: {str(e)}")
        return {'department_stats': [], 'total_records': 0, 'classified_records': 0, 'unclassified_records': 0}

@st.cache_data(ttl=300)
def get_cached_department_stats_detail(department, year_filter):
    """获取部门详细统计"""
    try:
        with get_connection() as conn:
            year_condition = ""
            params = [department]
            
            if year_filter != "全部年份":
                year_condition = "AND strftime('%Y', record_date) = ?"
                params.append(year_filter)
            
            query = f'''
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT customer_name) as customer_count,
                    COUNT(DISTINCT product_name) as product_count,
                    COUNT(DISTINCT color) as color_count,
                    COALESCE(SUM(quantity), 0) as total_quantity,
                    COALESCE(SUM(amount), 0) as total_amount,
                    COALESCE(AVG(unit_price), 0) as avg_price,
                    MIN(record_date) as earliest_date,
                    MAX(record_date) as latest_date
                FROM sales_records
                WHERE department = ? {year_condition}
            '''
            
            result = pd.read_sql_query(query, conn, params=params)
            
            if result.empty:
                return {
                    'total_records': 0,
                    'customer_count': 0,
                    'product_count': 0,
                    'color_count': 0,
                    'total_quantity': 0,
                    'total_amount': 0,
                    'avg_price': 0,
                    'date_range': {'start': None, 'end': None}
                }
            
            row = result.iloc[0]
            return {
                'total_records': int(row['total_records']),
                'customer_count': int(row['customer_count']),
                'product_count': int(row['product_count']),
                'color_count': int(row['color_count']),
                'total_quantity': int(row['total_quantity']),
                'total_amount': float(row['total_amount']),
                'avg_price': float(row['avg_price']),
                'date_range': {
                    'start': row['earliest_date'],
                    'end': row['latest_date']
                }
            }
    except Exception as e:
        st.error(f"加载部门详细统计失败: {str(e)}")
        return {
            'total_records': 0,
            'customer_count': 0,
            'product_count': 0,
            'color_count': 0,
            'total_quantity': 0,
            'total_amount': 0,
            'avg_price': 0,
            'date_range': {'start': None, 'end': None}
        }

@st.cache_data(ttl=300)
def get_cached_production_line_data(department, year_filter):
    """获取部门生产线数据"""
    try:
        with get_connection() as conn:
            year_condition = ""
            params = [department]
            
            if year_filter != "全部年份":
                year_condition = "AND strftime('%Y', record_date) = ?"
                params.append(year_filter)
            
            query = f'''
                SELECT 
                    production_line,
                    COUNT(*) as record_count,
                    SUM(amount) as total_amount,
                    SUM(quantity) as total_quantity,
                    AVG(unit_price) as avg_price
                FROM sales_records
                WHERE department = ? {year_condition}
                GROUP BY production_line
                HAVING record_count > 0
                ORDER BY record_count DESC
                LIMIT 20
            '''
            
            df = pd.read_sql_query(query, conn, params=params)
            return df
    except Exception as e:
        st.error(f"获取生产线数据失败: {str(e)}")
        return pd.DataFrame()

# ==================== ECharts图表函数 ====================
def format_chinese_month(month_str):
    """将YYYY-MM格式转换为中文月份格式"""
    try:
        year, month = month_str.split('-')
        month_names = ['一月', '二月', '三月', '四月', '五月', '六月', 
                      '七月', '八月', '九月', '十月', '十一月', '十二月']
        return f"{year}年{month_names[int(month)-1]}"
    except:
        return month_str

def create_echarts_line_bar_mix(monthly_data, title, primary_col, secondary_col, 
                               primary_name="销售额", secondary_name="交易次数"):
    """创建ECharts混合图表（折线+柱状）"""
    if monthly_data.empty or len(monthly_data) <= 1:
        return None
    
    monthly_data = monthly_data.copy()
    months = [format_chinese_month(m) for m in monthly_data['month'].tolist()]
    
    option = {
        "title": {
            "text": title,
            "left": "center",
            "textStyle": {
                "fontSize": 16,
                "fontWeight": "bold",
                "color": "#1f2937"
            }
        },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {
                "type": "cross",
                "crossStyle": {
                    "color": "#999"
                }
            }
        },
        "toolbox": {
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "magicType": {"show": True, "type": ["line", "bar"]},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "legend": {
            "data": [primary_name, secondary_name],
            "top": 30,
            "textStyle": {
                "fontSize": 12
            }
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "3%",
            "top": "15%",
            "containLabel": True
        },
        "xAxis": [
            {
                "type": "category",
                "data": months,
                "axisPointer": {
                    "type": "shadow"
                },
                "axisLabel": {
                    "rotate": 45,
                    "fontSize": 11
                }
            }
        ],
        "yAxis": [
            {
                "type": "value",
                "name": primary_name,
                "min": 0,
                "position": "left",
                "axisLine": {
                    "show": True,
                    "lineStyle": {
                        "color": COLOR_SCHEME['primary'][0]
                    }
                },
                "axisLabel": {
                    "formatter": "¥{value}"
                }
            },
            {
                "type": "value",
                "name": secondary_name,
                "min": 0,
                "position": "right",
                "axisLine": {
                    "show": True,
                    "lineStyle": {
                        "color": COLOR_SCHEME['success'][0]
                    }
                },
                "splitLine": {
                    "show": False
                }
            }
        ],
        "series": [
            {
                "name": primary_name,
                "type": "line",
                "yAxisIndex": 0,
                "data": monthly_data[primary_col].round(2).tolist(),
                "itemStyle": {
                    "color": COLOR_SCHEME['primary'][0]
                },
                "lineStyle": {
                    "width": 3
                },
                "symbolSize": 8,
                "smooth": True,
                "emphasis": {
                    "focus": "series"
                }
            },
            {
                "name": secondary_name,
                "type": "bar",
                "yAxisIndex": 1,
                "data": monthly_data[secondary_col].astype(int).tolist(),
                "itemStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0,
                        "y": 0,
                        "x2": 0,
                        "y2": 1,
                        "colorStops": [{
                            "offset": 0,
                            "color": COLOR_SCHEME['success'][0]
                        }, {
                            "offset": 1,
                            "color": COLOR_SCHEME['success'][2]
                        }]
                    }
                },
                "emphasis": {
                    "focus": "series"
                }
            }
        ],
        "dataZoom": [
            {
                "type": "inside",
                "start": 0,
                "end": 100
            },
            {
                "show": True,
                "type": "slider",
                "top": "90%",
                "start": 0,
                "end": 100
            }
        ]
    }
    
    return option

def create_echarts_pie_chart(data, value_col, name_col, title, radius=['40%', '70%']):
    """创建ECharts饼图"""
    if data.empty:
        return None
    
    chart_data = []
    for _, row in data.iterrows():
        chart_data.append({
            "value": float(row[value_col]),
            "name": str(row[name_col])
        })
    
    option = {
        # "title": {
        #     "text": title,
        #     "left": "center",
        #     "textStyle": {
        #         "fontSize": 16,
        #         "fontWeight": "bold"
        #     }
        # },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ¥{c} ({d}%)"
        },
        "legend": {
            "orient": "vertical",
            "right": "right",
            "top": "middle"
        },
        "series": [
            {
                "name": title,
                "type": "pie",
                "radius": radius,
                "data": chart_data,
                "emphasis": {
                    "itemStyle": {
                        "shadowBlur": 10,
                        "shadowOffsetX": 0,
                        "shadowColor": "rgba(0, 0, 0, 0.5)"
                    }
                },
                "itemStyle": {
                    "borderRadius": 8,
                    "borderColor": "#fff",
                    "borderWidth": 2
                },
                "label": {
                    "formatter": "{b}: {d}%"
                    # "show": False,
                }
            }
        ]
    }
    
    return option

def create_echarts_bar_chart(data, x_col, y_col, title, color_scheme='primary'):
    """创建ECharts柱状图"""
    if data.empty:
        return None
    
    x_data = data[x_col].tolist()
    y_data = data[y_col].round(2).tolist()
    
    option = {
        # "title": {
        #     "text": title,
        #     "left": "center",
        #     "textStyle": {
        #         "fontSize": 16,
        #         "fontWeight": "bold"
        #     }
        # },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {
                "type": "shadow"
            },
            "formatter": "{b}: {c}"
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "3%",
            "top": "15%",
            "containLabel": True
        },
        "xAxis": {
            "type": "category",
            "data": x_data,
            "axisTick": {
                "alignWithLabel": True
            },
            "axisLabel": {
                "rotate": 45,
                "fontSize": 10
            }
        },
        "yAxis": {
            "type": "value",
            "name": "",
            "axisLine": {
                "show": True
            }
        },
        "series": [
            {
                "name": title,
                "type": "bar",
                "barWidth": "60%",
                "data": y_data,
                "itemStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0,
                        "y": 0,
                        "x2": 0,
                        "y2": 1,
                        "colorStops": [{
                            "offset": 0,
                            "color": COLOR_SCHEME[color_scheme][0]
                        }, {
                            "offset": 1,
                            "color": COLOR_SCHEME[color_scheme][2]
                        }]
                    }
                },
                "emphasis": {
                    "itemStyle": {
                        "shadowBlur": 10,
                        "shadowOffsetX": 0,
                        "shadowColor": "rgba(0, 0, 0, 0.5)"
                    }
                }
            }
        ]
    }
    
    return option

# ==================== 总数分析组件 ====================
def render_total_metrics_optimized(stats):
    """总数分析指标"""
    # 使用Streamlit原生metric组件
    st.markdown("### 📈 核心业务指标")
    
    cols = st.columns(4)
    with cols[0]:
        st.metric("总记录数", f"{int(stats['total_records']):,}")
    with cols[1]:
        st.metric("总销售额", f"¥{int(stats['total_amount']):,}")
    with cols[2]:
        st.metric("客户总数", f"{int(stats['unique_customers']):,}")
    with cols[3]:
        st.metric("产品总数", f"{int(stats['unique_products']):,}")
    
    # 第二行指标
    cols2 = st.columns(4)
    with cols2[0]:
        date_range_text = "暂无数据"
        if stats['date_range'] and stats['date_range']['start']:
            start = stats['date_range']['start'][:10] if stats['date_range']['start'] else "未知"
            end = stats['date_range']['end'][:10] if stats['date_range']['end'] else "未知"
            date_range_text = f"{start} 至 {end}"
        st.metric("交易时间范围", date_range_text)
    with cols2[1]:
        st.metric("总销售量", f"{int(stats['total_quantity']):,}")
    with cols2[2]:
        st.metric("颜色种类", f"{int(stats['unique_colors']):,}")
    with cols2[3]:
        st.metric("平均单价", f"¥{stats['avg_price']:,.2f}")

def render_total_analysis_optimized(year_filter):
    """渲染优化的总数分析"""
    try:
        # 获取统计数据
        stats = get_cached_total_stats(year_filter)
        
        if stats['total_records'] == 0:
            st.warning(f"⚠️ {year_filter if year_filter != '全部年份' else ''}暂无数据")
            return
        
        # 标题
        # if year_filter != "全部年份":
        #     st.markdown(f"## 📊 {year_filter}年总体业务分析")
        # else:
        #     st.markdown("## 📊 总体业务分析（全部年份）")
        
        # 关键指标概览
        render_total_metrics_optimized(stats)
        
        # 部门销售额分析
        st.markdown("### 🏢 部门业绩分析")
        
        dept_data = get_cached_department_stats(year_filter)
        if dept_data['department_stats']:
            dept_df = pd.DataFrame(dept_data['department_stats'])
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 部门销售额对比")
                if not dept_df.empty:
                    option = create_echarts_bar_chart(
                        dept_df.head(10), 'department', 'total_amount',
                        "部门销售额排名", 'primary'
                    )
                    if option:
                        st_echarts(option, height=400)
            
            with col2:
                st.markdown("#### 部门销售占比")
                filtered_dept = dept_df[dept_df['department'] != '未分类']
                if not filtered_dept.empty:
                    option = create_echarts_pie_chart(
                        filtered_dept, 'total_amount', 'department',
                        "部门销售额占比", ['30%', '75%']
                    )
                    if option:
                        st_echarts(option, height=400)
        
        # 时间趋势分析
        st.markdown("### 📅 业务趋势分析")
        
        with get_connection() as conn:
            year_condition = ""
            params = []
            
            if year_filter != "全部年份":
                year_condition = "WHERE strftime('%Y', record_date) = ?"
                params = [year_filter]
            
            trend_query = f'''
                SELECT 
                    strftime('%Y-%m', record_date) as month,
                    COUNT(*) as transaction_count,
                    ROUND(SUM(amount), 2) as total_amount,
                    ROUND(AVG(unit_price), 2) as avg_price,
                    SUM(quantity) as total_quantity
                FROM sales_records
                {year_condition}
                GROUP BY strftime('%Y-%m', record_date)
                HAVING month IS NOT NULL AND month != ''
                ORDER BY month
            '''
            monthly_trend = pd.read_sql_query(trend_query, conn, params=params)
        
        if not monthly_trend.empty and len(monthly_trend) > 1:
            col1, col2 = st.columns(2)
            
            with col1:
                option1 = create_echarts_line_bar_mix(
                    monthly_trend, 
                    "📊 销售额 vs 交易量趋势",
                    'total_amount', 'transaction_count',
                    "销售额", "交易次数"
                )
                if option1:
                    st_echarts(option1, height=400)
            
            with col2:
                option2 = create_echarts_line_bar_mix(
                    monthly_trend,
                    "📦 平均单价 vs 销售数量趋势",
                    'avg_price', 'total_quantity',
                    "平均单价", "销售数量"
                )
                if option2:
                    st_echarts(option2, height=400)
            
            # 月度详细数据表格
            with st.expander("📈 月度详细数据", expanded=False):
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
            st.info("暂无足够的时间趋势数据")
        
        # 客户分析
        st.markdown("### 👥 客户价值分析")
        
        with get_connection() as conn:
            year_condition = ""
            params = []
            
            if year_filter != "全部年份":
                year_condition = "WHERE strftime('%Y', record_date) = ?"
                params = [year_filter]
            
            customer_query = f'''
                SELECT 
                    customer_name,
                    COUNT(DISTINCT color) as product_colors,
                    COUNT(*) as transaction_count,
                    ROUND(SUM(amount), 2) as total_amount,
                    ROUND(AVG(unit_price), 2) as avg_price
                FROM sales_records
                {year_condition}
                GROUP BY customer_name
                HAVING total_amount > 0
                ORDER BY total_amount DESC
                LIMIT 20
            '''
            customer_stats = pd.read_sql_query(customer_query, conn, params=params)
        
        if not customer_stats.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏆 TOP客户销售额")
                top_customers = customer_stats.head(10)
                
                option = create_echarts_bar_chart(
                    top_customers, 'customer_name', 'total_amount',
                    "TOP客户销售额", 'primary'
                )
                if option:
                    st_echarts(option)
            
            with col2:
                # 客户价值分析表格
                st.markdown("#### 💬 客户详情统计")
                display_customers = customer_stats.copy()
                display_customers = display_customers.rename(columns={
                    'customer_name': '客户名称',
                    'total_amount': '总金额',
                    'transaction_count': '交易次数',
                    'product_colors': '产品颜色数',
                    'avg_price': '平均单价'
                })
                
                st.dataframe(
                    display_customers[['客户名称', '总金额', '交易次数', '产品颜色数', '平均单价']],
                    width='stretch',
                    hide_index=True
                )
        
        # 产品分析
        st.markdown("### 🏺 产品表现分析")
        
        with get_connection() as conn:
            year_condition = ""
            params = []
            
            if year_filter != "全部年份":
                year_condition = "WHERE strftime('%Y', record_date) = ?"
                params = [year_filter]
            
            product_query = f'''
                SELECT 
                    product_name,
                    color,
                    COALESCE(NULLIF(grade, ''), '无等级') as grade,
                    COUNT(*) as transaction_count,
                    ROUND(AVG(unit_price), 2) as avg_price,
                    SUM(quantity) as total_quantity,
                    ROUND(SUM(amount), 2) as total_amount
                FROM sales_records
                {year_condition}
                GROUP BY product_name, color, grade
                HAVING total_amount > 0
                ORDER BY total_amount DESC
                LIMIT 25
            '''
            product_stats = pd.read_sql_query(product_query, conn, params=params)
        
        if not product_stats.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🔥 热销产品TOP10")
                top_products = product_stats.head(10)
                top_products['product_display'] = top_products.apply(
                    lambda x: f"{x['product_name']} - {x['color']}", axis=1
                )
                
                option = create_echarts_bar_chart(
                    top_products, 'product_display', 'total_amount',
                    "热销产品销售额", 'danger'
                )
                if option:
                    st_echarts(option)
            
            with col2:
                # 产品价格分析表格
                st.markdown("#### 📊 产品价格统计")
                display_products = product_stats.copy()
                display_products = display_products.rename(columns={
                    'product_name': '产品名称',
                    'color': '颜色',
                    'grade': '等级',
                    'total_amount': '总金额',
                    'transaction_count': '交易次数',
                    'total_quantity': '总数量',
                    'avg_price': '平均单价'
                })
                
                st.dataframe(
                    display_products[['产品名称', '颜色', '等级', '总金额', '交易次数', '总数量', '平均单价']],
                    width='stretch',
                    hide_index=True
                )
        
        # 数据导出
        st.markdown("### 💾 数据导出")
        cols = st.columns(4)
        
        with cols[0]:
            if 'monthly_trend' in locals() and not monthly_trend.empty:
                csv_monthly = monthly_trend.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📈 导出月度趋势",
                    data=csv_monthly,
                    file_name=f"月度趋势_{year_filter}.csv",
                    mime="text/csv",
                    width='stretch'
                )
        
        with cols[1]:
            if 'customer_stats' in locals() and not customer_stats.empty:
                csv_customer = customer_stats.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="👥 导出客户分析",
                    data=csv_customer,
                    file_name=f"客户分析_{year_filter}.csv",
                    mime="text/csv",
                    width='stretch'
                )
        
        with cols[2]:
            if 'product_stats' in locals() and not product_stats.empty:
                csv_product = product_stats.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="🏺 导出产品分析",
                    data=csv_product,
                    file_name=f"产品分析_{year_filter}.csv",
                    mime="text/csv",
                    width='stretch'
                )
        
        with cols[3]:
            summary_data = {
                '指标': ['总记录数', '总销售额', '客户总数', '产品总数', '平均单价', '交易均额'],
                '数值': [
                    stats['total_records'],
                    stats['total_amount'],
                    stats['unique_customers'],
                    stats['unique_products'],
                    stats['avg_price'],
                    stats['avg_transaction_amount']
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            csv_summary = summary_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📊 导出指标摘要",
                data=csv_summary,
                file_name=f"指标摘要_{year_filter}.csv",
                mime="text/csv",
                width='stretch'
            )
                
    except Exception as e:
        st.error(f"获取统计数据时出错: {str(e)}")
        st.info("请确保已正确导入数据并初始化数据库")

def create_department_analysis_tab_optimized(department, year_filter):
    """部门分析选项卡内容"""
    try:
        # 获取部门详细数据
        with get_connection() as conn:
            year_condition = ""
            params = [department]
            
            if year_filter != "全部年份":
                year_condition = "AND strftime('%Y', record_date) = ?"
                params.append(year_filter)
            
            # 部门统计数据
            stats_query = f'''
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT customer_name) as customer_count,
                    COUNT(DISTINCT product_name) as product_count,
                    COUNT(DISTINCT color) as color_count,
                    COALESCE(SUM(quantity), 0) as total_quantity,
                    COALESCE(SUM(amount), 0) as total_amount,
                    COALESCE(AVG(unit_price), 0) as avg_price,
                    MIN(record_date) as earliest_date,
                    MAX(record_date) as latest_date
                FROM sales_records
                WHERE department = ? {year_condition}
            '''
            
            result = pd.read_sql_query(stats_query, conn, params=params)
            
            if result.empty or result.iloc[0]['total_records'] == 0:
                st.warning(f"⚠️ {department}暂无{year_filter if year_filter != '全部年份' else ''}数据")
                return
            
            dept_stats = {
                'total_records': int(result.iloc[0]['total_records']),
                'customer_count': int(result.iloc[0]['customer_count']),
                'product_count': int(result.iloc[0]['product_count']),
                'color_count': int(result.iloc[0]['color_count']),
                'total_quantity': int(result.iloc[0]['total_quantity']),
                'total_amount': float(result.iloc[0]['total_amount']),
                'avg_price': float(result.iloc[0]['avg_price']),
                'date_range': {
                    'start': result.iloc[0]['earliest_date'],
                    'end': result.iloc[0]['latest_date']
                }
            }
        
        # 部门标题
        if year_filter != "全部年份":
            st.markdown(f"## 📊 {department} - {year_filter}年分析")
        else:
            st.markdown(f"## 📊 {department} - 全部年份分析")
        
        # 关键指标
        st.subheader(f"📈 {department}关键指标")
        
        cols = st.columns(4)
        with cols[0]:
            st.metric("总记录数", f"{dept_stats['total_records']:,}")
        with cols[1]:
            st.metric("客户数量", f"{dept_stats['customer_count']:,}")
        with cols[2]:
            st.metric("产品数量", f"{dept_stats['product_count']:,}")
        with cols[3]:
            st.metric("颜色种类", f"{dept_stats['color_count']:,}")
        
        cols2 = st.columns(4)
        with cols2[0]:
            st.metric("总金额", f"¥{int(dept_stats['total_amount']):,}")
        with cols2[1]:
            st.metric("总数量", f"{dept_stats['total_quantity']:,}")
        with cols2[2]:
            st.metric("平均价格", f"¥{dept_stats['avg_price']:.2f}")
        with cols2[3]:
            date_range_text = "暂无数据"
            if dept_stats['date_range'] and dept_stats['date_range']['start']:
                start = dept_stats['date_range']['start'][:10]
                end = dept_stats['date_range']['end'][:10]
                date_range_text = f"{start} 至 {end}"
            st.metric("数据周期", date_range_text)
        
        # 生产线详细分析
        st.markdown("---")
        st.subheader("🏭 生产线详细分析")
        
        production_data = get_cached_production_line_data(department, year_filter)
        
        if not production_data.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 生产线记录数TOP10")
                top_lines = production_data.nlargest(10, 'record_count')
                option = create_echarts_bar_chart(
                    top_lines, 'production_line', 'record_count',
                    f"{department}生产线记录数TOP10", 'warning'
                )
                if option:
                    st_echarts(option, height=400)
            
            with col2:
                st.markdown("#### 生产线销售额分布")
                option = create_echarts_pie_chart(
                    production_data, 'total_amount', 'production_line',
                    f"{department}生产线销售额分布", ['30%', '75%']
                )
                if option:
                    st_echarts(option, height=400)
            
            # 生产线详细数据表
            # st.markdown("#### 📋 生产线详细数据")
            with st.expander("💬 查看客户详情统计", expanded=False):
                display_lines = production_data.copy()
                display_lines = display_lines.rename(columns={
                    'production_line': '生产线',
                    'record_count': '记录数',
                    'total_amount': '总金额',
                    'total_quantity': '总数量',
                    'avg_price': '平均价格'
                })
                
                st.dataframe(
                    display_lines[['生产线', '记录数', '总数量', '平均价格', '总金额']],
                    width='stretch',
                    hide_index=True
                )
        
        # 时间趋势分析
        st.markdown("---")
        st.subheader("📅 时间趋势分析")
        
        with get_connection() as conn:
            year_condition = ""
            params = [department]
            
            if year_filter != "全部年份":
                year_condition = "AND strftime('%Y', record_date) = ?"
                params.append(year_filter)
            
            trend_query = f'''
                SELECT 
                    strftime('%Y-%m', record_date) as month,
                    COUNT(*) as transaction_count,
                    ROUND(SUM(amount), 2) as total_amount,
                    ROUND(AVG(unit_price), 2) as avg_price,
                    SUM(quantity) as total_quantity
                FROM sales_records
                WHERE department = ? {year_condition}
                GROUP BY strftime('%Y-%m', record_date)
                HAVING month IS NOT NULL AND month != ''
                ORDER BY month
            '''
            monthly_trend = pd.read_sql_query(trend_query, conn, params=params)
        
        if not monthly_trend.empty and len(monthly_trend) > 1:
            col1, col2 = st.columns(2)
            
            with col1:
                option1 = create_echarts_line_bar_mix(
                    monthly_trend, 
                    f"📊 {department}销售额 vs 交易量趋势",
                    'total_amount', 'transaction_count',
                    "销售额", "交易次数"
                )
                if option1:
                    st_echarts(option1, height=400)
            
            with col2:
                option2 = create_echarts_line_bar_mix(
                    monthly_trend,
                    f"📦 {department}平均单价 vs 销售数量趋势",
                    'avg_price', 'total_quantity',
                    "平均单价", "销售数量"
                )
                if option2:
                    st_echarts(option2, height=400)
            
            # 月度详细数据
            with st.expander("📈 月度详细数据", expanded=False):
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
        
        # 产品分析
        st.markdown("---")
        st.subheader("🏺 产品分析")
        
        with get_connection() as conn:
            year_condition = ""
            params = [department]
            
            if year_filter != "全部年份":
                year_condition = "AND strftime('%Y', record_date) = ?"
                params.append(year_filter)
            
            product_query = f'''
                SELECT 
                    product_name,
                    color,
                    COUNT(*) as transaction_count,
                    ROUND(AVG(unit_price), 2) as avg_price,
                    SUM(quantity) as total_quantity,
                    ROUND(SUM(amount), 2) as total_amount
                FROM sales_records
                WHERE department = ? {year_condition}
                GROUP BY product_name, color
                HAVING total_amount > 0
                ORDER BY total_amount DESC
                LIMIT 15
            '''
            dept_products = pd.read_sql_query(product_query, conn, params=params)
        
        if not dept_products.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 热销产品TOP10")
                top_products = dept_products.head(10)
                top_products['product_display'] = top_products.apply(
                    lambda x: f"{x['product_name']} - {x['color']}", axis=1
                )
                
                option = create_echarts_bar_chart(
                    top_products, 'product_display', 'total_amount',
                    f"{department}热销产品TOP10", 'danger'
                )
                if option:
                    st_echarts(option, height=400)
            
            with col2:
                # 产品价格分析表格
                st.markdown("#### 产品价格统计")
                display_products = dept_products.copy()
                display_products = display_products.rename(columns={
                    'product_name': '产品名称',
                    'color': '颜色',
                    'total_amount': '总金额',
                    'transaction_count': '交易次数',
                    'total_quantity': '总数量',
                    'avg_price': '平均价格'
                })
                
                st.dataframe(
                    display_products[['产品名称', '颜色', '总金额', '交易次数', '总数量', '平均价格']],
                    width='stretch',
                    hide_index=True
                )
        
        # 数据导出
        st.markdown("---")
        st.subheader("💾 数据导出")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 导出部门详细数据
            if 'dept_stats' in locals():
                summary_data = {
                    '指标': ['总记录数', '客户数量', '产品数量', '颜色种类', '总金额', '总数量', '平均价格'],
                    '数值': [
                        dept_stats['total_records'],
                        dept_stats['customer_count'],
                        dept_stats['product_count'],
                        dept_stats['color_count'],
                        dept_stats['total_amount'],
                        dept_stats['total_quantity'],
                        dept_stats['avg_price']
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                csv_summary = summary_df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 导出部门统计",
                    data=csv_summary,
                    file_name=f"{department}_{year_filter}_统计.csv",
                    mime="text/csv",
                    width='stretch'
                )
        
        with col2:
            # 导出生产线数据
            if 'production_data' in locals() and not production_data.empty:
                csv_lines = production_data.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="🏭 导出生产线数据",
                    data=csv_lines,
                    file_name=f"{department}_{year_filter}_生产线数据.csv",
                    mime="text/csv",
                    width='stretch'
                )
                
    except Exception as e:
        st.error(f"分析{department}数据时出错: {str(e)}")

# ==================== 侧边栏配置 ====================
with st.sidebar:
    st.markdown("### ⚙️ 分析设置")
    
    # 年份选择器
    available_years = get_available_years()
    selected_year = st.selectbox(
        "选择分析年份",
        available_years,
        key="year_selector",
        help="选择要分析的年份，'全部年份'将显示所有数据"
    )
    
    if selected_year != "全部年份":
        st.info(f"📅 当前分析: {selected_year}年")
    
    st.markdown("---")
    
    # 快速导航
    st.markdown("### 🔍 快速导航")
    
    # 获取当前年份的部门列表
    current_depts = get_department_list(selected_year)
    
    # 使用session_state管理当前视图
    if 'current_view' not in st.session_state:
        st.session_state.current_view = "总数分析"
    
    if st.button("📊 总体概览", width='stretch'):
        st.session_state.current_view = "总数分析"
        st.rerun()
    
    if current_depts:
        # st.markdown("**部门分析**")
        for dept in current_depts:
            if st.button(f"🏢 {dept}", width='stretch'):
                st.session_state.current_view = f"🏢 {dept}"
                st.rerun()
    else:
        st.info("暂无部门数据")
    
    st.markdown("---")
    
    # 页面信息
    st.markdown("#### ℹ️ 页面信息")
    stats = get_cached_total_stats(selected_year)
    st.caption(f"• 总记录数: {int(stats['total_records']):,}")
    st.caption(f"• 数据时间: {selected_year}")
    st.caption(f"• 部门数量: {len(current_depts)}")

# ==================== 主页面布局 ====================
st.markdown("---")

# 根据session_state显示不同视图
if st.session_state.current_view == "总数分析":
    render_total_analysis_optimized(selected_year)
else:
    # 部门详细分析
    department = st.session_state.current_view.replace("🏢 ", "")
    create_department_analysis_tab_optimized(department, selected_year)

# ==================== 页面底部说明 ====================
with st.expander("📚 使用说明与性能提示", expanded=False):
    st.markdown("""
    ### 📊 功能亮点
    
    **完整分析结构**
    - 关键指标卡片展示
    - 生产线详细分析（柱状图+饼图+表格）
    - 时间趋势分析（复合图带dataZoom）
    - 产品分析（热销产品TOP10+价格统计）
    - 月度详细数据表格
    
    **智能图表**
    - 复合图表（折线+柱状）带dataZoom
    - 交互式数据探索
    - 支持图表导出为图片
    
    **数据管理**
    - 一键导出各种格式数据
    - 支持按年份筛选分析
    - 实时数据更新与缓存
    """)

# 页面加载完成提示
st.toast("✅ 页面加载完成！", icon="🎉")
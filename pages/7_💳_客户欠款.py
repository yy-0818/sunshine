import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from core.debt_service import DebtAnalysisService
from core.customer_analysis import SalesDebtIntegrationService
from core.database import get_connection
from utils.auth import require_login
from utils.data_processor import process_debt_excel_data, validate_debt_data, get_sample_data

# -----------------------------------------------------------------------------
# 1. 配置与常量定义
# -----------------------------------------------------------------------------

st.logo(
    image='./assets/logo.png',
    icon_image='./assets/logo.png',
)

st.set_page_config(
    page_title="客户信用综合分析系统",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 专业的风险色阶 (背景色)
RISK_COLORS = {
    '低风险': '#E8F5E9',           # 极淡绿 (安全)
    '较低风险': '#E1F5FE',         # 极淡蓝 (正常)
    '中等风险': '#FFF8E1',         # 极淡黄 (警告)
    '较高风险': '#FFF3E0',         # 极淡橙 (较高风险)
    '高风险': '#FFEBEE'            # 极淡红 (高危)
}

# 风险文本颜色
RISK_TEXT_COLORS = {
    '低风险': '#2E7D32',           # 深绿
    '较低风险': '#0277BD',         # 深蓝
    '中等风险': '#F9A825',         # 深黄
    '较高风险': '#EF6C00',         # 深橙
    '高风险': '#C62828'            # 深红
}

# 综合等级到风险等级的映射
INTEGRATED_TO_RISK = {
    'A-优质大客户': '低风险',
    'A-优质活跃客户': '低风险',
    'B-大额休眠客户': '较低风险',
    'B-一般客户': '较低风险',
    'B1-低风险活跃欠款': '较低风险',
    'B2-低风险欠款': '较低风险',
    'C-小额客户': '中等风险',
    'C-长期无交易客户': '中等风险',
    'C1-中风险活跃欠款': '较高风险',
    'C2-中风险欠款': '较高风险',
    'D-无销售无欠款': '中等风险',
    'D-高风险欠款': '高风险',
    'D-高风险长期欠款': '高风险',
    'E-纯欠款客户': '高风险'
}

# 风险评分颜色映射
RISK_SCORE_COLORS = {
    (80, 101): '#E8F5E9',   # 低风险背景色
    (60, 80): '#E1F5FE',    # 较低风险背景色
    (40, 60): '#FFF8E1',    # 中等风险背景色
    (20, 40): '#FFF3E0',    # 较高风险背景色
    (0, 20): '#FFEBEE'      # 高风险背景色
}

# -----------------------------------------------------------------------------
# 2. 工具函数
# -----------------------------------------------------------------------------

def apply_style(df, highlight_integrated=True, highlight_score=True):
    """为 DataFrame 应用 Pandas Styler"""
    styler = df.style

    def get_integrated_style(val):
        risk_level = INTEGRATED_TO_RISK.get(val, '较低风险')
        bg_color = RISK_COLORS.get(risk_level, '')
        text_color = RISK_TEXT_COLORS.get(risk_level, '#333333')
        if bg_color:
            return f'background-color: {bg_color}; color: {text_color}; font-weight: 500;'
        return ''
    
    def get_risk_score_style(val):
        if pd.isna(val):
            return ''
        val = float(val)
        for (low, high), color in RISK_SCORE_COLORS.items():
            if low <= val < high:
                if high > 80:
                    text_color = '#2E7D32'
                elif high > 60:
                    text_color = '#0277BD'
                elif high > 40:
                    text_color = '#F9A825'
                elif high > 20:
                    text_color = '#EF6C00'
                else:
                    text_color = '#C62828'
                return f'background-color: {color}; color: {text_color}; font-weight: bold;'
        return ''

    if highlight_integrated and '客户综合等级' in df.columns:
        styler = styler.map(get_integrated_style, subset=['客户综合等级'])
    
    if highlight_score and '风险评分' in df.columns:
        styler = styler.map(get_risk_score_style, subset=['风险评分'])

    numeric_columns = [c for c in df.columns if any(keyword in c for keyword in ['欠款', '变化', '金额', '评分', '销量', '比率', '比例', '占比'])]
    if numeric_columns:
        styler = styler.format("{:,.2f}", subset=numeric_columns)
    
    return styler

def get_column_config(year=25):
    """配置 Streamlit 原生列显示格式 - 支持年份动态显示"""
    year_prefix = f"20{year}"
    config = {
        "财务编号": st.column_config.TextColumn("财务编号", width="small", help="统一的财务编号格式"),
        "客户代码": st.column_config.TextColumn("客户代码", width="small"),
        "客户名称": st.column_config.TextColumn("客户名称", width="medium"),
        "2023欠款": st.column_config.NumberColumn("2023欠款", format="¥%.2f", min_value=0),
        "2024欠款": st.column_config.NumberColumn("2024欠款", format="¥%.2f", min_value=0),
        "2025欠款": st.column_config.NumberColumn("2025欠款", format="¥%.2f", min_value=0, help="当前年度最新欠款金额"),
        "总销售额": st.column_config.NumberColumn("总销售额", format="¥%.2f", help="累计总销售额"),
        f"{year_prefix}销售额": st.column_config.NumberColumn(f"{year_prefix}销售额", format="¥%.2f", help=f"{year_prefix}年销售额"),
        "累计销售量": st.column_config.NumberColumn("累计销售量", format="%d"),
        "欠销比": st.column_config.NumberColumn("欠销比", format="%.1f%%", help="欠款占销售额的比例"),
        "销售活跃度": st.column_config.TextColumn("销售活跃度", width="medium"),
        "客户综合等级": st.column_config.TextColumn("综合等级", width="medium"),
        "风险评分": st.column_config.NumberColumn("风险分", format="%.0f", help="0-100分，分数越高风险越低"),
        "风险等级": st.column_config.TextColumn("风险等级", width="medium"),
        "最后销售日期": st.column_config.DateColumn("最后销售日期", format="YYYY-MM-DD"),
        "交易次数": st.column_config.NumberColumn("交易次数", format="%d"),
        "产品种类数": st.column_config.NumberColumn("产品种类", format="%d"),
        "所属部门": st.column_config.TextColumn("所属部门", width="small"),
    }
    return config

def render_sidebar_legend():
    """在侧边栏渲染图例"""
    with st.sidebar:
        st.header("📚 系统图例说明")
        
        # 移除了风险等级颜色图例，只保留风险评分颜色
        with st.expander("📈 风险评分颜色", expanded=True):
            # 按照风险等级从高到低排列
            score_ranges = [
                ((80, 101), "80-100分", "低风险"),
                ((60, 80), "60-79分", "较低风险"),
                ((40, 60), "40-59分", "中等风险"),
                ((20, 40), "20-39分", "较高风险"),
                ((0, 20), "0-19分", "高风险")
            ]
            
            for (low, high), label, desc in score_ranges:
                color = RISK_SCORE_COLORS.get((low, high), '#FFFFFF')
                text_color = '#2E7D32' if high > 80 else '#0277BD' if high > 60 else '#F9A825' if high > 40 else '#EF6C00' if high > 20 else '#C62828'
                st.markdown(
                    f'<div style="background-color: {color}; color: {text_color}; padding: 6px 10px; '
                    f'border-radius: 4px; margin-bottom: 6px; font-size: 0.9em; border: 1px solid {text_color}30;">'
                    f'<b>{label}</b> - {desc}</div>', 
                    unsafe_allow_html=True
                )
        
        st.divider()
        st.caption(f"📅 系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def format_currency(value):
    """格式化货币显示"""
    if value >= 1_000_000:
        return f"¥{value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"¥{value/1_000:.1f}K"
    else:
        return f"¥{value:.2f}"

def get_integrated_data(integration_service, year=25):
    """获取综合分析数据 - 统一获取函数"""
    try:
        print(f"开始获取综合数据，年份: {year}")
        integrated_df = integration_service.get_integrated_customer_analysis(year)
        
        return integrated_df
    except Exception as e:
        st.error(f"获取综合数据失败: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return pd.DataFrame()

def get_sales_by_year(integration_service, year=25):
    """获取指定年份的销售数据"""
    try:
        with get_connection() as conn:
            sales_query = f'''
                SELECT 
                    finance_id,
                    customer_name,
                    SUM(amount) as year_sales,
                    SUM(quantity) as year_quantity,
                    COUNT(*) as year_transactions
                FROM sales_records
                WHERE finance_id IS NOT NULL 
                    AND finance_id != '' 
                    AND year = ?
                GROUP BY finance_id, customer_name
            '''
            sales_df = pd.read_sql(sales_query, conn, params=(year,))
            
            if sales_df.empty:
                return sales_df
            
            sales_df['finance_id'] = sales_df['finance_id'].astype(str).str.strip()
            
            def remove_leading_zeros(finance_id):
                if pd.isna(finance_id):
                    return ''
                try:
                    return str(int(float(str(finance_id))))
                except:
                    return str(finance_id)
            
            sales_df['finance_id'] = sales_df['finance_id'].apply(remove_leading_zeros)
            
            return sales_df
    except Exception as e:
        st.error(f"获取销售数据失败: {str(e)}")
        return pd.DataFrame()

def get_year_sales_total(year):
    """获取指定年份的总销售额（包含退款退货）"""
    try:
        with get_connection() as conn:
            query = f"SELECT SUM(amount) as total_sales FROM sales_records WHERE year = ?"
            result = pd.read_sql(query, conn, params=(year,))
            total_sales = result.iloc[0]['total_sales'] if not result.empty else 0
            return total_sales if total_sales is not None else 0
    except Exception as e:
        st.error(f"获取年份销售额失败: {str(e)}")
        return 0

# -----------------------------------------------------------------------------
# 3. 数据导入页面
# -----------------------------------------------------------------------------

def render_data_import_tab(debt_service):
    """数据导入页面"""
    st.header("📥 数据导入中心")
    st.caption("请上传符合格式的 Excel 文件以更新系统数据。")

    col1, col2 = st.columns(2)

    def handle_upload(column, title, key_prefix, dept_type):
        """处理文件上传和导入"""
        with column:
            with st.container(border=True):
                st.subheader(f"{title}")
                uploaded_file = st.file_uploader(f"上传{dept_type}数据", type=['xlsx', 'xls'], key=f"{key_prefix}_file")
                
                if uploaded_file:
                    try:
                        df_raw = pd.read_excel(uploaded_file)
                        st.info(f"📄 读取到 {len(df_raw)} 行原始数据")
                        
                        with st.status("🔄 正在处理数据...", expanded=True) as status:
                            st.write("🔍 清洗数据格式...")
                            df_clean = process_debt_excel_data(df_raw, dept_type)
                            
                            if df_clean.empty:
                                st.error("❌ 未找到有效数据，请检查文件格式")
                                return
                            
                            st.write(f"✅ 有效数据: {len(df_clean)} 条")
                            
                            issues = validate_debt_data(df_clean)
                            if issues:
                                st.warning(f"⚠️ 发现 {len(issues)} 个潜在问题")
                                for i in issues[:3]:
                                    st.write(f"- {i}")
                                if len(issues) > 3:
                                    st.write(f"- ...等 {len(issues)-3} 个问题")
                            
                            status.update(label="✅ 数据准备就绪", state="complete", expanded=False)

                        st.write("📋 处理后的数据预览（前10行）:")
                        st.dataframe(
                            df_clean.head(10),
                            column_config={
                                "finance_id": "财务编号",
                                "customer_name": "客户名称",
                                "department": "所属部门",
                                "debt_2023": st.column_config.NumberColumn("2023欠款", format="¥%.2f"),
                                "debt_2024": st.column_config.NumberColumn("2024欠款", format="¥%.2f"),
                                "debt_2025": st.column_config.NumberColumn("2025欠款", format="¥%.2f"),
                            },
                            hide_index=True,
                            width='stretch'
                        )
                        
                        if st.button(f"🚀 确认导入{dept_type}数据", key=f"{key_prefix}_btn", type="primary", width='stretch'):
                            with st.spinner(f"正在导入{dept_type}数据..."):
                                success_count, error_count = debt_service.import_debt_data(df_clean, dept_type)
                                
                                if error_count == 0:
                                    st.success(f"✅ 导入成功！新增/更新 {success_count} 条记录")
                                    
                                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                                    with col_stat1:
                                        st.metric("总欠款额", format_currency(df_clean['debt_2025'].sum()))
                                    with col_stat2:
                                        st.metric("有欠款客户", len(df_clean[df_clean['debt_2025'] > 0]))
                                    with col_stat3:
                                        st.metric("无欠款客户", len(df_clean[df_clean['debt_2025'] == 0]))
                                else:
                                    st.warning(f"⚠️ 导入完成。成功: {success_count}, 失败: {error_count}")
                                    if error_count > 0:
                                        st.error("❌ 部分数据导入失败，请检查数据格式")
                    except Exception as e:
                        st.error(f"❌ 处理失败: {str(e)}")
                        st.exception(e)

    handle_upload(col1, "🏺 一期", "dept1", "一期")
    handle_upload(col2, "🏛️ 二期", "dept2", "二期")

    with st.expander("📝 查看数据格式要求", expanded=False):
        st.markdown("""
        ### Excel文件格式要求
        
        **文件结构（必须包含以下列）：**
        | 列位置 | 列名 | 说明 | 示例 |
        |--------|------|------|------|
        | 第1列 | 客户代码 | 必须以2203开头 | `2203.413.001` |
        | 第2列 | 客户名称 | 客户全称 | `鑫帅辉-九方昌盛` |
        | 第3列 | 2023欠款 | 2023年欠款金额 | `5000.00` |
        | 第6列 | 2024欠款 | 2024年欠款金额 | `3000.00` |
        | 第9列 | 2025欠款 | 2025年欠款金额 | `0.00` |
        
        **财务编号处理规则：**
        - `2203.413.001` → 自动处理为 `413-001`
        - `2203-413-001` → 自动处理为 `413-001`
        - `2203413001` → 自动处理为 `413-001`
        
        **注意：系统会自动统一财务编号格式，确保与销售数据一致。**
        """)
        
        st.markdown("### 示例数据格式：")
        sample_df = get_sample_data("二期")
        st.dataframe(sample_df, hide_index=True, width='stretch')
        
        csv = sample_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下载数据模板",
            data=csv,
            file_name="客户欠款数据模板.csv",
            mime="text/csv",
            help="下载标准格式的数据模板"
        )

# -----------------------------------------------------------------------------
# 4. 复核分析视图
# -----------------------------------------------------------------------------

def render_review_analysis_tab(integration_service):
    """复核分析视图"""
    st.header("🔍 客户信用复核分析")
    
    with st.container(border=True):
        st.subheader("⚙️ 分析参数设置")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            analysis_year = st.selectbox(
                "📅 分析年份",
                options=[25, 24, 23],
                index=0,
                format_func=lambda x: f"20{x}年",
                help="选择分析的主要年份"
            )
        
        with col2:
            department_filter = st.multiselect(
                "🏢 部门筛选",
                options=['二期', '一期'],
                default=['二期', '一期'],
                help="选择分析的部门"
            )
        
        with col3:
            min_debt = st.number_input(
                "💰 最低欠款筛选",
                min_value=0,
                value=0,
                step=1000,
                help="只显示欠款大于此值的客户"
            )
    
    with st.spinner("🔄 正在获取分析数据..."):
        try:
            integrated_df = get_integrated_data(integration_service, analysis_year)
            
            if integrated_df.empty:
                st.warning("📭 暂无数据，请先导入欠款数据")
                return
            
            # 部门筛选
            if department_filter and '所属部门' in integrated_df.columns:
                mask = integrated_df['所属部门'].isin(department_filter)
                integrated_df = integrated_df[mask]
            
            # 欠款筛选
            debt_column = f'20{analysis_year}欠款'
            if min_debt > 0 and debt_column in integrated_df.columns:
                mask = integrated_df[debt_column] >= min_debt
                integrated_df = integrated_df[mask]
            
        except Exception as e:
            st.error(f"❌ 数据获取失败: {str(e)}")
            return
    
    if integrated_df.empty:
        st.info("📊 没有符合筛选条件的数据")
        return
    
    st.subheader("📊 关键指标概览")
    
    total_customers = len(integrated_df)
    
    debt_column = f'20{analysis_year}欠款'
    total_debt = integrated_df[debt_column].sum() if debt_column in integrated_df.columns else 0
    
    total_sales = integrated_df['总销售额'].sum() if '总销售额' in integrated_df.columns else 0
    
    # 计算有销售的客户数量
    if '总销售额' in integrated_df.columns:
        customers_with_sales = len(integrated_df[integrated_df['总销售额'] > 0])
    else:
        customers_with_sales = 0
    
    # 计算欠销比
    debt_sales_ratio = (total_debt / total_sales * 100) if total_sales > 0 else 0
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.metric("分析客户数", f"{total_customers:,}")
    
    with kpi2:
        st.metric(
            f"20{analysis_year}总欠款",
            format_currency(total_debt),
            f"欠销比: {debt_sales_ratio:.1f}%" if total_sales > 0 else "无销售",
            delta_color="inverse"
        )
    
    with kpi3:
        st.metric(
            "总销售额",
            format_currency(total_sales),
            f"有销售客户: {customers_with_sales}个"
        )
    
    with kpi4:
        if '风险等级' in integrated_df.columns:
            high_risk_mask = integrated_df['风险等级'].isin(['高风险', '较高风险'])
            high_risk_customers = integrated_df[high_risk_mask].shape[0]
            high_risk_ratio = (high_risk_customers / total_customers * 100) if total_customers > 0 else 0
            st.metric(
                "风险客户",
                f"{high_risk_customers:,}",
                f"{high_risk_ratio:.1f}%",
                delta_color="inverse"
            )
        else:
            st.metric("风险客户", "N/A")
    
    st.divider()
    
    st.subheader("📋 详细数据查看")
    
    with st.container(border=True):
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        
        with col_filter1:
            search_term = st.text_input(
                "🔍 搜索客户",
                placeholder="输入客户名称或财务编号...",
                help="支持客户名称和财务编号搜索",
                key="review_search"
            )
        
        with col_filter2:
            if '风险等级' in integrated_df.columns:
                risk_options = integrated_df['风险等级'].unique().tolist()
                risk_selected = st.multiselect("风险等级", options=risk_options)
            else:
                risk_selected = []
        
        with col_filter3:
            if '客户综合等级' in integrated_df.columns:
                grade_options = integrated_df['客户综合等级'].unique().tolist()
                grade_selected = st.multiselect("综合等级", options=grade_options)
            else:
                grade_selected = []
    
    df_display = integrated_df.copy()
    
    if search_term:
        mask = (
            df_display['客户名称'].astype(str).str.contains(search_term, case=False, na=False) |
            df_display['财务编号'].astype(str).str.contains(search_term, case=False, na=False)
        )
        df_display = df_display[mask]
    
    if risk_selected:
        df_display = df_display[df_display['风险等级'].isin(risk_selected)]
    
    if grade_selected:
        df_display = df_display[df_display['客户综合等级'].isin(grade_selected)]
    
    # 定义显示的列
    base_columns = ['财务编号', '客户名称', '所属部门']
    sales_columns = ['总销售额']
    debt_columns = [debt_column, '欠销比'] if '欠销比' in df_display.columns else [debt_column]
    analysis_columns = ['销售活跃度', '客户综合等级', '风险评分']
    
    display_columns = base_columns + sales_columns + debt_columns + analysis_columns
    display_columns = [col for col in display_columns if col in df_display.columns]
    
    if not display_columns:
        st.warning("没有可显示的列")
        return
    
    # 应用样式
    styled_df = apply_style(
        df_display[display_columns],
        highlight_integrated=True,
        highlight_score=True
    )
    
    st.dataframe(
        styled_df,
        column_config=get_column_config(analysis_year),
        width='stretch',
        height=min(600, 100 + len(df_display) * 35),
        hide_index=True,
    )
    
    # 底部信息
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.caption(f"📊 显示 {len(df_display)} / {len(integrated_df)} 条记录")
    
    with col_info2:
        # if not df_display.empty:
        filtered_debt = df_display[debt_column].sum() if debt_column in df_display.columns else 0
        st.caption(f"💰 筛选欠款: {format_currency(filtered_debt)}")
    
    with col_info3:
        filtered_sales = df_display['总销售额'].sum() if '总销售额' in df_display.columns else 0
        st.caption(f"💰 销售额: {format_currency(filtered_sales)}")

    # 导出功能
    if not df_display.empty:
        csv = df_display[display_columns].to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 导出当前数据",
            data=csv,
            file_name=f"客户信用分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            width='stretch'
        )

# -----------------------------------------------------------------------------
# 5. 客户详情视图
# -----------------------------------------------------------------------------

def render_customer_detail_view(integration_service):
    """客户详情分析视图"""
    st.header("👤 客户详情分析")
    st.caption("查看单个客户的详细销售和欠款记录")
    
    col_search, col_help = st.columns([3, 1])
    
    with col_search:
        search_term = st.text_input(
            "请输入财务编号或客户名称",
            placeholder="例如：15、413-116、东湖熊峰",
            key="customer_search_input",
            help="支持财务编号精确匹配和客户名称关键词匹配"
        )
    
    with col_help:
        st.caption("📋 搜索说明：")
        st.caption("• 15 (财务编号-精确匹配)")
        st.caption("• 413-116 (财务编号-精确匹配)")
        st.caption("• 东湖熊峰 (客户名称-关键词匹配)")
        st.caption("• 熊峰 (客户名称-包含匹配)")
    
    if search_term:
        with st.spinner("🔍 正在搜索客户数据..."):
            try:
                customer_detail = integration_service.get_customer_detail(search_term)
                
                if customer_detail['sales_records'].empty and customer_detail['debt_records'].empty:
                    st.warning(f"❌ 未找到客户 '{search_term}' 的相关记录")
                    return
                
                display_name = customer_detail.get('matched_customer_names', [search_term])[0] if customer_detail.get('matched_customer_names') else search_term
                
                st.markdown(f"### 📋 客户概览 - {display_name}")
                
                col_overview1, col_overview2, col_overview3, col_overview4 = st.columns(4)
                
                with col_overview1:
                    st.metric(
                        "总销售额",
                        f"¥{customer_detail['total_sales']:,.2f}",
                        help="该客户所有交易的总销售额"
                    )
                
                with col_overview2:
                    st.metric(
                        "2025年交易",
                        customer_detail['recent_transactions'],
                        "次交易",
                        help="2025年交易次数"
                    )
                
                with col_overview3:
                    if not customer_detail['debt_records'].empty:
                        total_debt = customer_detail['debt_records']['debt_2025'].sum()
                        st.metric("当前欠款", f"¥{total_debt:,.2f}")
                    else:
                        st.metric("当前欠款", "¥0.00", "无欠款记录")
                
                with col_overview4:
                    if not customer_detail['sales_records'].empty:
                        unique_products = customer_detail['sales_records']['product_name'].nunique()
                        st.metric("产品种类", unique_products, "种产品")
                    else:
                        st.metric("产品种类", 0, "无销售记录")
                
                if customer_detail.get('finance_ids'):
                    st.info(f"📊 相关财务编号: {', '.join(map(str, customer_detail['finance_ids']))}")
                
                st.divider()
                
                if not customer_detail['sales_records'].empty:
                    st.subheader("📈 销售记录明细")
                    
                    sales_df = customer_detail['sales_records']
                    
                    col_stats1, col_stats2, col_stats3 = st.columns(3)
                    
                    with col_stats1:
                        total_records = len(sales_df)
                        st.metric("总交易笔数", total_records)
                    
                    with col_stats2:
                        if not sales_df.empty:
                            unique_finance_ids = sales_df['finance_id'].nunique()
                            st.metric("户头数量", unique_finance_ids)
                    
                    with col_stats3:
                        if not sales_df.empty and 'record_date' in sales_df.columns:
                            try:
                                recent_sales = sales_df.sort_values('record_date', ascending=False).iloc[0]
                                recent_date = recent_sales['record_date'].strftime('%Y-%m-%d') if hasattr(recent_sales['record_date'], 'strftime') else str(recent_sales['record_date'])
                                st.metric("最近交易", recent_date)
                            except:
                                st.metric("最近交易", "未知")
                    
                    st.dataframe(
                        sales_df,
                        column_config={
                            "year": st.column_config.NumberColumn("年", format="%d", width="small"),
                            "month": st.column_config.NumberColumn("月", format="%d", width="small"),
                            "day": st.column_config.NumberColumn("日", format="%d", width="small"),
                            "customer_name": st.column_config.TextColumn("客户名称", width="medium"),
                            "finance_id": st.column_config.TextColumn("财务编号", width="small"),
                            "sub_customer_name": st.column_config.TextColumn("子客户", width="medium"),
                            "product_name": st.column_config.TextColumn("产品名称", width="medium"),
                            "color": st.column_config.TextColumn("颜色", width="small"),
                            "grade": st.column_config.TextColumn("等级", width="small"),
                            "quantity": st.column_config.NumberColumn("数量", format="%d", width="small"),
                            "unit_price": st.column_config.NumberColumn("单价", format="¥%.2f", width="small"),
                            "amount": st.column_config.NumberColumn("金额", format="¥%.2f", width="small"),
                            "ticket_number": st.column_config.TextColumn("单据号", width="small"),
                            "production_line": st.column_config.TextColumn("生产线", width="small"),
                            "record_date": st.column_config.DateColumn("记录日期", format="YYYY-MM-DD"),
                            "department": st.column_config.TextColumn("部门", width="small")
                        },
                        hide_index=True,
                        height=400
                    )
                    
                    st.caption(f"📊 共 {len(sales_df)} 条销售记录")
                else:
                    st.info("📭 暂无销售记录")
                
                if not customer_detail['debt_records'].empty:
                    st.subheader("💰 欠款记录明细")
                    
                    debt_data = customer_detail['debt_records']
                    
                    col_debt1, col_debt2 = st.columns(2)
                    
                    with col_debt1:
                        total_debt_2025 = debt_data['debt_2025'].sum()
                        st.metric("2025总欠款", f"¥{total_debt_2025:,.2f}")
                    
                    with col_debt2:
                        unique_departments = debt_data['department'].nunique()
                        st.metric("涉及部门", unique_departments)
                    
                    for dept in debt_data['department'].unique():
                        dept_data = debt_data[debt_data['department'] == dept]
                        st.markdown(f"**{dept}部门欠款**")
                        
                        st.dataframe(
                            dept_data,
                            column_config={
                                "department": st.column_config.TextColumn("部门", width="small"),
                                "customer_name": st.column_config.TextColumn("客户名称", width="medium"),
                                "finance_id": st.column_config.TextColumn("财务编号", width="small"),
                                "debt_2023": st.column_config.NumberColumn("2023欠款", format="¥%.2f", width="medium"),
                                "debt_2024": st.column_config.NumberColumn("2024欠款", format="¥%.2f", width="medium"),
                                "debt_2025": st.column_config.NumberColumn("2025欠款", format="¥%.2f", width="medium")
                            },
                            hide_index=True
                        )
                else:
                    st.info("💰 暂无欠款记录")
                
                if not customer_detail['sales_records'].empty or not customer_detail['debt_records'].empty:
                    st.divider()
                    st.subheader("📤 数据导出")
                    
                    col_export1, col_export2 = st.columns(2)
                    
                    with col_export1:
                        if not customer_detail['sales_records'].empty:
                            sales_csv = customer_detail['sales_records'].to_csv(index=False).encode('utf-8-sig')
                            st.download_button(
                                label="📥 导出销售记录",
                                data=sales_csv,
                                file_name=f"{display_name}_销售记录_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv",
                                help="导出该客户的所有销售记录"
                            )
                    
                    with col_export2:
                        if not customer_detail['debt_records'].empty:
                            debt_csv = customer_detail['debt_records'].to_csv(index=False).encode('utf-8-sig')
                            st.download_button(
                                label="📥 导出欠款记录",
                                data=debt_csv,
                                file_name=f"{display_name}_欠款记录_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv",
                                help="导出该客户的所有欠款记录"
                            )
                
            except Exception as e:
                st.error(f"❌ 获取客户详情失败: {str(e)}")
                import traceback
                st.error(traceback.format_exc())

# -----------------------------------------------------------------------------
# 6. 分类说明页面
# -----------------------------------------------------------------------------

def render_classification_help_tab():
    """分类标准说明页面 - 专业优化版"""
    st.header("📋 客户信用分类标准")
    st.caption("基于量化指标的综合评估体系")
    
    # 创建专业标签页
    tab_logic, tab_calculation, tab_management = st.tabs(["🎯 分类逻辑", "🧮 计算模型", "📊 管理策略"])
    
    with tab_logic:
        st.subheader("客户综合等级分类体系")
        
        # 紧凑的表格展示分类标准
        classification_data = [
            {
                "等级": "A级",
                "分类": "A-优质大客户、A-优质活跃客户",
                "核心条件": "无欠款 + 高销售额 + 活跃交易",
                "风险等级": "低风险",
                "特征": "现金奶牛，业务稳定"
            },
            {
                "等级": "B级", 
                "分类": "B-大额休眠客户、B-一般客户\nB1-低风险活跃欠款、B2-低风险欠款",
                "核心条件": "欠销比 ≤ 20% 或 无欠款+历史销售良好",
                "风险等级": "较低风险",
                "特征": "信用良好，需适度关注"
            },
            {
                "等级": "C级",
                "分类": "C-小额客户、C-长期无交易客户\nC1-中风险活跃欠款、C2-中风险欠款",
                "核心条件": "20% < 欠销比 ≤ 50%",
                "风险等级": "中等风险",
                "特征": "需重点关注，控制风险"
            },
            {
                "等级": "D级",
                "分类": "D-无销售无欠款\nD-高风险欠款、D-高风险长期欠款",
                "核心条件": "欠销比 > 50% 或 有欠款且长期无交易",
                "风险等级": "较高风险",
                "特征": "高风险，需要严格控制"
            },
            {
                "等级": "E级",
                "分类": "E-纯欠款客户",
                "核心条件": "有欠款但无任何销售记录",
                "风险等级": "高风险",
                "特征": "疑似恶意欠款，立即处理"
            }
        ]
        
        # 创建紧凑表格
        df_classification = pd.DataFrame(classification_data)
        
        # 应用紧凑样式
        def style_classification_table(df):
            grade_colors = {
                'A级': '#E8F5E9',
                'B级': '#E1F5FE',
                'C级': '#FFF8E1',
                'D级': '#FFF3E0',
                'E级': '#FFEBEE'
            }
            
            grade_text_colors = {
                'A级': '#2E7D32',
                'B级': '#0277BD',
                'C级': '#F9A825',
                'D级': '#EF6C00',
                'E级': '#C62828'
            }
            
            styler = df.style
            
            # 等级列样式
            def apply_grade_style(val):
                if val in grade_colors:
                    return f'background-color: {grade_colors[val]}; color: {grade_text_colors[val]}; font-weight: bold; padding: 4px 8px;'
                return ''
            
            styler = styler.map(lambda x: apply_grade_style(x), subset=['等级'])
            
            # 风险等级样式
            def apply_risk_style(val):
                if val == '低风险':
                    return 'color: #2E7D32; font-weight: bold; padding: 4px 8px;'
                elif val == '较低风险':
                    return 'color: #0277BD; font-weight: bold; padding: 4px 8px;'
                elif val == '中等风险':
                    return 'color: #F9A825; font-weight: bold; padding: 4px 8px;'
                elif val == '较高风险':
                    return 'color: #EF6C00; font-weight: bold; padding: 4px 8px;'
                elif val == '高风险':
                    return 'color: #C62828; font-weight: bold; padding: 4px 8px;'
                return ''
            
            styler = styler.map(lambda x: apply_risk_style(x), subset=['风险等级'])
            
            return styler
        
        styled_table = style_classification_table(df_classification)
        
        # 紧凑显示表格
        st.dataframe(
            styled_table,
            hide_index=True,
            use_container_width=True,
            height=280  # 紧凑高度
        )
        
        # 关键指标定义
        st.subheader("📊 核心指标定义")
        
        col_metric1, col_metric2 = st.columns(2)
        
        with col_metric1:
            st.markdown("**欠销比 (Debt-to-Sales Ratio)**")
            st.latex(r"\text{欠销比} = \frac{\text{当前欠款金额}}{\text{历史总销售额}} \times 100\%")
            st.caption("**风险评估**：")
            st.markdown("- <20%：低风险")
            st.markdown("- 20%-50%：中等风险")
            st.markdown("- >50%：高风险")
        
        with col_metric2:
            st.markdown("**销售活跃度 (Sales Activity)**")
            st.markdown("**分类标准**：")
            st.markdown("- **活跃**：近3个月有交易")
            st.markdown("- **一般**：3-6个月内有交易")
            st.markdown("- **休眠**：6-12个月内有交易")
            st.markdown("- **长期休眠**：>12个月无交易")
    
    with tab_calculation:
        st.subheader("📐 核心计算模型")
        
        # 主计算公式部分
        st.markdown("### 1. 欠销比计算")
        st.latex(r"\text{欠销比} = \frac{\text{当前欠款}}{\text{历史总销售额}} \times 100\%")
        
        # 示例计算
        with st.expander("计算示例", expanded=False):
            st.code("""
# 客户示例数据：
总销售额 = 1,200,000元
当前欠款 = 180,000元

# 计算过程：
欠销比 = (180,000 ÷ 1,200,000) × 100% = 15.0%
            """)
        
        st.markdown("### 2. 风险评分模型")
        st.latex(r"\text{风险评分} = 100 - \text{欠销比扣分} - \text{活跃度扣分} \pm \text{规模修正}")
        
        # 详细公式展开
        col_formula1, col_formula2 = st.columns(2)
        
        with col_formula1:
            st.markdown("**欠销比扣分规则**")
            st.latex(r"""
            \begin{cases}
            0 & \text{欠销比} \leq 20\% \\
            0.5 \times (\text{欠销比} - 20\%) & 20\% < \text{欠销比} \leq 50\% \\
            15 + 0.7 \times (\text{欠销比} - 50\%) & \text{欠销比} > 50\%
            \end{cases}
            """)
        
        with col_formula2:
            st.markdown("**活跃度扣分规则**")
            st.latex(r"""
            \begin{cases}
            0 & \text{近3个月有交易} \\
            5 & \text{近3-6个月有交易} \\
            15 & \text{近6-12个月有交易} \\
            30 & \text{超过12个月无交易}
            \end{cases}
            """)
        
        # 客户规模修正
        st.markdown("**客户规模修正系数**")
        st.latex(r"""
        \begin{cases}
        1.1 & \text{年销售额} \geq 50\text{万元} \\
        1.0 & 5\text{万元} \leq \text{年销售额} < 50\text{万元} \\
        0.9 & \text{年销售额} < 5\text{万元}
        \end{cases}
        """)
        
        # 实际计算示例
        st.markdown("### 3. 实际计算案例")
        
        example_data = [
            {
                "案例": "优质大客户",
                "总销售额": "800,000元",
                "当前欠款": "0元",
                "欠销比": "0%",
                "最后交易": "30天前",
                "计算过程": "100分 - 0 - 0 = 100 × 1.1 = 110分",
                "风险等级": "低风险"
            },
            {
                "案例": "高风险客户",
                "总销售额": "150,000元",
                "当前欠款": "90,000元",
                "欠销比": "60%",
                "最后交易": "200天前",
                "计算过程": "100 - 22 - 15 = 63分",
                "风险等级": "中等风险"
            },
            {
                "案例": "纯欠款客户",
                "总销售额": "0元",
                "当前欠款": "50,000元",
                "欠销比": "100%",
                "最后交易": "从未交易",
                "计算过程": "100 - 50 - 30 = 20分",
                "风险等级": "高风险"
            }
        ]
        
        df_examples = pd.DataFrame(example_data)
        st.dataframe(df_examples, hide_index=True, use_container_width=True)
    
    with tab_management:
        st.subheader("📋 分级管理策略")
        
        # 简洁的管理策略表格
        strategy_data = [
            {
                "等级": "A级",
                "授信策略": "宽松授信",
                "账期": "60-90天",
                "发货政策": "优先供应",
                "催收频率": "到期提醒"
            },
            {
                "等级": "B级",
                "授信策略": "标准授信",
                "账期": "30天",
                "发货政策": "正常供应",
                "催收频率": "逾期提醒"
            },
            {
                "等级": "C级",
                "授信策略": "谨慎授信",
                "账期": "15-30天",
                "发货政策": "控制发货量",
                "催收频率": "提前催收"
            },
            {
                "等级": "D级",
                "授信策略": "严格授信",
                "账期": "现款现货",
                "发货政策": "停止赊销",
                "催收频率": "强力催收"
            },
            {
                "等级": "E级",
                "授信策略": "停止授信",
                "账期": "全款预付",
                "发货政策": "停止发货",
                "催收频率": "法律程序"
            }
        ]
        
        df_strategy = pd.DataFrame(strategy_data)
        
        # 应用清晰样式
        def style_strategy_table(df):
            grade_colors = {
                'A级': '#E8F5E9',
                'B级': '#E1F5FE', 
                'C级': '#FFF8E1',
                'D级': '#FFF3E0',
                'E级': '#FFEBEE'
            }
            
            grade_text_colors = {
                'A级': '#2E7D32',
                'B级': '#0277BD',
                'C级': '#F9A825',
                'D级': '#EF6C00',
                'E级': '#C62828'
            }
            
            styler = df.style
            
            def apply_strategy_style(val):
                if val in grade_colors:
                    return f'background-color: {grade_colors[val]}; color: {grade_text_colors[val]}; font-weight: bold; padding: 6px 8px;'
                return ''
            
            styler = styler.map(lambda x: apply_strategy_style(x), subset=['等级'])
            
            return styler
        
        styled_strategy = style_strategy_table(df_strategy)
        
        # 显示清晰表格
        st.dataframe(
            styled_strategy,
            hide_index=True,
            use_container_width=True,
            height=220
        )
        
        # 监控指标表格
        st.markdown("### 📈 关键监控指标")
        
        monitor_data = [
            {"监控周期": "日常", "重点关注": "D/E级客户新增、高风险欠款变化"},
            {"监控周期": "每周", "重点关注": "欠销比异常波动、逾期账款清单"},
            {"监控周期": "每月", "重点关注": "等级分布变化、平均欠销比趋势"},
            {"监控周期": "每季", "重点关注": "分类标准调整、授信政策优化"}
        ]
        
        df_monitor = pd.DataFrame(monitor_data)
        st.dataframe(df_monitor, hide_index=True, use_container_width=True)
        
        # 紧急处理指南
        st.markdown("### 🚨 紧急处理指南")
        
        urgent_actions = [
            {"情况": "C级客户欠销比>40%", "行动": "电话沟通了解情况，评估降级"},
            {"情况": "B级客户连续3个月无交易", "行动": "客户经理主动拜访，了解需求"},
            {"情况": "D级客户欠款逾期60天", "行动": "启动法律程序，停止发货"},
            {"情况": "A级客户要求延长账期", "行动": "评估批准，监控后续表现"}
        ]
        
        df_urgent = pd.DataFrame(urgent_actions)
        st.dataframe(df_urgent, hide_index=True, use_container_width=True)

# -----------------------------------------------------------------------------
# 7. 主程序入口
# -----------------------------------------------------------------------------

def main():
    require_login()
    
    try:
        debt_service = DebtAnalysisService()
        integration_service = SalesDebtIntegrationService()
    except Exception as e:
        st.error(f"❌ 服务初始化失败: {str(e)}")
        st.stop()
    
    render_sidebar_legend()
    
    st.title("💳 客户信用综合分析")
    st.caption("整合销售数据与欠款数据，提供全面的客户信用评估")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 数据导入", 
        "🔍 复核分析",
        "👤 客户详情",
        "📋 分类说明"
    ])
    
    with tab1:
        render_data_import_tab(debt_service)
    
    with tab2:
        try:
            render_review_analysis_tab(integration_service)
        except Exception as e:
            st.error(f"❌ 复核分析失败: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
    
    with tab3:
        try:
            render_customer_detail_view(integration_service)
        except Exception as e:
            st.error(f"❌ 客户详情获取失败: {str(e)}")
    
    with tab4:
        render_classification_help_tab()
    
    st.markdown("---")
    st.caption(f"© 2025 客户信用分析系统 | 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
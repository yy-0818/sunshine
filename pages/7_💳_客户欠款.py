import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from core.debt_service import DebtAnalysisService
from core.customer_analysis import SalesDebtIntegrationService
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
    '无风险': '#E8F5E9',           # 极淡绿 (安全)
    '正常跟踪': '#E1F5FE',         # 极淡蓝 (正常)
    '关注类(欠款增加)': '#FFF8E1',  # 极淡黄 (警告)
    '中风险坏账': '#FFF3E0',       # 极淡橙 (较高风险)
    '高风险坏账': '#FFEBEE'        # 极淡红 (高危)
}

# 风险文本颜色
RISK_TEXT_COLORS = {
    '无风险': '#2E7D32',           # 深绿
    '正常跟踪': '#0277BD',         # 深蓝
    '关注类(欠款增加)': '#F9A825',  # 深黄
    '中风险坏账': '#EF6C00',       # 深橙
    '高风险坏账': '#C62828'        # 深红
}

# 客户价值色阶
VALUE_COLORS = {
    'A级-优质客户': '#d1e7dd',
    'B级-良好客户': '#d2f4ea',
    'C级-小额欠款': '#cff4fc',
    'C级-中等欠款': '#e0cffc',
    'D级-风险客户': '#fff3cd',
    'D级-大额欠款': '#ffe5d0',
    'E级-高风险客户': '#f8d7da'
}

# 综合等级颜色
INTEGRATED_COLORS = {
    'A-优质大客户': '#1b5e20',      # 深绿
    'A-优质活跃客户': '#2e7d32',    # 绿
    'B-大额休眠客户': '#388e3c',    # 中绿
    'B-一般客户': '#43a047',        # 浅绿
    'B1-低风险活跃欠款': '#1565c0', # 深蓝
    'B2-低风险欠款': '#1976d2',     # 蓝
    'C-小额客户': '#757575',        # 灰
    'C1-中风险持续欠款': '#f57c00', # 橙
    'C2-中风险欠款': '#ff9800',     # 浅橙
    'D-无销售无欠款': '#bdbdbd',    # 浅灰
    'D1-高风险持续欠款': '#d32f2f', # 深红
    'D2-高风险欠款': '#e53935',     # 红
    'E-纯欠款客户': '#b71c1c'       # 深红
}

# 风险评分颜色映射
RISK_SCORE_COLORS = {
    (80, 100): '#4CAF50',   # 绿
    (60, 80): '#8BC34A',    # 浅绿
    (40, 60): '#FFC107',    # 黄
    (20, 40): '#FF9800',    # 橙
    (0, 20): '#F44336'      # 红
}

# -----------------------------------------------------------------------------
# 2. 工具函数
# -----------------------------------------------------------------------------

def apply_style(df, highlight_risk=True, highlight_value=True, highlight_integrated=False):
    """为 DataFrame 应用 Pandas Styler"""
    styler = df.style

    def get_risk_style(val):
        bg_color = RISK_COLORS.get(val, '')
        text_color = RISK_TEXT_COLORS.get(val, '#333333')
        if bg_color:
            return f'background-color: {bg_color}; color: {text_color}; font-weight: 500;'
        return ''

    def get_value_style(val):
        bg_color = VALUE_COLORS.get(val, '')
        if bg_color:
            return f'background-color: {bg_color}; color: #333333; font-weight: 500;'
        return ''
    
    def get_integrated_style(val):
        bg_color = INTEGRATED_COLORS.get(val, '')
        if bg_color:
            text_color = '#FFFFFF' if val in ['A-优质大客户', 'A-优质活跃客户', 'D1-高风险持续欠款', 'D2-高风险欠款', 'E-纯欠款客户'] else '#333333'
            return f'background-color: {bg_color}; color: {text_color}; font-weight: 500;'
        return ''
    
    def get_risk_score_style(val):
        if pd.isna(val):
            return ''
        val = float(val)
        for (low, high), color in RISK_SCORE_COLORS.items():
            if low <= val < high:
                text_color = '#FFFFFF' if val < 40 else '#333333'
                return f'background-color: {color}; color: {text_color}; font-weight: bold;'
        return ''

    if highlight_risk and '坏账风险' in df.columns:
        styler = styler.map(get_risk_style, subset=['坏账风险'])
    
    if highlight_value and '客户价值等级' in df.columns:
        styler = styler.map(get_value_style, subset=['客户价值等级'])
    
    if highlight_integrated and '客户综合等级' in df.columns:
        styler = styler.map(get_integrated_style, subset=['客户综合等级'])
    
    if '风险评分' in df.columns:
        styler = styler.map(get_risk_score_style, subset=['风险评分'])

    # 格式化数值列
    numeric_columns = [c for c in df.columns if any(keyword in c for keyword in ['欠款', '变化', '金额', '评分', '销量', '比率', '比例', '占比'])]
    if numeric_columns:
        styler = styler.format("{:,.2f}", subset=numeric_columns)
    
    return styler

def get_column_config():
    """配置 Streamlit 原生列显示格式"""
    config = {
        "财务编号": st.column_config.TextColumn("财务编号", width="small", help="统一的财务编号格式"),
        "客户代码": st.column_config.TextColumn("客户代码", width="small"),
        "客户名称": st.column_config.TextColumn("客户名称", width="medium"),
        "2023欠款": st.column_config.NumberColumn("2023欠款", format="¥%.2f", min_value=0),
        "2024欠款": st.column_config.NumberColumn("2024欠款", format="¥%.2f", min_value=0),
        "2025欠款": st.column_config.NumberColumn("2025欠款", format="¥%.2f", min_value=0, help="当前年度最新欠款金额"),
        "23-24变化": st.column_config.NumberColumn("23-24变化", format="¥%.2f"),
        "24-25变化": st.column_config.NumberColumn("24-25变化", format="¥%.2f"),
        "23-25总变化": st.column_config.NumberColumn("总变化趋势", format="¥%.2f", help="两年内的总欠款变化趋势"),
        "坏账风险": st.column_config.TextColumn("坏账风险", help="系统自动计算的风险评级", width="medium"),
        "客户价值等级": st.column_config.TextColumn("客户价值等级", width="medium"),
        "客户类型": st.column_config.TextColumn("客户类型", width="medium"),
        "详细分类": st.column_config.TextColumn("详细分类", width="medium"),
        "所属部门": st.column_config.TextColumn("所属部门", width="small"),
        "总销售额": st.column_config.NumberColumn("总销售额", format="¥%.2f"),
        "总销售量": st.column_config.NumberColumn("总销售量", format="%d"),
        "欠销比": st.column_config.NumberColumn("欠销比", format="%.1f%%", help="欠款占销售额的比例"),
        "销售活跃度": st.column_config.TextColumn("销售活跃度", width="medium"),
        "客户综合等级": st.column_config.TextColumn("综合等级", width="medium"),
        "风险评分": st.column_config.NumberColumn("风险分", format="%.0f", help="0-100分，分数越高风险越低"),
        "风险等级": st.column_config.TextColumn("风险等级", width="medium"),
        "最后销售日期": st.column_config.DateColumn("最后销售日期", format="YYYY-MM-DD"),
        "交易次数": st.column_config.NumberColumn("交易次数", format="%d"),
        "产品种类数": st.column_config.NumberColumn("产品种类", format="%d"),
    }
    return config

def render_sidebar_legend():
    """在侧边栏渲染图例"""
    with st.sidebar:
        st.header("📚 系统图例说明")
        
        with st.expander("📊 风险等级颜色", expanded=True):
            for risk, bg in RISK_COLORS.items():
                fg = RISK_TEXT_COLORS.get(risk, 'black')
                st.markdown(
                    f'<div style="background-color: {bg}; color: {fg}; padding: 4px 8px; '
                    f'border-radius: 4px; margin-bottom: 4px; font-size: 0.9em; border: 1px solid {fg}30;">'
                    f'<b>{risk}</b></div>', 
                    unsafe_allow_html=True
                )
        
        with st.expander("🏆 客户价值颜色", expanded=False):
            for val, bg in VALUE_COLORS.items():
                st.markdown(
                    f'<div style="background-color: {bg}; color: #333; padding: 4px 8px; '
                    f'border-radius: 4px; margin-bottom: 4px; font-size: 0.9em;">'
                    f'{val}</div>', 
                    unsafe_allow_html=True
                )
        
        with st.expander("🎯 综合等级颜色", expanded=False):
            for val, bg in INTEGRATED_COLORS.items():
                text_color = '#FFFFFF' if val in ['A-优质大客户', 'A-优质活跃客户', 'D1-高风险持续欠款', 'D2-高风险欠款', 'E-纯欠款客户'] else '#333333'
                st.markdown(
                    f'<div style="background-color: {bg}; color: {text_color}; padding: 4px 8px; '
                    f'border-radius: 4px; margin-bottom: 4px; font-size: 0.8em; font-weight: 500;">'
                    f'{val}</div>', 
                    unsafe_allow_html=True
                )
        
        with st.expander("📈 风险评分颜色", expanded=False):
            for (low, high), color in RISK_SCORE_COLORS.items():
                text_color = '#FFFFFF' if high <= 40 else '#333333'
                st.markdown(
                    f'<div style="background-color: {color}; color: {text_color}; padding: 4px 8px; '
                    f'border-radius: 4px; margin-bottom: 4px; font-size: 0.9em;">'
                    f'{low}-{high}分</div>', 
                    unsafe_allow_html=True
                )
        
        # 添加系统状态信息
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

# -----------------------------------------------------------------------------
# 3. 页面渲染逻辑
# -----------------------------------------------------------------------------

def render_data_import_tab(debt_service):
    """数据导入页面"""
    st.header("📥 数据导入中心")
    st.caption("请上传符合格式的 Excel 文件以更新系统数据。")

    col1, col2 = st.columns(2)

    def handle_upload(column, title, key_prefix, dept_type, import_func):
        with column:
            with st.container(border=True):
                st.subheader(f"{title}")
                uploaded_file = st.file_uploader(f"上传{dept_type}数据", type=['xlsx', 'xls'], key=f"{key_prefix}_file")
                
                if uploaded_file:
                    try:
                        # 读取Excel文件
                        df_raw = pd.read_excel(uploaded_file)
                        st.info(f"📄 读取到 {len(df_raw)} 行原始数据")
                        
                        with st.status("🔄 正在处理数据...", expanded=True) as status:
                            st.write("🔍 清洗数据格式...")
                            df_clean = process_debt_excel_data(df_raw, dept_type)
                            
                            if df_clean.empty:
                                st.error("❌ 未找到有效数据，请检查文件格式")
                                return
                            
                            st.write(f"✅ 有效数据: {len(df_clean)} 条")
                            
                            # 数据验证
                            issues = validate_debt_data(df_clean)
                            if issues:
                                st.warning(f"⚠️ 发现 {len(issues)} 个潜在问题")
                                for i in issues[:3]:
                                    st.write(f"- {i}")
                                if len(issues) > 3:
                                    st.write(f"- ...等 {len(issues)-3} 个问题")
                            
                            status.update(label="✅ 数据准备就绪", state="complete", expanded=False)

                        # 显示数据预览
                        st.write("📋 处理后的数据预览（前10行）:")
                        st.dataframe(
                            df_clean.head(10),
                            column_config={
                                "finance_id": "财务编号",
                                "customer_name": "客户名称",
                                "debt_2023": st.column_config.NumberColumn("2023欠款", format="¥%.2f"),
                                "debt_2024": st.column_config.NumberColumn("2024欠款", format="¥%.2f"),
                                "debt_2025": st.column_config.NumberColumn("2025欠款", format="¥%.2f"),
                            },
                            hide_index=True,
                            width='stretch'
                        )
                        
                        # 导入按钮
                        if st.button(f"🚀 确认导入{dept_type}数据", key=f"{key_prefix}_btn", type="primary", width='stretch'):
                            with st.spinner(f"正在导入{dept_type}数据..."):
                                success_count, error_count = import_func(df_clean)
                                
                                if error_count == 0:
                                    st.success(f"✅ 导入成功！新增/更新 {success_count} 条记录")
                                    
                                    # 显示导入统计
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

    handle_upload(col1, "🏛️ 古建部门", "dept1", "古建", debt_service.import_department1_debt)
    handle_upload(col2, "🏺 陶瓷部门", "dept2", "陶瓷", debt_service.import_department2_debt)

    # 数据模板说明
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
        
        # 示例数据
        st.markdown("### 示例数据格式：")
        sample_df = get_sample_data()
        st.dataframe(sample_df, hide_index=True, width='stretch')
        
        # 提供模板下载
        csv = sample_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下载数据模板",
            data=csv,
            file_name="客户欠款数据模板.csv",
            mime="text/csv",
            help="下载标准格式的数据模板"
        )

def render_analysis_view(df, title, icon):
    """
    单部门分析视图
    """
    if df.empty:
        st.warning(f"📭 暂无{title}数据，请先前往「数据导入」页面上传文件。")
        
        # 提供快速跳转
        if st.button(f"🚀 前往{title}数据导入", key=f"goto_{title}"):
            st.switch_page("7_💳_客户欠款.py#数据导入")
        return

    st.markdown(f"### {icon} {title}部门概览")
    
    # --- 计算单部门指标 ---
    total_2025 = df['2025欠款'].sum()
    total_2024 = df['2024欠款'].sum() if '2024欠款' in df.columns else 0
    change_val = total_2025 - total_2024
    change_percent = (change_val / total_2024 * 100) if total_2024 > 0 else 0
    
    # 统计各类客户
    high_risk_keywords = ['中风险坏账', '高风险坏账']
    high_risk_count = len(df[df['坏账风险'].isin(high_risk_keywords)])
    premium_count = len(df[df['客户价值等级'] == 'A级-优质客户'])
    no_debt_count = len(df[df['2025欠款'] == 0])
    
    # --- 顶部 KPI 卡片 ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "总客户数",
            f"{len(df):,}",
            "位客户",
            help=f"{title}部门总客户数"
        )
    
    with col2:
        st.metric(
            "2025欠款总额",
            format_currency(total_2025),
            f"{change_percent:+.1f}%",
            delta_color="inverse",
            help="当前年度总欠款及同比变化"
        )
    
    with col3:
        st.metric(
            "需关注客户",
            f"{high_risk_count:,}",
            f"{high_risk_count/len(df)*100:.1f}%",
            delta_color="inverse",
            help="中高风险坏账客户数量"
        )
    
    with col4:
        st.metric(
            "优质客户",
            f"{premium_count:,}",
            f"{no_debt_count}位无欠款",
            help="A级优质客户数量"
        )

    st.divider()

    # --- 图表分析区 ---
    st.subheader("📊 数据分析")
    
    tab_chart1, tab_chart2, tab_chart3 = st.columns(3)
    
    with tab_chart1:
        if '坏账风险' in df.columns:
            risk_counts = df['坏账风险'].value_counts()
            fig_risk = px.pie(
                values=risk_counts.values,
                names=risk_counts.index,
                title="客户风险分布",
                color=risk_counts.index,
                color_discrete_map=RISK_COLORS
            )
            fig_risk.update_traces(textposition='inside', textinfo='percent+label')
            fig_risk.update_layout(
                showlegend=True,
                margin=dict(t=50, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_risk, width='stretch')
        else:
            st.info("暂无风险分类数据")
    
    with tab_chart2:
        if '客户类型' in df.columns:
            type_counts = df['客户类型'].value_counts()
            fig_type = px.bar(
                x=type_counts.index,
                y=type_counts.values,
                title="客户类型分布",
                color=type_counts.index,
                labels={'x': '客户类型', 'y': '客户数量'},
                text=type_counts.values
            )
            fig_type.update_layout(
                xaxis_title="客户类型",
                yaxis_title="客户数量",
                showlegend=False
            )
            fig_type.update_traces(texttemplate='%{text}', textposition='outside')
            st.plotly_chart(fig_type, width='stretch')
    
    with tab_chart3:
        # 欠款金额分布
        if '2025欠款' in df.columns:
            # 按欠款金额分组
            df_copy = df.copy()
            df_copy['欠款区间'] = pd.cut(df_copy['2025欠款'], 
                                       bins=[0, 1000, 5000, 10000, 50000, float('inf')],
                                       labels=['0-1千', '1千-5千', '5千-1万', '1万-5万', '5万以上'])
            
            debt_group = df_copy['欠款区间'].value_counts().sort_index()
            fig_debt = px.bar(
                x=debt_group.index,
                y=debt_group.values,
                title="欠款金额分布",
                labels={'x': '欠款区间', 'y': '客户数量'},
                text=debt_group.values,
                color=debt_group.index,
                color_discrete_sequence=px.colors.sequential.Reds_r
            )
            fig_debt.update_layout(
                xaxis_title="欠款区间 (元)",
                yaxis_title="客户数量",
                showlegend=False
            )
            fig_debt.update_traces(texttemplate='%{text}', textposition='outside')
            st.plotly_chart(fig_debt, width='stretch')

    # --- 详细数据查询区 ---
    st.subheader("🔍 详细数据查询")
    
    with st.container(border=True):
        # 筛选器
        col_filter1, col_filter2, col_filter3, col_filter4 = st.columns([2, 2, 2, 1])
        
        with col_filter1:
            search_term = st.text_input(
                "🔍 搜索客户",
                placeholder="输入名称或编号...",
                key=f"search_{title}",
                help="支持客户名称和财务编号搜索"
            )
        
        with col_filter2:
            if '坏账风险' in df.columns:
                risk_options = ['全部'] + list(df['坏账风险'].unique())
                risk_selected = st.multiselect(
                    "风险等级",
                    options=risk_options,
                    default=['全部'],
                    key=f"risk_{title}"
                )
                if '全部' in risk_selected:
                    risk_filter = df['坏账风险'].unique()
                else:
                    risk_filter = risk_selected
        
        with col_filter3:
            if '客户价值等级' in df.columns:
                value_options = ['全部'] + list(df['客户价值等级'].unique())
                value_selected = st.multiselect(
                    "价值等级",
                    options=value_options,
                    default=['全部'],
                    key=f"value_{title}"
                )
                if '全部' in value_selected:
                    value_filter = df['客户价值等级'].unique()
                else:
                    value_filter = value_selected
        
        with col_filter4:
            st.write("")  # 占位
            st.write("")  # 占位
            show_colors = st.toggle("🎨 颜色高亮", value=True, key=f"colors_{title}")

    # 应用筛选
    df_filtered = df.copy()
    
    if search_term:
        mask = (
            df_filtered['客户名称'].str.contains(search_term, case=False, na=False) |
            df_filtered['客户代码'].astype(str).str.contains(search_term, case=False, na=False)
        )
        df_filtered = df_filtered[mask]
    
    if '坏账风险' in df.columns and 'risk_filter' in locals():
        df_filtered = df_filtered[df_filtered['坏账风险'].isin(risk_filter)]
    
    if '客户价值等级' in df.columns and 'value_filter' in locals():
        df_filtered = df_filtered[df_filtered['客户价值等级'].isin(value_filter)]
    
    # 选择显示列
    display_columns = [
        '客户代码', '客户名称', '2023欠款', '2024欠款', '2025欠款',
        '23-24变化', '24-25变化', '23-25总变化', '坏账风险', '客户价值等级'
    ]
    display_columns = [col for col in display_columns if col in df_filtered.columns]
    
    # 应用样式
    styled_df = apply_style(
        df_filtered[display_columns],
        highlight_risk=show_colors,
        highlight_value=show_colors
    )
    
    # 显示数据
    st.dataframe(
        styled_df,
        column_config=get_column_config(),
        width='stretch',
        height=min(600, 100 + len(df_filtered) * 35),
        hide_index=True
    )
    
    # 底部统计信息
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.caption(f"📊 显示 {len(df_filtered)} / {len(df)} 条记录")
    with col_info2:
        if not df_filtered.empty:
            total_filtered_debt = df_filtered['2025欠款'].sum()
            st.caption(f"💰 筛选欠款总额: {format_currency(total_filtered_debt)}")
    with col_info3:
        if not df_filtered.empty and '坏账风险' in df_filtered.columns:
            high_risk_filtered = len(df_filtered[df_filtered['坏账风险'].isin(high_risk_keywords)])
            st.caption(f"⚠️ 高风险客户: {high_risk_filtered} 位")

def render_comprehensive_tab(debt_service):
    """
    综合部门分析视图
    """
    # 获取数据
    df1 = debt_service.get_department1_debt()
    df2 = debt_service.get_department2_debt()

    if df1.empty and df2.empty:
        st.warning("📭 暂无数据，请先导入数据。")
        return

    # 分析数据 - 只在合并前分析一次
    if not df1.empty:
        df1_analyzed = debt_service.analyze_debt_data(df1)
        df1_analyzed['所属部门'] = '古建'
    else:
        df1_analyzed = pd.DataFrame()
    
    if not df2.empty:
        df2_analyzed = debt_service.analyze_debt_data(df2)
        df2_analyzed['所属部门'] = '陶瓷'
    else:
        df2_analyzed = pd.DataFrame()

    # 合并数据 - 只在最后合并一次
    df_all = pd.concat([df1_analyzed, df2_analyzed], ignore_index=True)
    
    if df_all.empty:
        st.warning("📭 合并后无数据")
        return

    st.header("📈 全公司欠款综合看板")
    
    # --- 计算全公司指标 ---
    total_2025 = df_all['2025欠款'].sum()
    total_2024 = df_all['2024欠款'].sum() if '2024欠款' in df_all.columns else 0
    total_change = total_2025 - total_2024
    change_percent = (total_change / total_2024 * 100) if total_2024 > 0 else 0

    # 顶部 KPI
    k1, k2, k3, k4 = st.columns(4)
    
    with k1:
        st.metric(
            "全公司客户数",
            f"{len(df_all):,}",
            f"古建:{len(df1)} 陶瓷:{len(df2)}",
            help="全公司总客户数及部门分布"
        )
    
    with k2:
        st.metric(
            "2025总欠款",
            format_currency(total_2025),
            f"{change_percent:+.1f}%",
            delta_color="inverse",
            help="全公司总欠款及同比变化"
        )
    
    with k3:
        high_risk_all = df_all[df_all['坏账风险'] == '高风险坏账']
        high_risk_count = len(high_risk_all)
        high_risk_percent = (high_risk_count / len(df_all) * 100) if len(df_all) > 0 else 0
        st.metric(
            "高风险坏账客户",
            f"{high_risk_count:,}",
            f"{high_risk_percent:.1f}%",
            delta_color="inverse",
            help="高风险坏账客户数量及占比"
        )
    
    with k4:
        if not df_all.empty:
            top_debtor = df_all.loc[df_all['2025欠款'].idxmax()]
            top_debtor_name = top_debtor['客户名称'][:15] + "..." if len(top_debtor['客户名称']) > 15 else top_debtor['客户名称']
            st.metric(
                "最大欠款客户",
                top_debtor_name,
                format_currency(top_debtor['2025欠款']),
                help="欠款金额最大的客户"
            )

    st.divider()

    # --- 部门对比分析 ---
    st.subheader("🏢 部门对比分析")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # 部门欠款对比
        if '所属部门' in df_all.columns:
            dept_debt = df_all.groupby('所属部门')['2025欠款'].sum().reset_index()
            fig_dept = px.bar(
                dept_debt,
                x='所属部门',
                y='2025欠款',
                title="部门欠款总额对比",
                text=[format_currency(x) for x in dept_debt['2025欠款']],
                color='所属部门',
                color_discrete_sequence=['#1f77b4', '#ff7f0e']
            )
            fig_dept.update_layout(
                xaxis_title="部门",
                yaxis_title="欠款总额 (¥)",
                height=350
            )
            fig_dept.update_traces(textposition='outside')
            st.plotly_chart(fig_dept, width='stretch')
    
    with col_chart2:
        # 部门客户数对比
        if '所属部门' in df_all.columns:
            dept_counts = df_all['所属部门'].value_counts().reset_index()
            dept_counts.columns = ['所属部门', '客户数']
            fig_counts = px.pie(
                dept_counts,
                values='客户数',
                names='所属部门',
                title="部门客户数分布",
                color='所属部门',
                color_discrete_sequence=['#1f77b4', '#ff7f0e']
            )
            fig_counts.update_traces(textposition='inside', textinfo='percent+label')
            fig_counts.update_layout(height=350)
            st.plotly_chart(fig_counts, width='stretch')

    # --- 全局数据检索 ---
    st.subheader("🌐 全局数据检索")
    
    with st.container(border=True):
        col_search1, col_search2, col_search3 = st.columns([2, 1, 2])
        
        with col_search1:
            all_search = st.text_input(
                "🔍 全局搜索",
                placeholder="输入客户名称或财务编号...",
                key="all_search_global"
            )
        
        with col_search2:
            dept_filter = st.multiselect(
                "部门筛选",
                ['古建', '陶瓷'],
                default=['古建', '陶瓷'],
                placeholder="选择部门"
            )
        
        with col_search3:
            if '坏账风险' in df_all.columns:
                risk_filter_all = st.multiselect(
                    "风险等级",
                    df_all['坏账风险'].unique(),
                    placeholder="选择风险等级"
                )

    # 应用筛选
    df_view = df_all.copy()
    
    if all_search:
        mask = (
            df_view['客户名称'].str.contains(all_search, case=False, na=False) |
            df_view['客户代码'].astype(str).str.contains(all_search, case=False, na=False)
        )
        df_view = df_view[mask]
    
    if dept_filter:
        df_view = df_view[df_view['所属部门'].isin(dept_filter)]
    
    if '坏账风险' in df_all.columns and risk_filter_all:
        df_view = df_view[df_view['坏账风险'].isin(risk_filter_all)]

    # 显示列配置
    display_cols = ['所属部门', '客户代码', '客户名称', '2025欠款', '23-25总变化', '坏账风险', '客户价值等级']
    display_cols = [col for col in display_cols if col in df_view.columns]
    
    # 应用样式
    styled_view = apply_style(df_view[display_cols])
    
    # 显示数据
    config = get_column_config()
    config["所属部门"] = st.column_config.TextColumn("部门", width="small")
    
    st.dataframe(
        styled_view,
        column_config=config,
        width='stretch',
        height=min(500, 100 + len(df_view) * 35),
        hide_index=True
    )
    
    # 导出按钮
    if not df_view.empty:
        csv = df_view[display_cols].to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 导出筛选结果",
            data=csv,
            file_name=f"全局数据检索_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            width='stretch'
        )

def render_integrated_analysis_tab(integration_service):
    """销售欠款综合分析页面"""
    st.header("🏆 销售欠款综合分析")
    st.caption("结合销售数据与欠款数据进行综合信用评估")
    
    # --- 分析参数设置 ---
    with st.container(border=True):
        st.subheader("⚙️ 分析参数设置")
        
        col_param1, col_param2, col_param3 = st.columns(3)
        
        with col_param1:
            analysis_year = st.selectbox(
                "📅 分析年份",
                options=[25, 24, 23],
                index=0,
                format_func=lambda x: f"20{x}年",
                help="选择分析的主要销售年份"
            )
        
        with col_param2:
            department_filter = st.multiselect(
                "🏢 部门筛选",
                options=['古建', '陶瓷'],
                default=['古建', '陶瓷'],
                help="选择分析的部门"
            )
        
        with col_param3:
            min_sales = st.number_input(
                "💰 最低销售额筛选",
                min_value=0,
                value=0,
                step=10000,
                help="只显示销售额大于此值的客户"
            )
    
    # --- 获取整合数据 ---
    with st.spinner("🔄 正在整合销售与欠款数据..."):
        try:
            integrated_df = integration_service.get_integrated_customer_analysis(analysis_year)
            
            if integrated_df.empty:
                st.warning("📭 暂无整合数据，请确保已导入销售数据和欠款数据")
                return
            
            # 应用部门筛选
            if department_filter and '所属部门' in integrated_df.columns:
                integrated_df = integrated_df[integrated_df['所属部门'].isin(department_filter)]
            
            # 应用销售额筛选
            if min_sales > 0 and '总销售额' in integrated_df.columns:
                integrated_df = integrated_df[integrated_df['总销售额'] >= min_sales]

            if not integrated_df.empty:
                # 确保财务编号是字符串类型
                if '财务编号' in integrated_df.columns:
                    integrated_df['财务编号'] = integrated_df['财务编号'].astype(str)
                
                # 检查并清理重复数据
                dup_check_cols = []
                if '财务编号' in integrated_df.columns:
                    dup_check_cols.append('财务编号')
                if '所属部门' in integrated_df.columns:
                    dup_check_cols.append('所属部门')
                
                if dup_check_cols:
                    duplicate_mask = integrated_df.duplicated(subset=dup_check_cols, keep='first')
                    if duplicate_mask.any():
                        st.warning(f"⚠️ 发现 {duplicate_mask.sum()} 条重复记录，已自动清理")
                        integrated_df = integrated_df[~duplicate_mask].reset_index(drop=True)
            
        except Exception as e:
            st.error(f"❌ 数据获取失败: {str(e)}")
            return
    
    # --- 关键指标 ---
    st.subheader("📊 综合指标概览")
    
    total_customers = len(integrated_df)
    active_customers = len(integrated_df[integrated_df['销售活跃度'].isin(['活跃(30天内)', '一般活跃(90天内)'])]) if '销售活跃度' in integrated_df.columns else 0
    premium_customers = len(integrated_df[integrated_df['客户综合等级'].str.startswith('A-')]) if '客户综合等级' in integrated_df.columns else 0
    high_risk_customers = len(integrated_df[integrated_df['风险等级'].isin(['高风险', '较高风险'])]) if '风险等级' in integrated_df.columns else 0
    
    total_sales = integrated_df['总销售额'].sum()
    total_debt = integrated_df['2025欠款'].sum() if '2025欠款' in integrated_df.columns else 0
    debt_sales_ratio = (total_debt / total_sales * 100) if total_sales > 0 else 0
    avg_risk_score = integrated_df['风险评分'].mean() if '风险评分' in integrated_df.columns else 0
    
    # KPI 指标卡片
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.metric(
            "总客户数",
            f"{total_customers:,}",
            help="包含销售和欠款数据的客户总数"
        )
    
    with kpi2:
        st.metric(
            "活跃客户",
            f"{active_customers:,}",
            f"{active_customers/total_customers*100:.1f}%" if total_customers > 0 else "0%",
            help="近90天内有销售的活跃客户"
        )
    
    with kpi3:
        st.metric(
            "优质客户",
            f"{premium_customers:,}",
            "A级客户",
            help="综合等级为A级的优质客户"
        )
    
    with kpi4:
        st.metric(
            "风险客户",
            f"{high_risk_customers:,}",
            "需重点关注",
            delta_color="inverse",
            help="高风险和较高风险客户"
        )
    
    # 第二行KPI
    kpi5, kpi6, kpi7 = st.columns(3)
    
    with kpi5:
        st.metric(
            "总销售额",
            format_currency(total_sales),
            help="所有客户的总销售额"
        )
    
    with kpi6:
        st.metric(
            "总欠款额",
            format_currency(total_debt),
            f"欠销比: {debt_sales_ratio:.1f}%",
            delta_color="inverse",
            help="总欠款额及欠款销售比"
        )
    
    with kpi7:
        st.metric(
            "平均风险分",
            f"{avg_risk_score:.0f}",
            "分",
            help="平均风险评分（0-100分，越高越好）"
        )
    
    st.divider()
    
    # --- 分析图表 ---
    st.subheader("📈 客户分布分析")
    
    tab_chart1, tab_chart2, tab_chart3, tab_chart4 = st.tabs(["等级分布", "风险分布", "部门对比", "欠销关系"])
    
    with tab_chart1:
        if '客户综合等级' in integrated_df.columns:
            level_counts = integrated_df['客户综合等级'].value_counts().reset_index()
            level_counts.columns = ['客户综合等级', '客户数']
            
            fig_level = px.bar(
                level_counts,
                x='客户综合等级',
                y='客户数',
                title="客户综合等级分布",
                color='客户综合等级',
                color_discrete_map=INTEGRATED_COLORS,
                text='客户数'
            )
            fig_level.update_layout(
                xaxis_title="综合等级",
                yaxis_title="客户数量",
                height=400,
                showlegend=False
            )
            fig_level.update_traces(textposition='outside')
            st.plotly_chart(fig_level, width='stretch')
    
    with tab_chart2:
        if '风险等级' in integrated_df.columns:
            risk_counts = integrated_df['风险等级'].value_counts().reset_index()
            risk_counts.columns = ['风险等级', '客户数']
            
            fig_risk = px.pie(
                risk_counts,
                values='客户数',
                names='风险等级',
                title="客户风险等级分布",
                color='风险等级',
                color_discrete_map={
                    '低风险': '#4CAF50',
                    '较低风险': '#8BC34A',
                    '中等风险': '#FFC107',
                    '较高风险': '#FF9800',
                    '高风险': '#F44336'
                }
            )
            fig_risk.update_traces(textposition='inside', textinfo='percent+label')
            fig_risk.update_layout(height=400)
            st.plotly_chart(fig_risk, width='stretch')
    
    with tab_chart3:
        if '所属部门' in integrated_df.columns and '风险等级' in integrated_df.columns:
            dept_risk = pd.crosstab(integrated_df['所属部门'], integrated_df['风险等级'])
            
            fig_heat = px.imshow(
                dept_risk,
                title="部门风险分布热力图",
                text_auto=True,
                color_continuous_scale='OrRd',
                labels=dict(x="风险等级", y="部门", color="客户数"),
                aspect="auto"
            )
            fig_heat.update_layout(height=400)
            st.plotly_chart(fig_heat, width='stretch')
    
    with tab_chart4:
        if '总销售额' in integrated_df.columns and '2025欠款' in integrated_df.columns:
            # 复制数据用于散点图
            scatter_df = integrated_df.copy()
            
            # 过滤掉异常数据：销售额<=0或欠款为负值
            scatter_df = scatter_df[
                (scatter_df['总销售额'] > 0) & 
                (scatter_df['2025欠款'] >= 0)
            ]
            
            if not scatter_df.empty:
                # 计算欠销比，确保非负
                scatter_df['欠销比'] = scatter_df.apply(
                    lambda row: max(0, (row['2025欠款'] / row['总销售额'] * 100)) 
                    if row['总销售额'] > 0 else 0,
                    axis=1
                )
                
                # 对欠销比进行归一化处理，用于散点大小
                # 避免太大或太小的值
                if scatter_df['欠销比'].max() > 0:
                    max_debt_ratio = scatter_df['欠销比'].max()
                    scatter_df['size_scaled'] = scatter_df['欠销比'].apply(
                        lambda x: max(5, min(50, (x / max_debt_ratio) * 30 + 5))
                    )
                else:
                    scatter_df['size_scaled'] = 10
                
                # 创建散点图
                fig_scatter = px.scatter(
                    scatter_df,
                    x='总销售额',
                    y='2025欠款',
                    size='size_scaled',
                    color='客户综合等级' if '客户综合等级' in scatter_df.columns else None,
                    hover_data=['客户名称', '财务编号', '欠销比'],
                    title="销售额 vs 欠款额 散点图",
                    color_discrete_map=INTEGRATED_COLORS,
                    log_x=True if scatter_df['总销售额'].min() > 0 else False,
                    log_y=True if scatter_df['2025欠款'].min() > 0 else False
                )
                
                fig_scatter.update_layout(
                    xaxis_title="总销售额 (元)",
                    yaxis_title="2025欠款 (元)",
                    height=400
                )
                
                # 添加趋势线（仅当有足够数据点时）
                if len(scatter_df) > 1:
                    try:
                        # 计算线性回归
                        from sklearn.linear_model import LinearRegression
                        import numpy as np
                        
                        X = scatter_df['总销售额'].values.reshape(-1, 1)
                        y = scatter_df['2025欠款'].values
                        
                        model = LinearRegression()
                        model.fit(X, y)
                        
                        # 生成预测线
                        x_range = np.linspace(X.min(), X.max(), 100).reshape(-1, 1)
                        y_pred = model.predict(x_range)
                        
                        fig_scatter.add_trace(go.Scatter(
                            x=x_range.flatten(),
                            y=y_pred,
                            mode='lines',
                            name='趋势线',
                            line=dict(color='red', width=2, dash='dash'),
                            showlegend=True
                        ))
                    except:
                        pass  # 如果无法计算趋势线，跳过
                
                st.plotly_chart(fig_scatter, width='stretch')
            else:
                st.info("📊 暂无有效的销售欠款数据用于散点图分析")
    
    # --- 详细数据表格 ---
    st.subheader("🔍 客户明细数据")
    
    with st.container(border=True):
        # 筛选器
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        
        with col_filter1:
            if '客户综合等级' in integrated_df.columns:
                grade_filter = st.multiselect(
                    "综合等级",
                    options=sorted(integrated_df['客户综合等级'].unique()),
                    placeholder="全部等级"
                )
        
        with col_filter2:
            if '风险等级' in integrated_df.columns:
                risk_filter = st.multiselect(
                    "风险等级",
                    options=sorted(integrated_df['风险等级'].unique()),
                    placeholder="全部风险等级"
                )
        
        with col_filter3:
            if '所属部门' in integrated_df.columns:
                dept_filter = st.multiselect(
                    "部门",
                    options=sorted(integrated_df['所属部门'].unique()),
                    placeholder="全部部门"
                )
        
        # 搜索框
        col_search, col_display = st.columns([3, 1])
        with col_search:
            search_query = st.text_input(
                "🔍 搜索客户名称或财务编号",
                placeholder="输入客户名称或财务编号..."
            )
        with col_display:
            st.write('')
            st.write('')
            show_colors = st.toggle("🎨 显示颜色", value=True, help="显示等级颜色高亮")
    
    # 应用筛选
    filtered_df = integrated_df.copy()
    
    if 'grade_filter' in locals() and grade_filter:
        filtered_df = filtered_df[filtered_df['客户综合等级'].isin(grade_filter)]
    
    if 'risk_filter' in locals() and risk_filter:
        filtered_df = filtered_df[filtered_df['风险等级'].isin(risk_filter)]
    
    if 'dept_filter' in locals() and dept_filter:
        filtered_df = filtered_df[filtered_df['所属部门'].isin(dept_filter)]
    
    if search_query:
        search_cols = []
        if '客户名称' in filtered_df.columns:
            search_cols.append('客户名称')
        if '财务编号' in filtered_df.columns:
            search_cols.append('财务编号')
        
        if search_cols:
            mask = pd.Series([False] * len(filtered_df))
            for col in search_cols:
                mask = mask | filtered_df[col].astype(str).str.contains(search_query, case=False, na=False)
            filtered_df = filtered_df[mask]
    
    # 选择显示列
    available_columns = [
        '财务编号', '客户名称', '所属部门', '总销售额', '2025欠款',
        '欠销比', '销售活跃度', '客户综合等级', '风险评分', '风险等级'
    ]
    
    display_columns = [col for col in available_columns if col in filtered_df.columns]
    
    if display_columns:
        display_df = filtered_df[display_columns].copy()
        
        # 格式化数值列
        if '欠销比' in display_df.columns:
            display_df['欠销比'] = display_df['欠销比'].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "0.0%")
        
        # 应用样式
        styled_df = apply_style(display_df, highlight_risk=False, highlight_value=False, highlight_integrated=show_colors)
        
        # 显示数据
        st.dataframe(
            styled_df,
            column_config=get_column_config(),
            width='stretch',
            height=min(600, 100 + len(filtered_df) * 35),
            hide_index=True
        )
        
        # 底部统计
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.caption(f"📊 显示 {len(filtered_df)} / {len(integrated_df)} 条记录")
        with col_stat2:
            if '总销售额' in filtered_df.columns:
                total_filtered_sales = filtered_df['总销售额'].sum()
                st.caption(f"💰 筛选销售额: {format_currency(total_filtered_sales)}")
        with col_stat3:
            if '2025欠款' in filtered_df.columns:
                total_filtered_debt = filtered_df['2025欠款'].sum()
                st.caption(f"💳 筛选欠款额: {format_currency(total_filtered_debt)}")
        
        # 导出按钮
        if not filtered_df.empty:
            csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 导出分析数据",
                data=csv,
                file_name=f"客户综合信用分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width='stretch'
            )

def render_customer_detail_view(integration_service):
    """客户详情分析视图"""
    st.header("👤 客户详情分析")
    st.caption("查看单个客户的详细销售和欠款记录")
    
    # 财务编号输入
    col_input, col_example = st.columns([2, 1])
    
    with col_input:
        """采用客户名称 避免编号重叠"""
        customer_name = st.text_input(
            "请输入客户名称",
            placeholder="例如：岳阳招罗甘威",
            key="customer_name_input",
            help="输入客户名称（支持模糊匹配）"
        )
    
    with col_example:
        st.caption("📋 示例客户名称:")
        st.caption("• 岳阳招罗甘威")
        st.caption("• 永州永州市陈跃军")
        st.caption("• 鑫帅辉-九方昌盛")
    
    if customer_name:
        with st.spinner("🔍 正在获取客户详情..."):
            try:
                customer_detail = integration_service.get_customer_detail(customer_name)
                
                if customer_detail['sales_records'].empty and customer_detail['debt_records'].empty:
                    st.warning(f"❌ 未找到名称为 '{customer_name}' 的客户数据")
                    return
                
                # 客户概览
                st.subheader(f"📋 客户概览 - {customer_name}")
                
                col_overview1, col_overview2, col_overview3, col_overview4 = st.columns(4)
                
                with col_overview1:
                    st.metric("总销售额", f"¥{customer_detail['total_sales']:,.2f}")
                
                with col_overview2:
                    st.metric("2025年交易", customer_detail['recent_transactions'], "次")
                
                with col_overview3:
                    if not customer_detail['debt_records'].empty:
                        total_debt = customer_detail['debt_records']['debt_2025'].sum()
                        st.metric("当前欠款", f"¥{total_debt:,.2f}")
                
                with col_overview4:
                    if not customer_detail['sales_records'].empty:
                        unique_products = customer_detail['sales_records']['product_name'].nunique()
                        st.metric("产品种类", unique_products, "种")
                
                st.divider()
                
                # 销售记录
                if not customer_detail['sales_records'].empty:
                    st.subheader("📈 销售记录明细")
                    
                    # 销售统计
                    col_sales1, col_sales2, col_sales3 = st.columns(3)
                    
                    with col_sales1:
                        avg_amount = customer_detail['sales_records']['amount'].mean()
                        st.metric("平均交易额", f"¥{avg_amount:,.2f}")
                    
                    with col_sales2:
                        max_amount = customer_detail['sales_records']['amount'].max()
                        st.metric("最大交易额", f"¥{max_amount:,.2f}")
                    
                    with col_sales3:
                        recent_date = customer_detail['sales_records'].iloc[0][['year', 'month', 'day']]
                        st.metric("最近交易", f"{recent_date['year']}-{recent_date['month']:02d}-{recent_date['day']:02d}")
                    
                    # 销售数据表格
                    st.dataframe(
                        customer_detail['sales_records'],
                        column_config={
                            "year": st.column_config.NumberColumn("年", format="%d"),
                            "month": st.column_config.NumberColumn("月", format="%d"),
                            "day": st.column_config.NumberColumn("日", format="%d"),
                            "product_name": st.column_config.TextColumn("产品名称"),
                            "color": st.column_config.TextColumn("颜色"),
                            "grade": st.column_config.TextColumn("等级"),
                            "quantity": st.column_config.NumberColumn("数量", format="%d"),
                            "unit_price": st.column_config.NumberColumn("单价", format="¥%.2f"),
                            "amount": st.column_config.NumberColumn("金额", format="¥%.2f"),
                            "ticket_number": st.column_config.TextColumn("单据号"),
                            "production_line": st.column_config.TextColumn("生产线")
                        },
                        hide_index=True,
                        width='stretch'
                    )
                else:
                    st.info("📭 暂无销售记录")
                
                # 欠款记录
                if not customer_detail['debt_records'].empty:
                    st.subheader("💰 欠款记录明细")
                    
                    # 欠款趋势图
                    debt_data = customer_detail['debt_records']
                    if len(debt_data) > 0:
                        # 汇总各部门欠款
                        debt_summary = debt_data[['debt_2023', 'debt_2024', 'debt_2025']].sum()
                        
                        col_debt1, col_debt2 = st.columns([2, 1])
                        
                        with col_debt1:
                            fig_debt = go.Figure()
                            fig_debt.add_trace(go.Bar(
                                x=['2023', '2024', '2025'],
                                y=debt_summary.values,
                                name='欠款金额',
                                marker_color='#e74c3c',
                                text=[f'¥{x:,.0f}' for x in debt_summary.values],
                                textposition='outside'
                            ))
                            fig_debt.update_layout(
                                title="欠款趋势变化",
                                xaxis_title="年份",
                                yaxis_title="欠款金额 (¥)",
                                height=300,
                                showlegend=False
                            )
                            st.plotly_chart(fig_debt, width='stretch')
                        
                        with col_debt2:
                            # 欠款部门分布
                            if 'department' in debt_data.columns:
                                dept_debt = debt_data.groupby('department')['debt_2025'].sum()
                                fig_dept = go.Figure(data=[go.Pie(
                                    labels=dept_debt.index,
                                    values=dept_debt.values,
                                    hole=.3,
                                    marker_colors=['#3498db', '#e74c3c']
                                )])
                                fig_dept.update_layout(
                                    title="部门欠款分布",
                                    height=300,
                                    showlegend=True
                                )
                                st.plotly_chart(fig_dept, width='stretch')
                    
                    # 欠款数据表格
                    st.dataframe(
                        debt_data,
                        column_config={
                            "department": st.column_config.TextColumn("部门"),
                            "customer_name": st.column_config.TextColumn("客户名称"),
                            "debt_2023": st.column_config.NumberColumn("2023欠款", format="¥%.2f"),
                            "debt_2024": st.column_config.NumberColumn("2024欠款", format="¥%.2f"),
                            "debt_2025": st.column_config.NumberColumn("2025欠款", format="¥%.2f")
                        },
                        hide_index=True,
                        width='stretch'
                    )
                else:
                    st.info("💰 暂无欠款记录")
                
                # 导出按钮
                if not customer_detail['sales_records'].empty or not customer_detail['debt_records'].empty:
                    col_export1, col_export2 = st.columns(2)
                    
                    with col_export1:
                        if not customer_detail['sales_records'].empty:
                            sales_csv = customer_detail['sales_records'].to_csv(index=False).encode('utf-8-sig')
                            st.download_button(
                                label="📥 导出销售记录",
                                data=sales_csv,
                                file_name=f"{customer_name}_销售记录_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv",
                                width='stretch'
                            )
                    
                    with col_export2:
                        if not customer_detail['debt_records'].empty:
                            debt_csv = customer_detail['debt_records'].to_csv(index=False).encode('utf-8-sig')
                            st.download_button(
                                label="📥 导出欠款记录",
                                data=debt_csv,
                                file_name=f"{customer_name}_欠款记录_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv",
                                width='stretch'
                            )
            
            except Exception as e:
                st.error(f"❌ 获取客户详情失败: {str(e)}")

def render_classification_help_tab():
    """分类标准说明页面"""
    st.header("📋 分类标准与管理建议")
    st.caption("了解系统分类逻辑和管理策略")
    
    # 创建标签页
    tab_explain, tab_advice, tab_colors = st.tabs(["分类说明", "管理建议", "颜色图例"])
    
    with tab_explain:
        st.subheader("🎯 客户分类逻辑")
        
        col_logic1, col_logic2 = st.columns(2)
        
        with col_logic1:
            st.markdown("""
            ### 📊 基础欠款分类
            
            **优质客户(无欠款)**
            - 三年欠款均为0的客户
            - 最优质的客户群体
            
            **已结清客户**
            - 从有欠款变为0的客户
            - 还款意愿良好的客户
            
            **新增欠款客户**
            - 从0变为有欠款的客户
            - 需要关注的新增风险
            
            **持续欠款客户**
            - 三年都有欠款的客户
            - 重点关注对象
            
            **波动客户**
            - 其他欠款变化情况的客户
            - 需要具体分析的客户
            """)
        
        with col_logic2:
            st.markdown("""
            ### 🎯 综合信用分类
            
            **A级客户 (优质)**
            - A-优质大客户：无欠款 + 高销售额 + 活跃
            - A-优质活跃客户：无欠款 + 中等销售额 + 活跃
            
            **B级客户 (良好)**
            - B-大额休眠客户：无欠款 + 高销售额 + 休眠
            - B-一般客户：无欠款 + 低销售额
            - B1/B2-低风险欠款：欠销比<20%
            
            **C级客户 (关注)**
            - C-小额客户：无欠款 + 无销售或极少销售
            - C1/C2-中风险欠款：欠销比20%-50%
            
            **D级客户 (风险)**
            - D-无销售无欠款：无任何业务往来
            - D1/D2-高风险欠款：欠销比>50%
            
            **E级客户 (高危)**
            - E-纯欠款客户：有欠款但无销售
            """)
    
    with tab_advice:
        st.subheader("💡 客户管理建议")
        
        advice_data = [
            {
                "等级": "A级客户",
                "特征": "无欠款、高价值、活跃",
                "管理策略": "VIP重点维护",
                "具体措施": "优先供货、价格优惠、定期拜访、新品推荐",
                "催款频率": "无需催款",
                "信用政策": "可提高信用额度"
            },
            {
                "等级": "B级客户",
                "特征": "低欠款、有销售、一般活跃",
                "管理策略": "正常维护",
                "具体措施": "标准账期、定期对账、保持沟通",
                "催款频率": "季度提醒",
                "信用政策": "维持现有政策"
            },
            {
                "等级": "C级客户",
                "特征": "中等欠款、欠销比较高",
                "管理策略": "重点关注",
                "具体措施": "缩短账期、关注欠款变化、了解经营状况",
                "催款频率": "月度跟进",
                "信用政策": "适度收紧"
            },
            {
                "等级": "D级客户",
                "特征": "高欠款、高风险",
                "管理策略": "风险控制",
                "具体措施": "停止赊销、预付款要求、专人跟进催收",
                "催款频率": "每周跟进",
                "信用政策": "现款现货"
            },
            {
                "等级": "E级客户",
                "特征": "纯欠款、无销售",
                "管理策略": "法律介入",
                "具体措施": "发律师函、准备诉讼、资产保全",
                "催款频率": "立即处理",
                "信用政策": "停止合作"
            }
        ]
        
        st.table(pd.DataFrame(advice_data))
        
        st.markdown("""
        ### 📋 风险评分说明
        
        **评分范围：0-100分**
        - **80-100分**：低风险，信用优秀
        - **60-79分**：较低风险，信用良好
        - **40-59分**：中等风险，需要关注
        - **20-39分**：较高风险，需要控制
        - **0-19分**：高风险，急需处理
        
        **评分因素：**
        1. 欠款金额（权重40%）
        2. 欠销比例（权重25%）
        3. 销售活跃度（权重20%）
        4. 持续欠款情况（权重15%）
        """)
    
    with tab_colors:
        st.subheader("🎨 系统颜色图例")
        
        col_color1, col_color2 = st.columns(2)
        
        with col_color1:
            st.markdown("##### 风险等级颜色")
            for risk, bg in RISK_COLORS.items():
                fg = RISK_TEXT_COLORS.get(risk, 'black')
                st.markdown(
                    f'<div style="background-color: {bg}; color: {fg}; padding: 8px 12px; '
                    f'border-radius: 6px; margin-bottom: 6px; font-size: 1em; border: 1px solid {fg}50; '
                    f'display: flex; justify-content: space-between; align-items: center;">'
                    f'<span><b>{risk}</b></span>'
                    f'<span style="font-size: 0.9em; color: {fg};">对应文本颜色</span>'
                    f'</div>', 
                    unsafe_allow_html=True
                )
        
        with col_color2:
            st.markdown("##### 综合等级颜色")
            for value, bg in INTEGRATED_COLORS.items():
                text_color = '#FFFFFF' if value in ['A-优质大客户', 'A-优质活跃客户', 'D1-高风险持续欠款', 'D2-高风险欠款', 'E-纯欠款客户'] else '#333333'
                st.markdown(
                    f'<div style="background-color: {bg}; color: {text_color}; padding: 8px 12px; '
                    f'border-radius: 6px; margin-bottom: 6px; font-size: 1em; font-weight: 500;">'
                    f'{value}'
                    f'</div>', 
                    unsafe_allow_html=True
                )
        
        st.markdown("##### 风险评分颜色")
        col_score1, col_score2, col_score3, col_score4, col_score5 = st.columns(5)
        
        score_ranges = [
            ((80, 100), "80-100分", "低风险"),
            ((60, 80), "60-79分", "较低风险"),
            ((40, 60), "40-59分", "中等风险"),
            ((20, 40), "20-39分", "较高风险"),
            ((0, 20), "0-19分", "高风险")
        ]
        
        for i, ((low, high), label, desc) in enumerate(score_ranges):
            with [col_score1, col_score2, col_score3, col_score4, col_score5][i]:
                color = RISK_SCORE_COLORS.get((low, high), '#FFFFFF')
                text_color = '#FFFFFF' if high <= 40 else '#333333'
                st.markdown(
                    f'<div style="background-color: {color}; color: {text_color}; padding: 15px; '
                    f'border-radius: 8px; text-align: center; margin-bottom: 5px; font-weight: bold;">'
                    f'{label}<br><span style="font-size: 0.8em;">{desc}</span>'
                    f'</div>', 
                    unsafe_allow_html=True
                )

# -----------------------------------------------------------------------------
# 6. 主程序入口
# -----------------------------------------------------------------------------

def main():
    # 页面认证
    require_login()
    
    # 初始化服务
    try:
        debt_service = DebtAnalysisService()
        integration_service = SalesDebtIntegrationService()
    except Exception as e:
        st.error(f"❌ 服务初始化失败: {str(e)}")
        st.stop()
    
    # 渲染侧边栏图例
    render_sidebar_legend()
    
    # 页面标题
    st.title("💳 客户信用综合分析系统")
    st.caption("整合销售数据与欠款数据，提供全面的客户信用评估")
    
    st.markdown("---")
    
    # 创建标签页
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📥 数据导入", 
        "🏛️ 古建分析", 
        "🏺 陶瓷分析", 
        "🔍 综合分析",
        "🏆 销售欠款分析",
        "👤 客户详情",
        "📋 分类说明"
    ])
    
    with tab1:
        render_data_import_tab(debt_service)
    
    with tab2:
        try:
            df = debt_service.get_department1_debt()
            if not df.empty:
                df = debt_service.analyze_debt_data(df)
            render_analysis_view(df, "古建", "🏛️")
        except Exception as e:
            st.error(f"❌ 古建数据分析失败: {str(e)}")
    
    with tab3:
        try:
            df = debt_service.get_department2_debt()
            if not df.empty:
                df = debt_service.analyze_debt_data(df)
            render_analysis_view(df, "陶瓷", "🏺")
        except Exception as e:
            st.error(f"❌ 陶瓷数据分析失败: {str(e)}")
    
    with tab4:
        try:
            render_comprehensive_tab(debt_service)
        except Exception as e:
            st.error(f"❌ 综合分析失败: {str(e)}")
    
    with tab5:
        try:
            render_integrated_analysis_tab(integration_service)
        except Exception as e:
            st.error(f"❌ 销售欠款分析失败: {str(e)}")
    
    with tab6:
        try:
            render_customer_detail_view(integration_service)
        except Exception as e:
            st.error(f"❌ 客户详情获取失败: {str(e)}")
    
    with tab7:
        render_classification_help_tab()
    
    # 页脚
    st.markdown("---")
    st.caption(f"© 2025 客户信用分析系统 | 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
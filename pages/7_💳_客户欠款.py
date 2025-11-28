import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.debt_service import DebtAnalysisService
from utils.auth import require_login
from utils.data_processor import process_debt_excel_data, validate_debt_data, get_sample_data

# -----------------------------------------------------------------------------
# 1. 配置与常量定义
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="客户欠款分析系统",
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

# -----------------------------------------------------------------------------
# 2. 工具函数
# -----------------------------------------------------------------------------

def apply_style(df, highlight_risk=True, highlight_value=True):
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

    if highlight_risk and '坏账风险' in df.columns:
        styler = styler.map(get_risk_style, subset=['坏账风险'])
    
    if highlight_value and '客户价值等级' in df.columns:
        styler = styler.map(get_value_style, subset=['客户价值等级'])

    return styler.format("{:,.2f}", subset=[c for c in df.columns if '欠款' in c or '变化' in c])

def get_column_config():
    """配置 Streamlit 原生列显示格式"""
    return {
        "2023欠款": st.column_config.NumberColumn("2023欠款", format="¥%.2f", min_value=0),
        "2024欠款": st.column_config.NumberColumn("2024欠款", format="¥%.2f", min_value=0),
        "2025欠款": st.column_config.NumberColumn("2025欠款", format="¥%.2f", min_value=0, help="当前年度最新欠款金额"),
        "23-24变化": st.column_config.NumberColumn("23-24变化", format="¥%.2f"),
        "24-25变化": st.column_config.NumberColumn("24-25变化", format="¥%.2f"),
        "23-25总变化": st.column_config.NumberColumn("总变化趋势", format="¥%.2f", help="两年内的总欠款变化趋势"),
        "坏账风险": st.column_config.TextColumn("坏账风险", help="系统自动计算的风险评级", width="medium"),
        "客户价值等级": st.column_config.TextColumn("客户价值等级", width="medium"),
        "客户代码": st.column_config.TextColumn("代码", width="small"),
    }

def render_sidebar_legend():
    """在侧边栏渲染图例"""
    with st.sidebar:
        st.header("📚 图例说明")
        with st.expander("风险等级颜色", expanded=True):
            for risk, bg in RISK_COLORS.items():
                fg = RISK_TEXT_COLORS.get(risk, 'black')
                st.markdown(
                    f'<div style="background-color: {bg}; color: {fg}; padding: 4px 8px; '
                    f'border-radius: 4px; margin-bottom: 4px; font-size: 0.9em; border: 1px solid {fg}30;">'
                    f'<b>{risk}</b></div>', 
                    unsafe_allow_html=True
                )
        with st.expander("客户价值颜色", expanded=False):
            for val, bg in VALUE_COLORS.items():
                st.markdown(
                    f'<div style="background-color: {bg}; color: #333; padding: 4px 8px; '
                    f'border-radius: 4px; margin-bottom: 4px; font-size: 0.9em;">'
                    f'{val}</div>', 
                    unsafe_allow_html=True
                )

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
                        df_raw = pd.read_excel(uploaded_file)
                        st.info(f"读取到 {len(df_raw)} 行原始数据")
                        with st.status("正在处理数据...", expanded=True) as status:
                            st.write("🔍 清洗数据格式...")
                            df_clean = process_debt_excel_data(df_raw, dept_type)
                            st.write(f"✅ 有效数据: {len(df_clean)} 条")
                            issues = validate_debt_data(df_clean)
                            if issues:
                                st.warning("⚠️ 发现潜在数据问题")
                                for i in issues[:3]: st.write(f"- {i}")
                            status.update(label="数据准备就绪", state="complete", expanded=False)

                        if not df_clean.empty:
                            if st.button(f"🚀 确认导入{dept_type}数据", key=f"{key_prefix}_btn", type="primary", use_container_width=True):
                                success_count, error_count = import_func(df_clean)
                                if error_count == 0:
                                    st.success(f"导入成功！新增/更新 {success_count} 条记录")
                                else:
                                    st.warning(f"导入完成。成功: {success_count}, 失败: {error_count}")
                    except Exception as e:
                        st.error(f"处理失败: {str(e)}")

    handle_upload(col1, "🏛️ 古建部门", "dept1", "古建", debt_service.import_department1_debt)
    handle_upload(col2, "🏺 陶瓷部门", "dept2", "陶瓷", debt_service.import_department2_debt)

    with st.expander("查看标准数据模板"):
        st.markdown("""
        ### 📝 Excel文件格式要求
        
        **文件结构（必须包含以下列）：**
        - **第1列**：客户代码（必须以2203开头）
        - **第2列**：客户名称  
        - **第3列**：2023年欠款金额
        - **第6列**：2024年欠款金额
        - **第9列**：2025年欠款金额
        
        **客户代码格式示例：**
        - `2203.12345` → 自动处理为 `12345`
        - `220312345` → 自动处理为 `12345`
        - `2203-12345` → 自动处理为 `12345`
        
        **示例数据格式：**
        """)
        st.dataframe(get_sample_data(), hide_index=True, use_container_width=True)

def render_analysis_view(df, title, icon):
    """
    【古建/陶瓷】单部门分析视图
    更新：总欠款指标包含与去年的差值对比
    """
    if df.empty:
        st.warning(f"暂无{title}数据，请先前往「数据导入」页面上传文件。")
        return

    st.markdown(f"### {icon} {title}概览")
    
    # --- 计算单部门指标 ---
    total_2025 = df['2025欠款'].sum()
    total_2024 = df['2024欠款'].sum() if '2024欠款' in df.columns else 0
    change_val = total_2025 - total_2024
    
    # 统计高风险客户 (根据实际风险名称)
    high_risk_keywords = ['中风险坏账', '高风险坏账', '关注类(欠款增加)']
    high_risk_count = len(df[df['坏账风险'].isin(high_risk_keywords)])
    premium_count = len(df[df['客户价值等级'] == 'A级-优质客户'])
    
    # --- 顶部 KPI ---
    m1, m2, m3, m4 = st.columns(4)
    
    m1.metric("总客户数", len(df), border=False)
    
    # 更新：展示2025总欠款及较去年的变化，保留两位小数
    m2.metric(
        "2025欠款总额", 
        f"¥{total_2025:,.2f}", 
        f"¥{change_val:,.2f}",
        delta_color="inverse",  # 红色代表增加(坏)，绿色代表减少(好)
        border=False
    )
    
    m3.metric("需关注客户", high_risk_count, delta="风险预警", delta_color="inverse", border=False)
    m4.metric("优质客户(A级)", premium_count, border=False)

    st.divider()

    # --- 图表区 ---
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("📊 风险等级分布")
        risk_counts = df['坏账风险'].value_counts().reindex(list(RISK_COLORS.keys())).fillna(0)
        
        fig_risk = px.bar(
            x=risk_counts.index, 
            y=risk_counts.values,
            color=risk_counts.index,
            color_discrete_map=RISK_TEXT_COLORS
        )
        
        fig_risk.update_layout(
            xaxis_title="风险等级",
            yaxis_title="客户数量 (人)",
            showlegend=False,
            margin=dict(t=20, b=20, l=40, r=20),
            height=350,
            xaxis={'categoryorder': 'array', 'categoryarray': list(RISK_COLORS.keys())}
        )
        st.plotly_chart(fig_risk, use_container_width=True)

    with c2:
        st.subheader("🍰 客户类型构成")
        type_counts = df['客户类型'].value_counts()
        fig_pie = px.pie(
            values=type_counts.values, 
            names=type_counts.index,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_layout(
            margin=dict(t=20, b=20, l=20, r=20), 
            height=350,
            legend_title="客户类型"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 数据详情与筛选区 ---
    st.subheader("🔍 详细数据查询")

    with st.container(border=True):
        f1, f2, f3 = st.columns([2, 1, 1])
        search_term = f1.text_input("搜索客户", placeholder="输入名称或代码...", key=f"search_{title}")
        risk_filter = f2.multiselect("风险等级", options=df['坏账风险'].unique(), placeholder="请选择风险等级", key=f"risk_{title}")
        value_filter = f3.multiselect("价值等级", options=df['客户价值等级'].unique(), placeholder="请选择价值等级", key=f"val_{title}")
        
        c_opts1, c_opts2 = st.columns(2)
        show_risk_color = c_opts1.toggle("🎨 显示风险高亮", value=True, key=f"tg_risk_{title}")
        show_val_color = c_opts2.toggle("🎨 显示价值高亮", value=True, key=f"tg_val_{title}")

    df_display = df.copy()
    if search_term:
        df_display = df_display[
            df_display['客户名称'].str.contains(search_term, case=False) | 
            df_display['客户代码'].astype(str).str.contains(search_term)
        ]
    if risk_filter:
        df_display = df_display[df_display['坏账风险'].isin(risk_filter)]
    if value_filter:
        df_display = df_display[df_display['客户价值等级'].isin(value_filter)]

    st.markdown(f"**共找到 {len(df_display)} 条记录**")
    
    display_cols = [
        '客户代码', '客户名称', '2023欠款', '2024欠款', '2025欠款',
        '23-24变化', '24-25变化', '23-25总变化', '坏账风险', '客户价值等级'
    ]
    final_cols = [c for c in display_cols if c in df_display.columns]
    
    styled_df = apply_style(
        df_display[final_cols], 
        highlight_risk=show_risk_color, 
        highlight_value=show_val_color
    )

    st.dataframe(
        styled_df,
        column_config=get_column_config(),
        use_container_width=True,
        height=500,
        hide_index=True
    )

def render_comprehensive_tab(debt_service):
    """
    【综合】分析视图
    更新：总欠款指标包含与去年的差值对比
    """
    df1 = debt_service.get_department1_debt()
    df2 = debt_service.get_department2_debt()

    if df1.empty and df2.empty:
        st.warning("请先导入数据。")
        return

    if not df1.empty:
        df1 = debt_service.analyze_debt_data(df1)
        df1['来源部门'] = '古建'
    if not df2.empty:
        df2 = debt_service.analyze_debt_data(df2)
        df2['来源部门'] = '陶瓷'

    df_all = pd.concat([df1, df2], ignore_index=True)

    st.header("📈 全公司欠款综合看板")
    
    # --- 计算全公司指标 ---
    total_2025 = df_all['2025欠款'].sum()
    total_2024 = df_all['2024欠款'].sum()
    total_change = total_2025 - total_2024

    # 顶部 KPI (无边框)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("全公司客户数", len(df_all), border=False)
    
    # 更新：展示2025总欠款及较去年的变化，保留两位小数
    k2.metric(
        "2025总欠款", 
        f"¥{total_2025:,.2f}", 
        f"{total_change:+,.2f}", 
        delta_color="inverse", 
        border=False
    )
    
    high_risk_all = df_all[df_all['坏账风险'] == '高风险坏账']
    k3.metric("高风险坏账客户", len(high_risk_all), delta="需立即处理", delta_color="inverse", border=False)
    
    top_debtor = df_all.loc[df_all['2025欠款'].idxmax()]
    k4.metric("最大单一欠款方", top_debtor['客户名称'], f"¥{top_debtor['2025欠款']:,.0f}", border=False)

    st.divider()

    st.subheader("部门对比分析")
    c1, c2 = st.columns(2)
    
    with c1:
        dept_debt = df_all.groupby('来源部门')['2025欠款'].sum().reset_index()
        fig_dept = px.bar(
            dept_debt, 
            x='来源部门', 
            y='2025欠款', 
            title="部门欠款总额对比", 
            text_auto='.2s', 
            color='来源部门'
        )
        fig_dept.update_layout(xaxis_title="部门", yaxis_title="欠款总额 (¥)")
        st.plotly_chart(fig_dept, use_container_width=True)
    
    with c2:
        risk_dept = pd.crosstab(df_all['来源部门'], df_all['坏账风险'])
        # 确保按我们定义的顺序显示
        valid_risks = [r for r in RISK_COLORS.keys() if r in risk_dept.columns]
        risk_dept = risk_dept[valid_risks] if valid_risks else risk_dept
        
        fig_heat = px.imshow(
            risk_dept, 
            title="部门风险分布热力图", 
            text_auto=True, 
            color_continuous_scale='OrRd',
            labels=dict(x="风险等级", y="部门", color="客户数")
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    st.subheader("🌐 全局数据检索")
    with st.container(border=True):
        col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
        all_search = col_s1.text_input("全局搜索", placeholder="搜索全公司客户...", key="all_search")
        dept_filter = col_s2.multiselect("部门筛选", ['古建', '陶瓷'], default=['古建', '陶瓷'], placeholder="请选择风险等级",)
        risk_filter_all = col_s3.multiselect("风险等级", df_all['坏账风险'].unique(), key="all_risk", placeholder="请选择风险等级",)

    df_view = df_all.copy()
    if all_search:
        df_view = df_view[df_view['客户名称'].str.contains(all_search, case=False)]
    if dept_filter:
        df_view = df_view[df_view['来源部门'].isin(dept_filter)]
    if risk_filter_all:
        df_view = df_view[df_view['坏账风险'].isin(risk_filter_all)]

    config = get_column_config()
    config["来源部门"] = st.column_config.TextColumn("所属部门", width="small")

    styled_view = apply_style(df_view[['来源部门', '客户代码', '客户名称', '2025欠款', '坏账风险', '客户价值等级', '23-25总变化']])
    st.dataframe(styled_view, column_config=config, use_container_width=True, hide_index=True)

def render_classification_help_tab(debt_service):
    """分类标准说明页面"""
    st.markdown('<h2 class="sub-header">📋 分类标准与管理建议</h2>', unsafe_allow_html=True)

    explanation_data = {
        '客户类型': {
            '优质客户(无欠款)': '当前无任何欠款',
            '新增欠款': '去年无欠款，今年新增',
            '持续欠款-减少': '欠款较去年有所减少',
            '持续欠款-增加': '欠款较去年增加',
        },
        '坏账风险': {
            '无风险': '欠款为0或负数',
            '正常跟踪': '欠款在正常业务范围内，有变动或金额较小',
            '关注类(欠款增加)': '欠款金额明显上升，需关注回款情况',
            '中风险坏账': '欠款金额较大或账龄较长，存在一定坏账可能',
            '高风险坏账': '巨额欠款或长期无变化，极高坏账风险'
        },
        '客户价值等级': {
            'A级': '无欠款优质客户',
            'B级': '欠款极少的良好客户',
            'C级': '正常业务往来欠款',
            'D级': '有一定风险的客户',
            'E级': '高危风险客户'
        }
    }

    st.subheader("1. 基础分类定义")
    tab_type, tab_risk, tab_val = st.tabs(["👥 客户类型", "⚠️ 风险等级", "📊 价值等级"])
    
    with tab_type:
        st.markdown("根据客户的欠款变化趋势进行分类：")
        st.table(pd.DataFrame(list(explanation_data['客户类型'].items()), columns=['类型名称', '详细定义']))

    with tab_risk:
        st.markdown("根据欠款金额大小及年限进行风险评估：")
        st.table(pd.DataFrame(list(explanation_data['坏账风险'].items()), columns=['风险等级', '判定标准']))

    with tab_val:
        st.markdown("综合考量客户价值与风险：")
        st.table(pd.DataFrame(list(explanation_data['客户价值等级'].items()), columns=['价值等级', '说明']))

    st.subheader("2. 💡 管理建议矩阵")
    advice_data = [
        {"客户等级": "A级/B级", "风险状态": "无风险/正常跟踪", "管理策略": "正常维护", "具体措施": "定期对账，保持良好关系"},
        {"客户等级": "C级", "风险状态": "关注类", "管理策略": "重点关注", "具体措施": "了解欠款增加原因，确认还款计划"},
        {"客户等级": "D级", "风险状态": "中风险坏账", "管理策略": "强力催收", "具体措施": "停止赊销，发催款函，专人跟进"},
        {"客户等级": "E级", "风险状态": "高风险坏账", "管理策略": "法律介入", "具体措施": "发律师函，准备诉讼，资产保全"}
    ]
    st.table(pd.DataFrame(advice_data))

    st.subheader("3. 🎨 系统颜色图例")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("风险等级颜色 (与数据表一致)")
        for risk, color in RISK_COLORS.items():
            text_color = RISK_TEXT_COLORS.get(risk, 'black')
            st.markdown(
                f"<div style='background-color: {color}; color: {text_color}; padding: 8px; margin: 2px; border-radius: 4px; text-align: center; border:1px solid #eee;'>"
                f"<b>{risk}</b>"
                f"</div>", 
                unsafe_allow_html=True
            )
    
    with c2:
        st.caption("价值等级颜色")
        for value, color in VALUE_COLORS.items():
            st.markdown(
                f"<div style='background-color: {color}; color: #333; padding: 8px; margin: 2px; border-radius: 4px; text-align: center; border:1px solid #eee;'>"
                f"<b>{value}</b>"
                f"</div>", 
                unsafe_allow_html=True
            )

# -----------------------------------------------------------------------------
# 4. 主程序入口
# -----------------------------------------------------------------------------

def main():
    require_login()
    debt_service = DebtAnalysisService()
    
    render_sidebar_legend()

    st.title("💳 客户欠款分析系统")
    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📥 数据导入", 
        "🏛️ 古建分析", 
        "🏺 陶瓷分析", 
        "🔍 综合分析",
        "📋 分类说明"
    ])

    with tab1:
        render_data_import_tab(debt_service)
    
    with tab2:
        df = debt_service.get_department1_debt()
        if not df.empty:
            df = debt_service.analyze_debt_data(df)
        render_analysis_view(df, "古建", "🏛️")
    
    with tab3:
        df = debt_service.get_department2_debt()
        if not df.empty:
            df = debt_service.analyze_debt_data(df)
        render_analysis_view(df, "陶瓷", "🏺")
    
    with tab4:
        render_comprehensive_tab(debt_service)
        
    with tab5:
        render_classification_help_tab(debt_service)

if __name__ == "__main__":
    main()
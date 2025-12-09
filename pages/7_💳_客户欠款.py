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
    'C1-中风险持续欠款': '较高风险',
    'C2-中风险欠款': '较高风险',
    'D-无销售无欠款': '中等风险',
    'D1-高风险持续欠款': '高风险',
    'D2-高风险欠款': '高风险',
    'E-纯欠款客户': '高风险'
}

# 风险评分颜色映射
RISK_SCORE_COLORS = {
    (80, 100): '#E8F5E9',   # 低风险背景色
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
        # 映射综合等级到风险等级
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
                # 为风险评分设置对应的文本颜色
                if high > 80:
                    text_color = '#2E7D32'  # 深绿
                elif high > 60:
                    text_color = '#0277BD'  # 深蓝
                elif high > 40:
                    text_color = '#F9A825'  # 深黄
                elif high > 20:
                    text_color = '#EF6C00'  # 深橙
                else:
                    text_color = '#C62828'  # 深红
                return f'background-color: {color}; color: {text_color}; font-weight: bold;'
        return ''

    if highlight_integrated and '客户综合等级' in df.columns:
        styler = styler.map(get_integrated_style, subset=['客户综合等级'])
    
    if highlight_score and '风险评分' in df.columns:
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
        "所属部门": st.column_config.TextColumn("所属部门", width="small"),
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

# -----------------------------------------------------------------------------
# 3. 数据导入页面 (已更新为统一欠款表)
# -----------------------------------------------------------------------------

def render_data_import_tab(debt_service):
    """数据导入页面 - 更新为统一欠款表"""
    st.header("📥 数据导入中心")
    st.caption("请上传符合格式的 Excel 文件以更新系统数据。")

    col1, col2 = st.columns(2)

    def handle_upload(column, title, key_prefix, dept_type):
        """处理文件上传和导入 - 更新为统一欠款表"""
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
                                "department": "所属部门",
                                "debt_2023": st.column_config.NumberColumn("2023欠款", format="¥%.2f"),
                                "debt_2024": st.column_config.NumberColumn("2024欠款", format="¥%.2f"),
                                "debt_2025": st.column_config.NumberColumn("2025欠款", format="¥%.2f"),
                            },
                            hide_index=True,
                            width='stretch'
                        )
                        
                        # 导入按钮 - 使用统一的导入函数
                        if st.button(f"🚀 确认导入{dept_type}数据", key=f"{key_prefix}_btn", type="primary", width='stretch'):
                            with st.spinner(f"正在导入{dept_type}数据..."):
                                # 调用统一导入函数
                                success_count, error_count = debt_service.import_debt_data(df_clean, dept_type)
                                
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

    handle_upload(col1, "🏛️ 古建部门", "dept1", "古建")
    handle_upload(col2, "🏺 陶瓷部门", "dept2", "陶瓷")

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
        sample_df = get_sample_data("古建")
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

# -----------------------------------------------------------------------------
# 4. 单部门分析视图 (基于综合分析数据)
# -----------------------------------------------------------------------------

def render_department_analysis(integration_service, department_name, icon):
    """
    单部门分析视图 - 基于综合分析数据
    """
    # 获取综合分析数据
    with st.spinner(f"正在获取{department_name}部门数据..."):
        try:
            integrated_df = get_integrated_data(integration_service)
            
            if integrated_df.empty:
                st.warning(f"📭 暂无{department_name}部门数据，请先导入销售数据和欠款数据。")
                return
            
            # 筛选特定部门 - 修复：正确处理部门筛选
            if '所属部门' in integrated_df.columns:
                # 筛选指定部门的记录
                dept_mask = integrated_df['所属部门'] == department_name
                dept_df = integrated_df[dept_mask].copy()
                
                # 去除重复的财务编号（同一个财务编号在同一个部门不应该有多条记录）
                if not dept_df.empty:
                    duplicate_mask = dept_df.duplicated(['财务编号'], keep='first')
                    if duplicate_mask.any():
                        print(f"发现 {duplicate_mask.sum()} 条重复记录，已自动清理")
                        dept_df = dept_df[~duplicate_mask].reset_index(drop=True)
            else:
                st.warning(f"❌ 数据中未找到部门信息列")
                return
            
            if dept_df.empty:
                st.warning(f"📭 暂无{department_name}部门数据")
                return
                
        except Exception as e:
            st.error(f"❌ 获取部门数据失败: {str(e)}")
            return

    st.markdown(f"### {icon} {department_name}部门综合概览")
    
    # --- 计算部门指标 ---
    total_customers = len(dept_df)
    total_debt_2025 = dept_df['2025欠款'].sum() if '2025欠款' in dept_df.columns else 0
    total_sales = dept_df['总销售额'].sum() if '总销售额' in dept_df.columns else 0
    
    # 统计风险客户
    high_risk_customers = len(dept_df[dept_df['风险等级'].isin(['高风险', '较高风险'])]) if '风险等级' in dept_df.columns else 0
    premium_customers = len(dept_df[dept_df['客户综合等级'].str.startswith('A-')]) if '客户综合等级' in dept_df.columns else 0
    active_customers = len(dept_df[dept_df['销售活跃度'].isin(['活跃(30天内)', '一般活跃(90天内)'])]) if '销售活跃度' in dept_df.columns else 0
    
    # --- 顶部 KPI 卡片 ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "总客户数",
            f"{total_customers:,}",
            help=f"{department_name}部门总客户数"
        )
    
    with col2:
        debt_sales_ratio = (total_debt_2025 / total_sales * 100) if total_sales > 0 else 0
        st.metric(
            "2025欠款总额",
            format_currency(total_debt_2025),
            f"欠销比: {debt_sales_ratio:.1f}%",
            delta_color="inverse",
            help="当前年度总欠款及欠销比例"
        )
    
    with col3:
        high_risk_ratio = (high_risk_customers / total_customers * 100) if total_customers > 0 else 0
        st.metric(
            "风险客户",
            f"{high_risk_customers:,}",
            f"{high_risk_ratio:.1f}%",
            delta_color="inverse",
            help="高风险和较高风险客户数量"
        )
    
    with col4:
        st.metric(
            "优质客户",
            f"{premium_customers:,}",
            f"{active_customers}位活跃",
            help="A级优质客户数量"
        )

    st.divider()

    # --- 图表分析区 ---
    st.subheader("📊 数据分析")
    
    tab_chart1, tab_chart2 = st.columns(2)
    
    with tab_chart1:
        if '风险等级' in dept_df.columns:
            risk_counts = dept_df['风险等级'].value_counts()
            # 按风险等级排序
            risk_order = ['低风险', '较低风险', '中等风险', '较高风险', '高风险']
            risk_counts = risk_counts.reindex(risk_order, fill_value=0)
            
            fig_risk = px.bar(
                x=risk_counts.index,
                y=risk_counts.values,
                title="客户风险等级分布",
                labels={'x': '风险等级', 'y': '客户数量'},
                text=risk_counts.values,
                color=risk_counts.index,
                color_discrete_map=RISK_COLORS
            )
            fig_risk.update_layout(
                xaxis_title="风险等级",
                yaxis_title="客户数量",
                height=400,
                showlegend=False
            )
            fig_risk.update_traces(texttemplate='%{text}', textposition='outside')
            st.plotly_chart(fig_risk, use_container_width=True)
    
    with tab_chart2:
        # 欠款金额分布
        if '2025欠款' in dept_df.columns:
            # 按欠款金额分组
            dept_df_copy = dept_df.copy()
            bins = [0, 1000, 5000, 10000, 50000, float('inf')]
            labels = ['0-1千', '1千-5千', '5千-1万', '1万-5万', '5万以上']
            dept_df_copy['欠款区间'] = pd.cut(dept_df_copy['2025欠款'], bins=bins, labels=labels)
            
            debt_group = dept_df_copy['欠款区间'].value_counts().sort_index()
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
                showlegend=False,
                height=400
            )
            fig_debt.update_traces(texttemplate='%{text}', textposition='outside')
            st.plotly_chart(fig_debt, use_container_width=True)

    # --- 详细数据查询区 ---
    st.subheader("🔍 详细数据查询")
    
    with st.container(border=True):
        # 筛选器
        col_filter1, col_filter2, col_filter3 = st.columns([3, 2, 1])
        
        with col_filter1:
            search_term = st.text_input(
                "🔍 搜索客户",
                placeholder="输入名称或财务编号...",
                key=f"search_{department_name}",
                help="支持客户名称和财务编号搜索"
            )
        
        with col_filter2:
            if '风险等级' in dept_df.columns:
                risk_options = ['全部'] + list(dept_df['风险等级'].unique())
                risk_selected = st.multiselect(
                    "风险等级",
                    options=risk_options,
                    default=['全部'],
                    key=f"risk_{department_name}"
                )
                if '全部' in risk_selected:
                    risk_filter = dept_df['风险等级'].unique()
                else:
                    risk_filter = risk_selected
        
        with col_filter3:
            st.write("")  # 占位
            st.write("")  # 占位
            show_colors = st.toggle("🎨 颜色高亮", value=True, key=f"colors_{department_name}")

    # 应用筛选
    df_filtered = dept_df.copy()
    
    if search_term:
        mask = (
            df_filtered['客户名称'].str.contains(search_term, case=False, na=False) |
            df_filtered['财务编号'].astype(str).str.contains(search_term, case=False, na=False)
        )
        df_filtered = df_filtered[mask]
    
    if '风险等级' in dept_df.columns and 'risk_filter' in locals():
        df_filtered = df_filtered[df_filtered['风险等级'].isin(risk_filter)]
    
    # 选择显示列
    display_columns = [
        '财务编号', '客户名称', '总销售额', '2025欠款', '欠销比',
        '销售活跃度', '客户综合等级', '风险评分', '风险等级'
    ]
    
    # 确保列存在
    display_columns = [col for col in display_columns if col in df_filtered.columns]
    
    # 应用样式
    styled_df = apply_style(
        df_filtered[display_columns],
        highlight_integrated=show_colors,
        highlight_score=show_colors
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
        st.caption(f"📊 显示 {len(df_filtered)} / {len(dept_df)} 条记录")
    with col_info2:
        if not df_filtered.empty and '2025欠款' in df_filtered.columns:
            total_filtered_debt = df_filtered['2025欠款'].sum()
            st.caption(f"💰 筛选欠款总额: {format_currency(total_filtered_debt)}")
    with col_info3:
        if not df_filtered.empty and '总销售额' in df_filtered.columns:
            total_filtered_sales = df_filtered['总销售额'].sum()
            st.caption(f"💼 筛选销售额: {format_currency(total_filtered_sales)}")

# -----------------------------------------------------------------------------
# 5. 综合部门分析视图
# -----------------------------------------------------------------------------

def render_comprehensive_tab(integration_service):
    """
    综合部门分析视图 - 基于综合分析数据
    """
    # 获取综合分析数据
    with st.spinner("正在获取综合数据..."):
        integrated_df = get_integrated_data(integration_service)
        
        if integrated_df.empty:
            st.warning("📭 暂无综合数据，请先导入销售数据和欠款数据。")
            return

    st.header("📈 全公司综合看板")
    
    # --- 计算全公司指标 ---
    # 按部门统计记录数
    if '所属部门' in integrated_df.columns:
        dept_counts = integrated_df.groupby('所属部门').size()
        dept1_count = dept_counts.get('古建', 0)
        dept2_count = dept_counts.get('陶瓷', 0)
    else:
        dept1_count = dept2_count = 0
    
    # 计算总客户数（按财务编号去重）
    total_unique_customers = integrated_df['财务编号'].nunique() if '财务编号' in integrated_df.columns else 0
    
    total_debt_2025 = integrated_df['2025欠款'].sum() if '2025欠款' in integrated_df.columns else 0
    total_sales = integrated_df['总销售额'].sum() if '总销售额' in integrated_df.columns else 0
    
    # 统计风险客户
    high_risk_customers = 0
    if '风险等级' in integrated_df.columns:
        high_risk_customers = len(integrated_df[integrated_df['风险等级'].isin(['高风险', '较高风险'])])
    
    premium_customers = 0
    if '客户综合等级' in integrated_df.columns:
        premium_customers = len(integrated_df[integrated_df['客户综合等级'].str.startswith('A-')])

    # 顶部 KPI
    k1, k2, k3, k4 = st.columns(4)
    
    with k1:
        st.metric(
            "全公司客户数",
            f"{total_unique_customers}",
            f"古建:{dept1_count}条 陶瓷:{dept2_count}条",
            help="按财务编号去重的客户数及部门分布"
        )
    
    with k2:
        debt_sales_ratio = (total_debt_2025 / total_sales * 100) if total_sales > 0 else 0
        st.metric(
            "2025总欠款",
            format_currency(total_debt_2025),
            f"欠销比: {debt_sales_ratio:.1f}%",
            delta_color="inverse",
            help="全公司总欠款及欠销比例"
        )
    
    with k3:
        high_risk_percent = (high_risk_customers / len(integrated_df) * 100) if len(integrated_df) > 0 else 0
        st.metric(
            "风险客户",
            f"{high_risk_customers:,}",
            f"{high_risk_percent:.1f}%",
            delta_color="inverse",
            help="高风险和较高风险客户数量"
        )
    
    with k4:
        if not integrated_df.empty and '2025欠款' in integrated_df.columns:
            # 找出欠款最多的客户
            max_debt_idx = integrated_df['2025欠款'].idxmax()
            top_debtor = integrated_df.loc[max_debt_idx]
            top_debtor_name = top_debtor['客户名称'][:15] + "..." if len(top_debtor['客户名称']) > 15 else top_debtor['客户名称']
            st.metric(
                "最大欠款客户",
                top_debtor_name,
                format_currency(top_debtor['2025欠款']),
                help="欠款金额最大的客户"
            )

    st.divider()

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
            if '风险等级' in integrated_df.columns:
                risk_filter_all = st.multiselect(
                    "风险等级",
                    integrated_df['风险等级'].unique(),
                    placeholder="选择风险等级"
                )

    # 应用筛选
    df_view = integrated_df.copy()
    
    if all_search:
        mask = (
            df_view['客户名称'].str.contains(all_search, case=False, na=False) |
            df_view['财务编号'].astype(str).str.contains(all_search, case=False, na=False)
        )
        df_view = df_view[mask]
    
    if dept_filter:
        df_view = df_view[df_view['所属部门'].isin(dept_filter)]
    
    if '风险等级' in integrated_df.columns and risk_filter_all:
        df_view = df_view[df_view['风险等级'].isin(risk_filter_all)]

    # 显示列配置
    display_cols = ['所属部门', '财务编号', '客户名称', '总销售额', '2025欠款', '欠销比', '销售活跃度', '客户综合等级', '风险等级']
    display_cols = [col for col in display_cols if col in df_view.columns]
    
    # 应用样式
    styled_view = apply_style(df_view[display_cols], highlight_integrated=True)
    
    # 显示数据
    config = get_column_config()
    st.dataframe(
        styled_view,
        column_config=config,
        width='stretch',
        height=min(500, 100 + len(df_view) * 35),
        hide_index=True
    )
    
    # 底部统计信息
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.caption(f"📊 显示 {len(df_view)} / {len(df_view)} 条记录")
    with col_info2:
        if not df_view.empty and '2025欠款' in df_view.columns:
            total_filtered_debt = df_view['2025欠款'].sum()
            st.caption(f"💰 筛选欠款总额: {format_currency(total_filtered_debt)}")
    with col_info3:
        if not df_view.empty and '总销售额' in df_view.columns:
            total_filtered_sales = df_view['总销售额'].sum()
            st.caption(f"💼 筛选销售额: {format_currency(total_filtered_sales)}")

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

# -----------------------------------------------------------------------------
# 6. 销售欠款综合分析
# -----------------------------------------------------------------------------

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
            
            # 检查数据质量
            if not integrated_df.empty:
                # 检查是否有重复的财务编号+部门组合
                dup_check = integrated_df.duplicated(subset=['财务编号', '所属部门'], keep=False)
                if dup_check.any():
                    st.warning(f"⚠️ 发现 {dup_check.sum()} 条重复记录，已自动清理")
                    integrated_df = integrated_df.drop_duplicates(subset=['财务编号', '所属部门'], keep='first')
                
                # 检查同一个财务编号是否有不同部门的记录
                finance_id_counts = integrated_df.groupby('财务编号')['所属部门'].nunique()
                multi_dept_ids = finance_id_counts[finance_id_counts > 1].index.tolist()
                if multi_dept_ids:
                    st.info(f"📊 {len(multi_dept_ids)} 个客户在两个部门都有记录")
            
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
            help=""
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
    
    tab_chart1, tab_chart2 = st.tabs(["客户分布总略", "多维度分析"])
    
    with tab_chart1:
        coltab_1,coltab_2 = st.columns(2)
        with coltab_1:
            if '风险等级' in integrated_df.columns:
                risk_counts = integrated_df['风险等级'].value_counts().reset_index()
                risk_counts.columns = ['风险等级', '客户数']
                
                # 按风险等级排序
                risk_order = ['低风险', '较低风险', '中等风险', '较高风险', '高风险']
                risk_counts['风险等级'] = pd.Categorical(risk_counts['风险等级'], categories=risk_order, ordered=True)
                risk_counts = risk_counts.sort_values('风险等级')
                
                fig_risk = px.bar(
                    risk_counts,
                    x='风险等级',
                    y='客户数',
                    title="客户风险等级分布",
                    color='风险等级',
                    color_discrete_map=RISK_COLORS,
                    text='客户数'
                )
                fig_risk.update_layout(
                    xaxis_title="风险等级",
                    yaxis_title="客户数量",
                    height=400,
                    showlegend=False
                )
                fig_risk.update_traces(textposition='outside')
                st.plotly_chart(fig_risk, width='stretch')

        with coltab_2:
            if '客户综合等级' in integrated_df.columns:
                level_counts = integrated_df['客户综合等级'].value_counts().reset_index()
                level_counts.columns = ['客户综合等级', '客户数']
                
                fig_level = px.bar(
                    level_counts,
                    x='客户综合等级',
                    y='客户数',
                    title="客户综合等级分布",
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
        coltab_3,coltab_4 = st.columns(2)
        with coltab_3:
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
    
        with coltab_4:
                if '总销售额' in integrated_df.columns and '2025欠款' in integrated_df.columns:
                    # 复制数据用于散点图
                    scatter_df = integrated_df.copy()
                    
                    # 过滤掉异常数据：销售额<=0或欠款为负值
                    scatter_df = scatter_df[
                        (scatter_df['总销售额'] > 0) & 
                        (scatter_df['2025欠款'] >= 0)
                    ]
                    
                    if not scatter_df.empty:
                        # 计算欠销比
                        scatter_df['欠销比'] = scatter_df.apply(
                            lambda row: (row['2025欠款'] / row['总销售额'] * 100) 
                            if row['总销售额'] > 0 else 0,
                            axis=1
                        )
                        
                        # 创建散点图
                        fig_scatter = px.scatter(
                            scatter_df,
                            x='总销售额',
                            y='2025欠款',
                            size='欠销比',
                            color='客户综合等级',
                            hover_data=['客户名称', '财务编号', '欠销比'],
                            title="销售额 vs 欠款额",
                            log_x=True if scatter_df['总销售额'].min() > 0 else False,
                            log_y=True if scatter_df['2025欠款'].min() > 0 else False
                        )
                        
                        fig_scatter.update_layout(
                            xaxis_title="总销售额 (元)",
                            yaxis_title="2025欠款 (元)",
                            height=400
                        )
                        
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
        styled_df = apply_style(display_df, highlight_integrated=show_colors, highlight_score=show_colors)
        
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

# -----------------------------------------------------------------------------
# 7. 客户详情视图 - 已更新使用统一欠款表
# -----------------------------------------------------------------------------

def render_customer_detail_view(integration_service):
    """客户详情分析视图"""
    st.header("👤 客户详情分析")
    st.caption("查看单个客户的详细销售和欠款记录")
    
    # 搜索区域
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
                
                # 显示匹配信息
                # if customer_detail.get('matched_customer_names'):
                #     matched_names = customer_detail['matched_customer_names']
                #     if len(matched_names) > 1:
                #         st.info(f"🔍 匹配到 {len(matched_names)} 个相关客户")
                #         for i, name in enumerate(matched_names, 1):
                #             st.write(f"{i}. {name}")
                #     else:
                #         st.info(f"🔍 匹配客户：{matched_names[0]}")
                
                # 获取客户名称用于显示（如果有多个，显示第一个）
                display_name = customer_detail.get('matched_customer_names', [search_term])[0] if customer_detail.get('matched_customer_names') else search_term
                
                st.markdown(f"### 📋 客户概览 - {display_name}")
                
                # 显示关键指标
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
                
                # 显示财务编号信息
                if customer_detail.get('finance_ids'):
                    st.info(f"📊 相关财务编号: {', '.join(map(str, customer_detail['finance_ids']))}")
                
                st.divider()
                
                # 销售记录部分
                if not customer_detail['sales_records'].empty:
                    st.subheader("📈 销售记录明细")
                    
                    sales_df = customer_detail['sales_records']
                    
                    # 统计信息
                    col_stats1, col_stats2, col_stats3 = st.columns(3)
                    
                    with col_stats1:
                        total_records = len(sales_df)
                        st.metric("总交易笔数", total_records)
                    
                    with col_stats2:
                        if not sales_df.empty:
                            # 按财务编号统计
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
                    
                    # 显示数据表格
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
                            "record_date": st.column_config.DateColumn("记录日期", format="YYYY-MM-DD")
                        },
                        hide_index=True,
                        height=400
                    )
                    
                    st.caption(f"📊 共 {len(sales_df)} 条销售记录")
                else:
                    st.info("📭 暂无销售记录")
                
                # 欠款记录部分
                if not customer_detail['debt_records'].empty:
                    st.subheader("💰 欠款记录明细")
                    
                    debt_data = customer_detail['debt_records']
                    
                    # 统计信息
                    col_debt1, col_debt2 = st.columns(2)
                    
                    with col_debt1:
                        total_debt_2025 = debt_data['debt_2025'].sum()
                        st.metric("2025总欠款", f"¥{total_debt_2025:,.2f}")
                    
                    with col_debt2:
                        unique_departments = debt_data['department'].nunique()
                        st.metric("涉及部门", unique_departments)
                    
                    # 按部门显示欠款
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
                
                # 导出功能
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
# 8. 分类说明页面
# -----------------------------------------------------------------------------

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
            ### 🏆 综合信用分类
            
            **A级客户 (优质)**
            - A-优质大客户：无欠款 + 高销售额 + 活跃
            - A-优质活跃客户：无欠款 + 中等销售额 + 活跃
            
            **B级客户 (良好)**
            - B-大额休眠客户：无欠款 + 高销售额 + 休眠
            - B-一般客户：无欠款 + 低销售额
            - B1-低风险活跃欠款：欠销比<20% + 活跃
            - B2-低风险欠款：欠销比<20% + 不活跃
            
            **C级客户 (关注)**
            - C-小额客户：无欠款 + 无销售或极少销售
            - C1-中风险持续欠款：欠销比20%-50% + 持续欠款
            - C2-中风险欠款：欠销比20%-50%
            
            **D级客户 (风险)**
            - D-无销售无欠款：无任何业务往来
            - D1-高风险持续欠款：欠销比>50% + 持续欠款
            - D2-高风险欠款：欠销比>50%
            
            **E级客户 (高危)**
            - E-纯欠款客户：有欠款但无销售
            """)
        
        with col_logic2:
            st.markdown("""
            ### 📊 风险等级说明
            
            **低风险**
            - 风险评分80-100分
            - A级优质客户
            
            **较低风险**
            - 风险评分60-79分
            - B级良好客户
            
            **中等风险**
            - 风险评分40-59分
            - C级关注客户
            
            **较高风险**
            - 风险评分20-39分
            - D级风险客户
            
            **高风险**
            - 风险评分0-19分
            - E级高危客户
            
            ### 📈 风险评分规则
            
            **评分范围：0-100分**
            - **80-100分**：低风险，信用优秀
            - **60-79分**：较低风险，信用良好
            - **40-59分**：中等风险，需要关注
            - **20-39分**：较高风险，需要控制
            - **0-19分**：高风险，急需处理
            
            **评分因素权重：**
            1. 欠款金额（权重40%）
            2. 欠销比例（权重25%）
            3. 销售活跃度（权重20%）
            4. 持续欠款情况（权重15%）
            """)
    
    with tab_advice:
        st.subheader("💡 客户管理建议")
        
        advice_data = [
            {
                "风险等级": "低风险",
                "特征": "无欠款、高价值、活跃",
                "管理策略": "VIP重点维护",
                "具体措施": "优先供货、价格优惠、定期拜访、新品推荐",
                "催款频率": "无需催款",
                "信用政策": "可提高信用额度"
            },
            {
                "风险等级": "较低风险",
                "特征": "低欠款、有销售、一般活跃",
                "管理策略": "正常维护",
                "具体措施": "标准账期、定期对账、保持沟通",
                "催款频率": "季度提醒",
                "信用政策": "维持现有政策"
            },
            {
                "风险等级": "中等风险",
                "特征": "中等欠款、欠销比适中",
                "管理策略": "重点关注",
                "具体措施": "缩短账期、关注欠款变化、了解经营状况",
                "催款频率": "月度跟进",
                "信用政策": "适度收紧"
            },
            {
                "风险等级": "较高风险",
                "特征": "高欠款、欠销比高",
                "管理策略": "风险控制",
                "具体措施": "停止赊销、预付款要求、专人跟进催收",
                "催款频率": "每周跟进",
                "信用政策": "现款现货"
            },
            {
                "风险等级": "高风险",
                "特征": "纯欠款、无销售或长期欠款",
                "管理策略": "法律介入",
                "具体措施": "发律师函、准备诉讼、资产保全",
                "催款频率": "立即处理",
                "信用政策": "停止合作"
            }
        ]
        
        st.table(pd.DataFrame(advice_data))
    
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
                    f'<span style="font-size: 0.9em; color: {fg};">风险等级</span>'
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
# 9. 主程序入口
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
            render_department_analysis(integration_service, "古建", "🏛️")
        except Exception as e:
            st.error(f"❌ 古建数据分析失败: {str(e)}")
    
    with tab3:
        try:
            render_department_analysis(integration_service, "陶瓷", "🏺")
        except Exception as e:
            st.error(f"❌ 陶瓷数据分析失败: {str(e)}")
    
    with tab4:
        try:
            render_comprehensive_tab(integration_service)
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
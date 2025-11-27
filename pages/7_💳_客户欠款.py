import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.debt_service import DebtAnalysisService
from utils.auth import require_login
from utils.data_processor import process_debt_excel_data, validate_debt_data, get_sample_data

# 设置页面
st.set_page_config(
    page_title="客户欠款分析",
    page_icon="💳",
    layout="wide"
)

def main():
    require_login()
    
    st.title("💳 客户欠款分析")
    st.markdown("---")
    
    debt_service = DebtAnalysisService()
    
    # 创建标签页
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📥 数据导入", 
        "📊 古建分析", 
        "📈 陶瓷分析", 
        "🔍 综合分析",
        "📋 分类说明"
    ])
    
    with tab1:
        render_data_import_tab(debt_service)
    
    with tab2:
        render_department_analysis_tab(debt_service, 1)
    
    with tab3:
        render_department_analysis_tab(debt_service, 2)
    
    with tab4:
        render_comprehensive_analysis_tab(debt_service)
        
    with tab5:
        render_classification_explanation_tab(debt_service)

def render_data_import_tab(debt_service):
    """数据导入标签页"""
    st.header("📥 数据导入")
    
    # 数据导入说明
    with st.expander("📋 数据格式说明", expanded=True):
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
        
        # 显示示例数据
        sample_df = get_sample_data()
        st.dataframe(sample_df, use_container_width=True)
        
        st.markdown("""
        **注意事项：**
        - 只处理以"2203"开头的客户代码行
        - 金额列应为数值格式
        - 空值会自动转换为0
        - 系统会自动去重，重复客户代码会更新最新数据
        """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 古建欠款数据")
        dept1_file = st.file_uploader(
            "上传古建欠款Excel文件", 
            type=['xlsx', 'xls'],
            key="dept1"
        )
        
        if dept1_file:
            try:
                df_dept1 = pd.read_excel(dept1_file)
                st.success("✅ 文件读取成功")
                
                with st.expander("📊 原始数据预览", expanded=False):
                    st.write("前5行数据:", df_dept1.head())
                    st.write("原始数据列名:", list(df_dept1.columns))
                
                # 处理数据
                with st.spinner("正在处理数据..."):
                    df_clean = process_debt_excel_data(df_dept1, "古建")
                
                if not df_clean.empty:
                    with st.expander("✅ 处理后的数据预览", expanded=True):
                        st.write(f"共找到 {len(df_clean)} 条有效记录")
                        st.write("处理后数据列名:", list(df_clean.columns))
                        st.dataframe(df_clean.head(), use_container_width=True)
                    
                    # 验证数据
                    issues = validate_debt_data(df_clean)
                    if issues:
                        st.warning("⚠️ 数据验证发现以下问题:")
                        for issue in issues:
                            st.write(f"- {issue}")
                    
                    if st.button("🚀 导入古建数据", key="import_dept1", use_container_width=True):
                        with st.spinner("正在导入数据..."):
                            success, error = debt_service.import_department1_debt(df_clean)
                        
                        if error == 0:
                            st.success(f"✅ 古建数据导入完成！成功导入 {success} 条记录")
                        else:
                            st.warning(f"⚠️ 古建数据导入完成！成功: {success}, 失败: {error}")
                else:
                    st.error("❌ 未找到有效的欠款数据，请检查文件格式")
                        
            except Exception as e:
                st.error(f"❌ 文件处理错误: {str(e)}")
                st.info("💡 如果问题持续存在，请检查Excel文件格式是否符合要求")
    
    with col2:
        st.subheader("📁 陶瓷欠款数据")
        dept2_file = st.file_uploader(
            "上传陶瓷欠款Excel文件", 
            type=['xlsx', 'xls'],
            key="dept2"
        )
        
        if dept2_file:
            try:
                df_dept2 = pd.read_excel(dept2_file)
                st.success("✅ 文件读取成功")
                
                with st.expander("📊 原始数据预览", expanded=False):
                    st.write("前5行数据:", df_dept2.head())
                    st.write("原始数据列名:", list(df_dept2.columns))
                
                # 处理数据
                with st.spinner("正在处理数据..."):
                    df_clean = process_debt_excel_data(df_dept2, "陶瓷")
                
                if not df_clean.empty:
                    with st.expander("✅ 处理后的数据预览", expanded=True):
                        st.write(f"共找到 {len(df_clean)} 条有效记录")
                        st.write("处理后数据列名:", list(df_clean.columns))
                        st.dataframe(df_clean.head(), use_container_width=True)
                    
                    # 验证数据
                    issues = validate_debt_data(df_clean)
                    if issues:
                        st.warning("⚠️ 数据验证发现以下问题:")
                        for issue in issues:
                            st.write(f"- {issue}")
                    
                    if st.button("🚀 导入陶瓷数据", key="import_dept2", use_container_width=True):
                        with st.spinner("正在导入数据..."):
                            success, error = debt_service.import_department2_debt(df_clean)
                        
                        if error == 0:
                            st.success(f"✅ 陶瓷数据导入完成！成功导入 {success} 条记录")
                        else:
                            st.warning(f"⚠️ 陶瓷数据导入完成！成功: {success}, 失败: {error}")
                else:
                    st.error("❌ 未找到有效的欠款数据，请检查文件格式")
                        
            except Exception as e:
                st.error(f"❌ 文件处理错误: {str(e)}")
                st.info("💡 如果问题持续存在，请检查Excel文件格式是否符合要求")

def render_department_analysis_tab(debt_service, department_num):
    """部门分析标签页"""
    # 修改这里：根据部门编号显示不同的名称
    department_name = "古建" if department_num == 1 else "陶瓷"
    st.header(f"📊 {department_name}欠款分析")
    
    try:
        if department_num == 1:
            df_dept = debt_service.get_department1_debt()
        else:
            df_dept = debt_service.get_department2_debt()
        
        if not df_dept.empty:
            analyzed_data = debt_service.analyze_debt_data(df_dept)
            display_analysis(analyzed_data, department_name)  # 这里也要修改
        else:
            st.info(f"📝 请先导入{department_name}欠款数据")  # 这里也要修改
            st.markdown(f"""
            **导入步骤：**
            1. 点击"数据导入"标签页
            2. 上传{department_name}的Excel文件  # 这里也要修改
            3. 查看数据预览并确认无误
            4. 点击导入按钮完成数据导入
            """)
    except Exception as e:
        st.error(f"❌ 分析{department_name}数据时出错: {str(e)}")  # 这里也要修改
        st.info("💡 请检查数据格式是否正确，或重新导入数据")

def render_comprehensive_analysis_tab(debt_service):
    """综合分析标签页"""
    st.header("🔍 综合欠款分析")
    
    try:
        df_dept1 = debt_service.get_department1_debt()
        df_dept2 = debt_service.get_department2_debt()
        
        if not df_dept1.empty and not df_dept2.empty:
            analyzed_dept1 = debt_service.analyze_debt_data(df_dept1)
            analyzed_dept2 = debt_service.analyze_debt_data(df_dept2)
            
            # 关键指标对比
            st.subheader("📈 关键指标对比")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_clients = len(analyzed_dept1) + len(analyzed_dept2)
                st.metric("总客户数", f"{total_clients} ")
            
            with col2:
                total_debt = analyzed_dept1['2025欠款'].sum() + analyzed_dept2['2025欠款'].sum()
                st.metric("总欠款金额", f"¥{total_debt:,.0f}")
            
            with col3:
                high_risk1 = len(analyzed_dept1[analyzed_dept1['坏账风险'] == '高风险坏账'])
                high_risk2 = len(analyzed_dept2[analyzed_dept2['坏账风险'] == '高风险坏账'])
                st.metric("高风险客户", f"{high_risk1 + high_risk2} ",help="欠款大于5万且多年无变化的客户")
            
            with col4:
                premium1 = len(analyzed_dept1[analyzed_dept1['客户类型'] == '优质客户(无欠款)'])
                premium2 = len(analyzed_dept2[analyzed_dept2['客户类型'] == '优质客户(无欠款)'])
                st.metric("优质客户", f"{premium1 + premium2} ",help="无欠款优质客户")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📋 部门汇总统计")
                # 修改这里：将部门1改为古建，部门2改为陶瓷
                summary_data = {
                    '部门': ['古建', '陶瓷'],  # 修改这里
                    '客户数量': [len(analyzed_dept1), len(analyzed_dept2)],
                    '2025欠款总额': [
                        analyzed_dept1['2025欠款'].sum(), 
                        analyzed_dept2['2025欠款'].sum()
                    ],
                    '高风险客户': [
                        len(analyzed_dept1[analyzed_dept1['坏账风险'] == '高风险坏账']),
                        len(analyzed_dept2[analyzed_dept2['坏账风险'] == '高风险坏账'])
                    ],
                    '优质客户': [
                        len(analyzed_dept1[analyzed_dept1['客户类型'] == '优质客户(无欠款)']),
                        len(analyzed_dept2[analyzed_dept2['客户类型'] == '优质客户(无欠款)'])
                    ]
                }
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True)
            
            with col2:
                st.subheader("📊 风险对比")
                fig = go.Figure()
                # 修改这里：将部门1改为古建，部门2改为陶瓷
                fig.add_trace(go.Bar(
                    name='古建',  # 修改这里
                    x=analyzed_dept1['坏账风险'].value_counts().index,
                    y=analyzed_dept1['坏账风险'].value_counts().values
                ))
                fig.add_trace(go.Bar(
                    name='陶瓷',  # 修改这里
                    x=analyzed_dept2['坏账风险'].value_counts().index,
                    y=analyzed_dept2['坏账风险'].value_counts().values
                ))
                fig.update_layout(
                    title="两部门风险分布对比",
                    xaxis_title="风险等级",
                    yaxis_title="客户数量",
                    showlegend=True
                )
                st.plotly_chart(fig, use_container_width=True)
                
            # 合并数据进行详细分析
            analyzed_combined = pd.concat([analyzed_dept1, analyzed_dept2], ignore_index=True)
            st.subheader("📋 合并详细数据")
            
            # 搜索功能
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                search_name = st.text_input("🔍 搜索客户名称", placeholder="输入客户名称关键词")
            with col2:
                filter_risk = st.selectbox("筛选风险等级", 
                                         ['全部'] + analyzed_combined['坏账风险'].unique().tolist())
            with col3:
                filter_tier = st.selectbox("筛选客户等级",
                                         ['全部'] + analyzed_combined['客户价值等级'].unique().tolist())
            
            # 应用筛选
            filtered_data = analyzed_combined
            if search_name:
                filtered_data = filtered_data[filtered_data['客户名称'].str.contains(search_name, case=False, na=False)]
            if filter_risk != '全部':
                filtered_data = filtered_data[filtered_data['坏账风险'] == filter_risk]
            if filter_tier != '全部':
                filtered_data = filtered_data[filtered_data['客户价值等级'] == filter_tier]
            
            # 定义要显示的列（排除不需要的字段）
            display_columns = [
                '客户代码', '客户名称', '2023欠款', '2024欠款', '2025欠款',
                '客户类型', '坏账风险', '客户价值等级', '23-24变化', '24-25变化', '23-25总变化'
            ]
            
            # 确保列存在
            available_columns = [col for col in display_columns if col in filtered_data.columns]
                
            st.write(f"找到 {len(filtered_data)} 条记录")
            st.dataframe(filtered_data[available_columns], use_container_width=True)
            
        else:
            st.info("📝 请先导入两个部门的欠款数据")
            missing_depts = []
            if df_dept1.empty:
                missing_depts.append("古建")  # 修改这里
            if df_dept2.empty:
                missing_depts.append("陶瓷")  # 修改这里
            st.warning(f"缺少数据: {', '.join(missing_depts)}")
    
    except Exception as e:
        st.error(f"❌ 综合分析时出错: {str(e)}")
        st.info("💡 请确保两个部门的数据都已正确导入")

def render_classification_explanation_tab(debt_service):
    """分类说明标签页"""
    st.header("📋 分类标准说明")
    
    try:
        explanations = debt_service.get_classification_explanation()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("👥 客户类型说明")
            for category, description in explanations['客户类型'].items():
                with st.container():
                    st.markdown(f"**{category}**")
                    st.caption(description)
                    st.markdown("---")
        
        with col2:
            st.subheader("⚠️ 坏账风险说明") 
            for category, description in explanations['坏账风险'].items():
                with st.container():
                    st.markdown(f"**{category}**")
                    st.caption(description)
                    st.markdown("---")
        
        with col3:
            st.subheader("📊 客户价值等级说明")
            for category, description in explanations['客户价值等级'].items():
                with st.container():
                    st.markdown(f"**{category}**")
                    st.caption(description)
                    st.markdown("---")
        
        # 管理建议
        st.subheader("💡 管理建议")
        st.markdown("""
        | 客户等级 | 管理策略 | 具体措施 |
        |---------|---------|---------|
        | **A级-优质客户** | 重点维护 | 给予信用优惠，优先合作 |
        | **B级-良好客户** | 正常维护 | 鼓励继续合作，保持良好关系 |
        | **C级-小额欠款** | 定期提醒 | 防止欠款扩大，及时沟通 |
        | **C级-中等欠款** | 重点关注 | 加强催收频率，控制信用额度 |
        | **D级-风险客户** | 严格管控 | 加强催收，限制信用额度 |
        | **D级-大额欠款** | 重点催收 | 制定还款计划，密切跟踪 |
        | **E级-高风险客户** | 立即行动 | 立即采取催收措施，考虑法律手段 |
        """)
    
    except Exception as e:
        st.error(f"❌ 加载分类说明时出错: {str(e)}")

def display_analysis(analyzed_data, department_name):
    """显示分析结果"""
    st.subheader(f"{department_name} - 分析概览")
    
    # 关键指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总客户数", f"{len(analyzed_data)} ")
    with col2:
        st.metric("总欠款金额", f"¥{analyzed_data['2025欠款'].sum():,.0f}")
    with col3:
        high_risk = len(analyzed_data[analyzed_data['坏账风险'] == '高风险坏账'])
        st.metric("高风险客户", f"{high_risk} ",help="欠款大于5万且多年无变化的客户")
    with col4:
        premium = len(analyzed_data[analyzed_data['客户类型'] == '优质客户(无欠款)'])
        st.metric("优质客户", f"{premium} ",help="无欠款优质客户")
    
    # 图表
    col1, col2 = st.columns(2)
    
    with col1:
        # 客户类型分布
        type_counts = analyzed_data['客户类型'].value_counts()
        fig1 = px.pie(
            values=type_counts.values, 
            names=type_counts.index,
            title="客户类型分布",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig1.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # 风险分布
        risk_counts = analyzed_data['坏账风险'].value_counts()
        fig2 = px.bar(
            x=risk_counts.index, 
            y=risk_counts.values,
            title="坏账风险分布",
            labels={'x': '风险等级', 'y': '客户数量'},
            color=risk_counts.values,
            color_continuous_scale='RdYlGn_r'
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # 详细数据
    st.subheader("📋 详细分析数据")
    
    # 搜索和筛选功能
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        search_name = st.text_input(f"🔍 搜索{department_name}客户名称", 
                                  placeholder="输入客户名称关键词", 
                                  key=f"search_{department_name}")
    with col2:
        filter_risk = st.selectbox(f"筛选{department_name}风险等级", 
                                 ['全部'] + analyzed_data['坏账风险'].unique().tolist(),
                                 key=f"risk_{department_name}")
    with col3:
        filter_tier = st.selectbox(f"筛选{department_name}客户等级",
                                 ['全部'] + analyzed_data['客户价值等级'].unique().tolist(),
                                 key=f"tier_{department_name}")
    
    # 应用筛选
    filtered_data = analyzed_data
    if search_name:
        filtered_data = filtered_data[filtered_data['客户名称'].str.contains(search_name, case=False, na=False)]
    if filter_risk != '全部':
        filtered_data = filtered_data[filtered_data['坏账风险'] == filter_risk]
    if filter_tier != '全部':
        filtered_data = filtered_data[filtered_data['客户价值等级'] == filter_tier]
    
    # 定义要显示的列（排除不需要的字段）
    display_columns = [
        '客户代码', '客户名称', '2023欠款', '2024欠款', '2025欠款',
        '客户类型', '坏账风险', '客户价值等级', '23-24变化', '24-25变化', '23-25总变化'
    ]
    
    # 确保列存在
    available_columns = [col for col in display_columns if col in filtered_data.columns]
    
    st.write(f"找到 {len(filtered_data)} 条记录")
    st.dataframe(filtered_data[available_columns], use_container_width=True)
    
    # 高风险客户清单
    high_risk_clients = analyzed_data[analyzed_data['坏账风险'] == '高风险坏账']
    if not high_risk_clients.empty:
        st.subheader("🚨 高风险客户清单")
        st.dataframe(
            high_risk_clients[available_columns].sort_values('2025欠款', ascending=False),
            use_container_width=True
        )
    
    # 欠款增加客户清单
    increasing_debt = analyzed_data[analyzed_data['详细分类'] == '持续欠款-显著增加']
    if not increasing_debt.empty:
        st.subheader("📈 欠款显著增加客户")
        st.dataframe(
            increasing_debt[['客户代码', '客户名称', '2023欠款', '2024欠款', '2025欠款', '23-25总变化']]
            .sort_values('23-25总变化', ascending=False),
            use_container_width=True
        )

if __name__ == "__main__":
    main()
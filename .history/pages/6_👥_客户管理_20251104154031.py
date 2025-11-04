import streamlit as st
import pandas as pd
from core.database import get_connection

st.set_page_config(page_title="客户管理", layout="wide")
st.title("👥 客户管理")

# 获取客户数据的函数
def load_customer_data():
    with get_connection() as conn:
        df = pd.read_sql_query('''
            SELECT 
                id,
                customer_name as 客户名称,
                finance_id as 财务编号,
                sub_customer_name as 子客户名称,
                region as 区域,
                contact_person as 联系人,
                phone as 电话,
                created_date as 创建时间,
                updated_date as 更新时间,
                is_active as 是否活跃
            FROM customers 
            ORDER BY customer_name, sub_customer_name
        ''', conn)
        
        # 处理空值
        df['子客户名称'] = df['子客户名称'].fillna('')
        df['区域'] = df['区域'].fillna('')
        df['联系人'] = df['联系人'].fillna('')
        df['电话'] = df['电话'].fillna('')
        
        return df

# 加载数据
customers_df = load_customer_data()

if customers_df.empty:
    st.warning("暂无客户数据，请先导入Excel文件")
else:
    # 客户统计
    st.subheader("📊 客户统计")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_customers = len(customers_df)
        st.metric("总客户记录", total_customers)
    
    with col2:
        # 安全处理布尔值
        active_mask = customers_df['是否活跃'].apply(
            lambda x: str(x).lower() == 'true' if isinstance(x, str) else bool(x)
        )
        active_count = active_mask.sum()
        st.metric("活跃客户", active_count)
    
    with col3:
        main_customers = len(customers_df[customers_df['子客户名称'] == ''])
        st.metric("主客户数", main_customers)
    
    with col4:
        sub_customers = len(customers_df[customers_df['子客户名称'] != ''])
        st.metric("子客户数", sub_customers)

    # 客户查询
    st.subheader("🔍 客户查询")
    
    search_term = st.text_input("搜索关键词", placeholder="输入客户名称、子客户名称或财务编号")
    
    # 实时筛选（不使用按钮）
    if search_term and search_term.strip():
        # 创建搜索掩码
        search_mask = (
            customers_df['客户名称'].str.contains(search_term, case=False, na=False) | 
            customers_df['财务编号'].str.contains(search_term, case=False, na=False) | 
            customers_df['子客户名称'].str.contains(search_term, case=False, na=False)
        )
        filtered_df = customers_df[search_mask]
    else:
        filtered_df = customers_df

    # 显示查询结果
    st.subheader(f"📋 客户列表 (共 {len(filtered_df)} 条记录)")
    
    if not filtered_df.empty:
        # 创建显示副本
        display_df = filtered_df.copy()
        
        # 格式化显示
        display_df['子客户名称'] = display_df['子客户名称'].apply(
            lambda x: '主客户' if x == '' else x
        )
        
        display_df['是否活跃'] = display_df['是否活跃'].apply(
            lambda x: '是' if (str(x).lower() == 'true' if isinstance(x, str) else bool(x)) else '否'
        )
        
        st.dataframe(display_df, width="stretch")
        
        # 客户编辑功能
        st.subheader("✏️ 客户信息编辑")
        
        # 创建简单的客户选择列表
        customer_list = []
        for index, row in filtered_df.iterrows():
            # 将行数据转换为字典，避免 Series 比较问题
            row_dict = {
                'index': index,
                'id': row['id'],
                'display': f"{row['客户名称']} - {row['财务编号']}",
                'customer_name': row['客户名称'],
                'finance_id': row['财务编号'],
                'sub_customer_name': row['子客户名称'],
                'region': row['区域'],
                'contact_person': row['联系人'],
                'phone': row['电话'],
                'is_active': row['是否活跃']
            }
            if row['子客户名称'] and row['子客户名称'] != '':
                row_dict['display'] += f" (子客户: {row['子客户名称']})"
            customer_list.append(row_dict)
        
        # 客户选择器
        if customer_list:
            # 创建选项列表
            options = [customer['display'] for customer in customer_list]
            selected_display = st.selectbox("选择要编辑的客户", options)
            
            # 找到选中的客户
            selected_customer = None
            for customer in customer_list:
                if customer['display'] == selected_display:
                    selected_customer = customer
                    break
            
            if selected_customer:
                # 编辑表单
                with st.form("customer_edit_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # 显示基本信息（只读）
                        st.text_input("客户名称", value=selected_customer['customer_name'], disabled=True)
                        st.text_input("财务编号", value=selected_customer['finance_id'], disabled=True)
                        
                        sub_display = '主客户' if selected_customer['sub_customer_name'] == '' else selected_customer['sub_customer_name']
                        st.text_input("子客户名称", value=sub_display, disabled=True)
                        
                        # 可编辑字段
                        new_region = st.text_input("区域", value=selected_customer['region'])
                        new_contact = st.text_input("联系人", value=selected_customer['contact_person'])
                        new_phone = st.text_input("电话", value=selected_customer['phone'])
                    
                    with col2:
                        # 状态选择
                        current_status = selected_customer['is_active']
                        if isinstance(current_status, str):
                            is_active = current_status.lower() == 'true'
                        else:
                            is_active = bool(current_status)
                        
                        new_status = st.selectbox(
                            "状态", 
                            options=[True, False], 
                            format_func=lambda x: "活跃" if x else "停用",
                            index=0 if is_active else 1
                        )
                        
                        st.markdown("---")
                        st.write("**当前信息:**")
                        st.write(f"- 区域: {selected_customer['region'] if selected_customer['region'] else '未设置'}")
                        st.write(f"- 联系人: {selected_customer['contact_person'] if selected_customer['contact_person'] else '未设置'}")
                        st.write(f"- 电话: {selected_customer['phone'] if selected_customer['phone'] else '未设置'}")
                        st.write(f"- 状态: {'活跃' if is_active else '停用'}")
                    
                    # 提交按钮
                    if st.form_submit_button("💾 更新客户信息", width="stretch"):
                        try:
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE customers 
                                    SET region = ?, contact_person = ?, phone = ?, is_active = ?, updated_date = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                ''', (
                                    new_region, 
                                    new_contact, 
                                    new_phone, 
                                    new_status,
                                    selected_customer['id']
                                ))
                                
                                st.success("✅ 客户信息更新成功！")
                                st.rerun()
                        except Exception as e:
                            st.error(f"更新失败: {str(e)}")
        
        # 数据导出
        st.subheader("💾 数据导出")
        csv_data = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 导出客户列表(CSV)",
            csv_data,
            "customers.csv",
            "text/csv",
            use_container_width=True
        )
    else:
        st.info("没有找到符合条件的客户")

# 使用说明
with st.expander("📚 使用说明", expanded=False):
    st.markdown("""
    ### 客户管理功能说明
    
    **客户类型说明**
    - **主客户**: 子客户名称为空的客户记录
    - **子客户**: 子客户名称不为空的客户记录
    - **活跃客户**: 状态为活跃的客户
    
    **筛选功能**
    - 支持按客户类型筛选（全部/仅主客户/仅子客户）
    - 支持按活跃状态筛选
    - 支持关键词搜索（客户名称、财务编号、子客户名称）
    
    **编辑功能**
    - 可选择客户进行信息编辑
    - 可更新区域、联系人、电话和状态信息
    - 客户名称、财务编号、子客户名称不可编辑
    
    **数据导出**
    - 支持导出筛选后的客户列表
    - 导出格式为CSV，兼容Excel
    """)
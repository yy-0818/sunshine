import streamlit as st
import pandas as pd
from core.database import get_connection, get_database_status

st.logo(
    image='./assets/logo.png',
    icon_image='./assets/logo.png',
)

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
                is_active as 是否活跃,
                updated_date as 更新时间
            FROM customers 
            ORDER BY customer_name, sub_customer_name
        ''', conn)
        
        # 处理空值
        df['区域'] = df['区域'].fillna('')
        df['联系人'] = df['联系人'].fillna('')
        df['电话'] = df['电话'].fillna('')
        
        return df

# 更新客户信息的函数
def update_customer_info(customer_id, updates):
    """更新客户信息"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values())
            values.append(customer_id)
            
            cursor.execute(f'''
                UPDATE customers 
                SET {set_clause}, updated_date = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', values)
            
            conn.commit()
            return True
    except Exception as e:
        st.error(f"更新失败: {str(e)}")
        return False

# 新增客户信息的函数
def add_new_customer(customer_data):
    """新增客户信息"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO customers 
                (customer_name, finance_id, sub_customer_name, region, contact_person, phone, is_active, created_date, updated_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (
                customer_data['customer_name'],
                customer_data['finance_id'],
                customer_data['sub_customer_name'],
                customer_data['region'],
                customer_data['contact_person'],
                customer_data['phone'],
                customer_data['is_active']
            ))
            
            conn.commit()
            return True
    except Exception as e:
        st.error(f"新增客户失败: {str(e)}")
        return False

# 加载数据
customers_df = load_customer_data()
status = get_database_status(days_threshold=180)

# 新增客户对话框
@st.dialog("新增客户信息",width="medium")
def add_customer_dialog():
    st.write("请填写新客户的信息")
    
    with st.form("add_customer_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**基本信息**")
            new_customer_name = st.text_input(
                "客户名称*", 
                placeholder="请输入客户完整名称",
                help="客户在系统中的完整名称"
            )
            
            new_finance_id = st.text_input(
                "财务编号*", 
                placeholder="财务系统唯一标识",
                help="财务系统中的唯一编号"
            )
            
            new_sub_customer = st.text_input(
                "子客户名称", 
                placeholder="留空表示主客户",
                help="如有关联子客户请填写"
            )
        
        with col2:
            st.markdown("**联系信息**")
            new_region = st.text_input(
                "区域", 
                placeholder="如：华东区、华北区等"
            )
            
            new_contact = st.text_input(
                "联系人", 
                placeholder="联系人姓名"
            )
            
            new_phone = st.text_input(
                "电话", 
                placeholder="联系电话"
            )
            
        st.markdown("**状态设置**")
        # 使用toggle表示活跃状态，默认启用
        is_active = st.toggle(
            "启用客户",
            value=True,
            help="启用表示客户活跃，禁用表示客户停用"
        )
        
        # 按钮布局
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        
        
        with col_btn2:
            submitted = st.form_submit_button(
                "💾 保存新客户",
                width='stretch'
            )
        
        if submitted:
            # 验证必填字段
            if not new_customer_name.strip():
                st.error("❌ 客户名称为必填字段")
            elif not new_finance_id.strip():
                st.error("❌ 财务编号为必填字段")
            else:
                customer_data = {
                    'customer_name': new_customer_name.strip(),
                    'finance_id': new_finance_id.strip(),
                    'sub_customer_name': new_sub_customer.strip(),
                    'region': new_region.strip(),
                    'contact_person': new_contact.strip(),
                    'phone': new_phone.strip(),
                    'is_active': is_active
                }
                
                if add_new_customer(customer_data):
                    st.success("✅ 新客户添加成功！")
                    st.session_state.show_add_dialog = False
                    st.rerun()

if customers_df.empty:
    st.warning("暂无客户数据，请先导入Excel文件")
else:
    # 客户统计和新增按钮
    col_header1, col_header2 = st.columns([3, 1])
    
    with col_header1:
        st.subheader("📊 客户统计")
    
    with col_header2:
        if st.button("➕ 新增客户",width='stretch'):
            add_customer_dialog()
    # 客户统计卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        col1.metric("总客户数", status["sub_customers"],help="所有有过交易的主客户及子客户")
    
    with col2:
        col2.metric("主客户数", status["main_customers"])

    with col3:
        col3.metric("活跃客户", status["active_sub_customers_recent"],status["active_sub_customers_recent"]-status["active_sub_customers_this_year"],help="在过去半年内有过订单的客户")
    
    with col4:
        col4.metric("月活跃客户", status["active_sub_customers_this_month"],status["active_sub_customers_this_month"]-status["active_sub_customers_last_month"],help="在过去一个月内有过订单的客户")

    # 客户查询
    st.subheader("🔍 客户查询")
    
    col_search1, col_search2, col_search3 = st.columns([2, 1, 1])
    
    with col_search1:
        search_term = st.text_input("搜索关键词", placeholder="输入客户名称、子客户名称或财务编号")
    
    with col_search2:
        status_filter = st.selectbox(
            "状态筛选",
            ["全部", "活跃", "停用"]
        )
    
    with col_search3:
        customer_type = st.selectbox(
            "客户类型",
            ["全部", "仅主客户", "仅子客户"]
        )
    
    # 应用筛选条件
    filtered_df = customers_df.copy()
    
    # 关键词搜索
    if search_term and search_term.strip():
        search_mask = (
            filtered_df['客户名称'].str.contains(search_term, case=False, na=False) | 
            filtered_df['财务编号'].str.contains(search_term, case=False, na=False) | 
            filtered_df['子客户名称'].str.contains(search_term, case=False, na=False)
        )
        filtered_df = filtered_df[search_mask]
    
    # 状态筛选
    if status_filter != "全部":
        status_value = status_filter == "活跃"
        filtered_df = filtered_df[
            filtered_df['是否活跃'].apply(
                lambda x: (str(x).lower() == 'true' if isinstance(x, str) else bool(x)) == status_value
            )
        ]
    
    # 客户类型筛选
    if customer_type == "仅主客户":
        filtered_df = filtered_df[filtered_df['子客户名称'] == '']
    elif customer_type == "仅子客户":
        filtered_df = filtered_df[filtered_df['子客户名称'] != '']

    # 显示查询结果和表格编辑
    st.subheader(f"📋 客户列表 (共 {len(filtered_df)} 条记录)")
    
    if not filtered_df.empty:
        # 创建显示副本用于编辑
        display_df = filtered_df.copy()
        
        # 格式化显示
        display_df['子客户名称'] = display_df['子客户名称'].apply(
            lambda x: '主客户' if x == '' else x
        )
        
        # 创建可编辑的数据编辑器
        edited_df = st.data_editor(
            display_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "客户名称": st.column_config.TextColumn("客户名称", disabled=True),
                "财务编号": st.column_config.TextColumn("财务编号", disabled=True),
                "子客户名称": st.column_config.TextColumn("子客户类型", disabled=True),
                "区域": st.column_config.TextColumn("区域"),
                "联系人": st.column_config.TextColumn("联系人"),
                "电话": st.column_config.TextColumn("电话"),
                "是否活跃": st.column_config.CheckboxColumn("是否活跃"),
                "更新时间": st.column_config.DatetimeColumn("更新时间", disabled=True)
            },
            hide_index=True,
            width='stretch',
            num_rows="fixed"
        )
        
        # 检查并保存表格中的更改
        if not edited_df.equals(display_df):
            changed_rows = edited_df[~edited_df.apply(tuple, 1).isin(display_df.apply(tuple, 1))]
            
            for _, row in changed_rows.iterrows():
                original_row = display_df[display_df['id'] == row['id']].iloc[0]
                updates = {}
                
                # 检查哪些字段被修改了
                for col in ['区域', '联系人', '电话', '是否活跃']:
                    if str(row[col]) != str(original_row[col]):
                        updates[{
                            '区域': 'region',
                            '联系人': 'contact_person', 
                            '电话': 'phone',
                            '是否活跃': 'is_active'
                        }[col]] = row[col]
                
                if updates:
                    if update_customer_info(row['id'], updates):
                        st.success(f"✅ 客户 {original_row['客户名称']} 信息已更新")
                        st.rerun()

    # 客户详细信息编辑
    st.subheader("✏️ 客户详细信息编辑")
    
    if not filtered_df.empty:
        # 创建客户选择器
        customer_options = []
        for _, row in filtered_df.iterrows():
            display_name = f"{row['客户名称']} - {row['财务编号']}"
            if row['子客户名称'] and row['子客户名称'] != '':
                display_name += f" (子客户: {row['子客户名称']})"
            customer_options.append((display_name, row['id']))
        
        selected_display = st.selectbox(
            "选择要编辑的客户",
            options=[opt[0] for opt in customer_options],
            key="customer_selector"
        )
        
        # 获取选中的客户数据
        selected_id = None
        for display_name, cust_id in customer_options:
            if display_name == selected_display:
                selected_id = cust_id
                break
        
        if selected_id:
            selected_customer = filtered_df[filtered_df['id'] == selected_id].iloc[0]
            
            # 编辑表单
            with st.form("customer_detail_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**基本信息**")
                    new_customer_name = st.text_input(
                        "客户名称*", 
                        value=selected_customer['客户名称'],
                        help="请输入客户完整名称"
                    )
                    
                    new_finance_id = st.text_input(
                        "财务编号*", 
                        value=selected_customer['财务编号'],
                        help="财务系统唯一标识"
                    )
                    
                    new_sub_customer = st.text_input(
                        "子客户名称", 
                        value=selected_customer['子客户名称'] if selected_customer['子客户名称'] != '主客户' else '',
                        placeholder="留空表示主客户",
                        help="如有关联子客户请填写"
                    )
                
                with col2:
                    st.markdown("**联系信息**")
                    new_region = st.text_input(
                        "区域", 
                        value=selected_customer['区域'],
                        placeholder="如：华东区、华北区等"
                    )
                    
                    new_contact = st.text_input(
                        "联系人", 
                        value=selected_customer['联系人'],
                        placeholder="联系人姓名"
                    )
                    
                    new_phone = st.text_input(
                        "电话", 
                        value=selected_customer['电话'],
                        placeholder="联系电话"
                    )
                    
                st.markdown("**状态设置**")
                # 使用toggle表示活跃状态
                current_status = selected_customer['是否活跃']
                if isinstance(current_status, str):
                    is_active = current_status.lower() == 'true'
                else:
                    is_active = bool(current_status)
                
                new_status = st.toggle(
                    "客户状态",
                    value=is_active,
                    help="启用表示客户活跃，禁用表示客户停用"
                )
                    
                
                # 表单提交按钮
                col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
                with col_btn2:
                    submitted = st.form_submit_button(
                        "💾 保存详细修改",
                        width='stretch'
                    )
                
                if submitted:
                    # 验证必填字段
                    if not new_customer_name.strip() or not new_finance_id.strip():
                        st.error("❌ 客户名称和财务编号为必填字段")
                    else:
                        updates = {
                            'customer_name': new_customer_name.strip(),
                            'finance_id': new_finance_id.strip(),
                            'sub_customer_name': new_sub_customer.strip(),
                            'region': new_region.strip(),
                            'contact_person': new_contact.strip(),
                            'phone': new_phone.strip(),
                            'is_active': new_status
                        }
                        
                        if update_customer_info(selected_id, updates):
                            st.success("✅ 客户详细信息更新成功！")
                            st.rerun()

    # 数据导出
    if not filtered_df.empty:
        st.subheader("💾 数据导出")
        
        export_df = filtered_df.copy()
        export_df['子客户名称'] = export_df['子客户名称'].apply(
            lambda x: '' if x == '主客户' else x
        )
        export_df['是否活跃'] = export_df['是否活跃'].apply(
            lambda x: '是' if (str(x).lower() == 'true' if isinstance(x, str) else bool(x)) else '否'
        )
        
        csv_data = export_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            "📥 导出当前客户列表(CSV)",
            csv_data,
            "customers_export.csv",
            "text/csv",
            width='stretch'
        )
    else:
        st.info("没有找到符合条件的客户")

# 使用说明
with st.expander("📚 使用说明", expanded=False):
    st.markdown("""
    ### 客户管理功能说明
    
    **快速编辑**
    - 在表格中直接修改**区域、联系人、电话、活跃状态**
    - 修改后系统会自动保存
    
    **详细编辑**  
    - 选择特定客户进行完整信息编辑
    - 可修改所有字段包括客户名称、财务编号等
    - 使用开关直观设置客户状态
    
    **新增客户**
    - 点击"新增客户"按钮打开对话框
    - 填写完整客户信息
    - 使用开关设置初始状态
    
    **筛选功能**
    - 支持关键词搜索（客户名称、财务编号、子客户名称）
    - 支持按状态筛选（活跃/停用）
    - 支持按客户类型筛选（主客户/子客户）
    
    **数据导出**
    - 支持导出筛选后的客户列表
    - 导出格式为CSV，兼容Excel
    
    *注：带 * 的字段为必填项*
    """)
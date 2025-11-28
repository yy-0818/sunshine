import streamlit as st
import pandas as pd
from datetime import datetime
from utils.auth import AuthSystem, require_login, check_permission, get_role_display_name, format_datetime

# 设置页面
st.set_page_config(
    page_title="用户管理",
    page_icon="👥",
    layout="wide"
)

def main():
    require_login()
    
    # 检查管理员权限
    if not check_permission('admin'):
        st.error("❌ 权限不足，需要管理员权限才能访问此页面")
        st.info("💡 请联系系统管理员获取相应权限")
        st.stop()
    
    st.title("👥 用户管理")
    st.markdown("---")
    
    # 初始化认证系统
    auth = AuthSystem()
    
    # 创建标签页
    tab1, tab2, tab3 = st.tabs(["📋 用户列表", "➕ 创建用户", "📊 用户统计"])
    
    with tab1:
        render_user_list_tab(auth)
    
    with tab2:
        render_create_user_tab(auth)
    
    with tab3:
        render_user_stats_tab(auth)

def render_user_list_tab(auth):
    """用户列表标签页"""
    st.header("📋 用户列表")
    
    # 获取用户数据
    users = auth.get_all_users()
    
    if not users:
        st.info("📝 暂无用户数据，请先创建用户")
        return
    
    # 转换为DataFrame用于显示和筛选
    user_data = []
    for user in users:
        user_data.append({
            'ID': user[0],
            '用户名': user[1],
            '角色': get_role_display_name(user[2]),
            '角色代码': user[2],
            '姓名': user[3],
            '部门': user[4] or '未设置',
            '状态': '✅ 活跃' if user[5] else '❌ 禁用',
            '状态值': user[5],
            '创建时间': format_datetime(user[6]),
            '最后登录': format_datetime(user[7])
        })
    
    df = pd.DataFrame(user_data)
    
    # 统计卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_users = len(users)
        st.metric("总用户数", total_users)
    with col2:
        active_users = len([u for u in users if u[5]])
        st.metric("活跃用户", active_users)
    with col3:
        admin_count = len([u for u in users if u[2] == 'admin'])
        st.metric("管理员", admin_count)
    with col4:
        never_logged_in = len([u for u in users if not u[7]])
        st.metric("从未登录", never_logged_in)
    
    st.markdown("---")
    
    # 搜索和筛选区域
    st.subheader("🔍 用户查询")
    
    col_search1, col_search2, col_search3 = st.columns([2, 1, 1])
    
    with col_search1:
        search_term = st.text_input("搜索关键词", placeholder="输入用户名或姓名")
    
    with col_search2:
        role_filter = st.selectbox(
            "角色筛选",
            ["全部角色", "系统管理员", "部门经理", "普通用户"]
        )
    
    with col_search3:
        status_filter = st.selectbox("状态筛选", ["全部", "活跃", "禁用"])
    
    # 应用筛选
    filtered_df = df.copy()
    
    # 关键词搜索
    if search_term and search_term.strip():
        search_mask = (
            filtered_df['用户名'].str.contains(search_term, case=False, na=False) |
            filtered_df['姓名'].str.contains(search_term, case=False, na=False)
        )
        filtered_df = filtered_df[search_mask]
    
    # 角色筛选
    if role_filter != "全部角色":
        role_mapping = {"系统管理员": "admin", "部门经理": "manager", "普通用户": "user"}
        filtered_df = filtered_df[filtered_df['角色代码'] == role_mapping[role_filter]]
    
    # 状态筛选
    if status_filter != "全部":
        status_value = status_filter == "活跃"
        filtered_df = filtered_df[filtered_df['状态值'] == status_value]
    
    # 显示查询结果
    st.subheader(f"📋 用户列表 (共 {len(filtered_df)} 条记录)")
    
    if filtered_df.empty:
        st.info("没有找到符合条件的用户")
        return
    
    # 使用数据编辑器显示用户列表
    display_df = filtered_df.copy()
    
    # 创建可编辑的数据编辑器
    edited_df = st.data_editor(
        display_df[['用户名', '姓名', '部门', '状态', '角色', '最后登录']],
        column_config={
            "用户名": st.column_config.TextColumn("用户名", disabled=True),
            "姓名": st.column_config.TextColumn("姓名"),
            "部门": st.column_config.TextColumn("部门"),
            "状态": st.column_config.TextColumn("状态", disabled=True),
            "角色": st.column_config.TextColumn("角色", disabled=True),
            "最后登录": st.column_config.TextColumn("最后登录", disabled=True)
        },
        hide_index=True,
        width='stretch',
        key="user_list_editor"
    )
    
    # 操作列 - 编辑和删除按钮
    st.subheader("🛠️ 用户操作")
    
    # 创建选择器选择要操作的用户
    user_options = []
    for _, row in filtered_df.iterrows():
        display_name = f"{row['用户名']} - {row['姓名']} ({row['角色']})"
        user_options.append((display_name, row['ID']))
    
    selected_display = st.selectbox(
        "选择要操作的用户",
        options=[opt[0] for opt in user_options],
        key="user_selector"
    )
    
    # 获取选中的用户ID
    selected_id = None
    for display_name, user_id in user_options:
        if display_name == selected_display:
            selected_id = user_id
            break
    
    if selected_id:
        selected_user = filtered_df[filtered_df['ID'] == selected_id].iloc[0]
        
        col_edit, col_del, col_export = st.columns([1, 1, 2])
        
        with col_edit:
            if st.button("✏️ 编辑用户信息", width='stretch'):
                st.session_state.editing_user_id = selected_id
        
        with col_del:
            # 不能删除默认用户
            if selected_user['用户名'] not in ['admin', 'manager', 'user']:
                if st.button("🗑️ 删除用户", width='stretch'):
                    st.session_state.deleting_user_id = selected_id
            else:
                st.button("🗑️ 删除用户", disabled=True, 
                         help="不能删除系统默认用户", width='stretch')
        
        with col_export:
            # 数据导出
            csv_data = filtered_df[['用户名', '姓名', '部门', '状态', '角色', '创建时间', '最后登录']].to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 导出用户列表(CSV)",
                csv_data,
                "users_export.csv",
                "text/csv",
                width='stretch'
            )
    
    # 编辑用户对话框
    if 'editing_user_id' in st.session_state:
        edit_user_dialog(auth, st.session_state.editing_user_id, users)
    
    # 删除用户对话框
    if 'deleting_user_id' in st.session_state:
        delete_user_dialog(auth, st.session_state.deleting_user_id, users)

@st.dialog("编辑用户信息", width="large")
def edit_user_dialog(auth, user_id, users):
    """编辑用户信息的对话框"""
    user_to_edit = [u for u in users if u[0] == user_id][0]
    
    st.write(f"正在编辑用户: **{user_to_edit[1]}**")
    
    with st.form(f"edit_user_form_{user_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**基本信息**")
            username = st.text_input(
                "用户名*",
                value=user_to_edit[1],
                disabled=True,
                help="用户名不可修改"
            )
            
            full_name = st.text_input(
                "姓名*", 
                value=user_to_edit[3] or "",
                placeholder="请输入真实姓名",
                help="用户的真实姓名"
            )
            
            department = st.text_input(
                "部门", 
                value=user_to_edit[4] or "",
                placeholder="请输入部门名称",
                help="用户所属部门"
            )
        
        with col2:
            st.markdown("**权限设置**")
            role = st.selectbox(
                "角色*",
                ['admin', 'manager', 'user'],
                format_func=get_role_display_name,
                index=['admin', 'manager', 'user'].index(user_to_edit[2]),
                help="选择用户的权限级别"
            )
            
            is_active = st.toggle(
                "启用用户",
                value=bool(user_to_edit[5]),
                help="启用表示用户可正常登录，禁用后用户将无法登录系统"
            )
            
            st.markdown("**账户信息**")
            st.text(f"创建时间: {format_datetime(user_to_edit[6])}")
            last_login = format_datetime(user_to_edit[7])
            st.text(f"最后登录: {last_login if last_login else '从未登录'}")
        
        # 按钮行
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            submitted = st.form_submit_button(
                "💾 保存更改",
                width='stretch'
            )
        
        with col_cancel:
            if st.form_submit_button("❌ 取消", width='stretch'):
                if 'editing_user_id' in st.session_state:
                    del st.session_state.editing_user_id
                st.rerun()
        
        if submitted:
            if not full_name.strip():
                st.error("❌ 姓名为必填字段")
            else:
                # 更新用户信息
                success, message = auth.update_user_info(
                    user_id, full_name.strip(), department.strip(), is_active
                )
                
                # 如果角色有变化，更新角色
                if success and role != user_to_edit[2]:
                    success, message = auth.update_user_role(user_id, role)
                
                if success:
                    st.success("✅ 用户信息更新成功")
                    if 'editing_user_id' in st.session_state:
                        del st.session_state.editing_user_id
                    st.rerun()
                else:
                    st.error(f"❌ {message}")

@st.dialog("删除用户确认", width="medium")
def delete_user_dialog(auth, user_id, users):
    """删除用户确认对话框"""
    user_to_delete = [u for u in users if u[0] == user_id][0]
    
    st.warning("⚠️ 确定要删除此用户吗？")
    st.error(f"即将删除用户: **{user_to_delete[1]}** ({user_to_delete[3]})")
    
    st.info("""
    **删除操作不可恢复！此操作将：**
    - 永久删除用户账户
    - 清除所有用户相关数据
    - 用户将无法再登录系统
    """)
    
    col_confirm, col_cancel = st.columns(2)
    
    with col_confirm:
        if st.button("✅ 确认删除", width='stretch', type="primary"):
            success, message = auth.delete_user(user_id)
            if success:
                st.success("✅ " + message)
                if 'deleting_user_id' in st.session_state:
                    del st.session_state.deleting_user_id
                st.rerun()
            else:
                st.error("❌ " + message)
    
    with col_cancel:
        if st.button("❌ 取消", width='stretch'):
            if 'deleting_user_id' in st.session_state:
                del st.session_state.deleting_user_id
            st.rerun()

def render_create_user_tab(auth):
    """创建用户标签页"""
    st.header("➕ 创建新用户")
    
    with st.form("create_user_form", clear_on_submit=True):
        st.subheader("📝 用户信息")
        
        col1, col2 = st.columns(2)
        
        with col1:
            username = st.text_input(
                "用户名*", 
                placeholder="请输入用户名",
                help="用户名必须唯一，用于登录系统"
            )
            password = st.text_input(
                "密码*", 
                type="password", 
                placeholder="请输入密码",
                help="密码长度至少6位，建议包含字母和数字"
            )
            confirm_password = st.text_input(
                "确认密码*", 
                type="password", 
                placeholder="请再次输入密码"
            )
        
        with col2:
            full_name = st.text_input(
                "姓名*", 
                placeholder="请输入真实姓名"
            )
            department = st.text_input(
                "部门", 
                placeholder="请输入部门名称"
            )
            role = st.selectbox(
                "角色*", 
                ['user', 'manager', 'admin'],
                format_func=get_role_display_name,
                help="选择用户的权限级别"
            )
        
        # 密码强度检查
        if password:
            col_pass1, col_pass2 = st.columns(2)
            with col_pass1:
                if len(password) >= 8 and any(c.isdigit() for c in password) and any(c.isalpha() for c in password):
                    st.success("🔒 密码强度: 强")
                elif len(password) >= 6:
                    st.warning("🔒 密码强度: 中")
                else:
                    st.error("🔒 密码强度: 弱")
            
            with col_pass2:
                if password == confirm_password:
                    st.success("✅ 密码一致")
                elif confirm_password:
                    st.error("❌ 密码不一致")
        
        submitted = st.form_submit_button(
            "👤 创建用户", 
            width='stretch'
        )
        
        if submitted:
            # 验证输入
            if not all([username, password, full_name]):
                st.error("❌ 请填写所有必填字段（标*）")
            elif len(password) < 6:
                st.error("❌ 密码长度至少6位")
            elif password != confirm_password:
                st.error("❌ 密码不一致")
            else:
                with st.spinner("正在创建用户..."):
                    success, message = auth.create_user(
                        username, password, role, full_name, department
                    )
                    if success:
                        st.success("✅ " + message)
                        st.balloons()
                    else:
                        st.error("❌ " + message)

def render_user_stats_tab(auth):
    """用户统计标签页"""
    st.header("📊 用户统计")
    
    users = auth.get_all_users()
    
    if not users:
        st.info("📝 暂无用户数据")
        return
    
    # 统计信息
    total_users = len(users)
    active_users = len([u for u in users if u[5]])
    inactive_users = total_users - active_users
    
    role_counts = {
        'admin': len([u for u in users if u[2] == 'admin']),
        'manager': len([u for u in users if u[2] == 'manager']),
        'user': len([u for u in users if u[2] == 'user'])
    }
    
    never_logged_in = len([u for u in users if not u[7]])
    
    # 关键指标
    st.subheader("📈 关键指标")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总用户数", total_users)
    with col2:
        st.metric("活跃用户", active_users, f"{active_users/total_users*100:.1f}%")
    with col3:
        st.metric("从未登录", never_logged_in)
    with col4:
        st.metric("默认用户", 3)  # admin, manager, user
    
    st.markdown("---")
    
    # 角色分布
    st.subheader("👥 角色分布")
    col1, col2 = st.columns(2)
    
    with col1:
        # 角色饼图数据
        role_data = {
            '角色': [get_role_display_name(role) for role in role_counts.keys()],
            '数量': list(role_counts.values())
        }
        role_df = pd.DataFrame(role_data)
        
        if not role_df.empty:
            st.bar_chart(role_df.set_index('角色'))
        else:
            st.info("暂无角色分布数据")
    
    with col2:
        # 状态分布
        status_data = pd.DataFrame({
            '状态': ['活跃', '禁用'],
            '数量': [active_users, inactive_users]
        })
        st.bar_chart(status_data.set_index('状态'))
    
    # 详细统计
    st.subheader("📋 详细统计")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**👑 角色统计**")
        for role, count in role_counts.items():
            percentage = count / total_users * 100
            st.write(f"- {get_role_display_name(role)}: {count}人 ({percentage:.1f}%)")
    
    with col2:
        st.markdown("**📊 状态统计**")
        st.write(f"- ✅ 活跃: {active_users}人 ({active_users/total_users*100:.1f}%)")
        st.write(f"- ❌ 禁用: {inactive_users}人 ({inactive_users/total_users*100:.1f}%)")
    
    with col3:
        st.markdown("**🔐 登录统计**")
        st.write(f"- 🔄 已登录: {total_users - never_logged_in}人")
        st.write(f"- ⏰ 从未登录: {never_logged_in}人")
    
    # 系统信息和建议
    st.markdown("---")
    st.subheader("💡 系统管理建议")
    
    if total_users == 3 and all(user[1] in ['admin', 'manager', 'user'] for user in users):
        st.warning("""
        **⚠️ 系统仍在使用默认账号**  
        
        **建议操作：**
        - 创建新的管理员账号用于日常管理
        - 为不同部门创建专属账号
        - 定期检查用户活跃状态
        - 及时清理不再使用的账号
        """)
    else:
        st.success("""
        **✅ 用户管理状况良好**  
        
        **维护建议：**
        - 定期审核用户权限是否合理
        - 检查长时间未登录的账号
        - 确保每个用户都有明确的职责
        - 定期备份用户数据
        """)
        
        # 额外建议
        if never_logged_in > 0:
            st.info(f"💡 有 {never_logged_in} 个用户从未登录，建议联系确认是否需要这些账号")

if __name__ == "__main__":
    main()
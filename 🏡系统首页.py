import streamlit as st
from core.database import init_database, get_database_status
from utils.auth import require_login, login_form, get_role_display_name

# 设置页面配置（放在最前面）
st.set_page_config(
    page_title="阳光陶瓷价格数据库", 
    page_icon="🗿", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 显示Logo
st.logo(
    image='./assets/logo.png',
    icon_image='./assets/logo.png',
)


def main():
    # 初始化数据库
    try:
        init_database()
        st.success("✅ 数据库初始化成功")
    except Exception as e:
        st.error(f"❌ 数据库初始化失败: {str(e)}")

    # 检查登录状态
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        show_login_page()
        return
    # 已登录用户显示主页面
    show_main_page()

def show_login_page():
    """显示登录页面"""
    st.title("🗿 陶瓷客户产品价格数据库")
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🔐 欢迎使用")
        st.markdown("""
        ### 系统功能特色
        
        **📊 全面的数据分析**
        - 销售数据管理与分析
        - 客户欠款风险监控
        - 价格趋势智能分析
        
        **👥 多级权限管理**
        - 管理员：完全系统权限
        - 经理：数据查看与分析权限  
        - 用户：基础数据查看权限
        
        **💾 安全可靠**
        - 数据加密存储
        - 操作日志记录
        - 定期数据备份
        """)
    
    with col2:
        login_form()

def show_main_page():
    """显示主页面"""
    require_login()
    
    # 显示用户信息
    user = st.session_state.user
    st.toast(f"Hooray! {user['full_name']}", icon="🎉")
    st.sidebar.success(f"👤{user['full_name']} ({get_role_display_name(user['role'])})")
    
    st.title("🗿 陶瓷客户产品价格数据库")
    st.markdown("---")
    
    # 显示系统概览
    render_dashboard()
    
    # 侧边栏状态
    render_sidebar_status()

def render_dashboard():
    """显示系统概览"""
    st.subheader("📊 系统概览")
    
    # 获取数据库状态
    try:
        status = get_database_status()
        
        # 关键指标
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("客户数量", status.get('sub_customers', 0))
        with col2:
            st.metric("销售记录", status.get('sales_records_count', 0))
        with col3:
            st.metric("产品颜色", status.get('unique_colors', 0))
        with col4:
            st.metric("数据大小", f"{status.get('db_size_mb', 0):.1f} MB")
            
    except Exception as e:
        st.error(f"获取数据库状态失败: {str(e)}")
        # 显示默认值
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("客户数量", 0)
        with col2:
            st.metric("销售记录", 0)
        with col3:
            st.metric("产品颜色", 0)
        with col4:
            st.metric("数据大小", "0 KB")
    
    # 快速导航
    st.markdown("---")
    st.subheader("🚀 快速导航")
    
    # 第一行导航按钮
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📥 数据导入", use_container_width=True):
            st.switch_page("pages/1_📥_数据导入.py")
    with col2:
        if st.button("📋 数据浏览", use_container_width=True):
            st.switch_page("pages/2_📋_数据浏览.py")
    with col3:
        if st.button("🔍 价格查询", use_container_width=True):
            st.switch_page("pages/3_🔍_价格查询.py")
    with col4:
        if st.button("📊 数据统计", use_container_width=True):
            st.switch_page("pages/4_📊_数据统计.py")
    
    # 第二行导航按钮
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        if st.button("📈 价格趋势", use_container_width=True):
            st.switch_page("pages/5_📈_价格趋势.py")
    with col6:
        if st.button("👥 客户管理", use_container_width=True):
            st.switch_page("pages/6_👥_客户管理.py")
    with col7:
        if st.button("💳 客户欠款", use_container_width=True):
            st.switch_page("pages/7_💳_客户欠款.py")
    with col8:
        if st.button("⚙️ 系统设置", use_container_width=True):
            st.switch_page("pages/8_⚙️_系统设置.py")
    
    # 管理员专属功能
    if st.session_state.user['role'] in ['admin', 'manager']:
        col9, col10, col11, col12 = st.columns(4)
        with col9:
            if st.button("👥 用户管理", use_container_width=True):
                st.switch_page("pages/9_👥_用户管理.py")
    
    # 使用说明
    with st.expander("📚 使用说明", expanded=True):
        st.markdown("""
        ### 系统功能说明
        
        **核心业务功能**
        - **📥 数据导入**: 支持Excel文件导入，自动识别客户和销售数据
        - **📋 数据浏览**: 查看数据库中所有表的数据，支持分页浏览和搜索
        - **🔍 价格查询**: 支持按客户、产品颜色、等级进行查询，实时显示最新价格信息
        - **📊 数据统计**: 全面的数据分析和可视化报表，多维度业务指标分析
        
        **高级分析功能**  
        - **📈 价格趋势**: 分析客户产品价格的历史变化趋势，可视化展示价格和数量变化
        - **👥 客户管理**: 查看和管理所有客户信息，支持客户信息的编辑和更新
        - **💳 客户欠款**: 欠款数据分析和风险识别，支持多部门数据管理
        
        **系统管理功能**
        - **👥 用户管理**: 用户账号和权限管理（仅管理员）
        - **⚙️ 系统设置**: 数据库维护和系统状态监控，数据备份和恢复功能
        """)

def render_sidebar_status():
    """侧边栏状态显示"""
    # try:
        # status = get_database_status()
        # 
        # st.sidebar.markdown("### 📊 数据库状态")
        # 
        # col1, col2 = st.sidebar.columns(2)
        # with col1:
        #     st.metric("客户", status.get('sub_customers', 0))
        # with col2:
        #     st.metric("销售记录", status.get('sales_records_count', 0))
        
        # 数据库信息
        # st.sidebar.markdown("---")
        # st.sidebar.markdown("### ℹ️ 系统信息")
        # st.sidebar.info(f"数据库大小: {status.get('db_size_mb', 0):.1f} MB")
        
        # 用户信息
    #     user = st.session_state.user
    #     st.sidebar.markdown("### 👤 用户信息")
    #     st.sidebar.text(f"姓名: {user['full_name']}")
    #     st.sidebar.text(f"角色: {user['role']}")
    #     st.sidebar.text(f"部门: {user['department']}")
        
    # except Exception as e:
    #     st.sidebar.error("获取数据库状态失败")
    
    # 操作按钮
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔧 快捷操作")
    if st.sidebar.button("优化数据库", use_container_width=True):
        try:
            from core.database import optimize_database
            optimize_database()
            st.sidebar.success("数据库优化完成")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"优化失败: {str(e)}")
    
    # 退出登录
    if st.sidebar.button("🚪 退出登录", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

if __name__ == "__main__":
    main()
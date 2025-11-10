import streamlit as st
import pandas as pd
import os
from core.import_service import ImportService
from utils.file_utils import validate_excel_structure, preview_excel_data, get_excel_file_info, validate_data_quality
from core.database import clear_database, get_database_status

# 页面配置
st.set_page_config(page_title="数据导入", layout="wide")
st.logo(image='./assets/logo.png', icon_image='./assets/logo.png')
st.title("📥 Excel 数据导入")

# 初始化服务
import_service = ImportService()

# 仅保留两种策略
STRATEGY_CONFIG = {
    "append": {
        "name": "智能更新",
        "icon": "📝",
        "color": "#3498db",
        "gradient": "linear-gradient(135deg, #dfe9f3 0%, #ffffff 100%)",
        "description": "不修改数据库中已有数据，仅导入新增数据"
    },
    "replace": {
        "name": "完全覆盖",
        "icon": "🔄",
        "color": "#e74c3c",
        "gradient": "linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)",
        "description": "清空数据库并导入新数据，操作不可恢复"
    }
}


@st.cache_data(ttl=300)
def get_current_db_status():
    """获取当前数据库状态"""
    return get_database_status()


def render_database_status():
    """渲染数据库状态"""
    db_status = get_current_db_status()
    if db_status:
        cols = st.columns(4)
        metrics = [
            ("客户数量", db_status.get('sub_customers', 0)),
            ("销售记录", db_status.get('sales_records_count', 0)),
            ("产品种类", db_status.get('unique_products', 0)),
            ("颜色种类", db_status.get('unique_colors', 0))
        ]
        for col, (label, value) in zip(cols, metrics):
            with col:
                st.metric(label, value)


def execute_import(file_path, strategy, replace_confirm):
    """执行数据导入"""
    if strategy == "replace" and not replace_confirm:
        st.error("请确认执行完全覆盖操作！")
        return

    with st.spinner("正在导入数据，请稍候..."):
        success, message = import_service.import_excel_data(
            file_path, "user", update_strategy=strategy
        )

    if success:
        st.success("✅ 导入成功！")
        st.info(message)
        st.toast(message, icon="🎉")
        st.balloons()
        st.cache_data.clear()
    else:
        st.error(f"❌ 导入失败：{message}")


def main():
    render_database_status()

    st.markdown("### 📋 导入策略选择")

    # 策略展示
    cols = st.columns(2)
    for i, (key, cfg) in enumerate(STRATEGY_CONFIG.items()):
        with cols[i]:
            st.markdown(
                f"""
                <div style='border-radius:12px;padding:12px;background:{cfg['gradient']};
                border-left:5px solid {cfg['color']};margin-bottom:10px'>
                <h4>{cfg['icon']} {cfg['name']}</h4>
                <p style='color:#555;'>{cfg['description']}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

    # 选择框
    strategy = st.radio(
        "选择导入模式：",
        options=list(STRATEGY_CONFIG.keys()),
        format_func=lambda x: f"{STRATEGY_CONFIG[x]['icon']} {STRATEGY_CONFIG[x]['name']}",
        horizontal=True
    )

    # 替换确认
    replace_confirm = True
    if strategy == "replace":
        st.warning("⚠️ 完全覆盖模式会清空所有数据，请谨慎操作！")
        replace_confirm = st.checkbox("我已备份数据，并确认执行", value=False)

    uploaded_file = st.file_uploader("📤 上传 Excel 文件", type=['xlsx', 'xls'])
    if not uploaded_file:
        st.info("请上传文件以开始导入")
        return

    temp_path = "temp_upload.xlsx"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    try:
        # 文件验证
        valid, msg = validate_excel_structure(temp_path)
        if not valid:
            st.error(msg)
            return

        # 数据预览
        ok, preview = preview_excel_data(temp_path, 5)
        if ok:
            st.subheader("👀 数据预览 (前5行)")
            st.dataframe(preview, width='stretch')

        # 导入执行
        st.markdown("---")
        if st.button("🚀 开始导入", width='stretch', type="primary"):
            execute_import(temp_path, strategy, replace_confirm)

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    main()

import streamlit as st
import pandas as pd
import os
import sys
from datetime import datetime
from core.database import (
    get_database_status,
    optimize_database,
    clear_database,
    init_database,
    get_connection
)
from core.analysis_service import AnalysisService
import shutil

# -------------------------------
# 页面配置与初始化
# -------------------------------
st.set_page_config(page_title="系统设置", layout="wide")
st.logo(image="./assets/logo.png", icon_image="./assets/logo.png")
st.title("⚙️ 系统设置")

analysis_service = AnalysisService()

# -------------------------------
# 系统信息
# -------------------------------
st.subheader("🖥️ 系统信息")
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📊 版本信息")
    st.write(f"Python版本：{sys.version.split()[0]}")
    st.write(f"Pandas版本：{pd.__version__}")
    st.write(f"Streamlit版本：{st.__version__}")
    st.write(f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with col2:
    st.markdown("#### 💾 系统环境")
    st.write(f"运行平台：{sys.platform}")
    st.write(f"工作目录：{os.getcwd()}")
    st.write(f"数据库路径：{os.path.abspath('ceramic_prices.db')}")

# -------------------------------
# 数据库状态
# -------------------------------
st.subheader("🗄️ 数据库状态")

# 获取数据库状态
db_status = get_database_status()

# ---- 指标卡片展示 ----
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("客户总数", db_status.get("sub_customers", 0))
col2.metric("主客户数", db_status.get("main_customers", 0))

col3.metric("产品总数", db_status.get("unique_products", 0))
col4.metric("销售记录", db_status.get("sales_records_count", 0))
col5.metric("数据库大小", f"{db_status.get('db_size_mb', 0):.2f} MB")

st.divider()

# -------------------------------
# 数据库表详情
# -------------------------------
st.subheader("📋 数据库表详情")
tables = [
    ("customers", "客户信息表", db_status.get("sub_customers", 0)),
    ("sales_records", "销售记录表", db_status.get("sales_records_count", 0)),
    ("price_change_history", "价格变更表", db_status.get("price_change_history_count", 0)),
    ("unified_debt", "客户欠款表", db_status.get("debt_count", 0)),
]
df_tables = pd.DataFrame(tables, columns=["表名", "描述", "记录数"])
st.dataframe(df_tables, width='stretch', hide_index=True)

# -------------------------------
# 数据库维护操作
# -------------------------------
st.subheader("🔧 数据库维护")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔄 重新初始化数据库", width='stretch'):
        if st.checkbox("确认重新初始化数据库？该操作会重建表结构", key="init_confirm"):
            init_database()
            st.success("✅ 数据库初始化完成")
            st.rerun()

with col2:
    if st.button("⚡ 优化数据库", width='stretch'):
        with st.spinner("正在优化数据库..."):
            optimize_database()
        st.success("✅ 数据库优化完成")
        st.rerun()

with col3:
    if st.button("🗑️ 清空所有数据", width='stretch', type="secondary"):
        if st.checkbox("确认清空所有数据？此操作不可恢复！", key="clear_confirm"):
            clear_database()
            st.success("✅ 所有数据已清空")
            st.rerun()

st.divider()

# -------------------------------
# 数据统计概览
# -------------------------------
st.subheader("📈 数据统计概览")

try:
    stats = analysis_service.get_statistics()
    if stats.get("total_records", 0) > 0:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("主客户数", db_status["main_customers"])
        col2.metric("总客户数", db_status["sub_customers"])
        col3.metric("产品种类", db_status["unique_products"])
        col4.metric("产品颜色", db_status["unique_colors"])
        col5.metric("总记录数", db_status["sales_records_count"])


        st.markdown("#### 💰 数据对比图")
        st.bar_chart(
            pd.DataFrame({
                "指标": ["主客户数", "总客户数", "产品种类", "产品颜色", "总记录数"],
                "数量": [
                    db_status.get("main_customers", 0),
                    db_status.get("sub_customers", 0),
                    db_status.get("unique_products", 0),
                    db_status.get("unique_colors", 0),
                    db_status.get("sales_records_count", 0),
                ],
            }).set_index("指标")
        )
    else:
        st.info("暂无数据统计信息。请先导入销售数据。")

except Exception as e:
    st.error(f"获取统计信息出错：{e}")

st.divider()

# -------------------------------
# 最近操作日志
# -------------------------------
st.subheader("📝 最近7天内操作记录")

try:
    with get_connection() as conn:
        df_log = pd.read_sql_query('''
            SELECT 
                customer_name AS 客户,
                product_name AS 产品,
                color AS 颜色,
                unit_price AS 单价,
                strftime('%Y-%m-%d %H:%M', created_date) AS 时间
            FROM sales_records
            WHERE created_date >= datetime('now', '-7 days')
            ORDER BY created_date DESC
            LIMIT 10
        ''', conn)

    if df_log.empty:
        st.info("最近7天内无销售记录更新。")
    else:
        st.dataframe(df_log, width='stretch', hide_index=True)
except Exception as e:
    st.warning(f"操作日志加载失败：{e}")

st.divider()

# -------------------------------
# 数据备份与恢复
# -------------------------------
st.subheader("💾 数据备份与恢复")

if st.button("📤 备份数据库", width='stretch'):
    try:
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2("ceramic_prices.db", backup_name)
        st.success(f"✅ 数据库已备份为 {backup_name}")
    except Exception as e:
        st.error(f"备份失败: {e}")

uploaded_backup = st.file_uploader("上传备份文件进行恢复", type=["db"])
if uploaded_backup is not None:
    if st.button("🔄 恢复数据库", type="secondary", width='stretch'):
        try:
            with open("ceramic_prices.db", "wb") as f:
                f.write(uploaded_backup.getbuffer())
            st.success("✅ 数据库恢复成功")
            st.rerun()
        except Exception as e:
            st.error(f"恢复失败: {e}")

st.divider()

# -------------------------------
# 使用说明
# -------------------------------
with st.expander("📚 使用说明", expanded=False):
    st.markdown("""
    ### 系统功能概览
    **数据导入**  
    支持 Excel 文件导入，自动识别客户及销售数据并进行验证。

    **价格查询与趋势**  
    可按客户、产品、颜色、等级查询价格趋势。

    **数据统计**  
    提供客户数量、产品分布、价格范围等多维度统计。

    **数据库维护**  
    - **初始化数据库**：重建表结构，保留现有数据。  
    - **优化数据库**：清理碎片，提升性能。  
    - **清空所有数据**：彻底删除所有数据记录。

    **备份与恢复**  
    - 一键备份数据库文件。  
    - 支持 `.db` 文件上传恢复。
    """)


import streamlit as st
import pandas as pd
import os
import sys
from datetime import datetime
from core.database import get_database_status, optimize_database, clear_database, init_database, get_connection
from core.analysis_service import AnalysisService

st.set_page_config(page_title="系统设置", layout="wide")
st.title("⚙️ 系统设置")

analysis_service = AnalysisService()

# 系统信息
st.subheader("🖥️ 系统信息")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📊 版本信息")
    st.write(f"Python版本: {sys.version.split()[0]}")
    st.write(f"Pandas版本: {pd.__version__}")
    st.write(f"Streamlit版本: {st.__version__}")
    st.write(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with col2:
    st.markdown("#### 💾 系统状态")
    st.write(f"运行平台: {sys.platform}")
    st.write(f"工作目录: {os.getcwd()}")
    st.write(f"数据库路径: {os.path.abspath('ceramic_prices.db')}")

# 数据库状态
st.subheader("🗄️ 数据库状态")

# 获取数据库状态
db_status = get_database_status()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("客户表记录", db_status.get('customers_count', 0))
    st.metric("销售记录", db_status.get('sales_records_count', 0))

with col2:
    st.metric("变更历史记录", db_status.get('price_change_history_count', 0))
    st.metric("数据库大小", f"{db_status.get('db_size_kb', 0):.1f} KB")

with col3:
    # 数据完整性检查
    try:
        stats = analysis_service.get_statistics()
        st.metric("有效销售记录", stats.get('total_records', 0))
        st.metric("产品颜色数", stats.get('unique_colors', 0))
    except:
        st.metric("有效销售记录", 0)
        st.metric("产品颜色数", 0)

# 数据库表详情
st.subheader("📋 数据库表详情")

tables_info = []
for table in ['customers', 'sales_records', 'price_change_history']:
    count = db_status.get(f'{table}_count', 0)
    tables_info.append({"表名": table, "记录数": count})

tables_df = pd.DataFrame(tables_info)
st.dataframe(tables_df, use_container_width=True)

# 数据库维护
st.subheader("🔧 数据库维护")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔄 重新初始化数据库", use_container_width=True):
        if st.checkbox("确认重新初始化数据库？这将重建所有表结构"):
            init_database()
            st.success("✅ 数据库初始化完成")
            st.rerun()

with col2:
    if st.button("⚡ 优化数据库", use_container_width=True):
        with st.spinner("正在优化数据库..."):
            optimize_database()
        st.success("✅ 数据库优化完成")
        st.rerun()

with col3:
    if st.button("🗑️ 清空所有数据", use_container_width=True, type="secondary"):
        if st.checkbox("确认清空所有数据？此操作不可恢复！"):
            clear_database()
            st.success("✅ 所有数据已清空")
            st.rerun()

# 数据统计
st.subheader("📈 数据统计概览")

try:
    stats = analysis_service.get_statistics()
    
    if stats['total_records'] > 0:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("总记录数", stats['total_records'])
            st.metric("唯一客户", stats['unique_customers'])
        
        with col2:
            st.metric("子客户数", stats['sub_customers'])
            st.metric("产品颜色", stats['unique_colors'])
        
        with col3:
            min_price = stats.get('min_price', 0)
            max_price = stats.get('max_price', 0)
            st.metric("最低价格", f"¥{min_price:.2f}")
            st.metric("最高价格", f"¥{max_price:.2f}")
        
        with col4:
            total_amount = stats.get('total_amount', 0)
            total_quantity = stats.get('total_quantity', 0)
            st.metric("总金额", f"¥{total_amount:,.2f}")
            st.metric("总数量", f"{total_quantity:,.0f}")
        
        # 金额对比
        st.markdown("#### 💰 业务统计")
        amount_data = pd.DataFrame({
            '类型': ['总记录数', '总客户数', '总产品颜色', '总交易数量'],
            '数值': [stats['total_records'], stats['unique_customers'], stats['unique_colors'], stats['total_quantity']]
        })
        st.bar_chart(amount_data.set_index('类型'))
        
    else:
        st.info("暂无数据统计信息")
        
except Exception as e:
    st.error(f"获取统计信息时出错: {str(e)}")
    st.info("请确保已正确导入数据")

# 系统日志（简化版）
st.subheader("📝 最近操作")

# 显示最近的数据库操作
try:
    with get_connection() as conn:
        recent_operations = pd.read_sql_query('''
            SELECT 
                '销售记录' as 操作类型,
                strftime('%Y-%m-%d %H:%M', created_date) as 时间,
                customer_name as 客户名称,
                color as 产品颜色,
                unit_price as 单价
            FROM sales_records 
            WHERE created_date >= datetime('now', '-7 days')
            ORDER BY created_date DESC
            LIMIT 10
        ''', conn)
    
    if not recent_operations.empty:
        st.dataframe(recent_operations, use_container_width=True)
    else:
        st.info("最近7天内无操作记录")
except:
    st.info("操作日志功能待完善")

# 数据备份和恢复
st.subheader("💾 数据备份")

col1, col2 = st.columns(2)

with col1:
    if st.button("📤 备份数据库", use_container_width=True):
        try:
            import shutil
            import datetime
            backup_name = f"ceramic_prices_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2('ceramic_prices.db', backup_name)
            st.success(f"✅ 数据库已备份为: {backup_name}")
        except Exception as e:
            st.error(f"备份失败: {str(e)}")

with col2:
    uploaded_backup = st.file_uploader("恢复备份", type=['db'])
    if uploaded_backup is not None:
        if st.button("🔄 恢复数据库", type="secondary"):
            try:
                with open('ceramic_prices.db', 'wb') as f:
                    f.write(uploaded_backup.getbuffer())
                st.success("✅ 数据库恢复成功")
                st.rerun()
            except Exception as e:
                st.error(f"恢复失败: {str(e)}")

# 使用说明
with st.expander("📚 使用说明", expanded=False):
    st.markdown("""
    ### 系统功能说明
    
    **数据导入**
    - 支持Excel文件导入，自动识别客户和销售数据
    - 数据验证确保导入数据的完整性
    
    **价格查询**
    - 支持按客户、产品颜色、等级进行查询
    - 实时显示最新价格信息
    
    **价格趋势**
    - 分析客户产品价格的历史变化趋势
    - 可视化展示价格和数量变化
    
    **数据统计**
    - 全面的数据分析和可视化报表
    - 多维度业务指标分析
    
    **客户管理**
    - 查看和管理所有客户信息
    - 支持客户信息的编辑和更新
    
    **系统设置**
    - 数据库维护和系统状态监控
    - 数据统计和系统配置
    - 数据备份和恢复功能
    
    ### 数据库维护说明
    
    **重新初始化数据库**
    - 重建所有数据库表结构
    - 保留现有数据
    
    **优化数据库**
    - 清理数据库碎片，提高性能
    - 建议定期执行
    
    **清空所有数据**
    - 删除所有数据，恢复到初始状态
    - 操作不可逆，请谨慎使用
    """)
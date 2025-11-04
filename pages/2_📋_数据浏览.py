import streamlit as st
import pandas as pd
from core.database import get_connection

st.set_page_config(page_title="数据浏览", layout="wide")
st.title("📋 数据库数据浏览")

# 获取所有表的数据
def get_table_data(table_name):
    """获取指定表的所有数据"""
    with get_connection() as conn:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY id", conn)
            return df
        except Exception as e:
            st.error(f"读取表 {table_name} 时出错: {str(e)}")
            return pd.DataFrame()

# 获取表记录数
def get_table_count(table_name):
    """获取表的记录数"""
    with get_connection() as conn:
        try:
            count = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table_name}", conn).iloc[0]['count']
            return count
        except Exception as e:
            st.error(f"获取表 {table_name} 记录数失败: {str(e)}")
            return 0

# 获取所有表名
def get_table_names():
    """获取数据库中的所有表名"""
    with get_connection() as conn:
        try:
            tables = pd.read_sql_query("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """, conn)
            return tables['name'].tolist()
        except Exception as e:
            st.error(f"获取表名失败: {str(e)}")
            return []

# 获取数据库大小
def get_database_size():
    """获取数据库大小"""
    with get_connection() as conn:
        try:
            db_info = pd.read_sql_query("""
                SELECT 
                    page_count * page_size as size_bytes,
                    (page_count * page_size) / 1024.0 as size_kb
                FROM (
                    SELECT 
                        page_count, 
                        page_size
                    FROM pragma_page_count(), pragma_page_size()
                )
            """, conn)
            if not db_info.empty:
                return db_info.iloc[0]['size_kb']
            return 0
        except Exception as e:
            st.error(f"获取数据库大小失败: {str(e)}")
            return 0

# 获取表的列信息
def get_table_columns(table_name):
    """获取表的列信息"""
    with get_connection() as conn:
        try:
            columns = pd.read_sql_query(f"PRAGMA table_info({table_name})", conn)
            return columns
        except Exception as e:
            st.error(f"获取表 {table_name} 列信息失败: {str(e)}")
            return pd.DataFrame()

# 主界面
st.subheader("🗃️ 数据库表选择")

# 获取所有表名
table_names = get_table_names()

if not table_names:
    st.warning("数据库中暂无表")
else:
    # 表选择
    selected_table = st.selectbox("选择要查看的数据表", table_names)
    
    if selected_table:
        # 显示表结构信息
        st.subheader(f"📋 {selected_table} 表结构")
        columns_info = get_table_columns(selected_table)
        if not columns_info.empty:
            st.dataframe(columns_info[['name', 'type', 'notnull', 'dflt_value']].rename(
                columns={'name': '列名', 'type': '数据类型', 'notnull': '是否非空', 'dflt_value': '默认值'}
            ), width="stretch")
        
        # 获取表数据
        with st.spinner(f"正在加载 {selected_table} 表数据..."):
            table_data = get_table_data(selected_table)
        
        if not table_data.empty:
            # 表信息统计
            st.subheader(f"📊 {selected_table} 表信息")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总记录数", len(table_data))
            with col2:
                st.metric("列数", len(table_data.columns))
            with col3:
                st.metric("数据大小", f"{table_data.memory_usage(deep=True).sum() / 1024:.1f} KB")
            with col4:
                # 检查是否有时间字段
                time_cols = [col for col in table_data.columns if 'date' in col.lower() or 'time' in col.lower()]
                if time_cols:
                    latest_date = table_data[time_cols[0]].max()
                    st.metric("最新记录", str(latest_date)[:10])
                else:
                    # 检查是否有id字段
                    if 'id' in table_data.columns:
                        st.metric("主键范围", f"{table_data['id'].min()} - {table_data['id'].max()}")
                    else:
                        st.metric("数据状态", "正常")
            
            # 数据预览
            st.subheader("👀 数据预览")
            
            # 分页控制
            col1, col2, col3 = st.columns([.5, 4, .5])
            with col1:
                page_size = st.selectbox("每页显示行数", [50, 100, 200, 500], index=0)
            with col2:
                st.write("")  # 占位
            with col3:
                total_pages = max(1, (len(table_data) + page_size - 1) // page_size)
                page_number = st.number_input("", min_value=1, max_value=total_pages, value=1)
            
            # 计算分页
            start_idx = (page_number - 1) * page_size
            end_idx = start_idx + page_size
            page_data = table_data.iloc[start_idx:end_idx]
            
            # 显示数据
            st.dataframe(page_data, width="stretch")
            
            # 分页信息
            st.caption(f"第 {page_number} / {total_pages} 页` `第 {start_idx + 1} - {min(end_idx, len(table_data))} 行，共 {len(table_data)} 行")
            
            # 数据统计
            st.subheader("📈 数据统计")
            
            tab1, tab2, tab3 = st.tabs(["列信息", "数据类型", "数值统计"])
            
            with tab1:
                # 列信息
                col_info = []
                for col in table_data.columns:
                    col_info.append({
                        '列名': col,
                        '非空值数': table_data[col].count(),
                        '空值数': table_data[col].isnull().sum(),
                        '空值比例': f"{(table_data[col].isnull().sum() / len(table_data) * 100):.1f}%",
                        '唯一值数': table_data[col].nunique()
                    })
                col_info_df = pd.DataFrame(col_info)
                st.dataframe(col_info_df, width="stretch")
            
            with tab2:
                # 数据类型
                dtype_info = []
                for col in table_data.columns:
                    dtype = table_data[col].dtype
                    sample_value = table_data[col].iloc[0] if not table_data[col].empty else None
                    dtype_info.append({
                        '列名': col,
                        '数据类型': str(dtype),
                        '示例值': str(sample_value)[:50] if sample_value is not None else 'None'
                    })
                dtype_df = pd.DataFrame(dtype_info)
                st.dataframe(dtype_df, width="stretch")
            
            with tab3:
                # 数值列统计
                numeric_cols = table_data.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    numeric_stats = table_data[numeric_cols].describe()
                    st.dataframe(numeric_stats, width="stretch")
                else:
                    st.info("该表没有数值列")
            
            # 数据导出
            st.subheader("💾 数据导出")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 导出当前页
                page_csv = page_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 导出当前页(CSV)",
                    page_csv,
                    f"{selected_table}_page_{page_number}.csv",
                    "text/csv",
                    width="stretch"
                )
            
            with col2:
                # 导出整个表
                full_csv = table_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 导出整个表(CSV)",
                    full_csv,
                    f"{selected_table}_full.csv",
                    "text/csv",
                    width="stretch"
                )
            
            # 快速查询
            st.subheader("🔍 快速查询")
            
            query_col1, query_col2 = st.columns([3, 1])
            with query_col1:
                search_term = st.text_input("搜索关键词", placeholder="在所有列中搜索...")
            with query_col2:
                st.write("")  # 占位
                st.write("")  # 占位
                search_clicked = st.button("搜索", width="stretch")
            
            if search_clicked and search_term:
                # 在所有列中搜索
                search_results = table_data.copy()
                mask = pd.Series([False] * len(search_results))
                
                for col in search_results.columns:
                    if search_results[col].dtype == 'object':
                        col_mask = search_results[col].astype(str).str.contains(
                            search_term, case=False, na=False
                        )
                        mask = mask | col_mask
                
                search_results = search_results[mask]
                
                if not search_results.empty:
                    st.success(f"找到 {len(search_results)} 条匹配记录")
                    st.dataframe(search_results, width="stretch")
                    
                    # 导出搜索结果
                    search_csv = search_results.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 导出搜索结果(CSV)",
                        search_csv,
                        f"{selected_table}_search_results.csv",
                        "text/csv",
                        width="stretch"
                    )
                else:
                    st.warning("没有找到匹配的记录")
        
        else:
            st.warning(f"表 {selected_table} 中没有数据")
    
    # 数据库概览
    st.subheader("🗄️ 数据库概览")
    
    overview_col1, overview_col2 = st.columns(2)
    
    with overview_col1:
        st.write("**所有数据表:**")
        total_records = 0
        for table in table_names:
            count = get_table_count(table)
            total_records += count
            st.write(f"- {table}: {count} 条记录")
    
    with overview_col2:
        # 数据库大小信息
        db_size_kb = get_database_size()
        st.write("**数据库信息:**")
        st.write(f"- 总大小: {db_size_kb:.1f} KB")
        st.write(f"- 表数量: {len(table_names)}")
        st.write(f"- 总记录数: {total_records}")

# 使用说明
with st.expander("📚 使用说明", expanded=False):
    st.markdown("""
    ### 数据浏览功能说明
    
    **主要功能**
    - 📊 查看数据库中所有表的数据
    - 🔍 支持分页浏览和搜索
    - 📈 提供详细的数据统计信息
    - 💾 支持数据导出
    
    **表说明**
    - **customers**: 客户信息表
    - **sales_records**: 销售记录表  
    - **price_change_history**: 价格变更历史表
    
    **使用技巧**
    - 使用分页功能浏览大量数据
    - 利用搜索功能快速定位数据
    - 查看数据统计了解数据质量
    - 导出数据用于进一步分析
    
    **注意事项**
    - 大数据表建议使用分页功能
    - 导出整个表时请注意数据量
    - 搜索功能在所有文本列中进行
    
    ### 表结构说明
    
    **customers 表**
    - `id`: 主键，自增长
    - `customer_name`: 客户名称 (必需)
    - `finance_id`: 财务编号 (必需)
    - `sub_customer_name`: 子客户名称 (可选)
    - `region`: 区域信息 (可选)
    - `contact_person`: 联系人 (可选)
    - `phone`: 联系电话 (可选)
    - `created_date`: 创建时间
    - `updated_date`: 更新时间
    - `is_active`: 是否活跃
    
    **sales_records 表**
    - `id`: 主键，自增长
    - `customer_name`: 客户名称 (必需)
    - `finance_id`: 财务编号 (必需)
    - `sub_customer_name`: 子客户名称 (可选)
    - `year`: 交易年份 (必需)
    - `month`: 交易月份 (必需)
    - `day`: 交易日期 (必需)
    - `color`: 产品颜色 (必需)
    - `grade`: 产品等级 (可选)
    - `quantity`: 销售数量 (可选)
    - `unit_price`: 产品单价 (可选)
    - `amount`: 销售金额 (可选)
    - `ticket_number`: 票据号码 (可选)
    - `remark`: 交易备注 (可选)
    - `production_line`: 生产线信息 (可选)
    - `record_date`: 记录日期
    - `created_date`: 创建时间
    - `updated_date`: 更新时间
    
    **price_change_history 表**
    - `id`: 主键，自增长
    - `sales_record_id`: 关联的销售记录ID
    - `old_price`: 变更前的价格
    - `new_price`: 变更后的价格
    - `change_date`: 价格变更时间
    - `changed_by`: 变更操作人
    - `change_reason`: 变更原因
    """)
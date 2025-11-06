import streamlit as st
import pandas as pd
import os
from core.import_service import ImportService
from utils.file_utils import validate_excel_structure, preview_excel_data
from core.database import clear_database

st.logo(
    image='https://doc-logo.streamlit.app/~/+/media/5bbeb2aa8dae615df2081a396b47e30bb710e10dd2f4f3f2e7b06c81.png',
    icon_image='https://doc-logo.streamlit.app/~/+/media/5bbeb2aa8dae615df2081a396b47e30bb710e10dd2f4f3f2e7b06c81.png',
)

st.set_page_config(page_title="数据导入", layout="wide")
st.title("📥 Excel数据导入")

import_service = ImportService()

# 数据格式说明
with st.expander("📋 数据格式说明", expanded=True):
    st.markdown("""
    **Excel文件应包含以下列：**
    - ✅ **客户名称** (必需) - 大客户名称
    - ✅ **编号** (必需) - 财务唯一编号
    - ✅ **子客户名称** (可选) - 子客户名称
    - ✅ **年** (必需) - 交易年份
    - ✅ **月** (必需) - 交易月份
    - ✅ **日** (必需) - 交易日期
    - ✅ **产品名称** (必需) - 产品名称
    - ✅ **颜色** (必需) - 产品颜色
    - ⚠️ **等级** (可选) - 产品等级
    - ⚠️ **数量** (可选) - 销售数量
    - ⚠️ **单价** (可选) - 产品单价
    - ⚠️ **金额** (可选) - 销售金额
    - ⚠️ **票号** (可选) - 票据号码
    - ⚠️ **备注** (可选) - 交易备注
    - ⚠️ **生产线** (可选) - 生产线信息
    """)

uploaded_file = st.file_uploader("上传Excel文件", type=['xlsx', 'xls'])

if uploaded_file is not None:
    # 显示文件信息
    file_details = {
        "文件名": uploaded_file.name,
        "文件大小": f"{uploaded_file.size / 1024:.2f} KB"
    }
    st.write("📄 文件信息:", file_details)
    
    # 保存临时文件
    temp_path = "temp_upload.xlsx"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # 验证文件结构
    is_valid, message = validate_excel_structure(temp_path)
    if is_valid:
        st.success("✅ 文件结构验证通过")
        
        # 数据预览
        success, preview_df = preview_excel_data(temp_path, 5)
        if success:
            st.subheader("👀 数据预览 (前5行)")
            st.dataframe(preview_df, width="stretch")
        else:
            st.error(f"预览失败: {preview_df}")
    else:
        st.error(f"❌ 文件结构错误: {message}")
    
    # 操作按钮
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚀 开始导入", type="primary", width="stretch"):
            with st.spinner("正在导入数据..."):
                success, message = import_service.import_excel_data(temp_path, "user")
            
            if success:
                st.success(message)
                st.balloons()
            else:
                st.error(message)
    
    with col2:
        if st.button("🔄 重新验证", width="stretch"):
            st.rerun()
    
    with col3:
        if st.button("🗑️ 清空数据库", type="secondary", width="stretch"):
            if st.checkbox("确认清空所有数据？此操作不可恢复！"):
                clear_database()
                st.success("数据库已清空")
                st.rerun()
    
    # 清理临时文件
    if os.path.exists(temp_path):
        os.remove(temp_path)
else:
    st.info("👆 请上传Excel文件开始导入")
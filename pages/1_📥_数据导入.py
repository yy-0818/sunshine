import streamlit as st
import pandas as pd
import os
from core.import_service import ImportService
from utils.file_utils import validate_excel_structure, preview_excel_data
from core.database import get_database_status

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

def show_example_format():
    """显示表格格式示例"""
    with st.expander("📋 查看Excel表格格式要求", expanded=False):
        st.info("请确保Excel文件至少包含前3列（必填），其余列按需填写：")
        
        # 创建示例数据
        example_data = {
            "客户名称": ["衡阳张三", "衡阳张三"],
            "编号": [1, 1],
            "子客户名称": ["衡阳张三", "衡阳李四"],
            "年": [25, 25],
            "月": [1, 1],
            "日": [1, 1],
            "收款金额": ["", ""],
            "颜色": ["福迩家罗曼瓦290*420孔雀兰", "福迩家罗曼瓦290*420中国红"],
            "等级": ["优", "优"],
            "数量": [12800, 15000],
            "单价": [1.7, 1.8],
            "金额": [21760, 27000],
            "余额": ["", ""],
            "票号": ["0618YG049", "0619YG050"],
            "备注": ["", ""],
            "生产线": ["三线罗曼瓦", "三线罗曼瓦"],
            "部门": ["一期", "二期"],  # 新增部门列
            "区域": ["衡阳", "衡阳"],
            "联系人": ["张三", "李四"],
            "电话": ["13800000000", "13800000001"],
            "是否活跃": [1, 1]
        }
        
        example_df = pd.DataFrame(example_data)
        st.dataframe(example_df, width='stretch')
        
        # 添加格式要求说明
        st.markdown("""
        **📝 格式要求说明：**
        - 必填列：`客户名称`、`编号`、`备注（小客户名称）`
        - 新增`部门`列：用于记录所属部门（如：一期、二期等）
        - 其余列可为空；建议按需填写以便更完整分析
        - 列顺序可调整，但列名需一致；`票 号` 将自动识别为 `票号`
        - 日期请分别填入年、月、日列；缺失时系统将自动填充当前日期用于记录
        - 数值列（数量、单价、金额、收款金额、余额）可为空；若填写需为有效数字
        - `品牌` 将作为分析维度保留；`生产线`用于“一期/二期”分类分析
        """)

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
    # 显示数据库状态
    st.markdown("### 🗃️ 当前数据库状态")
    render_database_status()
    
    # 显示表格格式示例
    show_example_format()
    
    st.markdown("### ⚙️ 导入配置")
    
    # 策略展示
    st.markdown("#### 📋 导入策略选择")
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
        horizontal=True,
        key="strategy_selector"
    )
    
    # 替换确认
    replace_confirm = True
    if strategy == "replace":
        st.warning("""
        ⚠️ **完全覆盖模式警告**
        - 此操作会清空数据库中的所有现有数据
        - 操作不可恢复，请确保已备份重要数据
        - 导入完成后需要重新设置系统参数
        """)
        replace_confirm = st.checkbox("我已备份数据，并确认执行完全覆盖操作", value=False)
    
    # 文件上传区域
    st.markdown("#### 📤 文件上传")
    uploaded_file = st.file_uploader(
        "上传 Excel 文件", 
        type=['xlsx', 'xls'],
        help="请上传符合格式要求的Excel文件，支持 .xlsx 和 .xls 格式"
    )
    
    if not uploaded_file:
        st.info("👆 请上传Excel文件以开始导入流程")
        return
    
    # 临时保存文件
    temp_path = "temp_upload.xlsx"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    try:
        # 文件验证
        st.markdown("#### 🔍 文件验证")
        with st.status("正在验证文件格式...", expanded=True) as status:
            valid, msg = validate_excel_structure(temp_path)
            if not valid:
                st.error(f"❌ 文件验证失败：{msg}")
                status.update(label="文件验证失败", state="error", expanded=False)
                return
            else:
                st.success("✅ 文件格式验证通过")
                status.update(label="文件验证完成", state="complete", expanded=False)
        
        # 数据预览
        st.markdown("#### 👀 数据预览")
        ok, preview = preview_excel_data(temp_path, 5)
        if ok:
            st.success(f"成功读取数据，共 {len(preview)} 行记录")
            st.dataframe(preview, width='stretch')
            
            # 显示数据统计
            cols = st.columns(3)
            with cols[0]:
                st.metric("预览行数", len(preview))
            with cols[1]:
                st.metric("总列数", len(preview.columns))
            with cols[2]:
                st.metric("文件大小", f"{uploaded_file.size / 1024:.1f} KB")
        else:
            st.error("❌ 数据预览失败")
            return
        
        # 导入执行区域
        st.markdown("---")
        st.markdown("#### 🚀 执行导入")
        
        if strategy == "replace" and not replace_confirm:
            st.error("请先确认完全覆盖操作")
            return
            
        if st.button(
            "开始导入数据", 
            type="primary", 
            width='stretch',
            key="import_button"
        ):
            execute_import(temp_path, strategy, replace_confirm)
            
    except Exception as e:
        st.error(f"❌ 处理文件时发生错误：{str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    main()
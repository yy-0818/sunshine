# utils/file_utils.py
import pandas as pd
import warnings
from openpyxl import load_workbook

def validate_excel_structure(file_path):
    """验证Excel文件结构 - 适配新表头"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = load_workbook(file_path, data_only=True)
            sheet = wb.active
            
            # 获取表头
            headers = []
            for cell in sheet[1]:
                if cell.value is not None:
                    headers.append(str(cell.value).strip())
            
            # 必需的表头 - 根据新数据源调整
            required_headers = ['客户名称', '编号', '子客户名称', '年', '月', '日', '颜色', '等级', '数量', '单价', '金额', '备注', '票号']
            missing_headers = [h for h in required_headers if h not in headers]
            
            if missing_headers:
                return False, f"缺少必要的表头: {missing_headers}"
            
            return True, "文件结构正确"
        
    except Exception as e:
        return False, f"文件检查失败: {str(e)}"

def preview_excel_data(file_path, nrows=5):
    """预览Excel数据"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_excel(file_path, engine='openpyxl', nrows=nrows)
        return True, df
    except Exception as e:
        return False, f"无法读取文件: {str(e)}"
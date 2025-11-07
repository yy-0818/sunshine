import pandas as pd
import warnings
from openpyxl import load_workbook
from typing import Tuple, Dict, Any

def validate_excel_structure(file_path: str) -> Tuple[bool, str]:
    """验证Excel文件结构"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = load_workbook(file_path, data_only=True, read_only=True)
            sheet = wb.active
            
            # 获取表头
            headers = []
            for cell in sheet[1]:
                if cell.value is not None:
                    headers.append(str(cell.value).strip())
            
            wb.close()
            
            # 必需的表头
            required_headers = ['客户名称', '编号', '子客户名称', '年', '月', '日', '颜色', '等级', '数量', '单价', '金额', '备注']
            missing_headers = [h for h in required_headers if h not in headers]
            
            if missing_headers:
                return False, f"缺少必要的表头: {missing_headers}"
            
            return True, "文件结构正确"
        
    except Exception as e:
        return False, f"文件检查失败: {str(e)}"

def preview_excel_data(file_path: str, nrows: int = 5) -> Tuple[bool, pd.DataFrame]:
    """预览Excel数据"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.read_excel(file_path, engine='openpyxl', nrows=nrows)
        return True, df
    except Exception as e:
        return False, f"无法读取文件: {str(e)}"

def get_excel_file_info(file_path: str) -> Dict[str, Any]:
    """获取Excel文件的详细信息"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = load_workbook(file_path, data_only=True, read_only=True)
            sheet = wb.active
            
            # 获取表头
            headers = []
            for cell in sheet[1]:
                if cell.value is not None:
                    headers.append(str(cell.value).strip())
            
            # 统计行数（不包括表头）
            row_count = 0
            for row_idx, row in enumerate(sheet.iter_rows(min_row=2, max_row=100000), 2):
                # 检查第一列是否有数据
                if row[0].value is not None:
                    row_count += 1
                else:
                    break
            
            wb.close()
            
            # 读取数据获取更多统计信息
            df = pd.read_excel(file_path, engine='openpyxl', nrows=1000)  # 只读前1000行用于统计
            
            info = {
                "headers": headers,
                "row_count": row_count,
                "column_count": len(headers),
                "required_headers_present": all(h in headers for h in ['客户名称', '编号', '子客户名称', '年', '月', '日', '颜色', '等级', '数量', '单价', '金额', '备注']),
                "sample_data_available": len(df) > 0 if not df.empty else False
            }
            
            # 如果数据不为空，添加更多统计信息
            if not df.empty:
                info.update({
                    "customer_count": df['客户名称'].nunique() if '客户名称' in df.columns else 0,
                    "product_count": df['产品名称'].nunique() if '产品名称' in df.columns else 0,
                    "color_count": df['颜色'].nunique() if '颜色' in df.columns else 0,
                    "has_numeric_data": any(col in df.columns for col in ['数量', '单价', '金额'])
                })
            
            return info
            
    except Exception as e:
        return {"error": f"获取文件信息失败: {str(e)}"}

def get_import_strategy_description(strategy: str) -> Dict[str, Any]:
    """获取导入策略的详细说明"""
    descriptions = {
        "update": {
            "name": "智能更新",
            "description": "更新重复数据，添加新数据，保持数据同步",
            "icon": "📝",
            "recommended": True,
            "details": [
                "✅ 更新重复的销售记录",
                "✅ 添加新的销售记录",  
                "✅ 保持客户信息同步更新",
                "💡 **适用场景**: 日常数据更新、修正错误数据"
            ]
        },
        "append": {
            "name": "仅新增", 
            "description": "只导入不存在的新数据，不修改已有记录",
            "icon": "➕",
            "recommended": False,
            "details": [
                "✅ 只导入不存在的新数据",
                "❌ 不修改任何已有记录", 
                "💡 **适用场景**: 补充历史数据、避免数据冲突"
            ]
        },
        "replace": {
            "name": "完全替换",
            "description": "清空所有数据后重新导入完整数据集", 
            "icon": "🔄",
            "recommended": False,
            "details": [
                "⚠️ 清空所有现有数据",
                "⚠️ 重新导入完整数据集",
                "💡 **适用场景**: 数据重构、重大结构调整"
            ]
        }
    }
    return descriptions.get(strategy, descriptions["update"])

def validate_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """验证数据质量"""
    issues = []
    warnings = []
    
    # 检查必需字段的空值
    required_fields = ['客户名称', '编号']
    for field in required_fields:
        if field in df.columns:
            null_count = df[field].isnull().sum()
            if null_count > 0:
                issues.append(f"字段 '{field}' 有 {null_count} 个空值")
    
    # 检查数值字段的有效性
    numeric_fields = ['数量', '单价', '金额']
    for field in numeric_fields:
        if field in df.columns:
            # # 检查负值
            # negative_count = (df[field] < 0).sum()
            # if negative_count > 0:
            #     warnings.append(f"字段 '{field}' 有 {negative_count} 个负值")
            
            # 检查异常大值（假设大于100万为异常）
            large_value_count = (df[field] > 1000000).sum()
            if large_value_count > 0:
                warnings.append(f"字段 '{field}' 有 {large_value_count} 个异常大值")
    
    # 检查日期字段的有效性
    date_fields = ['年', '月', '日']
    for field in date_fields:
        if field in df.columns:
            invalid_count = df[field].isnull().sum()
            if invalid_count > 0:
                warnings.append(f"字段 '{field}' 有 {invalid_count} 个无效值")
    
    return {
        "has_issues": len(issues) > 0,
        "has_warnings": len(warnings) > 0,
        "issues": issues,
        "warnings": warnings,
        "total_records": len(df),
        "valid_records": len(df) - len(issues)
    }

def get_recommended_strategy(file_info: Dict[str, Any], db_status: Dict[str, Any]) -> str:
    """根据文件信息和数据库状态推荐导入策略"""
    
    # 如果数据库为空，推荐替换模式
    if db_status.get('sales_records_count', 0) == 0:
        return "replace"
    
    # 如果文件包含大量数据且数据库已有数据，推荐更新模式
    if file_info.get('row_count', 0) > 1000 and db_status.get('sales_records_count', 0) > 0:
        return "update"
    
    # 如果文件数据量较小，推荐追加模式
    if file_info.get('row_count', 0) < 100:
        return "append"
    
    # 默认推荐更新模式
    return "update"
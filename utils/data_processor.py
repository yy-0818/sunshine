import pandas as pd
import numpy as np
import re

def process_debt_excel_data(df, department_name=""):
    """
    处理欠款Excel数据
    统一财务编号格式：将点(.)替换为短横线(-)
    返回统一格式的数据，包含部门信息
    """
    data = []
    
    for i in range(len(df)):
        # 跳过空行
        if pd.isna(df.iloc[i, 0]):
            continue
            
        customer_code = str(df.iloc[i, 0]).strip()
        
        # 只处理以2203开头的有效行
        if customer_code.startswith('2203'):
            # 统一财务编号格式：将点替换为短横线
            finance_id = clean_finance_id(customer_code)
            
            # 确保金额字段是数值类型
            try:
                debt_2023 = float(df.iloc[i, 2]) if pd.notna(df.iloc[i, 2]) else 0.0
            except (ValueError, TypeError):
                debt_2023 = 0.0
                
            try:
                debt_2024 = float(df.iloc[i, 5]) if pd.notna(df.iloc[i, 5]) else 0.0
            except (ValueError, TypeError):
                debt_2024 = 0.0
                
            try:
                debt_2025 = float(df.iloc[i, 8]) if pd.notna(df.iloc[i, 8]) else 0.0
            except (ValueError, TypeError):
                debt_2025 = 0.0
            
            row_data = {
                'finance_id': finance_id,
                'customer_name': str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else f"未知客户_{finance_id}",
                'department': department_name,
                'debt_2023': debt_2023,
                'debt_2024': debt_2024,
                'debt_2025': debt_2025,
            }
            data.append(row_data)
    
    result_df = pd.DataFrame(data)
    
    if len(result_df) > 0:
        print(f"成功处理 {len(result_df)} 条欠款记录")
    else:
        print("未找到有效的欠款记录")
    
    return result_df

def clean_finance_id(finance_id):
    """
    清理财务编号，统一格式
    将点(.)替换为短横线(-)，并移除2203前缀
    """
    code_str = str(finance_id).strip()
    
    # 移除2203前缀
    if code_str.startswith('2203'):
        code_str = code_str[4:]
        if code_str.startswith('.') or code_str.startswith('-'):
            code_str = code_str[1:]
    
    # 统一格式：将点替换为短横线
    code_str = code_str.replace('.', '-')
    
    # 确保格式正确：如果有多个短横线，合并为一个
    code_str = re.sub(r'-+', '-', code_str)
    
    return code_str

def validate_debt_data(df):
    """验证欠款数据的完整性"""
    issues = []
    
    if df.empty:
        issues.append("数据为空")
        return issues
    
    required_columns = ['finance_id', 'customer_name', 'department', 'debt_2023', 'debt_2024', 'debt_2025']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        issues.append(f"缺少必要的列: {missing_columns}")
    
    if 'finance_id' in df.columns and 'department' in df.columns:
        for dept in df['department'].unique():
            dept_df = df[df['department'] == dept]
            duplicate_ids = dept_df[dept_df.duplicated('finance_id', keep=False)]
            if not duplicate_ids.empty:
                issues.append(f"部门 {dept} 发现重复的财务编号: {duplicate_ids['finance_id'].unique().tolist()}")
    
    amount_columns = ['debt_2023', 'debt_2024', 'debt_2025']
    for col in amount_columns:
        if col in df.columns:
            invalid_amounts = df[~df[col].apply(lambda x: isinstance(x, (int, float)) or pd.isna(x))]
            if not invalid_amounts.empty:
                issues.append(f"列 {col} 包含非数值数据")
    
    if 'department' in df.columns:
        valid_departments = ['一期', '二期']
        invalid_depts = df[~df['department'].isin(valid_departments)]
        if not invalid_depts.empty:
            issues.append(f"发现无效的部门名称: {invalid_depts['department'].unique().tolist()}")
    
    return issues

def get_sample_data(department="二期"):
    """获取示例数据格式"""
    sample_data = {
        '客户代码': ['2203.10001', '2203.10002', '220310003'],
        '客户名称': ['示例客户A', '示例客户B', '示例客户C'],
        '2023年欠款金额': [5000.0, 0.0, 15000.0],
        '2024年欠款金额': [3000.0, 0.0, 12000.0],
        '2025年欠款金额': [0.0, 8000.0, 18000.0]
    }
    df = pd.DataFrame(sample_data)
    
    processed_data = []
    for i in range(len(df)):
        finance_id = clean_finance_id(df.iloc[i, 0])
        processed_data.append({
            'finance_id': finance_id,
            'customer_name': df.iloc[i, 1],
            'department': department,
            'debt_2023': df.iloc[i, 2],
            'debt_2024': df.iloc[i, 3],
            'debt_2025': df.iloc[i, 4]
        })
    
    return pd.DataFrame(processed_data)
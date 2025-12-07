import pandas as pd
import numpy as np
import re

def process_debt_excel_data(df, department_name=""):
    """
    处理欠款Excel数据
    统一财务编号格式：将点(.)替换为短横线(-)
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
                'finance_id': finance_id,  # 使用统一格式的财务编号
                'customer_name': str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else f"未知客户_{finance_id}",
                'debt_2023': debt_2023,
                'debt_2024': debt_2024,
                'debt_2025': debt_2025,
                'data_source': department_name
            }
            data.append(row_data)
    
    result_df = pd.DataFrame(data)
    
    # 记录处理日志
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
        # 移除可能的分隔符（点、短横线）
        if code_str.startswith('.') or code_str.startswith('-'):
            code_str = code_str[1:]
    
    # 统一格式：将点替换为短横线
    code_str = code_str.replace('.', '-')
    
    return code_str

def validate_debt_data(df):
    """验证欠款数据的完整性"""
    issues = []
    
    if df.empty:
        issues.append("数据为空")
        return issues
    
    # 检查必要的列
    required_columns = ['finance_id', 'customer_name', 'debt_2023', 'debt_2024', 'debt_2025']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        issues.append(f"缺少必要的列: {missing_columns}")
    
    # 检查财务编号唯一性
    duplicate_ids = df[df.duplicated('finance_id', keep=False)]
    if not duplicate_ids.empty:
        issues.append(f"发现重复的财务编号: {duplicate_ids['finance_id'].unique().tolist()}")
    
    # 检查金额数据的有效性
    amount_columns = ['debt_2023', 'debt_2024', 'debt_2025']
    for col in amount_columns:
        if col in df.columns:
            invalid_amounts = df[~df[col].apply(lambda x: isinstance(x, (int, float)) or pd.isna(x))]
            if not invalid_amounts.empty:
                issues.append(f"列 {col} 包含非数值数据")
    
    return issues

def get_sample_data():
    """获取示例数据格式"""
    sample_data = {
        '客户代码': ['2203.10001', '2203.10002', '220310003'],
        '客户名称': ['示例客户A', '示例客户B', '示例客户C'],
        '2023年欠款金额': [5000.0, 0.0, 15000.0],
        '2024年欠款金额': [3000.0, 0.0, 12000.0],
        '2025年欠款金额': [0.0, 8000.0, 18000.0]
    }
    return pd.DataFrame(sample_data)
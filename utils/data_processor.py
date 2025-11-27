import pandas as pd
import numpy as np
import re

def process_debt_excel_data(df, department_name=""):
    """
    处理欠款Excel数据
    支持多种格式的客户代码处理
    """
    data = []
    
    for i in range(len(df)):
        # 跳过空行
        if pd.isna(df.iloc[i, 0]):
            continue
            
        customer_code = str(df.iloc[i, 0]).strip()
        
        # 只处理以2203开头的有效行
        if customer_code.startswith('2203'):
            # 多种方式处理客户代码
            processed_code = clean_customer_code(customer_code)
            
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
                '客户代码': processed_code,
                '客户名称': str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else f"未知客户_{processed_code}",
                '2023欠款': debt_2023,
                '2024欠款': debt_2024,
                '2025欠款': debt_2025,
                '数据来源': department_name
            }
            data.append(row_data)
    
    result_df = pd.DataFrame(data)
    
    # 记录处理日志
    if len(result_df) > 0:
        print(f"成功处理 {len(result_df)} 条欠款记录")
    else:
        print("未找到有效的欠款记录")
    
    return result_df

def clean_customer_code(customer_code):
    """清理客户代码，移除2203前缀"""
    code_str = str(customer_code).strip()
    
    # 方法1: 直接替换 '2203.'
    if '2203.' in code_str:
        return code_str.replace('2203.', '')
    
    # 方法2: 移除前4个字符 '2203'
    elif code_str.startswith('2203'):
        return code_str[4:]
    
    # 方法3: 使用正则表达式移除2203前缀
    elif re.match(r'^2203[\.\-\s]?', code_str):
        return re.sub(r'^2203[\.\-\s]?', '', code_str)
    
    # 如果都不匹配，返回原值
    else:
        return code_str

def validate_debt_data(df):
    """验证欠款数据的完整性"""
    issues = []
    
    if df.empty:
        issues.append("数据为空")
        return issues
    
    # 检查必要的列
    required_columns = ['客户代码', '客户名称', '2023欠款', '2024欠款', '2025欠款']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        issues.append(f"缺少必要的列: {missing_columns}")
    
    # 检查客户代码唯一性
    duplicate_codes = df[df.duplicated('客户代码', keep=False)]
    if not duplicate_codes.empty:
        issues.append(f"发现重复的客户代码: {duplicate_codes['客户代码'].unique().tolist()}")
    
    # 检查金额数据的有效性
    amount_columns = ['2023欠款', '2024欠款', '2025欠款']
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
        '2023欠款': [5000.0, 0.0, 15000.0],
        '2024欠款': [3000.0, 0.0, 12000.0],
        '2025欠款': [0.0, 8000.0, 18000.0]
    }
    return pd.DataFrame(sample_data)
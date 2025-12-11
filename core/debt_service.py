import pandas as pd
import numpy as np
from core.database import get_connection, import_debt_data, get_debt_by_department

class DebtAnalysisService:
    def __init__(self):
        pass
    
    def import_debt_data(self, df, department):
        """
        导入欠款数据到统一欠款表
        Args:
            df: 处理后的欠款数据
            department: 部门名称 ('古建' 或 '陶瓷')
        """
        if df.empty:
            return 0, 0
        
        success_count, error_count = import_debt_data(df, department)
        return success_count, error_count
    
    def get_debt_data(self, department=None):
        """
        获取欠款数据
        Args:
            department: None-全部部门, '古建', '陶瓷'
        """
        return get_debt_by_department(department)
    
    def analyze_debt_data(self, df, department=None):
        """
        分析欠款数据
        Args:
            df: 欠款数据DataFrame
            department: 部门名称
        """
        if df.empty:
            return pd.DataFrame()
        
        df_clean = df.copy()
        
        # 确保列名正确
        column_mapping = {
            'debt_2023': '2023欠款',
            'debt_2024': '2024欠款',
            'debt_2025': '2025欠款',
            'finance_id': '财务编号',
            'customer_name': '客户名称'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df_clean.columns and new_col not in df_clean.columns:
                df_clean = df_clean.rename(columns={old_col: new_col})
        
        # 添加部门信息
        if department:
            df_clean['所属部门'] = department
        
        # 客户分类函数
        def classify_customer(row):
            # 确保金额是数值类型
            debt_2023 = float(row.get('2023欠款', 0)) if pd.notna(row.get('2023欠款')) else 0
            debt_2024 = float(row.get('2024欠款', 0)) if pd.notna(row.get('2024欠款')) else 0
            debt_2025 = float(row.get('2025欠款', 0)) if pd.notna(row.get('2025欠款')) else 0
            
            if debt_2023 == 0 and debt_2024 == 0 and debt_2025 == 0:
                return '优质客户(无欠款)'
            elif debt_2025 == 0 and (debt_2023 > 0 or debt_2024 > 0):
                return '已结清客户'
            elif debt_2023 == 0 and debt_2024 == 0 and debt_2025 > 0:
                return '新增欠款客户'
            elif debt_2023 > 0 and debt_2024 > 0 and debt_2025 > 0:
                return '持续欠款客户'
            else:
                return '波动客户'
        
        # 应用分类
        df_clean['客户类型'] = df_clean.apply(classify_customer, axis=1)
        
        # 计算变化
        if '2023欠款' in df_clean.columns and '2024欠款' in df_clean.columns:
            df_clean['23-24变化'] = df_clean['2024欠款'] - df_clean['2023欠款']
        
        if '2024欠款' in df_clean.columns and '2025欠款' in df_clean.columns:
            df_clean['24-25变化'] = df_clean['2025欠款'] - df_clean['2024欠款']
        
        if '2023欠款' in df_clean.columns and '2025欠款' in df_clean.columns:
            df_clean['23-25总变化'] = df_clean['2025欠款'] - df_clean['2023欠款']
        
        # 详细分类
        def classify_debt_trend(row):
            if row['客户类型'] != '持续欠款客户':
                return row['客户类型']
            
            total_change = row.get('23-25总变化', 0)
            if total_change < -10000:
                return '持续欠款-显著减少'
            elif total_change > 10000:
                return '持续欠款-显著增加'
            elif abs(total_change) <= 1000:
                return '持续欠款-稳定'
            else:
                return '持续欠款-波动'
        
        df_clean['详细分类'] = df_clean.apply(classify_debt_trend, axis=1)
        
        return df_clean
    
    def get_classification_explanation(self):
        """获取分类标准说明"""
        return {
            '客户类型': {
                '优质客户(无欠款)': '三年欠款均为0的客户',
                '已结清客户': '从有欠款变为0的客户',
                '新增欠款客户': '从0变为有欠款的客户', 
                '持续欠款客户': '三年都有欠款的客户',
                '波动客户': '其他欠款变化情况的客户'
            }
        }
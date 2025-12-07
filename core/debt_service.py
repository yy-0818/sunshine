import pandas as pd
import numpy as np
from core.database import get_connection
import sqlite3

class DebtAnalysisService:
    def __init__(self):
        pass
    
    def import_department1_debt(self, df):
        """导入古建欠款数据 - 简化版本"""
        success_count = 0
        error_count = 0
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            for _, row in df.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO department1_debt 
                        (finance_id, customer_name, debt_2023, debt_2024, debt_2025)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        str(row['finance_id']),
                        str(row['customer_name']),
                        float(row['debt_2023']),
                        float(row['debt_2024']),
                        float(row['debt_2025'])
                    ))
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"导入失败 {row.get('finance_id', '未知')}: {e}")
        
        return success_count, error_count
    
    def import_department2_debt(self, df):
        """导入陶瓷欠款数据 - 简化版本"""
        success_count = 0
        error_count = 0
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            for _, row in df.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO department2_debt 
                        (finance_id, customer_name, debt_2023, debt_2024, debt_2025)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        str(row['finance_id']),
                        str(row['customer_name']),
                        float(row['debt_2023']),
                        float(row['debt_2024']),
                        float(row['debt_2025'])
                    ))
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"导入失败 {row.get('finance_id', '未知')}: {e}")
        
        return success_count, error_count
    
    def get_department1_debt(self):
        """获取古建欠款数据"""
        with get_connection() as conn:
            df = pd.read_sql('''
                SELECT finance_id as "客户代码", 
                       customer_name as "客户名称", 
                       debt_2023 as "2023欠款", 
                       debt_2024 as "2024欠款", 
                       debt_2025 as "2025欠款"
                FROM department1_debt
            ''', conn)
            return df
    
    def get_department2_debt(self):
        """获取陶瓷欠款数据"""
        with get_connection() as conn:
            df = pd.read_sql('''
                SELECT finance_id as "客户代码", 
                       customer_name as "客户名称", 
                       debt_2023 as "2023欠款", 
                       debt_2024 as "2024欠款", 
                       debt_2025 as "2025欠款"
                FROM department2_debt
            ''', conn)
            return df
    
    def analyze_debt_data(self, df):
        """分析欠款数据（基于古建客户欠款分析逻辑）"""
        df_clean = df.copy()
        
        # 检查必要的列是否存在
        required_columns = ['2023欠款', '2024欠款', '2025欠款']
        missing_columns = [col for col in required_columns if col not in df_clean.columns]
        
        if missing_columns:
            # 尝试使用英文列名
            english_mapping = {
                'debt_2023': '2023欠款',
                'debt_2024': '2024欠款', 
                'debt_2025': '2025欠款',
                'finance_id': '客户代码',
                'customer_name': '客户名称'
            }
            
            for eng_col, chn_col in english_mapping.items():
                if eng_col in df_clean.columns and chn_col not in df_clean.columns:
                    df_clean = df_clean.rename(columns={eng_col: chn_col})
            
            # 再次检查缺失列
            missing_columns = [col for col in required_columns if col not in df_clean.columns]
            if missing_columns:
                raise KeyError(f"缺少必要的列: {missing_columns}。可用列: {list(df_clean.columns)}")
        
        # 客户分类函数
        def classify_customer(row):
            # 确保金额是数值类型
            debt_2023 = float(row['2023欠款']) if pd.notna(row['2023欠款']) else 0
            debt_2024 = float(row['2024欠款']) if pd.notna(row['2024欠款']) else 0
            debt_2025 = float(row['2025欠款']) if pd.notna(row['2025欠款']) else 0
            
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
        
        df_clean['客户类型'] = df_clean.apply(classify_customer, axis=1)
        
        # 计算变化
        df_clean['23-24变化'] = df_clean['2024欠款'] - df_clean['2023欠款']
        df_clean['24-25变化'] = df_clean['2025欠款'] - df_clean['2024欠款']
        df_clean['23-25总变化'] = df_clean['2025欠款'] - df_clean['2023欠款']
        
        # 详细分类
        def classify_debt_trend(row):
            if row['客户类型'] != '持续欠款客户':
                return row['客户类型']
            
            total_change = row['23-25总变化']
            if total_change < -10000:
                return '持续欠款-显著减少'
            elif total_change > 10000:
                return '持续欠款-显著增加'
            elif abs(total_change) <= 1000:
                return '持续欠款-稳定'
            else:
                return '持续欠款-波动'
        
        df_clean['详细分类'] = df_clean.apply(classify_debt_trend, axis=1)
        
        # 坏账风险分析
        def identify_bad_debt_risk(row):
            current_debt = float(row['2025欠款']) if pd.notna(row['2025欠款']) else 0
            
            if current_debt == 0:
                return '无风险'
            if row['详细分类'] == '持续欠款-稳定' and current_debt > 50000:
                return '高风险坏账'
            elif row['详细分类'] == '持续欠款-稳定' and current_debt > 10000:
                return '中风险坏账'
            elif '显著增加' in row['详细分类']:
                return '关注类(欠款增加)'
            else:
                return '正常跟踪'
        
        df_clean['坏账风险'] = df_clean.apply(identify_bad_debt_risk, axis=1)
        
        # 客户价值等级
        def customer_value_tier(row):
            current_debt = float(row['2025欠款']) if pd.notna(row['2025欠款']) else 0
            
            if row['客户类型'] == '优质客户(无欠款)':
                return 'A级-优质客户'
            elif row['客户类型'] == '已结清客户':
                return 'B级-良好客户'
            elif current_debt == 0:
                return 'B级-良好客户'
            elif current_debt <= 10000:
                return 'C级-小额欠款'
            elif current_debt <= 50000:
                if row['坏账风险'] in ['高风险坏账', '中风险坏账']:
                    return 'D级-风险客户'
                else:
                    return 'C级-中等欠款'
            else:
                if row['坏账风险'] in ['高风险坏账', '中风险坏账']:
                    return 'E级-高风险客户'
                else:
                    return 'D级-大额欠款'
        
        df_clean['客户价值等级'] = df_clean.apply(customer_value_tier, axis=1)
        
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
            },
            '坏账风险': {
                '无风险': '当前无欠款的客户',
                '高风险坏账': '欠款大于5万且多年无变化的客户',
                '中风险坏账': '欠款1-5万且多年无变化的客户',
                '关注类(欠款增加)': '欠款持续显著增加的客户',
                '正常跟踪': '其他有欠款但风险可控的客户'
            },
            '客户价值等级': {
                'A级-优质客户': '无欠款优质客户',
                'B级-良好客户': '已结清或无欠款客户',
                'C级-小额欠款': '欠款1万以下的客户',
                'C级-中等欠款': '欠款1-5万且风险可控的客户',
                'D级-风险客户': '欠款1-5万且有风险的客户',
                'D级-大额欠款': '欠款5万以上但风险可控的客户', 
                'E级-高风险客户': '欠款5万以上且有风险的客户'
            }
        }
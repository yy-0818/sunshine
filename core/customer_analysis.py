import pandas as pd
import numpy as np
from core.database import get_connection
from datetime import datetime, timedelta

class SalesDebtIntegrationService:
    def __init__(self):
        pass
    
    def get_customer_sales_summary(self, year=25):
        """
        获取客户销售数据汇总
        Args:
            year: 年份，如25表示2025年
        """
        with get_connection() as conn:
            query = f'''
                SELECT 
                    finance_id,
                    customer_name,
                    sub_customer_name,
                    SUM(quantity) as total_quantity,
                    SUM(amount) as total_amount,
                    COUNT(DISTINCT product_name) as unique_products,
                    COUNT(DISTINCT production_line) as production_lines,
                    MAX(date('20{year:02d}-' || substr('00' || month, -2) || '-' || substr('00' || day, -2))) as last_sale_date,
                    COUNT(*) as transaction_count
                FROM sales_records
                WHERE year = ?
                GROUP BY finance_id, customer_name, sub_customer_name
            '''
            df = pd.read_sql(query, conn, params=(year,))
            
            # 计算活跃度指标
            if not df.empty and 'last_sale_date' in df.columns:
                df['last_sale_date'] = pd.to_datetime(df['last_sale_date'], errors='coerce')
                current_date = pd.Timestamp.now()
                df['days_since_last_sale'] = (current_date - df['last_sale_date']).dt.days
                
                # 客户活跃度分类
                def classify_activity(days):
                    if pd.isna(days):
                        return '无销售记录'
                    elif days <= 30:
                        return '活跃(30天内)'
                    elif days <= 90:
                        return '一般活跃(90天内)'
                    elif days <= 180:
                        return '低活跃(180天内)'
                    else:
                        return '休眠客户'
                
                df['销售活跃度'] = df['days_since_last_sale'].apply(classify_activity)
            
            return df
    
    def get_customer_debt_summary(self, department=None):
        """
        获取客户欠款数据汇总
        Args:
            department: None-全部部门, '古建', '陶瓷'
        """
        with get_connection() as conn:
            queries = []
            
            if department in [None, '古建']:
                queries.append('''
                    SELECT 
                        finance_id,
                        customer_name,
                        '古建' as department,
                        debt_2023,
                        debt_2024,
                        debt_2025,
                        CASE 
                            WHEN debt_2023 > 0 AND debt_2024 > 0 AND debt_2025 > 0 THEN '持续欠款'
                            WHEN debt_2023 = 0 AND debt_2024 = 0 AND debt_2025 > 0 THEN '新增欠款'
                            WHEN debt_2023 > 0 AND debt_2024 = 0 AND debt_2025 = 0 THEN '已结清'
                            WHEN debt_2023 = 0 AND debt_2024 = 0 AND debt_2025 = 0 THEN '无欠款'
                            ELSE '波动欠款'
                        END as debt_trend
                    FROM department1_debt
                ''')
            
            if department in [None, '陶瓷']:
                queries.append('''
                    SELECT 
                        finance_id,
                        customer_name,
                        '陶瓷' as department,
                        debt_2023,
                        debt_2024,
                        debt_2025,
                        CASE 
                            WHEN debt_2023 > 0 AND debt_2024 > 0 AND debt_2025 > 0 THEN '持续欠款'
                            WHEN debt_2023 = 0 AND debt_2024 = 0 AND debt_2025 > 0 THEN '新增欠款'
                            WHEN debt_2023 > 0 AND debt_2024 = 0 AND debt_2025 = 0 THEN '已结清'
                            WHEN debt_2023 = 0 AND debt_2024 = 0 AND debt_2025 = 0 THEN '无欠款'
                            ELSE '波动欠款'
                        END as debt_trend
                    FROM department2_debt
                ''')
            
            if not queries:
                return pd.DataFrame()
            
            query = " UNION ALL ".join(queries)
            df = pd.read_sql(query, conn)
            return df
    
    def get_integrated_customer_analysis(self, current_year=25):
        """
        整合销售与欠款数据进行分析
        """
        # 获取销售数据
        sales_df = self.get_customer_sales_summary(current_year)
        
        # 获取欠款数据
        debt_df = self.get_customer_debt_summary()
        
        if sales_df.empty and debt_df.empty:
            return pd.DataFrame()
        
        # 合并数据 - 基于 finance_id
        if not sales_df.empty:
            merged_df = sales_df.copy()
            if not debt_df.empty:
                # 按 finance_id 合并欠款数据
                merged_df = pd.merge(
                    merged_df, 
                    debt_df, 
                    on='finance_id', 
                    how='left',
                    suffixes=('_sales', '_debt')
                )
        else:
            merged_df = debt_df.copy()
        
        # 填充缺失值
        numeric_cols = ['debt_2023', 'debt_2024', 'debt_2025', 'total_amount', 'total_quantity']
        for col in numeric_cols:
            if col in merged_df.columns:
                merged_df[col] = merged_df[col].fillna(0)
        
        # 计算欠销比
        if 'total_amount' in merged_df.columns and 'debt_2025' in merged_df.columns:
            merged_df['欠销比'] = merged_df.apply(
                lambda row: row['debt_2025'] / row['total_amount'] if row['total_amount'] > 0 else 0,
                axis=1
            )
        
        # 客户综合分类
        def integrated_classification(row):
            # 获取数据
            total_sales = row.get('total_amount', 0)
            debt_2025 = row.get('debt_2025', 0)
            debt_trend = row.get('debt_trend', '')
            activity = row.get('销售活跃度', '无销售记录')
            
            # 1. 无欠款客户
            if debt_2025 == 0:
                if total_sales == 0:
                    return 'D-无销售无欠款'
                elif total_sales > 50000:
                    if activity in ['活跃(30天内)', '一般活跃(90天内)']:
                        return 'A-优质大客户'
                    else:
                        return 'B-大额休眠客户'
                elif total_sales > 10000:
                    if activity in ['活跃(30天内)', '一般活跃(90天内)']:
                        return 'A-优质活跃客户'
                    else:
                        return 'B-一般客户'
                else:
                    return 'C-小额客户'
            
            # 2. 有欠款客户
            else:
                if total_sales == 0:
                    return 'E-纯欠款客户'
                
                debt_ratio = row.get('欠销比', 0)
                
                if debt_ratio < 0.2:  # 欠款占销售额小于20%
                    if activity == '活跃(30天内)':
                        return 'B1-低风险活跃欠款'
                    else:
                        return 'B2-低风险欠款'
                elif debt_ratio < 0.5:  # 20%-50%
                    if debt_trend == '持续欠款':
                        return 'C1-中风险持续欠款'
                    else:
                        return 'C2-中风险欠款'
                else:  # 超过50%
                    if debt_trend == '持续欠款':
                        return 'D1-高风险持续欠款'
                    else:
                        return 'D2-高风险欠款'
        
        if not merged_df.empty:
            merged_df['客户综合等级'] = merged_df.apply(integrated_classification, axis=1)
            
            # 计算风险评分（简化版）
            def calculate_risk_score(row):
                score = 100
                
                # 欠款因素
                debt_2025 = row.get('debt_2025', 0)
                if debt_2025 > 50000:
                    score -= 30
                elif debt_2025 > 10000:
                    score -= 20
                elif debt_2025 > 0:
                    score -= 10
                
                # 销售活跃度
                activity = row.get('销售活跃度', '无销售记录')
                if activity == '休眠客户':
                    score -= 15
                elif activity == '无销售记录':
                    score -= 25
                
                # 欠销比
                debt_ratio = row.get('欠销比', 0)
                if debt_ratio > 0.5:
                    score -= 25
                elif debt_ratio > 0.2:
                    score -= 15
                
                # 持续欠款
                if row.get('debt_trend', '') == '持续欠款':
                    score -= 10
                
                return max(0, min(100, score))
            
            merged_df['风险评分'] = merged_df.apply(calculate_risk_score, axis=1)
            
            # 风险等级分类
            def risk_classification(score):
                if score >= 80:
                    return '低风险'
                elif score >= 60:
                    return '较低风险'
                elif score >= 40:
                    return '中等风险'
                elif score >= 20:
                    return '较高风险'
                else:
                    return '高风险'
            
            merged_df['风险等级'] = merged_df['风险评分'].apply(risk_classification)
        
        # 重命名列以显示中文
        column_mapping = {
            'finance_id': '财务编号',
            'customer_name_sales': '客户名称',
            'customer_name_debt': '欠款客户名称',
            'sub_customer_name': '子客户名称',
            'total_amount': '总销售额',
            'total_quantity': '总销售量',
            'unique_products': '产品种类数',
            'production_lines': '生产线数',
            'transaction_count': '交易次数',
            'last_sale_date': '最后销售日期',
            'days_since_last_sale': '距上次销售天数',
            '销售活跃度': '销售活跃度',
            'department': '所属部门',
            'debt_2023': '2023欠款',
            'debt_2024': '2024欠款',
            'debt_2025': '2025欠款',
            'debt_trend': '欠款趋势',
            '欠销比': '欠销比',
            '客户综合等级': '客户综合等级',
            '风险评分': '风险评分',
            '风险等级': '风险等级'
        }
        
        # 只映射存在的列
        existing_columns = {k: v for k, v in column_mapping.items() if k in merged_df.columns}
        if existing_columns:
            merged_df = merged_df.rename(columns=existing_columns)
        
        return merged_df
    
    def get_customer_detail(self, finance_id):
        """
        获取单个客户详情
        """
        with get_connection() as conn:
            # 获取销售记录
            sales_query = '''
                SELECT 
                    year, month, day, 
                    product_name, color, grade,
                    quantity, unit_price, amount,
                    ticket_number, production_line
                FROM sales_records
                WHERE finance_id = ?
                ORDER BY year DESC, month DESC, day DESC
                LIMIT 20
            '''
            sales_df = pd.read_sql(sales_query, conn, params=(finance_id,))
            
            # 获取欠款记录
            debt_queries = []
            params = []
            
            debt_queries.append('''
                SELECT '古建' as department, customer_name, debt_2023, debt_2024, debt_2025
                FROM department1_debt
                WHERE finance_id = ?
            ''')
            params.append(finance_id)
            
            debt_queries.append('''
                SELECT '陶瓷' as department, customer_name, debt_2023, debt_2024, debt_2025
                FROM department2_debt
                WHERE finance_id = ?
            ''')
            params.append(finance_id)
            
            debt_df = pd.concat(
                [pd.read_sql(query, conn, params=(param,)) for query, param in zip(debt_queries, params)],
                ignore_index=True
            )
            
            return {
                'sales_records': sales_df,
                'debt_records': debt_df,
                'total_sales': sales_df['amount'].sum() if not sales_df.empty else 0,
                'recent_transactions': len(sales_df[sales_df['year'] == 25]) if not sales_df.empty and 25 in sales_df['year'].values else 0
            }
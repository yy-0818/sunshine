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
        解决客户在不同部门有不同财务编号的问题
        """
        # 获取销售数据 - 按财务编号汇总
        sales_df = self.get_customer_sales_summary(current_year)
        
        # 获取欠款数据 - 包括两个部门
        debt_df = self.get_customer_debt_summary()
        
        if sales_df.empty and debt_df.empty:
            return pd.DataFrame()
        
        # 处理销售数据：我们需要按客户名称进行匹配，而不是财务编号
        if not sales_df.empty:
            # 为销售数据创建一个标准化的客户标识
            # 使用客户名称作为主要标识，因为同一客户在不同部门可能有不同编号
            sales_by_customer = sales_df.copy()
            
            # 清理客户名称：去除空格和特殊字符
            sales_by_customer['customer_name_clean'] = sales_by_customer['customer_name'].str.strip().str.lower()
            
            # 按客户名称汇总销售数据（同一客户可能有多个子客户，这里按主客户汇总）
            def get_main_customer_name(name):
                # 尝试提取主客户名称（如"岳阳招罗甘威"可能是主客户）
                # 这里可以根据实际业务规则调整
                if '-' in name:
                    return name.split('-')[0].strip()
                return name
            
            sales_by_customer['main_customer'] = sales_by_customer['customer_name'].apply(get_main_customer_name)
            
            # 按主客户汇总销售数据
            customer_sales_summary = sales_by_customer.groupby('main_customer').agg({
                'total_amount': 'sum',
                'total_quantity': 'sum',
                'unique_products': 'sum',
                'transaction_count': 'sum',
                'last_sale_date': 'max',
                'days_since_last_sale': 'min',
                '销售活跃度': lambda x: x.mode()[0] if not x.mode().empty else '无销售记录'
            }).reset_index()
            
            # 为每个主客户保留一个示例财务编号
            customer_finance_map = sales_by_customer.groupby('main_customer')['finance_id'].first().reset_index()
            customer_finance_map.columns = ['main_customer', 'sales_finance_id']
            
            customer_sales_summary = pd.merge(customer_sales_summary, customer_finance_map, on='main_customer', how='left')
        else:
            customer_sales_summary = pd.DataFrame(columns=['main_customer', 'total_amount', 'total_quantity', 
                                                        'unique_products', 'transaction_count', 'last_sale_date',
                                                        'days_since_last_sale', '销售活跃度', 'sales_finance_id'])
        
        # 处理欠款数据
        if not debt_df.empty:
            # 清理欠款数据中的客户名称
            debt_df['customer_name_clean'] = debt_df['customer_name'].str.strip().str.lower()
            debt_df['main_customer'] = debt_df['customer_name'].apply(lambda x: x.split('-')[0].strip() if '-' in x else x)
        else:
            # 创建空的欠款DataFrame
            debt_df = pd.DataFrame(columns=['finance_id', 'customer_name', 'department', 
                                            'debt_2023', 'debt_2024', 'debt_2025', 'debt_trend',
                                            'customer_name_clean', 'main_customer'])
        
        # 合并数据：基于主客户名称进行合并
        merged_records = []
        
        # 如果有销售数据，基于销售客户进行匹配
        if not customer_sales_summary.empty:
            for _, sales_row in customer_sales_summary.iterrows():
                main_customer = sales_row['main_customer']
                
                # 查找该主客户在欠款数据中的记录
                customer_debts = debt_df[debt_df['main_customer'] == main_customer]
                
                if customer_debts.empty:
                    # 该客户有销售但无欠款记录
                    merged_row = {
                        'finance_id': sales_row['sales_finance_id'],
                        'main_customer': main_customer,
                        'customer_name': sales_row['main_customer'],  # 使用主客户名称
                        'total_amount': sales_row['total_amount'],
                        'total_quantity': sales_row['total_quantity'],
                        'unique_products': sales_row['unique_products'],
                        'transaction_count': sales_row['transaction_count'],
                        'last_sale_date': sales_row['last_sale_date'],
                        'days_since_last_sale': sales_row['days_since_last_sale'],
                        '销售活跃度': sales_row['销售活跃度'],
                        'department': '未知',
                        'debt_2023': 0,
                        'debt_2024': 0,
                        'debt_2025': 0,
                        'debt_trend': '无欠款'
                    }
                    merged_records.append(merged_row)
                else:
                    # 该客户有销售也有欠款（可能多个部门）
                    for _, debt_row in customer_debts.iterrows():
                        merged_row = {
                            'finance_id': debt_row['finance_id'],  # 使用欠款数据的财务编号
                            'main_customer': main_customer,
                            'customer_name': debt_row['customer_name'],  # 使用欠款数据中的客户名称
                            'total_amount': sales_row['total_amount'],
                            'total_quantity': sales_row['total_quantity'],
                            'unique_products': sales_row['unique_products'],
                            'transaction_count': sales_row['transaction_count'],
                            'last_sale_date': sales_row['last_sale_date'],
                            'days_since_last_sale': sales_row['days_since_last_sale'],
                            '销售活跃度': sales_row['销售活跃度'],
                            'department': debt_row['department'],
                            'debt_2023': debt_row['debt_2023'],
                            'debt_2024': debt_row['debt_2024'],
                            'debt_2025': debt_row['debt_2025'],
                            'debt_trend': debt_row['debt_trend']
                        }
                        merged_records.append(merged_row)
        
        # 处理只有欠款没有销售的客户
        if not debt_df.empty:
            # 找出所有有欠款但还没有被合并的客户
            merged_main_customers = set([r['main_customer'] for r in merged_records]) if merged_records else set()
            
            for _, debt_row in debt_df.iterrows():
                main_customer = debt_row['main_customer']
                
                if main_customer not in merged_main_customers:
                    # 只有欠款，没有销售记录
                    merged_row = {
                        'finance_id': debt_row['finance_id'],
                        'main_customer': main_customer,
                        'customer_name': debt_row['customer_name'],
                        'total_amount': 0,
                        'total_quantity': 0,
                        'unique_products': 0,
                        'transaction_count': 0,
                        'last_sale_date': None,
                        'days_since_last_sale': None,
                        '销售活跃度': '无销售记录',
                        'department': debt_row['department'],
                        'debt_2023': debt_row['debt_2023'],
                        'debt_2024': debt_row['debt_2024'],
                        'debt_2025': debt_row['debt_2025'],
                        'debt_trend': debt_row['debt_trend']
                    }
                    merged_records.append(merged_row)
        
        # 创建合并后的DataFrame
        if not merged_records:
            return pd.DataFrame()
        
        merged_df = pd.DataFrame(merged_records)
        
        # 计算欠销比
        merged_df['欠销比'] = merged_df.apply(
            lambda row: row['debt_2025'] / row['total_amount'] if row['total_amount'] > 0 else 0,
            axis=1
        )
        
        # 客户综合分类（保持原有逻辑，但使用主客户和部门信息）
        def integrated_classification(row):
            total_sales = row.get('total_amount', 0)
            debt_2025 = row.get('debt_2025', 0)
            debt_trend = row.get('debt_trend', '')
            activity = row.get('销售活跃度', '无销售记录')
            department = row.get('department', '未知')
            
            # 如果是"未知"部门且无销售无欠款，可能是数据不完整
            if department == '未知' and total_sales == 0 and debt_2025 == 0:
                return '数据不完整'
            
            # 1. 无欠款客户
            if debt_2025 == 0:
                if total_sales == 0:
                    return 'D-无销售无欠款'
                elif total_sales > 50000:
                    if activity in ['活跃(30天内)', '一般活跃(90天内)']:
                        return f'A-优质大客户({department})'
                    else:
                        return f'B-大额休眠客户({department})'
                elif total_sales > 10000:
                    if activity in ['活跃(30天内)', '一般活跃(90天内)']:
                        return f'A-优质活跃客户({department})'
                    else:
                        return f'B-一般客户({department})'
                else:
                    return f'C-小额客户({department})'
            
            # 2. 有欠款客户
            else:
                if total_sales == 0:
                    return f'E-纯欠款客户({department})'
                
                debt_ratio = row.get('欠销比', 0)
                
                if debt_ratio < 0.2:  # 欠款占销售额小于20%
                    if activity == '活跃(30天内)':
                        return f'B1-低风险活跃欠款({department})'
                    else:
                        return f'B2-低风险欠款({department})'
                elif debt_ratio < 0.5:  # 20%-50%
                    if debt_trend == '持续欠款':
                        return f'C1-中风险持续欠款({department})'
                    else:
                        return f'C2-中风险欠款({department})'
                else:  # 超过50%
                    if debt_trend == '持续欠款':
                        return f'D1-高风险持续欠款({department})'
                    else:
                        return f'D2-高风险欠款({department})'
        
        merged_df['客户综合等级'] = merged_df.apply(integrated_classification, axis=1)
        
        # 计算风险评分
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
            
            # 部门因素：陶瓷部门可能风险更高？根据业务调整
            if row.get('department') == '陶瓷' and debt_2025 > 0:
                score -= 5
            
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
        
        # 重命名列
        column_mapping = {
            'finance_id': '财务编号',
            'main_customer': '主客户名称',
            'customer_name': '客户名称',
            'total_amount': '总销售额',
            'total_quantity': '总销售量',
            'unique_products': '产品种类数',
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
    
    def get_customer_detail(self, customer_name):
        """
        获取单个客户详情（基于客户名称而不是财务编号）
        """
        # 清理客户名称
        customer_name_clean = customer_name.strip().lower()
        
        with get_connection() as conn:
            # 首先查找该客户的所有财务编号
            finance_ids_query = '''
                SELECT DISTINCT finance_id, customer_name
                FROM sales_records
                WHERE LOWER(TRIM(customer_name)) LIKE ? 
                OR LOWER(TRIM(customer_name)) LIKE ?
            '''
            
            # 尝试精确匹配和模糊匹配
            search_pattern1 = f"%{customer_name_clean}%"
            search_pattern2 = f"%{customer_name_clean.split('-')[0].strip()}%" if '-' in customer_name_clean else search_pattern1
            
            finance_ids_df = pd.read_sql(finance_ids_query, conn, params=(search_pattern1, search_pattern2))
            
            if finance_ids_df.empty:
                return {
                    'sales_records': pd.DataFrame(),
                    'debt_records': pd.DataFrame(),
                    'total_sales': 0,
                    'recent_transactions': 0,
                    'finance_ids': [],
                    'customer_name': customer_name
                }
            
            finance_ids = finance_ids_df['finance_id'].tolist()
            
            # 获取销售记录（所有相关的财务编号）
            if finance_ids:
                placeholders = ','.join(['?'] * len(finance_ids))
                sales_query = f'''
                    SELECT 
                        year, month, day, 
                        customer_name, finance_id, sub_customer_name,
                        product_name, color, grade,
                        quantity, unit_price, amount,
                        ticket_number, production_line
                    FROM sales_records
                    WHERE finance_id IN ({placeholders})
                    ORDER BY year DESC, month DESC, day DESC
                    LIMIT 50
                '''
                sales_df = pd.read_sql(sales_query, conn, params=finance_ids)
            else:
                sales_df = pd.DataFrame()
            
            # 获取欠款记录 - 基于客户名称匹配
            debt_queries = []
            
            debt_queries.append('''
                SELECT '古建' as department, finance_id, customer_name, debt_2023, debt_2024, debt_2025
                FROM department1_debt
                WHERE LOWER(TRIM(customer_name)) LIKE ? OR LOWER(TRIM(customer_name)) LIKE ?
            ''')
            
            debt_queries.append('''
                SELECT '陶瓷' as department, finance_id, customer_name, debt_2023, debt_2024, debt_2025
                FROM department2_debt
                WHERE LOWER(TRIM(customer_name)) LIKE ? OR LOWER(TRIM(customer_name)) LIKE ?
            ''')
            
            params = (search_pattern1, search_pattern2, search_pattern1, search_pattern2)
            
            debt_dfs = []
            for i, query in enumerate(debt_queries):
                param = params[i*2:(i+1)*2]
                df = pd.read_sql(query, conn, params=param)
                debt_dfs.append(df)
            
            debt_df = pd.concat(debt_dfs, ignore_index=True) if debt_dfs else pd.DataFrame()
            
            return {
                'sales_records': sales_df,
                'debt_records': debt_df,
                'total_sales': sales_df['amount'].sum() if not sales_df.empty else 0,
                'recent_transactions': len(sales_df[sales_df['year'] == 25]) if not sales_df.empty and 25 in sales_df['year'].values else 0,
                'finance_ids': finance_ids,
                'customer_name': customer_name,
                'matched_customer_names': finance_ids_df['customer_name'].tolist() if not finance_ids_df.empty else []
            }
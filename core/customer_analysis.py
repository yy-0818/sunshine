import pandas as pd
import numpy as np
from core.database import get_connection, get_all_debt_data
from datetime import datetime, timedelta

class SalesDebtIntegrationService:
    def __init__(self):
        pass
    
    def _get_year_sales_data(self, year=25):
        """获取指定年份的销售数据 - 按财务编号分组汇总"""
        sales_df = pd.DataFrame()
        with get_connection() as conn:
            # 获取指定年份的销售数据，按财务编号、客户名称、部门分组
            sales_query = f'''
                SELECT 
                    finance_id,
                    customer_name,
                    department,
                    SUM(amount) as year_amount,
                    SUM(quantity) as year_quantity,
                    COUNT(DISTINCT product_name) as unique_products,
                    COUNT(*) as transaction_count,
                    MAX(date('20' || substr('00' || year, -2) || '-' || 
                          substr('00' || month, -2) || '-' || 
                          substr('00' || day, -2))) as last_sale_date
                FROM sales_records
                WHERE finance_id IS NOT NULL 
                    AND finance_id != '' 
                    AND TRIM(finance_id) != ''
                    AND year = '{year}'
                GROUP BY finance_id, customer_name, department
                ORDER BY finance_id, customer_name, department
            '''
            sales_df = pd.read_sql(sales_query, conn)
            
            if not sales_df.empty:
                print(f"获取到 {year} 年销售数据: {len(sales_df)} 条记录")
                
                # 添加活跃度分类
                sales_df['last_sale_date'] = pd.to_datetime(sales_df['last_sale_date'], errors='coerce')
                current_date = pd.Timestamp.now()
                sales_df['days_since_last_sale'] = (current_date - sales_df['last_sale_date']).dt.days
                
                def classify_activity(days):
                    if pd.isna(days):
                        return '无销售记录'
                    elif days <= 30:
                        return '活跃(30天内)'
                    elif days <= 90:
                        return '一般活跃(90天内)'
                    elif days <= 180:
                        return '低活跃(180天内)'
                    elif days <= 365:
                        return '休眠客户'
                    # else:
                    #     return '一年内无销售'
                
                sales_df['销售活跃度'] = sales_df['days_since_last_sale'].apply(classify_activity)
        
        return sales_df
    
    def get_integrated_customer_analysis(self, current_year=25):
        """获取综合客户分析数据 - 支持年度销售额"""
        # 1. 获取所有欠款数据
        debt_df = get_all_debt_data()
        print(f"欠款数据: {len(debt_df)} 条记录")
        
        if debt_df.empty:
            print("没有欠款数据，跳过分析")
            return pd.DataFrame()
        
        # 2. 获取所有销售数据 - 按财务编号分组汇总
        sales_df = pd.DataFrame()
        with get_connection() as conn:
            # 获取所有销售数据，按财务编号、客户名称、部门分组
            sales_query = '''
                SELECT 
                    finance_id,
                    customer_name,
                    department,
                    SUM(amount) as total_amount,
                    SUM(quantity) as total_quantity,
                    COUNT(DISTINCT product_name) as unique_products,
                    COUNT(*) as transaction_count,
                    MAX(date('20' || substr('00' || year, -2) || '-' || 
                        substr('00' || month, -2) || '-' || 
                        substr('00' || day, -2))) as last_sale_date
                FROM sales_records
                WHERE finance_id IS NOT NULL 
                    AND finance_id != '' 
                    AND TRIM(finance_id) != ''
                GROUP BY finance_id, customer_name, department
                ORDER BY finance_id, customer_name, department
            '''
            sales_df = pd.read_sql(sales_query, conn)
            
            if sales_df.empty:
                print("没有销售数据")
            else:
                print(f"销售数据: {len(sales_df)} 条记录")
                
                # 添加活跃度分类
                sales_df['last_sale_date'] = pd.to_datetime(sales_df['last_sale_date'], errors='coerce')
                current_date = pd.Timestamp.now()
                sales_df['days_since_last_sale'] = (current_date - sales_df['last_sale_date']).dt.days
                
                def classify_activity(days):
                    if pd.isna(days):
                        return '无销售记录'
                    elif days <= 30:
                        return '活跃(30天内)'
                    elif days <= 90:
                        return '一般活跃(90天内)'
                    elif days <= 180:
                        return '低活跃(180天内)'
                    elif days <= 365:
                        return '休眠客户'
                    else:
                        return '一年内无销售'
                
                sales_df['销售活跃度'] = sales_df['days_since_last_sale'].apply(classify_activity)
                
                # 获取年度销售数据（复用现有数据过滤）
                year_sales_query = f'''
                    SELECT 
                        finance_id,
                        customer_name,
                        department,
                        SUM(amount) as year_amount
                    FROM sales_records
                    WHERE finance_id IS NOT NULL 
                        AND finance_id != '' 
                        AND TRIM(finance_id) != ''
                        AND year = '{current_year}'
                    GROUP BY finance_id, customer_name, department
                '''
                year_sales_df = pd.read_sql(year_sales_query, conn)
                
                # 将年度销售额合并到主销售数据
                if not year_sales_df.empty:
                    print(f"获取到 {current_year} 年销售数据: {len(year_sales_df)} 条记录")
                    # 创建合并键
                    year_sales_df['merge_key'] = year_sales_df['finance_id'].astype(str) + '|' + year_sales_df['customer_name'].astype(str) + '|' + year_sales_df['department'].astype(str)
                    sales_df['merge_key'] = sales_df['finance_id'].astype(str) + '|' + sales_df['customer_name'].astype(str) + '|' + sales_df['department'].astype(str)
                    
                    # 合并年度销售额
                    sales_df = sales_df.merge(
                        year_sales_df[['merge_key', 'year_amount']],
                        on='merge_key',
                        how='left'
                    )
                    sales_df['year_amount'] = sales_df['year_amount'].fillna(0.0)
                else:
                    sales_df['year_amount'] = 0.0
                    print(f"未找到 {current_year} 年销售数据")
        
        # 3. 基本数据清洗 - 只做最基本的处理
        def clean_data(df):
            df = df.copy()
            if 'finance_id' in df.columns:
                df['finance_id_clean'] = df['finance_id'].astype(str).str.strip()
                # 对于纯数字且长度小于2的，补0到2位
                def pad_zero(x):
                    if x.isdigit():
                        if len(x) < 2:
                            return x.zfill(2)
                    return x
                df['finance_id_clean'] = df['finance_id_clean'].apply(pad_zero)
            
            if 'customer_name' in df.columns:
                df['customer_name_clean'] = df['customer_name'].astype(str).str.strip()
                # 只做最简单的处理：如果有'-'，取后面的部分
                df['customer_name_clean'] = df['customer_name_clean'].apply(
                    lambda x: x.split('-', 1)[1].strip() if '-' in x else x
                )
            
            if 'department' in df.columns:
                df['department_clean'] = df['department'].astype(str).str.strip()
            
            return df
        
        if not sales_df.empty:
            sales_df = clean_data(sales_df)
        
        if not debt_df.empty:
            debt_df = clean_data(debt_df)
        
        # 4. 建立销售数据索引
        sales_index = {}
        unmatched_sales = []  # 存储未匹配的销售记录
        
        if not sales_df.empty:
            for _, row in sales_df.iterrows():
                finance_id = row.get('finance_id_clean', '')
                department = row.get('department_clean', '')
                
                if not finance_id:
                    continue
                    
                # 创建唯一键
                key = f"{finance_id}|{department}"
                
                if key not in sales_index:
                    sales_index[key] = {
                        'total_amount': float(row['total_amount']) if pd.notna(row['total_amount']) else 0.0,
                        'year_amount': float(row['year_amount']) if pd.notna(row['year_amount']) else 0.0,
                        'total_quantity': int(row['total_quantity']) if pd.notna(row['total_quantity']) else 0,
                        'unique_products': int(row['unique_products']) if pd.notna(row['unique_products']) else 0,
                        'transaction_count': int(row['transaction_count']) if pd.notna(row['transaction_count']) else 0,
                        'last_sale_date': row['last_sale_date'],
                        'days_since_last_sale': row['days_since_last_sale'],
                        '销售活跃度': row['销售活跃度'],
                        'matched': False,
                        'customer_names': [row['customer_name_clean']]
                    }
                else:
                    # 如果已存在，合并数据（理论上不应该出现）
                    sales_index[key]['total_amount'] += float(row['total_amount']) if pd.notna(row['total_amount']) else 0.0
                    sales_index[key]['year_amount'] += float(row['year_amount']) if pd.notna(row['year_amount']) else 0.0
                    sales_index[key]['total_quantity'] += int(row['total_quantity']) if pd.notna(row['total_quantity']) else 0
                    # 产品种类取最大值
                    sales_index[key]['unique_products'] = max(
                        sales_index[key]['unique_products'],
                        int(row['unique_products']) if pd.notna(row['unique_products']) else 0
                    )
                    sales_index[key]['transaction_count'] += int(row['transaction_count']) if pd.notna(row['transaction_count']) else 0
                    # 取最近的销售日期
                    if pd.notna(row['last_sale_date']):
                        if pd.isna(sales_index[key]['last_sale_date']) or row['last_sale_date'] > sales_index[key]['last_sale_date']:
                            sales_index[key]['last_sale_date'] = row['last_sale_date']
                            sales_index[key]['days_since_last_sale'] = row['days_since_last_sale']
                            sales_index[key]['销售活跃度'] = row['销售活跃度']
                    
                    # 添加客户名称到列表
                    if row['customer_name_clean'] not in sales_index[key]['customer_names']:
                        sales_index[key]['customer_names'].append(row['customer_name_clean'])
        
        # 5. 匹配逻辑 - 严格一对一匹配
        matched_records = []
        
        for _, debt_row in debt_df.iterrows():
            finance_id = debt_row.get('finance_id_clean', '')
            department = debt_row.get('department_clean', '')
            
            if not finance_id:
                # 财务编号为空，只能创建欠款记录
                matched_records.append({
                    '财务编号': debt_row.get('finance_id', ''),
                    '客户名称': debt_row.get('customer_name', ''),
                    '所属部门': department,
                    '总销售额': 0.0,
                    f'20{current_year}销售额': 0.0,
                    '总销售量': 0,
                    '产品种类数': 0,
                    '交易次数': 0,
                    '最后销售日期': None,
                    '距上次销售天数': None,
                    '销售活跃度': '无销售记录',
                    '2023欠款': float(debt_row.get('debt_2023', 0)) if pd.notna(debt_row.get('debt_2023')) else 0.0,
                    '2024欠款': float(debt_row.get('debt_2024', 0)) if pd.notna(debt_row.get('debt_2024')) else 0.0,
                    '2025欠款': float(debt_row.get('debt_2025', 0)) if pd.notna(debt_row.get('debt_2025')) else 0.0
                })
                continue
            
            # 尝试匹配
            key = f"{finance_id}|{department}"
            sales_match = None
            
            if key in sales_index and not sales_index[key]['matched']:
                sales_match = sales_index[key]
            
            if sales_match:
                # 有匹配的销售记录
                # 选择最匹配的客户名称
                debt_customer_name = debt_row.get('customer_name_clean', '')
                best_customer_match = debt_customer_name
                
                if sales_match['customer_names']:
                    # 如果欠款客户名称在销售客户名称列表中，使用它
                    if debt_customer_name in sales_match['customer_names']:
                        best_customer_match = debt_customer_name
                    else:
                        # 否则使用第一个销售客户名称
                        best_customer_match = sales_match['customer_names'][0]
                
                matched_records.append({
                    '财务编号': debt_row.get('finance_id', ''),
                    '客户名称': best_customer_match,
                    '所属部门': department,
                    '总销售额': sales_match['total_amount'],
                    f'20{current_year}销售额': sales_match['year_amount'],
                    '总销售量': sales_match['total_quantity'],
                    '产品种类数': sales_match['unique_products'],
                    '交易次数': sales_match['transaction_count'],
                    '最后销售日期': sales_match['last_sale_date'],
                    '距上次销售天数': sales_match['days_since_last_sale'],
                    '销售活跃度': sales_match['销售活跃度'],
                    '2023欠款': float(debt_row.get('debt_2023', 0)) if pd.notna(debt_row.get('debt_2023')) else 0.0,
                    '2024欠款': float(debt_row.get('debt_2024', 0)) if pd.notna(debt_row.get('debt_2024')) else 0.0,
                    '2025欠款': float(debt_row.get('debt_2025', 0)) if pd.notna(debt_row.get('debt_2025')) else 0.0
                })
                
                # 标记为已匹配
                sales_index[key]['matched'] = True
            else:
                # 没有匹配的销售记录
                matched_records.append({
                    '财务编号': debt_row.get('finance_id', ''),
                    '客户名称': debt_row.get('customer_name', ''),
                    '所属部门': department,
                    '总销售额': 0.0,
                    f'20{current_year}销售额': 0.0,
                    '总销售量': 0,
                    '产品种类数': 0,
                    '交易次数': 0,
                    '最后销售日期': None,
                    '距上次销售天数': None,
                    '销售活跃度': '无销售记录',
                    '2023欠款': float(debt_row.get('debt_2023', 0)) if pd.notna(debt_row.get('debt_2023')) else 0.0,
                    '2024欠款': float(debt_row.get('debt_2024', 0)) if pd.notna(debt_row.get('debt_2024')) else 0.0,
                    '2025欠款': float(debt_row.get('debt_2025', 0)) if pd.notna(debt_row.get('debt_2025')) else 0.0
                })
        
        # 6. 检查未匹配的销售记录（可选）
        unmatched_sales_total = 0
        for key, sales_data in sales_index.items():
            if not sales_data['matched']:
                unmatched_sales_total += sales_data['total_amount']
                print(f"未匹配的销售记录: {key}, 销售额: {sales_data['total_amount']}")
        
        if unmatched_sales_total > 0:
            print(f"有未匹配的销售记录，总金额: ¥{unmatched_sales_total:,.2f}")
        
        # 7. 创建DataFrame并计算指标
        if not matched_records:
            return pd.DataFrame()
        
        merged_df = pd.DataFrame(matched_records)
        print(f"合并后数据: {len(merged_df)} 条记录")
        
        # 计算总销售额并与数据库对比
        total_sales_calculated = merged_df['总销售额'].sum()
        print(f"计算的总销售额: ¥{total_sales_calculated:,.2f}")
        
        # 计算年度销售额
        year_sales_column = f'20{current_year}销售额'
        year_sales_calculated = merged_df[year_sales_column].sum()
        print(f"计算的{current_year}年销售额: ¥{year_sales_calculated:,.2f}")
        
        # 直接从数据库获取实际总销售额
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(amount) FROM sales_records")
            total_sales_actual = cursor.fetchone()[0] or 0
            print(f"数据库实际总销售额: ¥{total_sales_actual:,.2f}")
            
            # 获取年度实际销售额
            cursor.execute(f"SELECT SUM(amount) FROM sales_records WHERE year = '{current_year}'")
            year_sales_actual = cursor.fetchone()[0] or 0
            print(f"数据库{current_year}年实际销售额: ¥{year_sales_actual:,.2f}")
            
            # 计算匹配率
            if total_sales_actual > 0:
                match_rate = (total_sales_calculated / total_sales_actual) * 100
                print(f"销售额匹配率: {match_rate:.2f}%")
            
            if year_sales_actual > 0:
                year_match_rate = (year_sales_calculated / year_sales_actual) * 100
                print(f"{current_year}年销售额匹配率: {year_match_rate:.2f}%")
        
        # 计算欠销比
        year_key = f'20{current_year}欠款'
        merged_df['欠销比'] = merged_df.apply(
            lambda row: (row[year_key] / row[year_sales_column] * 100) if row[year_sales_column] > 0 else 0,
            axis=1
        )
        
        # 客户分类和风险评分
        merged_df['客户综合等级'] = merged_df.apply(self._classify_customer, axis=1)
        merged_df['风险评分'] = merged_df.apply(self._calculate_risk_score, axis=1)
        merged_df['风险等级'] = merged_df['风险评分'].apply(self._classify_risk)
        
        return merged_df

    def _classify_customer(self, row):
        total_sales = row.get('总销售额', 0)
        debt_2025 = row.get('2025欠款', 0)
        activity = row.get('销售活跃度', '无销售记录')
        
        if debt_2025 > 0 and total_sales == 0:
            return 'E-纯欠款客户'
        
        if debt_2025 == 0:
            if total_sales == 0:
                return 'D-无销售无欠款'
            elif activity == '一年内无销售':
                return 'C-长期无交易客户'
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
        
        debt_ratio = row.get('欠销比', 0) / 100
        
        if debt_ratio < 0.2:
            if activity == '活跃(30天内)':
                return 'B1-低风险活跃欠款'
            else:
                return 'B2-低风险欠款'
        elif debt_ratio < 0.5:
            if activity == '活跃(30天内)':
                return 'C1-中风险活跃欠款'
            else:
                return 'C2-中风险欠款'
        else:
            if debt_ratio > 1.0:
                return 'D-高风险欠款'
            else:
                return 'D-高风险欠款'
    
    def _calculate_risk_score(self, row):
        score = 100
        
        total_sales = row.get('总销售额', 0)
        debt_2025 = row.get('2025欠款', 0)
        activity = row.get('销售活跃度', '无销售记录')
        
        if debt_2025 > 0 and total_sales == 0:
            return 0
        
        if debt_2025 > 0:
            score -= 10
            
            if debt_2025 > 100000:
                score -= 35
            elif debt_2025 > 50000:
                score -= 25
            elif debt_2025 > 10000:
                score -= 15
            
            if total_sales > 0:
                debt_ratio = debt_2025 / total_sales
                if debt_ratio > 1.0:
                    score -= 35
                elif debt_ratio > 0.5:
                    score -= 25
                elif debt_ratio > 0.2:
                    score -= 15
                elif debt_ratio > 0:
                    score -= 5
        else:
            score += 5
        
        if activity == '一年内无销售':
            score -= 30
        elif activity == '休眠客户':
            score -= 20
        elif activity == '无销售记录':
            score -= 25
        elif activity == '低活跃(180天内)':
            score -= 10
        elif activity == '一般活跃(90天内)':
            score -= 5
        
        if total_sales > 50000:
            score += 10
        elif total_sales > 10000:
            score += 5
        
        return max(0, min(100, int(score)))
    
    def _classify_risk(self, score):
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

    def get_customer_detail(self, search_term):
        """单客户详情查询"""
        if not search_term or str(search_term).strip() == '':
            return {
                'sales_records': pd.DataFrame(),
                'debt_records': pd.DataFrame(),
                'total_sales': 0,
                'recent_transactions': 0,
                'finance_ids': [],
                'matched_customer_names': []
            }
        
        search_term = str(search_term).strip()
        
        with get_connection() as conn:
            # 先尝试财务编号搜索
            finance_search = '''
                SELECT 
                    year, month, day, 
                    customer_name, finance_id, sub_customer_name,
                    product_name, color, grade,
                    quantity, unit_price, amount,
                    ticket_number, production_line, record_date,
                    department
                FROM sales_records
                WHERE finance_id = ?
                ORDER BY year DESC, month DESC, day DESC
            '''
            
            sales_df = pd.read_sql(finance_search, conn, params=(search_term,))
            
            if not sales_df.empty:
                # 找到销售记录，再找对应的欠款记录
                debt_search = '''
                    SELECT 
                        department,
                        finance_id,
                        customer_name,
                        debt_2023,
                        debt_2024,
                        debt_2025
                    FROM unified_debt
                    WHERE finance_id = ?
                    ORDER BY department
                '''
                debt_df = pd.read_sql(debt_search, conn, params=(search_term,))
                
                # 获取匹配的客户名称和财务编号
                matched_customer_names = sales_df['customer_name'].unique().tolist()
                if not debt_df.empty:
                    debt_customer_names = debt_df['customer_name'].unique().tolist()
                    matched_customer_names.extend(debt_customer_names)
                
                matched_customer_names = list(set(matched_customer_names))
                finance_ids = [search_term]
            else:
                # 没有财务编号匹配，尝试客户名称搜索
                sales_name_search = '''
                    SELECT 
                        year, month, day, 
                        customer_name, finance_id, sub_customer_name,
                        product_name, color, grade,
                        quantity, unit_price, amount,
                        ticket_number, production_line, record_date,
                        department
                    FROM sales_records
                    WHERE customer_name LIKE ?
                    ORDER BY year DESC, month DESC, day DESC
                '''
                sales_df = pd.read_sql(sales_name_search, conn, params=(f"%{search_term}%",))
                
                # 搜索欠款记录
                debt_name_search = '''
                    SELECT 
                        department,
                        finance_id,
                        customer_name,
                        debt_2023,
                        debt_2024,
                        debt_2025
                    FROM unified_debt
                    WHERE customer_name LIKE ?
                    ORDER BY department
                '''
                debt_df = pd.read_sql(debt_name_search, conn, params=(f"%{search_term}%",))
                
                # 获取匹配的客户名称和财务编号
                matched_customer_names = []
                finance_ids = []
                
                if not sales_df.empty:
                    matched_customer_names.extend(sales_df['customer_name'].unique().tolist())
                    finance_ids.extend(sales_df['finance_id'].dropna().unique().tolist())
                
                if not debt_df.empty:
                    matched_customer_names.extend(debt_df['customer_name'].unique().tolist())
                    finance_ids.extend(debt_df['finance_id'].dropna().unique().tolist())
                
                matched_customer_names = list(set(matched_customer_names))
                finance_ids = list(set(finance_ids))
            
            # 计算总销售额和最近交易次数
            total_sales = sales_df['amount'].sum() if not sales_df.empty else 0
            recent_transactions = 0
            if not sales_df.empty and 'year' in sales_df.columns:
                current_year = 25
                recent_transactions = len(sales_df[sales_df['year'] == current_year])
            
            return {
                'sales_records': sales_df,
                'debt_records': debt_df,
                'total_sales': total_sales,
                'recent_transactions': recent_transactions,
                'finance_ids': finance_ids,
                'matched_customer_names': matched_customer_names
            }
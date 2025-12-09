import pandas as pd
import numpy as np
from core.database import get_connection, get_sales_by_finance_id_and_name, get_all_debt_data
from datetime import datetime, timedelta
import re

class SalesDebtIntegrationService:
    def __init__(self):
        pass
    
    def get_integrated_customer_analysis(self, current_year=25):
        """
        整合销售与欠款数据进行分析 - 基于财务编号+客户名称匹配
        核心优化点：
        1. 改进匹配算法，使用多级匹配策略
        2. 处理同一客户在不同部门的情况
        3. 添加客户名称标准化处理
        """
        print(f"开始整合分析，当前年份: {current_year}")
        
        # 1. 获取所有销售数据
        with get_connection() as conn:
            # 获取分组后的销售数据
            sales_query = '''
                SELECT 
                    finance_id,
                    customer_name,
                    SUM(amount) as total_amount,
                    SUM(quantity) as total_quantity,
                    COUNT(DISTINCT product_name) as unique_products,
                    COUNT(*) as transaction_count,
                    MAX(date('20' || substr('00' || year, -2) || '-' || 
                          substr('00' || month, -2) || '-' || 
                          substr('00' || day, -2))) as last_sale_date
                FROM sales_records
                WHERE finance_id IS NOT NULL AND finance_id != ''
                GROUP BY finance_id, customer_name
                ORDER BY finance_id, customer_name
            '''
            sales_df = pd.read_sql(sales_query, conn)
            
            if not sales_df.empty:
                # 计算活跃度
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
                    else:
                        return '休眠客户'
                
                sales_df['销售活跃度'] = sales_df['days_since_last_sale'].apply(classify_activity)
            
            print(f"销售数据: {len(sales_df)} 条记录")
        
        # 2. 获取所有欠款数据
        debt_df = get_all_debt_data()
        print(f"欠款数据: {len(debt_df)} 条记录")
        
        if sales_df.empty and debt_df.empty:
            print("没有销售和欠款数据")
            return pd.DataFrame()
        
        # 3. 数据预处理：清洗和标准化
        sales_df = self._preprocess_sales_data(sales_df)
        if not debt_df.empty:
            debt_df = self._preprocess_debt_data(debt_df)
        
        # 4. 多级匹配策略
        merged_records = []
        
        if not debt_df.empty:
            # 第一轮：精确匹配（财务编号+标准化客户名称）
            matched_indices = set()
            
            for debt_idx, debt_row in debt_df.iterrows():
                finance_id = debt_row['finance_id']
                debt_customer_name = debt_row['customer_name']
                department = debt_row['department']
                
                # 标准化客户名称用于匹配
                standardized_debt_name = self._standardize_customer_name(debt_customer_name)
                
                # 查找销售数据中的匹配项
                sales_match = None
                
                # 策略1：精确匹配财务编号 + 标准化客户名称
                sales_mask = (
                    (sales_df['finance_id'] == finance_id) & 
                    (sales_df['standardized_name'] == standardized_debt_name)
                )
                if sales_mask.any():
                    sales_match = sales_df[sales_mask].iloc[0]
                    match_type = '精确匹配'
                
                # 策略2：财务编号匹配 + 客户名称包含关系
                if sales_match is None:
                    sales_same_finance = sales_df[sales_df['finance_id'] == finance_id]
                    if not sales_same_finance.empty:
                        # 检查客户名称是否包含关系
                        for _, sales_row in sales_same_finance.iterrows():
                            if (debt_customer_name in sales_row['customer_name'] or 
                                sales_row['customer_name'] in debt_customer_name or
                                self._is_similar_name(debt_customer_name, sales_row['customer_name'])):
                                sales_match = sales_row
                                match_type = '名称包含匹配'
                                break
                
                # 策略3：财务编号匹配 + 关键词匹配
                if sales_match is None and not sales_same_finance.empty:
                    debt_keywords = self._extract_keywords(debt_customer_name)
                    if debt_keywords:
                        for _, sales_row in sales_same_finance.iterrows():
                            sales_keywords = self._extract_keywords(sales_row['customer_name'])
                            # 检查关键词重叠
                            common_keywords = set(debt_keywords) & set(sales_keywords)
                            if common_keywords:
                                sales_match = sales_row
                                match_type = '关键词匹配'
                                break
                
                # 策略4：仅财务编号匹配（取最近活跃的销售记录）
                if sales_match is None and not sales_same_finance.empty:
                    # 选择交易次数最多的
                    sales_same_finance_sorted = sales_same_finance.sort_values(
                        ['transaction_count', 'days_since_last_sale'], 
                        ascending=[False, True]
                    )
                    sales_match = sales_same_finance_sorted.iloc[0]
                    match_type = '财务编号匹配'
                
                # 处理匹配结果
                if sales_match is not None:
                    # 标记已匹配的销售记录
                    sales_index = sales_match.name
                    if sales_index not in matched_indices:
                        matched_indices.add(sales_index)
                        
                        merged_row = self._create_merged_record(
                            finance_id=finance_id,
                            customer_name=debt_customer_name,
                            department=department,
                            sales_row=sales_match,
                            debt_row=debt_row,
                            match_type=match_type
                        )
                        merged_records.append(merged_row)
                    else:
                        # 如果销售记录已被匹配，可能同一个财务编号对应多个部门
                        # 创建仅欠款的记录（无销售数据）
                        merged_row = self._create_debt_only_record(
                            finance_id=finance_id,
                            customer_name=debt_customer_name,
                            department=department,
                            debt_row=debt_row
                        )
                        merged_records.append(merged_row)
                else:
                    # 无匹配的销售记录
                    merged_row = self._create_debt_only_record(
                        finance_id=finance_id,
                        customer_name=debt_customer_name,
                        department=department,
                        debt_row=debt_row
                    )
                    merged_records.append(merged_row)
        
        # 5. 处理只有销售数据没有欠款数据的记录
        if not sales_df.empty:
            for sales_idx, sales_row in sales_df.iterrows():
                if sales_idx not in matched_indices:
                    # 创建仅销售的记录
                    merged_row = self._create_sales_only_record(sales_row)
                    merged_records.append(merged_row)
        
        # 6. 创建DataFrame并计算指标
        if not merged_records:
            print("没有合并记录")
            return pd.DataFrame()
        
        merged_df = pd.DataFrame(merged_records)
        print(f"合并后数据条数: {len(merged_df)}")
        
        # 计算欠销比
        merged_df['欠销比'] = merged_df.apply(
            lambda row: (row['2025欠款'] / row['总销售额'] * 100) if row['总销售额'] > 0 else 0,
            axis=1
        )
        
        # 7. 客户综合分类和风险评分（保持原有逻辑）
        merged_df['客户综合等级'] = merged_df.apply(self._classify_customer, axis=1)
        merged_df['风险评分'] = merged_df.apply(self._calculate_risk_score, axis=1)
        merged_df['风险等级'] = merged_df['风险评分'].apply(self._classify_risk)
        
        return merged_df
    
    def _preprocess_sales_data(self, sales_df):
        """预处理销售数据"""
        if sales_df.empty:
            return sales_df
            
        # 清洗数据
        sales_df['finance_id'] = sales_df['finance_id'].astype(str).str.strip()
        sales_df['customer_name'] = sales_df['customer_name'].astype(str).str.strip()
        
        # 添加标准化名称
        sales_df['standardized_name'] = sales_df['customer_name'].apply(self._standardize_customer_name)
        
        return sales_df
    
    def _preprocess_debt_data(self, debt_df):
        """预处理欠款数据"""
        if debt_df.empty:
            return debt_df
            
        # 清洗数据
        debt_df['finance_id'] = debt_df['finance_id'].astype(str).str.strip()
        debt_df['customer_name'] = debt_df['customer_name'].astype(str).str.strip()
        
        # 添加标准化名称
        debt_df['standardized_name'] = debt_df['customer_name'].apply(self._standardize_customer_name)
        
        return debt_df
    
    def _standardize_customer_name(self, customer_name):
        """标准化客户名称"""
        if pd.isna(customer_name):
            return ''
        
        name_str = str(customer_name)
        
        # 移除常见前缀和分隔符
        prefixes = ['鑫帅辉-', '鑫帅辉_', '九方昌盛-', '九方昌盛_', '古建-', '陶瓷-']
        for prefix in prefixes:
            if name_str.startswith(prefix):
                name_str = name_str[len(prefix):]
        
        # 移除空白字符和特殊字符
        name_str = re.sub(r'[^\w\u4e00-\u9fff\-]', '', name_str)
        
        return name_str.strip()
    
    def _extract_keywords(self, customer_name):
        """从客户名称中提取关键词"""
        if pd.isna(customer_name):
            return []
        
        name_str = str(customer_name)
        
        # 移除常见前缀
        prefixes = ['鑫帅辉-', '鑫帅辉_', '九方昌盛-', '九方昌盛_', '古建-', '陶瓷-']
        for prefix in prefixes:
            if name_str.startswith(prefix):
                name_str = name_str[len(prefix):]
        
        # 按常见分隔符分割
        separators = ['-', '_', '—', ' ', '·', '（', '(', '）', ')']
        
        keywords = []
        current_str = name_str
        
        for sep in separators:
            if sep in current_str:
                parts = [part.strip() for part in current_str.split(sep) if part.strip()]
                # 通常最后一部分是企业核心名称
                if parts:
                    keywords.extend(parts)
                    # 重点关注较长的部分（通常为核心名称）
                    keywords.extend([p for p in parts if len(p) > 2])
                break
        
        # 如果没有分隔符，尝试提取核心部分
        if not keywords:
            # 移除数字和特殊字符，保留中文字符
            chinese_parts = re.findall(r'[\u4e00-\u9fff]{2,}', name_str)
            keywords.extend(chinese_parts)
        
        # 去重并过滤短词
        keywords = list(set([k for k in keywords if len(k) > 1]))
        
        return keywords
    
    def _is_similar_name(self, name1, name2, threshold=0.7):
        """判断两个客户名称是否相似"""
        from difflib import SequenceMatcher
        
        if pd.isna(name1) or pd.isna(name2):
            return False
        
        str1 = str(name1)
        str2 = str(name2)
        
        # 标准化处理
        str1_clean = self._standardize_customer_name(str1)
        str2_clean = self._standardize_customer_name(str2)
        
        # 检查是否互相包含
        if str1_clean in str2_clean or str2_clean in str1_clean:
            return True
        
        # 使用序列匹配计算相似度
        similarity = SequenceMatcher(None, str1_clean, str2_clean).ratio()
        
        return similarity >= threshold
    
    def _create_merged_record(self, finance_id, customer_name, department, sales_row, debt_row, match_type='未知'):
        """创建合并记录"""
        return {
            '财务编号': finance_id,
            '客户名称': customer_name,
            '所属部门': department,
            '匹配类型': match_type,
            '总销售额': float(sales_row['total_amount']) if pd.notna(sales_row['total_amount']) else 0.0,
            '总销售量': int(sales_row['total_quantity']) if pd.notna(sales_row['total_quantity']) else 0,
            '产品种类数': int(sales_row['unique_products']) if pd.notna(sales_row['unique_products']) else 0,
            '交易次数': int(sales_row['transaction_count']) if pd.notna(sales_row['transaction_count']) else 0,
            '最后销售日期': sales_row['last_sale_date'],
            '距上次销售天数': sales_row.get('days_since_last_sale', None),
            '销售活跃度': sales_row.get('销售活跃度', '无销售记录'),
            '2023欠款': float(debt_row['debt_2023']) if pd.notna(debt_row['debt_2023']) else 0.0,
            '2024欠款': float(debt_row['debt_2024']) if pd.notna(debt_row['debt_2024']) else 0.0,
            '2025欠款': float(debt_row['debt_2025']) if pd.notna(debt_row['debt_2025']) else 0.0,
            '欠款趋势': debt_row.get('debt_trend', '无欠款') if 'debt_trend' in debt_row else '无欠款'
        }
    
    def _create_debt_only_record(self, finance_id, customer_name, department, debt_row):
        """创建仅欠款记录"""
        return {
            '财务编号': finance_id,
            '客户名称': customer_name,
            '所属部门': department,
            '匹配类型': '仅欠款',
            '总销售额': 0.0,
            '总销售量': 0,
            '产品种类数': 0,
            '交易次数': 0,
            '最后销售日期': None,
            '距上次销售天数': None,
            '销售活跃度': '无销售记录',
            '2023欠款': float(debt_row['debt_2023']) if pd.notna(debt_row['debt_2023']) else 0.0,
            '2024欠款': float(debt_row['debt_2024']) if pd.notna(debt_row['debt_2024']) else 0.0,
            '2025欠款': float(debt_row['debt_2025']) if pd.notna(debt_row['debt_2025']) else 0.0,
            '欠款趋势': debt_row.get('debt_trend', '无欠款') if 'debt_trend' in debt_row else '无欠款'
        }
    
    def _create_sales_only_record(self, sales_row):
        """创建仅销售记录"""
        return {
            '财务编号': sales_row['finance_id'],
            '客户名称': sales_row['customer_name'],
            '所属部门': '未知',
            '匹配类型': '仅销售',
            '总销售额': float(sales_row['total_amount']) if pd.notna(sales_row['total_amount']) else 0.0,
            '总销售量': int(sales_row['total_quantity']) if pd.notna(sales_row['total_quantity']) else 0,
            '产品种类数': int(sales_row['unique_products']) if pd.notna(sales_row['unique_products']) else 0,
            '交易次数': int(sales_row['transaction_count']) if pd.notna(sales_row['transaction_count']) else 0,
            '最后销售日期': sales_row['last_sale_date'],
            '距上次销售天数': sales_row.get('days_since_last_sale', None),
            '销售活跃度': sales_row.get('销售活跃度', '无销售记录'),
            '2023欠款': 0.0,
            '2024欠款': 0.0,
            '2025欠款': 0.0,
            '欠款趋势': '无欠款'
        }
    
    def _classify_customer(self, row):
        """客户综合分类"""
        total_sales = row.get('总销售额', 0)
        debt_2025 = row.get('2025欠款', 0)
        debt_trend = row.get('欠款趋势', '')
        activity = row.get('销售活跃度', '无销售记录')
        department = row.get('所属部门', '未知')
        
        if department == '未知' and total_sales == 0 and debt_2025 == 0:
            return '数据不完整'
        
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
            
            debt_ratio = row.get('欠销比', 0) / 100  # 转换为小数
            
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
    
    def _calculate_risk_score(self, row):
        """计算风险评分"""
        score = 100
        
        # 欠款因素
        debt_2025 = row.get('2025欠款', 0)
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
        debt_ratio = row.get('欠销比', 0) / 100  # 转换为小数
        if debt_ratio > 0.5:
            score -= 25
        elif debt_ratio > 0.2:
            score -= 15
        
        # 持续欠款
        if row.get('欠款趋势', '') == '持续欠款':
            score -= 10
        
        # 匹配类型惩罚
        match_type = row.get('匹配类型', '')
        if match_type == '仅欠款':
            score -= 5
        elif match_type == '仅销售':
            score += 5  # 无欠款是好事
        
        return max(0, min(100, int(score)))
    
    def _classify_risk(self, score):
        """风险等级分类"""
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
        """
        获取单个客户详情 - 优化搜索逻辑
        """
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
            # 策略1：先尝试按财务编号精确匹配
            finance_id_match = False
            matched_finance_ids = []
            
            import re
            finance_id_pattern = re.compile(r'^[\d\-]+$')
            
            if finance_id_pattern.match(search_term):
                # 按财务编号精确查询销售记录
                sales_query_finance = '''
                    SELECT 
                        year, month, day, 
                        customer_name, finance_id, sub_customer_name,
                        product_name, color, grade,
                        quantity, unit_price, amount,
                        ticket_number, production_line, record_date
                    FROM sales_records
                    WHERE finance_id = ?
                    ORDER BY year DESC, month DESC, day DESC
                '''
                sales_df_finance = pd.read_sql(sales_query_finance, conn, params=(search_term,))
                
                if not sales_df_finance.empty:
                    finance_id_match = True
                    matched_finance_ids = [search_term]
                    
                    # 标准化搜索词，用于后续匹配
                    standard_search = self._standardize_customer_name(search_term)
            
            if finance_id_match:
                # 财务编号匹配成功
                sales_df = sales_df_finance
                
                # 查询这些财务编号对应的欠款记录
                if matched_finance_ids:
                    placeholders = ','.join(['?'] * len(matched_finance_ids))
                    debt_query = f'''
                        SELECT 
                            department,
                            finance_id,
                            customer_name,
                            debt_2023,
                            debt_2024,
                            debt_2025
                        FROM unified_debt
                        WHERE finance_id IN ({placeholders})
                        ORDER BY department
                    '''
                    debt_df = pd.read_sql(debt_query, conn, params=tuple(matched_finance_ids))
                else:
                    debt_df = pd.DataFrame()
                
                # 获取匹配的客户名称
                matched_customer_names = sales_df['customer_name'].unique().tolist() if not sales_df.empty else []
                if not debt_df.empty:
                    debt_customer_names = debt_df['customer_name'].unique().tolist()
                    matched_customer_names = list(set(matched_customer_names + debt_customer_names))
            else:
                # 策略2：按客户名称关键词匹配
                # 标准化搜索词
                standard_search = self._standardize_customer_name(search_term)
                search_keywords = self._extract_keywords(search_term)
                
                # 获取所有唯一的客户名称
                all_customers_query = '''
                    SELECT DISTINCT customer_name 
                    FROM sales_records 
                    UNION 
                    SELECT DISTINCT customer_name 
                    FROM unified_debt
                '''
                all_customers_df = pd.read_sql(all_customers_query, conn)
                
                # 找出匹配的客户名称
                matched_names = []
                if not all_customers_df.empty:
                    for customer_name in all_customers_df['customer_name'].dropna():
                        if isinstance(customer_name, str):
                            # 标准化对比
                            standard_name = self._standardize_customer_name(customer_name)
                            
                            # 1. 完全匹配
                            if standard_search == standard_name:
                                matched_names.append(customer_name)
                            # 2. 包含匹配
                            elif standard_search and standard_search in standard_name:
                                matched_names.append(customer_name)
                            # 3. 被包含匹配
                            elif standard_name and standard_name in standard_search:
                                matched_names.append(customer_name)
                            # 4. 关键词匹配
                            elif search_keywords:
                                customer_keywords = self._extract_keywords(customer_name)
                                common_keywords = set(search_keywords) & set(customer_keywords)
                                if common_keywords:
                                    matched_names.append(customer_name)
                
                # 去重
                matched_names = list(set(matched_names))
                
                if not matched_names:
                    # 没有匹配到任何客户
                    return {
                        'sales_records': pd.DataFrame(),
                        'debt_records': pd.DataFrame(),
                        'total_sales': 0,
                        'recent_transactions': 0,
                        'finance_ids': [],
                        'matched_customer_names': []
                    }
                
                # 查询这些匹配客户的销售记录
                if matched_names:
                    placeholders = ','.join(['?'] * len(matched_names))
                    sales_query = f'''
                        SELECT 
                            year, month, day, 
                            customer_name, finance_id, sub_customer_name,
                            product_name, color, grade,
                            quantity, unit_price, amount,
                            ticket_number, production_line, record_date
                        FROM sales_records
                        WHERE customer_name IN ({placeholders})
                        ORDER BY year DESC, month DESC, day DESC
                    '''
                    sales_df = pd.read_sql(sales_query, conn, params=tuple(matched_names))
                    
                    # 查询这些匹配客户的欠款记录
                    debt_query = f'''
                        SELECT 
                            department,
                            finance_id,
                            customer_name,
                            debt_2023,
                            debt_2024,
                            debt_2025
                        FROM unified_debt
                        WHERE customer_name IN ({placeholders})
                        ORDER BY department
                    '''
                    debt_df = pd.read_sql(debt_query, conn, params=tuple(matched_names))
                    
                    # 提取匹配的财务编号
                    matched_finance_ids = sales_df['finance_id'].unique().tolist() if not sales_df.empty else []
                    if not debt_df.empty:
                        debt_finance_ids = debt_df['finance_id'].unique().tolist()
                        matched_finance_ids = list(set(matched_finance_ids + debt_finance_ids))
                else:
                    sales_df = pd.DataFrame()
                    debt_df = pd.DataFrame()
                    matched_finance_ids = []
            
            # 计算统计信息
            total_sales = sales_df['amount'].sum() if not sales_df.empty else 0
            recent_transactions = 0
            if not sales_df.empty and 'year' in sales_df.columns:
                current_year = 25
                recent_transactions = len(sales_df[sales_df['year'] == current_year])
            
            # 获取最终匹配的客户名称
            final_matched_names = []
            if not sales_df.empty:
                final_matched_names.extend(sales_df['customer_name'].unique().tolist())
            if not debt_df.empty:
                final_matched_names.extend(debt_df['customer_name'].unique().tolist())
            
            final_matched_names = list(set(final_matched_names))
            
            return {
                'sales_records': sales_df,
                'debt_records': debt_df,
                'total_sales': total_sales,
                'recent_transactions': recent_transactions,
                'finance_ids': matched_finance_ids,
                'matched_customer_names': final_matched_names
            }
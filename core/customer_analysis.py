import pandas as pd
import numpy as np
from core.database import get_connection, get_all_debt_data
from datetime import datetime, timedelta

class SalesDebtIntegrationService:
    def __init__(self):
        pass
    
    def get_integrated_customer_analysis(self, current_year=25):
        """获取综合客户分析数据 - 优化版分类模型"""
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
                
                # 添加活跃度分类（优化版）
                sales_df['last_sale_date'] = pd.to_datetime(sales_df['last_sale_date'], errors='coerce')
                current_date = pd.Timestamp.now()
                sales_df['days_since_last_sale'] = (current_date - sales_df['last_sale_date']).dt.days
                
                def classify_activity(days):
                    if pd.isna(days):
                        return '无销售记录'
                    elif days <= 30:
                        return '活跃客户(30天内)'
                    elif days <= 90:
                        return '一般活跃(90天内)'
                    elif days <= 180:
                        return '低活跃(180天内)'
                    elif days <= 365:
                        return '休眠客户(1年内)'
                    else:
                        return '无销售记录'  # 统一为无销售记录
                
                sales_df['销售活跃度'] = sales_df['days_since_last_sale'].apply(classify_activity)
                
                # 获取年度销售数据
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
        
        # 3. 基本数据清洗
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
            print(f"清洗后销售数据: {len(sales_df)} 条")
        
        if not debt_df.empty:
            debt_df = clean_data(debt_df)
            print(f"清洗后欠款数据: {len(debt_df)} 条")
        
        # 4. 建立销售数据索引
        sales_index = {}
        
        if not sales_df.empty:
            for idx, row in sales_df.iterrows():
                finance_id = row.get('finance_id_clean', '')
                department = row.get('department_clean', '')
                
                if not finance_id:
                    print(f"销售记录 {idx} 财务编号为空: {row['customer_name']}")
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
                        'customer_names': [row['customer_name_clean']],
                        'original_names': [row['customer_name']],
                        'original_finance_id': row['finance_id']
                    }
                else:
                    # 如果已存在，合并数据
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
                        sales_index[key]['original_names'].append(row['customer_name'])
        
        print(f"建立销售索引: {len(sales_index)} 个唯一键")
        
        # 5. 匹配逻辑 - 严格一对一匹配
        matched_records = []
        unmatched_sales_keys = []  # 记录未匹配的销售记录键
        unmatched_debt_records = []  # 记录未匹配的欠款记录
        
        for idx, debt_row in debt_df.iterrows():
            finance_id = debt_row.get('finance_id_clean', '')
            department = debt_row.get('department_clean', '')
            original_finance_id = debt_row.get('finance_id', '')
            original_customer_name = debt_row.get('customer_name', '')
            
            if not finance_id:
                # 财务编号为空，只能创建欠款记录
                print(f"欠款记录 {idx} 财务编号为空: {original_customer_name}")
                unmatched_debt_records.append({
                    'type': '财务编号为空',
                    'original_finance_id': original_finance_id,
                    'original_customer_name': original_customer_name,
                    'department': department,
                    'debt_2025': float(debt_row.get('debt_2025', 0)) if pd.notna(debt_row.get('debt_2025')) else 0.0
                })
                
                matched_records.append({
                    '财务编号': original_finance_id,
                    '客户名称': original_customer_name,
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
                        print(f"✅ 精确匹配: {original_finance_id}|{department} - {debt_customer_name}")
                    else:
                        # 否则使用第一个销售客户名称
                        best_customer_match = sales_match['customer_names'][0]
                        print(f"🔄 名称差异匹配: {original_finance_id}|{department} - 欠款名称: {debt_customer_name}, 销售名称: {best_customer_match}")
                
                matched_records.append({
                    '财务编号': original_finance_id,
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
                if key in sales_index:
                    # 销售记录已被其他欠款记录匹配
                    print(f"❌ 销售记录已被占用: {key}")
                    unmatched_debt_records.append({
                        'type': '销售记录已被占用',
                        'original_finance_id': original_finance_id,
                        'original_customer_name': original_customer_name,
                        'department': department,
                        'debt_2025': float(debt_row.get('debt_2025', 0)) if pd.notna(debt_row.get('debt_2025')) else 0.0,
                        'sales_key': key
                    })
                else:
                    # 完全找不到销售记录
                    print(f"❌ 无匹配销售记录: {key} - {original_customer_name}")
                    unmatched_debt_records.append({
                        'type': '无销售记录',
                        'original_finance_id': original_finance_id,
                        'original_customer_name': original_customer_name,
                        'department': department,
                        'debt_2025': float(debt_row.get('debt_2025', 0)) if pd.notna(debt_row.get('debt_2025')) else 0.0,
                        'sales_key': key
                    })
                
                matched_records.append({
                    '财务编号': original_finance_id,
                    '客户名称': original_customer_name,
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
        
        # 6. 检查未匹配的销售记录（销售数据中有，但欠款数据中没有的）
        unmatched_sales_records = []
        unmatched_sales_total = 0
        
        for key, sales_data in sales_index.items():
            if not sales_data['matched']:
                unmatched_sales_keys.append(key)
                unmatched_sales_total += sales_data['total_amount']
                unmatched_sales_records.append({
                    'key': key,
                    'finance_id': sales_data['original_finance_id'],
                    'customer_names': sales_data['original_names'],
                    'department': key.split('|')[1],
                    'total_amount': sales_data['total_amount'],
                    'year_amount': sales_data['year_amount'],
                    'last_sale_date': sales_data['last_sale_date']
                })
        
        # 打印详细的匹配统计信息
        print("\n" + "="*80)
        print("数据匹配统计报告")
        print("="*80)
        
        print(f"\n📊 总体统计:")
        print(f"  欠款记录总数: {len(debt_df)}")
        print(f"  销售记录总数: {len(sales_df)}")
        print(f"  匹配后总记录数: {len(matched_records)}")
        
        print(f"\n✅ 匹配成功:")
        print(f"  有销售记录的客户: {len(matched_records) - len(unmatched_debt_records)}")
        
        print(f"\n❌ 未匹配的欠款记录 ({len(unmatched_debt_records)} 条):")
        for record in unmatched_debt_records[:10]:  # 只显示前10条
            print(f"  - 类型: {record['type']}, 财务编号: {record['original_finance_id']}, 客户: {record['original_customer_name']}, 部门: {record['department']}, 欠款: ¥{record['debt_2025']:,.2f}")
        if len(unmatched_debt_records) > 10:
            print(f"  ... 还有 {len(unmatched_debt_records) - 10} 条未显示")
        
        print(f"\n📈 未匹配的销售记录 ({len(unmatched_sales_records)} 条，总金额: ¥{unmatched_sales_total:,.2f}):")
        for record in unmatched_sales_records[:10]:  # 只显示前10条
            customer_name = record['customer_names'][0] if record['customer_names'] else '未知'
            print(f"  - 财务编号: {record['finance_id']}, 客户: {customer_name}, 部门: {record['department']}, 总销售额: ¥{record['total_amount']:,.2f}, 年度销售额: ¥{record['year_amount']:,.2f}")
        if len(unmatched_sales_records) > 10:
            print(f"  ... 还有 {len(unmatched_sales_records) - 10} 条未显示")
        
        print("\n🎯 匹配率分析:")
        if len(debt_df) > 0:
            match_rate = ((len(matched_records) - len(unmatched_debt_records)) / len(debt_df)) * 100
            print(f"  欠款记录匹配率: {match_rate:.1f}%")
        
        if len(sales_df) > 0:
            sales_match_rate = (len(sales_index) - len(unmatched_sales_records)) / len(sales_index) * 100
            print(f"  销售记录匹配率: {sales_match_rate:.1f}%")
        
        print("="*80 + "\n")
        
        # 7. 创建DataFrame并计算指标
        if not matched_records:
            return pd.DataFrame()
        
        merged_df = pd.DataFrame(matched_records)
        print(f"合并后数据: {len(merged_df)} 条记录")
        
        # 添加年度欠款列
        year_debt_column = f'20{current_year}欠款'
        if current_year == 25:
            merged_df[year_debt_column] = merged_df['2025欠款']
        elif current_year == 24:
            merged_df[year_debt_column] = merged_df['2024欠款']
        elif current_year == 23:
            merged_df[year_debt_column] = merged_df['2023欠款']
        
        # 计算欠销比（使用对应年份的销售额和欠款）
        year_sales_column = f'20{current_year}销售额'
        merged_df['欠销比'] = merged_df.apply(
            lambda row: (row[year_debt_column] / row[year_sales_column] * 100) if row[year_sales_column] > 0 else 0,
            axis=1
        )
        
        # 客户分类和风险评分（优化版）
        merged_df['客户综合等级'] = merged_df.apply(self._classify_customer_optimized, axis=1, current_year=current_year)
        merged_df['风险评分'] = merged_df.apply(self._calculate_risk_score_optimized, axis=1, current_year=current_year)
        
        return merged_df
    
    def _classify_customer_optimized(self, row, current_year=25):
        """优化版客户分类逻辑"""
        year_sales_column = f'20{current_year}销售额'
        year_debt_column = f'20{current_year}欠款'
        
        year_sales = row.get(year_sales_column, 0)
        year_debt = row.get(year_debt_column, 0)
        activity = row.get('销售活跃度', '无销售记录')
        debt_ratio = row.get('欠销比', 0) / 100
        
        # 无销售记录且有欠款 - 最高风险
        if year_sales == 0 and year_debt > 0:
            return 'E2-无销售高欠款'
        
        # 有销售记录的情况
        if year_debt == 0:
            # 无欠款客户
            if year_sales >= 5_000_000:  # 500万以上
                if activity in ['活跃客户(30天内)', '一般活跃(90天内)']:
                    return 'A1-核心大客户'
                else:
                    return 'B1-良好稳定客户'
            elif year_sales >= 500_000:  # 50万以上
                if activity in ['活跃客户(30天内)', '一般活跃(90天内)']:
                    return 'A2-优质活跃客户'
                else:
                    return 'B2-一般活跃客户'
            elif year_sales > 0:
                if activity in ['活跃客户(30天内)', '一般活跃(90天内)']:
                    return 'C1-需关注客户'
                else:
                    return 'C3-低活跃客户'
            else:
                return 'C1-需关注客户'
        else:
            # 有欠款客户
            if debt_ratio <= 0.2:  # 欠销比 ≤ 20%
                if activity in ['活跃客户(30天内)', '一般活跃(90天内)']:
                    return 'B3-低风险欠款客户'
                else:
                    return 'C2-中风险欠款客户'
            elif debt_ratio <= 0.5:  # 20% < 欠销比 ≤ 50%
                return 'C2-中风险欠款客户'
            elif debt_ratio <= 1.0:  # 50% < 欠销比 ≤ 100%
                return 'D1-高风险欠款客户'
            else:  # 欠销比 > 100%
                return 'E1-严重风险客户'
    
    def _calculate_risk_score_optimized(self, row, current_year=25):
        """优化版风险评分计算"""
        year_sales_column = f'20{current_year}销售额'
        year_debt_column = f'20{current_year}欠款'
        
        year_sales = row.get(year_sales_column, 0)
        year_debt = row.get(year_debt_column, 0)
        activity = row.get('销售活跃度', '无销售记录')
        
        score = 100
        
        # 1. 欠销比扣分（核心权重）
        if year_sales > 0:
            debt_ratio = year_debt / year_sales
            if debt_ratio <= 0.2:
                score -= 0  # 不扣分
            elif debt_ratio <= 0.5:
                score -= (debt_ratio - 0.2) * 200  # 线性扣分，最多扣60分
            else:
                score -= 60 + (debt_ratio - 0.5) * 400  # 严厉扣分
        elif year_debt > 0:
            # 无销售但有欠款，直接扣100分
            score -= 100
        
        # 2. 活跃度扣分
        activity_penalty = {
            '活跃客户(30天内)': 0,
            '一般活跃(90天内)': 5,
            '低活跃(180天内)': 10,
            '休眠客户(1年内)': 20,
            '无销售记录': 30
        }
        score -= activity_penalty.get(activity, 30)
        
        # 3. 欠款规模扣分
        if year_debt > 1_000_000:  # 100万以上
            score -= 20
        elif year_debt > 500_000:  # 50-100万
            score -= 10
        elif year_debt > 100_000:  # 10-50万
            score -= 5
        
        # 4. 销售规模加分（上限100分）
        if year_sales >= 5_000_000:  # 500万以上
            score += 15
        elif year_sales >= 1_000_000:  # 100-500万
            score += 10
        elif year_sales >= 500_000:  # 50-100万
            score += 5
        
        # 确保分数在0-100范围内
        return max(0, min(100, round(score)))
    
    def get_summary_statistics(self, year):
        """获取指定年份的统计数据"""
        try:
            integrated_df = self.get_integrated_customer_analysis(year)
            
            if integrated_df.empty:
                return {}
            
            year_debt_column = f'20{year}欠款'
            total_debt = integrated_df[year_debt_column].sum() if year_debt_column in integrated_df.columns else 0
            
            # 计算高风险客户数量
            high_risk_count = 0
            if '风险评分' in integrated_df.columns:
                high_risk_count = len(integrated_df[integrated_df['风险评分'] < 40])
            
            # 计算平均风险评分
            avg_score = integrated_df['风险评分'].mean() if '风险评分' in integrated_df.columns else 0
            
            return {
                '总欠款': total_debt,
                '高风险客户数量': high_risk_count,
                '平均风险评分': avg_score
            }
        except:
            return {}
    
    def get_customer_detail(self, search_term, year=25):
        """单客户详情查询 - 支持年份筛选"""
        if not search_term or str(search_term).strip() == '':
            return {
                'sales_records': pd.DataFrame(),
                'debt_records': pd.DataFrame(),
                'year_sales': 0,
                'year_transactions': 0,
                'finance_ids': [],
                'matched_customer_names': [],
                'risk_score': 0
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
            
            # 计算指定年份的销售额和交易次数
            year_sales = 0
            year_transactions = 0
            
            if not sales_df.empty and 'year' in sales_df.columns and 'amount' in sales_df.columns:
                year_sales_df = sales_df[sales_df['year'] == year]
                year_sales = year_sales_df['amount'].sum() if not year_sales_df.empty else 0
                year_transactions = len(year_sales_df)
            
            # 计算风险评分
            risk_score = 0
            if not sales_df.empty or not debt_df.empty:
                # 模拟计算风险评分
                total_sales = sales_df['amount'].sum() if not sales_df.empty else 0
                
                # 获取指定年份的欠款
                year_debt = 0
                if not debt_df.empty:
                    if year == 25 and 'debt_2025' in debt_df.columns:
                        year_debt = debt_df['debt_2025'].sum()
                    elif year == 24 and 'debt_2024' in debt_df.columns:
                        year_debt = debt_df['debt_2024'].sum()
                    elif year == 23 and 'debt_2023' in debt_df.columns:
                        year_debt = debt_df['debt_2023'].sum()
                
                # 计算活跃度
                activity = '无销售记录'
                if not sales_df.empty and 'record_date' in sales_df.columns:
                    latest_date = pd.to_datetime(sales_df['record_date'].max(), errors='coerce')
                    if pd.notna(latest_date):
                        days_diff = (pd.Timestamp.now() - latest_date).days
                        if days_diff <= 30:
                            activity = '活跃客户(30天内)'
                        elif days_diff <= 90:
                            activity = '一般活跃(90天内)'
                        elif days_diff <= 180:
                            activity = '低活跃(180天内)'
                        elif days_diff <= 365:
                            activity = '休眠客户(1年内)'
                
                # 计算风险评分
                score = 100
                
                # 欠销比扣分
                if year_sales > 0:
                    debt_ratio = year_debt / year_sales
                    if debt_ratio <= 0.2:
                        score -= 0
                    elif debt_ratio <= 0.5:
                        score -= (debt_ratio - 0.2) * 200
                    else:
                        score -= 60 + (debt_ratio - 0.5) * 400
                elif year_debt > 0:
                    score -= 100
                
                # 活跃度扣分
                activity_penalty = {
                    '活跃客户(30天内)': 0,
                    '一般活跃(90天内)': 5,
                    '低活跃(180天内)': 10,
                    '休眠客户(1年内)': 20,
                    '无销售记录': 30
                }
                score -= activity_penalty.get(activity, 30)
                
                # 销售规模加分
                if year_sales >= 5_000_000:
                    score += 15
                elif year_sales >= 1_000_000:
                    score += 10
                elif year_sales >= 500_000:
                    score += 5
                
                risk_score = max(0, min(100, round(score)))
            
            return {
                'sales_records': sales_df,
                'debt_records': debt_df,
                'year_sales': year_sales,
                'year_transactions': year_transactions,
                'finance_ids': finance_ids,
                'matched_customer_names': matched_customer_names,
                'risk_score': risk_score
            }
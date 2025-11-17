import pandas as pd
import os
from core.database import get_connection

class AnalysisService:
    def __init__(self):
        pass

    # ==========================
    # 🔹 通用查询方法保持不变
    # ==========================
    def get_all_sales_records(self, customer_filter=None, color_filter=None, grade_filter=None):
        """获取所有销售记录"""
        with get_connection() as conn:
            query = '''
                SELECT 
                    customer_name,
                    finance_id,
                    sub_customer_name,
                    color,
                    grade,
                    quantity,
                    unit_price,
                    amount,
                    ticket_number,
                    remark,
                    production_line,
                    record_date
                FROM sales_records
                WHERE 1=1
            '''
            
            params = []
            if customer_filter and customer_filter.strip():
                query += " AND (customer_name LIKE ? OR sub_customer_name LIKE ?)"
                params.extend([f'%{customer_filter}%', f'%{customer_filter}%'])
            
            if color_filter and color_filter.strip():
                query += " AND color LIKE ?"
                params.append(f'%{color_filter}%')
                
            if grade_filter and grade_filter.strip():
                query += " AND grade LIKE ?"
                params.append(f'%{grade_filter}%')
            
            query += " ORDER BY record_date DESC, customer_name"
            df = pd.read_sql_query(query, conn, params=params)
            return self._format_dataframe(df)

    def get_latest_prices(self, customer_filter=None, color_filter=None, grade_filter=None):
        """获取最新价格 - 基于最新销售记录"""
        with get_connection() as conn:
            query = '''
                WITH LatestSales AS (
                    SELECT 
                        customer_name,
                        finance_id,
                        sub_customer_name,
                        color,
                        grade,
                        unit_price,
                        quantity,
                        amount,
                        record_date,
                        ROW_NUMBER() OVER (
                            PARTITION BY customer_name, finance_id, sub_customer_name, color, grade 
                            ORDER BY record_date DESC
                        ) as rn
                    FROM sales_records
                    WHERE unit_price > 0
                )
                SELECT 
                    customer_name,
                    finance_id,
                    sub_customer_name,
                    color,
                    grade,
                    unit_price,
                    quantity,
                    amount,
                    record_date
                FROM LatestSales
                WHERE rn = 1
            '''
            
            params = []
            conditions = []
            
            if customer_filter and customer_filter.strip():
                conditions.append("(customer_name LIKE ? OR sub_customer_name LIKE ?)")
                params.extend([f'%{customer_filter}%', f'%{customer_filter}%'])
            
            if color_filter and color_filter.strip():
                conditions.append("color LIKE ?")
                params.append(f'%{color_filter}%')
                
            if grade_filter and grade_filter.strip():
                conditions.append("grade LIKE ?")
                params.append(f'%{grade_filter}%')
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " ORDER BY customer_name, sub_customer_name, color"
            df = pd.read_sql_query(query, conn, params=params)
            return self._format_dataframe(df)

    def get_customers(self):
        """获取客户列表（仅活跃）"""
        with get_connection() as conn:
            df = pd.read_sql_query('''
                SELECT DISTINCT 
                    customer_name,
                    finance_id
                FROM customers 
                WHERE is_active = TRUE 
                ORDER BY customer_name
            ''', conn)
            return df

    def get_products(self):
        """获取产品列表"""
        with get_connection() as conn:
            df = pd.read_sql_query('''
                SELECT DISTINCT 
                    color,
                    grade
                FROM sales_records 
                WHERE color IS NOT NULL AND color != ''
                ORDER BY color, grade
            ''', conn)
            return df

    # ==========================
    # 🔹 重点：统计逻辑优化
    # ==========================
    def get_statistics(self):
        """统一获取统计信息"""
        stats = {}
        with get_connection() as conn:
            try:
                # 唯一主客户 customer_name,finance_id
                main_customers = pd.read_sql_query('''
                    SELECT COUNT(*) AS count
                    FROM (
                        SELECT DISTINCT customer_name, finance_id
                        FROM customers
                        WHERE customer_name IS NOT NULL
                            AND finance_id IS NOT NULL
                    ) AS unique_customers
                ''', conn)
                stats['main_customers'] = main_customers.iloc[0]['count'] if not main_customers.empty else 0


                # 总客户数（所有子客户数合）
                sub_customers = pd.read_sql_query('''
                    SELECT COUNT(*) AS count
                    FROM (
                        SELECT DISTINCT customer_name, finance_id, sub_customer_name
                        FROM customers
                        WHERE customer_name IS NOT NULL
                            AND finance_id IS NOT NULL
                            AND sub_customer_name IS NOT NULL
                    ) AS unique_customers
                ''', conn)
                stats['sub_customers'] = sub_customers.iloc[0]['count'] if not sub_customers.empty else 0


                # 活跃客户数
                active_customers = pd.read_sql_query('SELECT COUNT(*) AS count FROM customers WHERE is_active = 1', conn)
                stats['active_customers'] = active_customers.iloc[0]['count'] if not active_customers.empty else 0

                # 唯一颜色数（非空）
                unique_colors = pd.read_sql_query('''
                    SELECT COUNT(DISTINCT color) AS count
                    FROM sales_records
                     WHERE color IS NOT NULL AND color != ''
                ''', conn)
                stats['unique_colors'] = unique_colors.iloc[0]['count'] if not unique_colors.empty else 0

                # 唯一产品数（非空）
                unique_products = pd.read_sql_query('''
                    SELECT COUNT(DISTINCT product_name) AS count
                    FROM sales_records
                    -- WHERE product_name IS NOT NULL AND product_name != ''
                ''', conn)
                stats['unique_products'] = unique_products.iloc[0]['count'] if not unique_products.empty else 0

                # 唯一等级
                stats['unique_grades'] = pd.read_sql_query(
                    "SELECT COUNT(DISTINCT grade) AS c FROM sales_records "
                    "-- WHERE grade != ''",
                    conn
                )['c'][0]

                # 最高价
                stats['max_price'] = pd.read_sql_query(
                    "SELECT MAX(unit_price) AS m FROM sales_records ",
                    conn
                )['m'][0]

                # 最低价
                stats['min_price'] = pd.read_sql_query(
                    "SELECT MIN(unit_price) AS m FROM sales_records WHERE unit_price > 0",
                    conn
                )['m'][0]

                # 销售汇总
                sales_summary = pd.read_sql_query('''
                    SELECT 
                        COUNT(*) AS total_records,
                        SUM(quantity) AS total_quantity,
                        SUM(amount) AS total_amount,
                        AVG(unit_price) AS avg_price
                    FROM sales_records
                    WHERE unit_price > 0
                ''', conn)
                if not sales_summary.empty:
                    for key, value in sales_summary.iloc[0].to_dict().items():
                        stats[key] = float(value) if pd.notna(value) else 0

                # 数据库大小
                try:
                    db_size = os.path.getsize("ceramic_prices.db") / 1024 / 1024
                except:
                    db_size = 0
                stats['db_size_mb'] = round(db_size, 2)

            except Exception as e:
                print(f"获取统计信息失败: {e}")
                stats = {k: 0 for k in [
                    'main_customers', 'sub_customers', 'total_customers', 'active_customers',
                    'unique_colors', 'unique_products', 'total_records', 'total_quantity',
                    'total_amount', 'avg_price', 'db_size_mb'
                ]}

        return stats

    def get_price_trend(self, finance_id, color, grade=None, sub_customer_name=None):
        """获取价格趋势"""
        with get_connection() as conn:
            query = '''
                SELECT 
                    strftime('%Y-%m', record_date) as month,
                    AVG(unit_price) as avg_price,
                    SUM(quantity) as total_quantity,
                    SUM(amount) as total_amount,
                    COUNT(*) as transaction_count
                FROM sales_records
                WHERE finance_id = ? AND color = ?
            '''
            
            params = [finance_id, color]
            
            if grade and grade.strip():
                query += " AND grade = ?"
                params.append(grade)
            else:
                query += " AND (grade IS NULL OR grade = '')"
                
            if sub_customer_name and sub_customer_name.strip():
                query += " AND sub_customer_name = ?"
                params.append(sub_customer_name)
            else:
                query += " AND (sub_customer_name IS NULL OR sub_customer_name = '')"
            
            query += " GROUP BY strftime('%Y-%m', record_date) ORDER BY month"
            
            try:
                df = pd.read_sql_query(query, conn, params=params)
                return self._format_dataframe(df)
            except Exception as e:
                print(f"获取价格趋势失败: {e}")
                return pd.DataFrame()

    def _format_dataframe(self, df):
        """格式化DataFrame"""
        if df.empty:
            return df
        numeric_columns = ['unit_price', 'quantity', 'amount', 'avg_price', 'total_quantity', 'total_amount']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
        return df

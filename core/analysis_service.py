import pandas as pd
from core.database import get_connection

class AnalysisService:
    def __init__(self):
        pass
    
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
        """获取客户列表"""
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
                ORDER BY color, grade
            ''', conn)
            return df
    
    def get_statistics(self):
        """获取统计信息"""
        with get_connection() as conn:
            stats = {}
            
            try:
                # 基础统计
                basic_stats = pd.read_sql_query('''
                    SELECT 
                        COUNT(*) as total_records,
                        COUNT(DISTINCT customer_name || finance_id) as unique_customers,
                        COUNT(DISTINCT color) as unique_colors,
                        COUNT(DISTINCT grade) as unique_grades,
                        SUM(quantity) as total_quantity,
                        SUM(amount) as total_amount,
                        AVG(unit_price) as avg_price,
                        MIN(unit_price) as min_price,
                        MAX(unit_price) as max_price
                    FROM sales_records
                    WHERE unit_price > 0
                ''', conn)
                
                if not basic_stats.empty:
                    for key, value in basic_stats.iloc[0].to_dict().items():
                        stats[key] = value if pd.notna(value) else 0
                
                # 子客户统计
                sub_customers = pd.read_sql_query('''
                    SELECT COUNT(DISTINCT sub_customer_name) as count 
                    FROM sales_records 
                    WHERE sub_customer_name != ''
                ''', conn)
                stats['sub_customers'] = sub_customers.iloc[0]['count'] if not sub_customers.empty else 0
                
                # 总客户数（包含重复）
                total_customers = pd.read_sql_query('''
                    SELECT COUNT(*) as count FROM customers
                ''', conn)
                stats['total_customers'] = total_customers.iloc[0]['count'] if not total_customers.empty else 0
                
            except Exception as e:
                print(f"获取统计信息失败: {e}")
                # 设置默认值
                stats = {
                    'total_records': 0,
                    'unique_customers': 0,
                    'unique_colors': 0,
                    'unique_grades': 0,
                    'total_quantity': 0,
                    'total_amount': 0,
                    'avg_price': 0,
                    'min_price': 0,
                    'max_price': 0,
                    'sub_customers': 0,
                    'total_customers': 0
                }
            
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
        """格式化数据框"""
        if df.empty:
            return df
        
        # 数值列格式化
        numeric_columns = ['unit_price', 'quantity', 'amount', 'avg_price', 'total_quantity', 'total_amount']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).round(2)
        
        return df
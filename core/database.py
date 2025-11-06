import sqlite3
import pandas as pd
import os
from datetime import datetime
from contextlib import contextmanager

@contextmanager
def get_connection():
    """数据库连接上下文管理器"""
    conn = sqlite3.connect('ceramic_prices.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """初始化数据库 - 适配新数据源结构"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 客户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                finance_id TEXT NOT NULL,
                sub_customer_name TEXT,
                region TEXT,
                contact_person TEXT,
                phone TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                UNIQUE(customer_name, finance_id, sub_customer_name)
            )
        ''')
        
        # 销售记录表 - 包含产品名称
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                finance_id TEXT NOT NULL,
                sub_customer_name TEXT,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                product_name TEXT,
                color TEXT NOT NULL,
                grade TEXT,
                quantity INTEGER,
                unit_price REAL,
                amount REAL,
                ticket_number TEXT,
                remark TEXT,
                production_line TEXT,
                record_date DATE,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_name, finance_id, sub_customer_name) 
                REFERENCES customers(customer_name, finance_id, sub_customer_name)
            )
        ''')
        
        # 价格变更历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_change_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sales_record_id INTEGER,
                old_price REAL,
                new_price REAL,
                change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                changed_by TEXT,
                change_reason TEXT,
                FOREIGN KEY (sales_record_id) REFERENCES sales_records (id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_finance_id ON sales_records(finance_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_color_grade ON sales_records(color, grade)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_record_date ON sales_records(record_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_product_name ON sales_records(product_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_customer_hierarchy ON customers(customer_name, finance_id, sub_customer_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sales_customer_product ON sales_records(finance_id, sub_customer_name, color, grade, record_date)')

        # 添加可能缺失的列
        columns_to_add = [
            ('customers', 'region', 'TEXT'),
            ('customers', 'contact_person', 'TEXT'),
            ('customers', 'phone', 'TEXT'),
            ('sales_records', 'product_name', 'TEXT')
        ]
        
        for table, column, col_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                print(f"成功添加列 {table}.{column}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"列 {table}.{column} 已存在")
                else:
                    print(f"列 {table}.{column} 添加失败: {e}")
        
        # 检查表结构
        try:
            tables = ['customers', 'sales_records']
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                print(f"表 {table} 的列: {column_names}")
        except Exception as e:
            print(f"检查表结构时出错: {e}")

def get_database_status():
    """获取数据库状态"""
    status = {}
    
    with get_connection() as conn:
        # 表记录数
        tables = ['customers', 'sales_records', 'price_change_history']
        for table in tables:
            try:
                count = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table}", conn).iloc[0]['count']
                status[f'{table}_count'] = count
            except Exception as e:
                print(f"获取表 {table} 记录数失败: {e}")
                status[f'{table}_count'] = 0
        
        # 产品统计
        try:
            product_stats = pd.read_sql_query('''
                SELECT 
                    COUNT(DISTINCT color) as unique_colors,
                    COUNT(DISTINCT product_name) as unique_products,
                    COUNT(DISTINCT color || product_name) as unique_combinations
                FROM sales_records
            ''', conn).iloc[0]
            status['unique_colors'] = product_stats['unique_colors']
            status['unique_products'] = product_stats['unique_products']
            status['unique_combinations'] = product_stats['unique_combinations']
        except Exception as e:
            print(f"获取产品统计失败: {e}")
            status.update({'unique_colors': 0, 'unique_products': 0, 'unique_combinations': 0})
        
        # 客户统计
        try:
            customers_count = pd.read_sql_query(
                "SELECT COUNT(DISTINCT customer_name || finance_id) as count FROM customers", 
                conn
            ).iloc[0]['count']
            status['customers_count'] = customers_count
        except Exception as e:
            print(f"获取客户统计失败: {e}")
            status['customers_count'] = 0
            
        # 销售记录统计
        try:
            sales_count = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM sales_records", 
                conn
            ).iloc[0]['count']
            status['sales_records_count'] = sales_count
            status['product_prices_count'] = sales_count
        except Exception as e:
            print(f"获取销售记录统计失败: {e}")
            status['sales_records_count'] = 0
            status['product_prices_count'] = 0
        
        # 数据库大小
        try:
            db_size = os.path.getsize('ceramic_prices.db') / 1024 / 1024  # 转换为MB
            status['db_size_mb'] = round(db_size, 2)
        except:
            status['db_size_mb'] = 0
    
    return status

def optimize_database():
    """优化数据库"""
    with get_connection() as conn:
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
    print("数据库优化完成")

def clear_database():
    """清空数据库"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sales_records')
        cursor.execute('DELETE FROM customers')
        cursor.execute('DELETE FROM price_change_history')
    print("数据库已清空")
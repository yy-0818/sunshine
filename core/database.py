import sqlite3
import pandas as pd
import os
from datetime import datetime
from contextlib import contextmanager
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库配置
DB_CONFIG = {
    'database': 'ceramic_prices.db',
    'timeout': 30,
    'detect_types': sqlite3.PARSE_DECLTYPES,
    'check_same_thread': False
}

@contextmanager
def get_connection():
    """数据库连接上下文管理器"""
    conn = sqlite3.connect(**DB_CONFIG)
    conn.row_factory = sqlite3.Row
    # 性能优化设置
    conn.execute("PRAGMA journal_mode=WAL")  # 写前日志，提高并发
    conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和数据安全
    conn.execute("PRAGMA cache_size=-64000")  # 增加缓存大小
    conn.execute("PRAGMA temp_store=MEMORY")  # 临时表存储在内存
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB内存映射
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"数据库操作失败: {e}")
        raise
    finally:
        conn.close()

def init_database():
    """初始化数据库"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 启用外键约束
        cursor.execute("PRAGMA foreign_keys=ON")
        
        # 使用批量执行减少IO操作
        table_scripts = [
            # 客户表
            '''
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
            ''',
            # 销售记录表
            '''
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
            ''',
            # 价格变更历史表
            '''
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
            '''
        ]

        for i, script in enumerate(table_scripts):
            try:
                cursor.execute(script)
                logger.info(f"成功创建表 {i+1}")
            except Exception as e:
                logger.error(f"创建表 {i+1} 时出错: {e}")
        
        # 批量创建索引
        index_scripts = [
            'CREATE INDEX IF NOT EXISTS idx_finance_id ON sales_records(finance_id)',
            'CREATE INDEX IF NOT EXISTS idx_color_grade ON sales_records(color, grade)',
            'CREATE INDEX IF NOT EXISTS idx_record_date ON sales_records(record_date)',
            'CREATE INDEX IF NOT EXISTS idx_product_name ON sales_records(product_name)',
            'CREATE INDEX IF NOT EXISTS idx_customer_hierarchy ON customers(customer_name, finance_id, sub_customer_name)',
            'CREATE INDEX IF NOT EXISTS idx_sales_customer_product ON sales_records(finance_id, sub_customer_name, color, grade, record_date)',
            'CREATE INDEX IF NOT EXISTS idx_sales_date_composite ON sales_records(year, month, day)',
            'CREATE INDEX IF NOT EXISTS idx_customer_finance ON customers(finance_id)',
            # 新增生产线相关索引
            'CREATE INDEX IF NOT EXISTS idx_production_line ON sales_records(production_line);',
            'CREATE INDEX IF NOT EXISTS idx_production_line_date ON sales_records(production_line, record_date);'
        ]
        
        for i, script in enumerate(index_scripts):
            try:
                cursor.execute(script)
                logger.info(f"成功创建索引 {i+1}")
            except Exception as e:
                logger.error(f"创建索引 {i+1} 时出错: {e}")
        
        # 优化表结构检查
        _check_and_alter_tables(cursor)
        
        logger.info("数据库初始化完成")

def _check_and_alter_tables(cursor):
    """检查并修改表结构"""
    columns_to_add = [
        ('customers', 'region', 'TEXT'),
        ('customers', 'contact_person', 'TEXT'),
        ('customers', 'phone', 'TEXT'),
        ('sales_records', 'product_name', 'TEXT'),
        ('sales_records', 'ticket_number', 'TEXT')
    ]
    
    for table, column, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            logger.info(f"成功添加列 {table}.{column}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.debug(f"列 {table}.{column} 已存在")
            else:
                logger.warning(f"列 {table}.{column} 添加失败: {e}")

def get_database_status(days_threshold=30):
    """获取数据库状态，统一统计关键指标
    Args:
        days_threshold: 活跃客户的时间阈值（天），默认30天内有过交易的客户为活跃客户
    """
    status = {}
    with get_connection() as conn:
        cursor = conn.cursor()

        # 销售记录数量
        cursor.execute("SELECT COUNT(*) FROM sales_records")
        status['sales_records_count'] = cursor.fetchone()[0]

        # 总销售金额
        cursor.execute("SELECT SUM(amount) FROM sales_records")
        total_sales = cursor.fetchone()[0]
        status['total_sales'] = total_sales if total_sales else 0

        # 价格变更记录数量
        cursor.execute("SELECT COUNT(*) FROM price_change_history")
        status['price_change_history_count'] = cursor.fetchone()[0]

        # 数据库大小
        try:
            db_size = os.path.getsize("ceramic_prices.db") / 1024 / 1024
        except:
            db_size = 0
        status['db_size_mb'] = round(db_size, 2)

        # 子客户数（唯一 customer_name, finance_id, sub_customer_name）
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT customer_name, finance_id, sub_customer_name
                FROM customers
                WHERE customer_name IS NOT NULL 
                    AND finance_id IS NOT NULL 
                    AND sub_customer_name IS NOT NULL
            ) AS unique_customers
        """)
        status['sub_customers'] = cursor.fetchone()[0]

        # 主客户数（唯一 customer_name,finance_id）
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT customer_name, finance_id
                FROM customers
                WHERE customer_name IS NOT NULL
                    AND finance_id IS NOT NULL
            ) AS unique_customers
        """)
        status['main_customers'] = cursor.fetchone()[0]

        # 产品颜色数
        cursor.execute("SELECT COUNT(DISTINCT color) FROM sales_records")
        status['unique_colors'] = cursor.fetchone()[0]

        # 产品数
        cursor.execute("SELECT COUNT(DISTINCT product_name) FROM sales_records")
        status['unique_products'] = cursor.fetchone()[0]

        # ================== 基于子客户的活跃客户统计 ==================
        
        # 最近N天内的活跃子客户数 - 使用子查询方式
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT customer_name, finance_id, sub_customer_name
                FROM sales_records 
                WHERE record_date >= date('now', ?)
            )
        """, (f'-{days_threshold} days',))
        status['active_sub_customers_recent'] = cursor.fetchone()[0]

        # 本月活跃子客户数
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT customer_name, finance_id, sub_customer_name
                FROM sales_records 
                WHERE strftime('%Y-%m', record_date) = strftime('%Y-%m', 'now')
            )
        """)
        status['active_sub_customers_this_month'] = cursor.fetchone()[0]

        # 上月活跃子客户数
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT customer_name, finance_id, sub_customer_name
                FROM sales_records 
                WHERE strftime('%Y-%m', record_date) = strftime('%Y-%m', 'now', '-1 month')
            )
        """)
        status['active_sub_customers_last_month'] = cursor.fetchone()[0]

        # 年度活跃子客户数
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT customer_name, finance_id, sub_customer_name
                FROM sales_records 
                WHERE strftime('%Y', record_date) = strftime('%Y', 'now')
            )
        """)
        status['active_sub_customers_this_year'] = cursor.fetchone()[0]

        # 计算活跃率
        total_sub_customers = status['sub_customers']
        if total_sub_customers > 0:
            status['active_sub_customers_rate_recent'] = round(status['active_sub_customers_recent'] / total_sub_customers * 100, 2)
            status['active_sub_customers_rate_this_month'] = round(status['active_sub_customers_this_month'] / total_sub_customers * 100, 2)
        else:
            status['active_sub_customers_rate_recent'] = 0
            status['active_sub_customers_rate_this_month'] = 0

    return status



def optimize_database():
    """优化数据库"""
    with get_connection() as conn:
        conn.execute("PRAGMA optimize")
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
    logger.info("数据库优化完成")

def clear_database():
    """清空数据库"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # 禁用外键约束以提高删除速度
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute('DELETE FROM price_change_history')
        cursor.execute('DELETE FROM sales_records')
        cursor.execute('DELETE FROM customers')
        # 重新启用外键约束
        cursor.execute("PRAGMA foreign_keys=ON")
    logger.info("数据库已清空")

def batch_insert_sales_records(records):
    """批量插入销售记录"""
    if not records:
        return
    
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany('''
                INSERT INTO sales_records 
                (customer_name, finance_id, sub_customer_name, year, month, day, 
                 product_name, color, grade, quantity, unit_price, amount, 
                 ticket_number, remark, production_line, record_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', records)
            logger.info(f"批量插入了 {len(records)} 条销售记录")
        except Exception as e:
            logger.error(f"批量插入失败: {e}")
            raise

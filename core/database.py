import sqlite3
import os
import pandas as pd
from contextlib import contextmanager
import logging
import hashlib

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
                department TEXT,  -- 新增部门字段
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
            ''',
            # 统一欠款表（合并一二期）
            '''
            CREATE TABLE IF NOT EXISTS unified_debt (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finance_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                department TEXT NOT NULL,  -- '一期' 或 '二期'
                debt_2023 REAL DEFAULT 0,
                debt_2024 REAL DEFAULT 0,
                debt_2025 REAL DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(finance_id, department)
            )
            ''',
            # 用户表（用于账号管理）
            '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',  -- 'admin', 'manager', 'user'
                full_name TEXT,
                department TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
            '''
        ]
        
        for i, script in enumerate(table_scripts):
            try:
                cursor.execute(script)
                logger.info(f"成功创建表 {i+1}")
            except Exception as e:
                logger.error(f"创建表 {i+1} 时出错: {e}")
                raise
        
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
            'CREATE INDEX IF NOT EXISTS idx_production_line ON sales_records(production_line)',
            'CREATE INDEX IF NOT EXISTS idx_production_line_date ON sales_records(production_line, record_date)',
            'CREATE INDEX IF NOT EXISTS idx_department ON sales_records(department)',  # 新增部门索引
            'CREATE INDEX IF NOT EXISTS idx_department_date ON sales_records(department, record_date)',  # 新增部门+日期索引
            # 欠款数据索引
            'CREATE INDEX IF NOT EXISTS idx_debt_finance_id ON unified_debt(finance_id)',
            'CREATE INDEX IF NOT EXISTS idx_debt_department ON unified_debt(department)',
            'CREATE INDEX IF NOT EXISTS idx_debt_finance_department ON unified_debt(finance_id, department)',
            # 账号索引
            'CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)',
            'CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)'
        ]
        
        for i, script in enumerate(index_scripts):
            try:
                cursor.execute(script)
                logger.info(f"成功创建索引 {i+1}")
            except Exception as e:
                logger.error(f"创建索引 {i+1} 时出错: {e}")
        
        # 检查并添加必要的列（修复检查逻辑）
        _check_and_alter_tables(cursor)
        # 创建默认用户
        _create_default_users(cursor)
        
        logger.info("数据库初始化完成")

def _check_and_alter_tables(cursor):
    """检查并修改表结构"""
    try:
        # 首先检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_records'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            logger.error("sales_records 表不存在，无法添加列")
            return
        
        # 检查哪些列不存在，然后添加
        columns_to_check = [
            ('sales_records', 'product_name', 'TEXT'),
            ('sales_records', 'ticket_number', 'TEXT'),
            ('sales_records', 'department', 'TEXT'),  # 新增部门字段
            ('customers', 'region', 'TEXT'),
            ('customers', 'contact_person', 'TEXT'),
            ('customers', 'phone', 'TEXT'),
            ('users', 'department', 'TEXT'),
            ('users', 'last_login', 'TIMESTAMP')
        ]
        
        for table, column, col_type in columns_to_check:
            try:
                # 首先检查表是否存在
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if cursor.fetchone() is None:
                    logger.warning(f"表 {table} 不存在，跳过添加列 {column}")
                    continue
                
                # 检查列是否已存在
                cursor.execute(f"PRAGMA table_info({table})")
                existing_columns = [info[1] for info in cursor.fetchall()]
                
                if column not in existing_columns:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    logger.info(f"成功添加列 {table}.{column}")
                else:
                    logger.debug(f"列 {table}.{column} 已存在")
                    
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    logger.debug(f"列 {table}.{column} 已存在")
                else:
                    logger.warning(f"处理列 {table}.{column} 时出错: {e}")
            except Exception as e:
                logger.warning(f"处理列 {table}.{column} 时发生未知错误: {e}")
                
    except Exception as e:
        logger.error(f"_check_and_alter_tables 执行失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")

def _create_default_users(cursor):
    """创建默认用户"""
    default_users = [
        ('admin', 'admin123', 'admin', '系统管理员', '销售部'),
        ('manager', 'manager123', 'manager', '部门经理', '销售部'),
        ('user', 'user123', 'user', '普通用户', '销售部')
    ]
    
    for username, password, role, full_name, department in default_users:
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute('''
                INSERT OR IGNORE INTO users 
                (username, password_hash, role, full_name, department)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, password_hash, role, full_name, department))
            logger.info(f"创建默认用户: {username}")
        except Exception as e:
            logger.debug(f"用户 {username} 已存在或创建失败: {e}")

def get_database_status(days_threshold=30):
    """获取数据库状态，统一统计关键指标"""
    status = {}
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # 首先检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_records'")
            if cursor.fetchone() is None:
                logger.warning("sales_records 表不存在，返回空状态")
                return {
                    'sales_records_count': 0,
                    'total_sales': 0,
                    'db_size_mb': 0,
                    'sub_customers': 0,
                    'main_customers': 0,
                    'unique_colors': 0,
                    'unique_products': 0,
                    'active_sub_customers_recent': 0,
                    'active_sub_customers_this_month': 0,
                    'active_sub_customers_last_month': 0,
                    'active_sub_customers_this_year': 0,
                    'active_sub_customers_rate_recent': 0,
                    'active_sub_customers_rate_this_month': 0,
                    'debt_count': 0,
                    'total_debt': 0,
                    'department_debt_stats': 0,
                }

            # 销售记录数量
            cursor.execute("SELECT COUNT(*) FROM sales_records")
            status['sales_records_count'] = cursor.fetchone()[0]

            # 总销售金额
            cursor.execute("SELECT SUM(amount) FROM sales_records")
            total_sales = cursor.fetchone()[0]
            status['total_sales'] = total_sales if total_sales else 0

            # 数据库大小
            try:
                db_size = os.path.getsize("ceramic_prices.db") / 1024 / 1024
            except:
                db_size = 0
            status['db_size_mb'] = round(db_size, 2)
            
            # 总客户or子客户数（唯一 customer_name, finance_id, sub_customer_name）
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

            # 统一欠款统计
            cursor.execute("SELECT COUNT(*) FROM unified_debt")
            status['debt_count'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(debt_2025) FROM unified_debt")
            total_debt = cursor.fetchone()[0]
            status['total_debt'] = total_debt if total_debt else 0
            
            # 按部门统计欠款
            cursor.execute("""
                SELECT 
                    department,
                    COUNT(*) as count,
                    SUM(debt_2025) as total_debt
                FROM unified_debt
                GROUP BY department
            """)
            dept_stats = cursor.fetchall()
            status['department_debt_stats'] = {}
            for dept, count, total in dept_stats:
                status['department_debt_stats'][dept] = {
                    'count': count,
                    'total_debt': total if total else 0
                }

            # 部门统计（新增）
            cursor.execute("SELECT COUNT(DISTINCT department) FROM sales_records WHERE department IS NOT NULL AND department != ''")
            status['unique_departments'] = cursor.fetchone()[0]
            
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return {}
    
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
        cursor.execute('DELETE FROM unified_debt')
        # 保留users表，但清空非默认用户
        cursor.execute("DELETE FROM users WHERE username NOT IN ('admin', 'manager', 'user')")
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

def import_debt_data(df, department):
    """导入欠款数据到统一欠款表"""
    success_count = 0
    error_count = 0
    
    if df.empty:
        return success_count, error_count
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unified_debt'")
        if not cursor.fetchone():
            logger.error("unified_debt表不存在，请先初始化数据库")
            return 0, len(df)
        
        for _, row in df.iterrows():
            try:
                # 确保列名正确
                finance_id = str(row['finance_id']) if 'finance_id' in row else ''
                customer_name = str(row['customer_name']) if 'customer_name' in row else f"未知客户_{finance_id}"
                debt_2023 = float(row['debt_2023']) if 'debt_2023' in row and pd.notna(row['debt_2023']) else 0.0
                debt_2024 = float(row['debt_2024']) if 'debt_2024' in row and pd.notna(row['debt_2024']) else 0.0
                debt_2025 = float(row['debt_2025']) if 'debt_2025' in row and pd.notna(row['debt_2025']) else 0.0
                
                cursor.execute('''
                    INSERT OR REPLACE INTO unified_debt 
                    (finance_id, customer_name, department, debt_2023, debt_2024, debt_2025)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    finance_id,
                    customer_name,
                    department,
                    debt_2023,
                    debt_2024,
                    debt_2025
                ))
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"导入欠款数据失败 {finance_id}: {e}")
    
    return success_count, error_count

def get_debt_by_department(department=None):
    """获取欠款数据，可指定部门"""
    with get_connection() as conn:
        if department:
            query = '''
                SELECT 
                    finance_id,
                    customer_name,
                    department,
                    debt_2023,
                    debt_2024,
                    debt_2025
                FROM unified_debt
                WHERE department = ?
                ORDER BY finance_id
            '''
            df = pd.read_sql(query, conn, params=(department,))
        else:
            query = '''
                SELECT 
                    finance_id,
                    customer_name,
                    department,
                    debt_2023,
                    debt_2024,
                    debt_2025
                FROM unified_debt
                ORDER BY department, finance_id
            '''
            df = pd.read_sql(query, conn)
        return df

def get_all_debt_data():
    """获取所有欠款数据"""
    return get_debt_by_department()

def get_sales_by_finance_id_and_name():
    """获取销售数据，按财务编号和客户名称分组"""
    with get_connection() as conn:
        query = '''
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
        df = pd.read_sql(query, conn)
        
        # 计算活跃度
        if not df.empty and 'last_sale_date' in df.columns:
            df['last_sale_date'] = pd.to_datetime(df['last_sale_date'], errors='coerce')
            current_date = pd.Timestamp.now()
            df['days_since_last_sale'] = (current_date - df['last_sale_date']).dt.days
            
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

def get_all_debt_data():
    """获取所有欠款数据"""
    with get_connection() as conn:
        query = '''
            SELECT 
                finance_id,
                customer_name,
                department,
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
            FROM unified_debt
            ORDER BY finance_id, department
        '''
        df = pd.read_sql(query, conn)
        return df

# 新增：用户认证相关函数
def verify_user_credentials(username, password):
    """验证用户凭据"""
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, role, full_name, department 
            FROM users 
            WHERE username = ? AND password_hash = ? AND is_active = TRUE
        ''', (username, password_hash))
        
        user = cursor.fetchone()
        return dict(user) if user else None

def get_user_by_username(username):
    """根据用户名获取用户信息"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, role, full_name, department, is_active
            FROM users 
            WHERE username = ?
        ''', (username,))
        
        user = cursor.fetchone()
        return dict(user) if user else None
import pandas as pd
import re
import warnings
from openpyxl import load_workbook
from datetime import datetime
import logging
from typing import Tuple, List, Dict, Any
import numpy as np

# 配置日志
logger = logging.getLogger(__name__)

class ImportService:
    def __init__(self):
        self.required_headers = ['客户名称', '编号', '子客户名称', '年', '月', '日', '颜色', '等级', '数量', '单价', '金额']
        
        # 预编译正则表达式
        self.clean_pattern = re.compile(r'\s+')
        self.punctuation_pattern = re.compile(r'^\s*[、，,]\s*')
        
        # 定义颜色和产品关键词
        self.colors = ['孔雀兰', '孔雀蓝', '钢灰', '橘红', '亚光黑', '大红', '深灰', '玫红', '蓝灰', '铁红', 
                      '古兰', '浅灰', '橘黄', '磨砂蓝', '亚光灰', '铁红', '九号蓝', '蓝灰']
        
        self.product_keywords = ['鑫阳光', '福迩家', '星月祥', '劲彩', '玖玉龙凤', '花脊座', '人字脊', 
                               '边瓦', '长沟瓦', '脊瓦', '大脊瓦', '短沟瓦']
        
        # 创建颜色匹配模式
        self.color_pattern = re.compile('|'.join(self.colors))
    
    def import_excel_data(self, file_path: str, user: str = "system", update_strategy: str = "update") -> Tuple[bool, str]:
        """
        导入Excel数据
        
        Args:
            file_path: 文件路径
            user: 操作用户
            update_strategy: 更新策略
                - "update": 更新模式（覆盖重复数据）
                - "append": 追加模式（只导入新数据）
                - "replace": 替换模式（清空后重新导入）
        """
        try:
            # 验证文件结构
            is_valid, message = self.validate_excel_structure(file_path)
            if not is_valid:
                return False, message
            
            # 使用更高效的数据读取方式
            df = self._read_excel_optimized(file_path)
            
            if df.empty:
                return False, "Excel文件中没有数据"
            
            # 数据清洗和转换
            df = self._clean_data_optimized(df)
            
            # 验证数据
            is_valid, message = self._validate_data(df)
            if not is_valid:
                return False, message
            
            # 根据策略导入数据库
            if update_strategy == "replace":
                return self._replace_import_to_database(df, user)
            elif update_strategy == "append":
                return self._append_import_to_database(df, user)
            else:  # update
                return self._update_import_to_database(df, user)
            
        except Exception as e:
            logger.error(f"数据导入失败: {str(e)}")
            return False, f"数据导入失败: {str(e)}"
    
    def _read_excel_optimized(self, file_path: str) -> pd.DataFrame:
        """优化Excel读取性能"""
        # 使用更兼容的dtype设置
        dtype_spec = {
            '客户名称': 'object',
            '编号': 'object',
            '子客户名称': 'object',
            '年': 'object',
            '月': 'object',
            '日': 'object',
            '颜色': 'object',
            '等级': 'object',
            '数量': 'object',
            '单价': 'object',
            '金额': 'object'
        }
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # 只读取必要的列
            usecols = lambda x: x in self.required_headers + ['产品名称', '票号', '票 号', '备注', '生产线']
            
            df = pd.read_excel(
                file_path, 
                engine='openpyxl',
                dtype=dtype_spec,
                usecols=usecols,
                na_values=['', ' ', 'NULL', 'null', 'None'],
                keep_default_na=True
            )
        
        return df
    
    def validate_excel_structure(self, file_path: str) -> Tuple[bool, str]:
        """验证Excel文件结构"""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                wb = load_workbook(file_path, data_only=True, read_only=True)
                sheet = wb.active
                
                # 只读取第一行
                headers = []
                for cell in sheet[1]:
                    if cell.value is not None:
                        headers.append(str(cell.value).strip())
                
                wb.close()
                
                missing_headers = [h for h in self.required_headers if h not in headers]
                
                if missing_headers:
                    return False, f"缺少必要的表头: {missing_headers}"
                
                return True, "文件结构正确"
            
        except Exception as e:
            return False, f"文件检查失败: {str(e)}"
    
    def _clean_data_optimized(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        # 首先拆分颜色列
        if '颜色' in df.columns:
            df = self._split_color_column_optimized(df)
        
        # 列名映射
        column_mapping = {
            '客户名称': 'customer_name',
            '编号': 'finance_id',
            '子客户名称': 'sub_customer_name',
            '年': 'year',
            '月': 'month',
            '日': 'day',
            '产品名称': 'product_name',
            '颜色': 'color',
            '等级': 'grade',
            '数量': 'quantity',
            '单价': 'unit_price',
            '金额': 'amount',
            '票 号': 'ticket_number',
            '票号': 'ticket_number',
            '备注': 'remark',
            '生产线': 'production_line'
        }
        
        # 批量重命名
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=existing_columns)
        
        # 使用安全的空值处理方法
        string_columns = ['sub_customer_name', 'product_name', 'grade', 'ticket_number', 'remark', 'production_line', 'color']
        for col in string_columns:
            if col in df.columns:
                # 使用安全的转换方法，避免 pd.NA
                df[col] = df[col].astype(str).replace('nan', '').replace('None', '').replace('<NA>', '')
        
        # 处理 customer_name 和 finance_id
        if 'customer_name' in df.columns:
            df['customer_name'] = df['customer_name'].astype(str).replace('nan', '').replace('None', '')
        if 'finance_id' in df.columns:
            df['finance_id'] = df['finance_id'].astype(str).replace('nan', '').replace('None', '')
        
        # 数值列处理 - 使用更安全的方法
        numeric_columns = ['year', 'month', 'day', 'quantity', 'unit_price', 'amount']
        for col in numeric_columns:
            if col in df.columns:
                # 先转换为字符串，再处理空值，最后转换为数值
                df[col] = df[col].astype(str).replace('nan', '0').replace('None', '0').replace('<NA>', '0')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 优化日期构建
        df['record_date'] = self._build_record_date_vectorized(df)

        # 过滤掉金额为0的记录
        # df = df[df['amount'] > 0]

        # 创建唯一标识符，用于数据去重和更新
        df['data_key'] = df.apply(
            lambda row: f"{row['customer_name']}_{row['finance_id']}_{row['sub_customer_name']}_"
                       f"{row['year']}_{row['month']}_{row['day']}_{row['product_name']}_"
                       f"{row['color']}_{row['grade']}", 
            axis=1
        )
        
        return df
    
    def _build_record_date_vectorized(self, df: pd.DataFrame) -> pd.Series:
        """向量化构建记录日期"""
        def build_date(row):
            try:
                year_val = float(row['year']) if pd.notna(row['year']) else 0
                month_val = float(row['month']) if pd.notna(row['month']) else 0
                day_val = float(row['day']) if pd.notna(row['day']) else 0
                
                if year_val > 0 and month_val > 0 and day_val > 0:
                    return f"20{int(year_val)}-{int(month_val):02d}-{int(day_val):02d}"
                return datetime.now().strftime('%Y-%m-%d')
            except:
                return datetime.now().strftime('%Y-%m-%d')
        
        return df.apply(build_date, axis=1)
    
    def _split_color_column_optimized(self, df: pd.DataFrame) -> pd.DataFrame:
        """优化颜色列拆分"""
        def extract_product_and_color_optimized(text):
            if pd.isna(text) or text == "" or text == "nan" or text == "None":
                return "", ""
            
            text_str = str(text).strip()
            
            # 处理特殊情况
            if text_str.endswith('壹'):
                text_str = text_str[:-1]
            
            # 使用预编译的正则表达式匹配颜色
            color_match = self.color_pattern.search(text_str)
            if color_match:
                color = color_match.group()
                product_name = self.color_pattern.sub('', text_str)
                product_name = self.clean_pattern.sub(' ', product_name).strip()
                product_name = self.punctuation_pattern.sub('', product_name)
                # 如果拆分后颜色为空，返回原始文本作为产品名称
                if not color.strip():
                    return text_str, ""
                return product_name, color
            
            # 基于产品关键词拆分
            for keyword in self.product_keywords:
                if keyword in text_str:
                    product_name = keyword
                    color = text_str.replace(keyword, '').strip()
                    # 如果拆分后颜色为空，返回原始文本作为产品名称
                    if not color.strip():
                        return text_str, ""
                    return product_name, color
            
            # 简单的空格拆分
            parts = text_str.split()
            if len(parts) >= 2:
                color_part = parts[-1]
                product_name = ' '.join(parts[:-1])
                # 验证颜色部分是否真的是颜色
                if self.color_pattern.search(color_part) or len(color_part) <= 4:  # 颜色名称不会太长
                    return product_name, color_part
            
            return text_str, ""
        
        # 应用拆分函数
        split_results = df['颜色'].apply(extract_product_and_color_optimized)
        
        # 批量分配结果
        df = df.copy()
        df['产品名称'] = split_results.str[0]
        df['颜色'] = split_results.str[1]
        
        return df
    
    def _validate_data(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """数据验证"""
        required_columns = ['customer_name'] 
        for col in required_columns:
            if col not in df.columns:
                return False, f"缺少必要的列: {col}"
            
            # 检查空值
            if df[col].isnull().any():
                return False, f"列 '{col}' 中存在空值，请检查数据"
            
            # 检查转换后的空字符串
            if (df[col].astype(str).str.strip() == '').any():
                return False, f"列 '{col}' 中存在空值，请检查数据"
        
        return True, "数据验证通过"
    
    def _safe_convert_value(self, value, default=None):
        """安全转换值，避免 pd.NA 问题"""
        if pd.isna(value) or value is None:
            return default
        
        try:
            # 如果是字符串类型的空值
            if isinstance(value, str) and value.strip() in ['', 'nan', 'None', '<NA>']:
                return default
            return value
        except:
            return default
    
    def _safe_convert_numeric(self, value, default=0):
        """安全转换数值"""
        if pd.isna(value) or value is None:
            return default
        
        try:
            if isinstance(value, str) and value.strip() in ['', 'nan', 'None', '<NA>']:
                return default
            return float(value)
        except:
            return default
    
    def _get_existing_data_keys(self, cursor, date_range=None):
        """获取已存在数据的唯一标识符"""
        query = """
            SELECT 
                customer_name, finance_id, sub_customer_name, 
                year, month, day, product_name, color, grade
            FROM sales_records
        """
        
        if date_range:
            query += " WHERE record_date BETWEEN ? AND ?"
            cursor.execute(query, date_range)
        else:
            cursor.execute(query)
        
        existing_records = cursor.fetchall()
        
        # 构建唯一标识符集合
        existing_keys = set()
        for record in existing_records:
            key = f"{record['customer_name']}_{record['finance_id']}_{record['sub_customer_name']}_" \
                  f"{record['year']}_{record['month']}_{record['day']}_{record['product_name']}_" \
                  f"{record['color']}_{record['grade']}"
            existing_keys.add(key)
        
        return existing_keys
    
    def _update_import_to_database(self, df: pd.DataFrame, user: str) -> Tuple[bool, str]:
        """更新模式：覆盖重复数据，插入新数据"""
        from core.database import get_connection
        
        with get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                # 获取已存在数据的唯一标识符
                existing_keys = self._get_existing_data_keys(cursor)
                
                # 分离新数据和更新数据
                new_records = []
                update_records = []
                
                for _, row in df.iterrows():
                    record_key = row['data_key']
                    record_data = (
                        self._safe_convert_value(row['customer_name'], ''),
                        self._safe_convert_value(row['finance_id'], ''),
                        self._safe_convert_value(row['sub_customer_name'], ''),
                        int(self._safe_convert_numeric(row['year'])),
                        int(self._safe_convert_numeric(row['month'])),
                        int(self._safe_convert_numeric(row['day'])),
                        self._safe_convert_value(row.get('product_name', ''), ''),
                        self._safe_convert_value(row['color'], ''),
                        self._safe_convert_value(row['grade'], ''),
                        self._safe_convert_numeric(row['quantity']),
                        self._safe_convert_numeric(row['unit_price']),
                        self._safe_convert_numeric(row['amount']),
                        self._safe_convert_value(row['ticket_number'], ''),
                        self._safe_convert_value(row['remark'], ''),
                        self._safe_convert_value(row['production_line'], ''),
                        self._safe_convert_value(row['record_date'], datetime.now().strftime('%Y-%m-%d'))
                    )
                    
                    if record_key in existing_keys:
                        update_records.append(record_data)
                    else:
                        new_records.append(record_data)
                
                # 批量更新客户数据
                customers_data = df[['customer_name', 'finance_id', 'sub_customer_name']].drop_duplicates()
                customer_tuples = []
                
                for _, row in customers_data.iterrows():
                    customer_tuples.append((
                        self._safe_convert_value(row['customer_name'], ''),
                        self._safe_convert_value(row['finance_id'], ''),
                        self._safe_convert_value(row['sub_customer_name'], '')
                    ))
                
                if customer_tuples:
                    cursor.executemany('''
                        INSERT OR REPLACE INTO customers 
                        (customer_name, finance_id, sub_customer_name, updated_date)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ''', customer_tuples)
                
                # 先删除需要更新的记录，然后插入所有记录
                if update_records:
                    # 构建删除条件
                    placeholders = ','.join(['?'] * len(update_records))
                    delete_keys = [record[1] for record in update_records]  # finance_id 作为删除条件
                    
                    cursor.execute(f'''
                        DELETE FROM sales_records 
                        WHERE finance_id IN ({placeholders})
                    ''', delete_keys)
                
                # 插入所有记录（包括更新的和新加的）
                all_records = update_records + new_records
                if all_records:
                    cursor.executemany('''
                        INSERT INTO sales_records 
                        (customer_name, finance_id, sub_customer_name, year, month, day, 
                         product_name, color, grade, quantity, unit_price, amount, 
                         ticket_number, remark, production_line, record_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', all_records)
                
                # 获取统计信息
                stats = self._get_import_statistics(
                    df, len(customer_tuples), len(new_records), len(update_records)
                )
                
                return True, stats
                
            except Exception as e:
                logger.error(f"数据更新导入失败: {str(e)}")
                import traceback
                logger.error(f"详细错误信息: {traceback.format_exc()}")
                return False, f"数据更新导入失败: {str(e)}"
    
    def _append_import_to_database(self, df: pd.DataFrame, user: str) -> Tuple[bool, str]:
        """追加模式：只导入不存在的数据"""
        from core.database import get_connection
        
        with get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                # 获取已存在数据的唯一标识符
                existing_keys = self._get_existing_data_keys(cursor)
                
                # 过滤出不存在的数据
                new_data = df[~df['data_key'].isin(existing_keys)].copy()
                
                if new_data.empty:
                    return True, "没有新数据需要导入，所有数据已存在"
                
                # 导入新数据
                return self._batch_import_new_data(new_data, cursor)
                
            except Exception as e:
                logger.error(f"数据追加导入失败: {str(e)}")
                return False, f"数据追加导入失败: {str(e)}"
    
    def _replace_import_to_database(self, df: pd.DataFrame, user: str) -> Tuple[bool, str]:
        """替换模式：清空后重新导入"""
        from core.database import get_connection, clear_database
        
        try:
            # 清空数据库
            clear_database()
            
            # 重新导入所有数据
            return self._batch_import_new_data(df, user)
            
        except Exception as e:
            logger.error(f"数据替换导入失败: {str(e)}")
            return False, f"数据替换导入失败: {str(e)}"
    
    def _batch_import_new_data(self, df: pd.DataFrame, user: str) -> Tuple[bool, str]:
        """批量导入新数据（基础导入方法）"""
        from core.database import get_connection
        
        with get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                # 批量导入客户数据
                customers_data = df[['customer_name', 'finance_id', 'sub_customer_name']].drop_duplicates()
                customer_tuples = []
                
                for _, row in customers_data.iterrows():
                    customer_tuples.append((
                        self._safe_convert_value(row['customer_name'], ''),
                        self._safe_convert_value(row['finance_id'], ''),
                        self._safe_convert_value(row['sub_customer_name'], '')
                    ))
                
                if customer_tuples:
                    cursor.executemany('''
                        INSERT OR IGNORE INTO customers 
                        (customer_name, finance_id, sub_customer_name, updated_date)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ''', customer_tuples)
                
                # 准备销售记录数据
                sales_records = []
                for _, row in df.iterrows():
                    record = (
                        self._safe_convert_value(row['customer_name'], ''),
                        self._safe_convert_value(row['finance_id'], ''),
                        self._safe_convert_value(row['sub_customer_name'], ''),
                        int(self._safe_convert_numeric(row['year'])),
                        int(self._safe_convert_numeric(row['month'])),
                        int(self._safe_convert_numeric(row['day'])),
                        self._safe_convert_value(row.get('product_name', ''), ''),
                        self._safe_convert_value(row['color'], ''),
                        self._safe_convert_value(row['grade'], ''),
                        self._safe_convert_numeric(row['quantity']),
                        self._safe_convert_numeric(row['unit_price']),
                        self._safe_convert_numeric(row['amount']),
                        self._safe_convert_value(row['ticket_number'], ''),
                        self._safe_convert_value(row['remark'], ''),
                        self._safe_convert_value(row['production_line'], ''),
                        self._safe_convert_value(row['record_date'], datetime.now().strftime('%Y-%m-%d'))
                    )
                    sales_records.append(record)
                
                # 批量插入销售记录
                if sales_records:
                    cursor.executemany('''
                        INSERT INTO sales_records 
                        (customer_name, finance_id, sub_customer_name, year, month, day, 
                         product_name, color, grade, quantity, unit_price, amount, 
                         ticket_number, remark, production_line, record_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', sales_records)
                
                # 获取统计信息
                stats = self._get_import_statistics(df, len(customer_tuples), len(sales_records), 0)
                
                return True, stats
                
            except Exception as e:
                logger.error(f"数据导入失败: {str(e)}")
                return False, f"数据导入失败: {str(e)}"
    
    def _get_import_statistics(self, df: pd.DataFrame, customer_count: int, new_records: int = 0, updated_records: int = 0) -> str:
        """获取导入统计信息"""
        record_count = len(df)
        product_varieties = df['product_name'].nunique() if 'product_name' in df.columns else 0
        color_varieties = df['color'].nunique() if 'color' in df.columns else 0
        
        if updated_records > 0:
            return (f"数据更新成功！"
                    f"导入客户数: {customer_count}, "
                    f"总记录数: {record_count}, "
                    f"新增记录: {new_records}, "
                    f"更新记录: {updated_records}, "
                    f"产品种类: {product_varieties}, "
                    f"颜色种类: {color_varieties}")
        else:
            return (f"数据导入成功！"
                    f"导入客户数: {customer_count}, "
                    f"销售记录数: {record_count}, "
                    f"产品种类: {product_varieties}, "
                    f"颜色种类: {color_varieties}")

    def import_multiple_files(self, file_paths: List[str], user: str = "system", update_strategy: str = "update") -> Dict[str, Any]:
        """批量导入多个文件"""
        results = {
            'successful': [],
            'failed': [],
            'total_files': len(file_paths)
        }
        
        for file_path in file_paths:
            try:
                success, message = self.import_excel_data(file_path, user, update_strategy)
                if success:
                    results['successful'].append({'file': file_path, 'message': message})
                else:
                    results['failed'].append({'file': file_path, 'error': message})
            except Exception as e:
                results['failed'].append({'file': file_path, 'error': str(e)})
        
        return results
    
    def get_data_overview(self, date_range=None):
        """获取数据概览，用于判断是否需要更新"""
        from core.database import get_connection
        
        with get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                # 获取最新数据日期
                cursor.execute('''
                    SELECT MAX(record_date) as latest_date, 
                           COUNT(*) as total_records,
                           COUNT(DISTINCT customer_name) as unique_customers
                    FROM sales_records
                ''')
                
                overview = cursor.fetchone()
                
                return {
                    'latest_date': overview['latest_date'],
                    'total_records': overview['total_records'],
                    'unique_customers': overview['unique_customers']
                }
                
            except Exception as e:
                logger.error(f"获取数据概览失败: {str(e)}")
                return {}
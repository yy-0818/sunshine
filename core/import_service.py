import pandas as pd
import warnings
from openpyxl import load_workbook
from datetime import datetime
from core.database import get_connection

class ImportService:
    def __init__(self):
        pass
    
    def import_excel_data(self, file_path, user="system"):
        """导入Excel数据 - 适配新数据源结构"""
        try:
            # 验证文件结构
            is_valid, message = self.validate_excel_structure(file_path)
            if not is_valid:
                return False, message
            
            # 读取数据
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_excel(file_path, engine='openpyxl')
            
            if df.empty:
                return False, "Excel文件中没有数据"
            
            # 数据清洗和转换
            df = self._clean_data(df)
            
            # 验证数据
            is_valid, message = self._validate_data(df)
            if not is_valid:
                return False, message
            
            # 导入数据库
            return self._import_to_database(df, user)
            
        except Exception as e:
            return False, f"数据导入失败: {str(e)}"
    
    def validate_excel_structure(self, file_path):
        """验证Excel文件结构 - 适配新表头"""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                wb = load_workbook(file_path, data_only=True)
                sheet = wb.active
                
                # 获取表头
                headers = []
                for cell in sheet[1]:
                    if cell.value is not None:
                        headers.append(str(cell.value).strip())
                
                # 必需的表头 - 根据新数据源调整
                required_headers = ['客户名称', '编号', '子客户名称', '年', '月', '日', '颜色', '等级', '数量', '单价', '金额']
                missing_headers = [h for h in required_headers if h not in headers]
                
                if missing_headers:
                    return False, f"缺少必要的表头: {missing_headers}"
                
                return True, "文件结构正确"
            
        except Exception as e:
            return False, f"文件检查失败: {str(e)}"
    
    def _clean_data(self, df):
        """数据清洗 - 适配新数据源"""
        # 重命名列
        df = df.rename(columns={
            '客户名称': 'customer_name',
            '编号': 'finance_id',
            '子客户名称': 'sub_customer_name',
            '年': 'year',
            '月': 'month',
            '日': 'day',
            '颜色': 'color',
            '等级': 'grade',
            '数量': 'quantity',
            '单价': 'unit_price',
            '金额': 'amount',
            '票 号': 'ticket_number',
            '备注': 'remark',
            '生产线': 'production_line'
        })
        
        # 处理空值
        df['sub_customer_name'] = df['sub_customer_name'].fillna('')
        df['finance_id'] = df['finance_id'].astype(str)
        df['grade'] = df['grade'].fillna('')
        df['ticket_number'] = df['ticket_number'].fillna('')
        df['remark'] = df['remark'].fillna('')
        df['production_line'] = df['production_line'].fillna('')
        
        # 数值列处理
        numeric_columns = ['year', 'month', 'day', 'quantity', 'unit_price', 'amount']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 构建记录日期
        df['record_date'] = df.apply(
            lambda row: f"20{int(row['year'])}-{int(row['month']):02d}-{int(row['day']):02d}" 
            if row['year'] > 0 and row['month'] > 0 and row['day'] > 0 
            else datetime.now().strftime('%Y-%m-%d'), 
            axis=1
        )
        
        return df
    
    def _validate_data(self, df):
        """数据验证"""
        required_columns = ['customer_name', 'finance_id', 'color']
        for col in required_columns:
            if col not in df.columns or df[col].isnull().any():
                return False, f"列 '{col}' 中存在空值或缺失，请检查数据"
        return True, "数据验证通过"
    
    def _import_to_database(self, df, user):
        """导入数据到数据库"""
        with get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                # 导入客户数据
                customers_data = df[['customer_name', 'finance_id', 'sub_customer_name']].drop_duplicates()
                for _, row in customers_data.iterrows():
                    cursor.execute('''
                        INSERT OR REPLACE INTO customers 
                        (customer_name, finance_id, sub_customer_name, updated_date)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (row['customer_name'], row['finance_id'], row['sub_customer_name']))
                
                # 导入销售记录
                for _, row in df.iterrows():
                    cursor.execute('''
                        INSERT INTO sales_records 
                        (customer_name, finance_id, sub_customer_name, year, month, day, 
                         color, grade, quantity, unit_price, amount, 
                         ticket_number, remark, production_line, record_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['customer_name'],
                        row['finance_id'],
                        row['sub_customer_name'],
                        int(row['year']) if pd.notna(row['year']) else None,
                        int(row['month']) if pd.notna(row['month']) else None,
                        int(row['day']) if pd.notna(row['day']) else None,
                        row['color'],
                        row['grade'],
                        row['quantity'] if pd.notna(row['quantity']) else None,
                        row['unit_price'] if pd.notna(row['unit_price']) else None,
                        row['amount'] if pd.notna(row['amount']) else None,
                        row['ticket_number'],
                        row['remark'],
                        row['production_line'],
                        row['record_date']
                    ))
                
                # 获取统计信息
                customer_count = len(customers_data)
                record_count = len(df)
                
                return True, f"数据导入成功！导入客户数: {customer_count}, 销售记录数: {record_count}"
                
            except Exception as e:
                return False, f"数据库导入失败: {str(e)}"
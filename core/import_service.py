import pandas as pd
import re
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
        """数据清洗 - 颜色拆分"""
        # 首先拆分颜色列
        if '颜色' in df.columns:
            df = self._split_color_column(df)
        
        # 重命名列
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
            '票号': 'ticket_number',  # 兼容不同列名
            '备注': 'remark',
            '生产线': 'production_line'
        }
        
        # 只重命名存在的列
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=existing_columns)
        
        # 处理空值
        df['sub_customer_name'] = df.get('sub_customer_name', '').fillna('')
        df['finance_id'] = df['finance_id'].astype(str)
        df['product_name'] = df.get('product_name', '').fillna('')
        df['grade'] = df.get('grade', '').fillna('')
        df['ticket_number'] = df.get('ticket_number', '').fillna('')
        df['remark'] = df.get('remark', '').fillna('')
        df['production_line'] = df.get('production_line', '').fillna('')
        df['color'] = df.get('color', '').fillna('')
        
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
    
    def _split_color_column(self, df):
        """
        拆分颜色列 - 将产品名称与颜色分开
        """
        # 定义常见颜色列表
        colors = ['孔雀兰', '钢灰', '橘红', '亚光黑', '大红', '深灰', '玫红', '蓝灰', '铁红', 
                '古兰', '浅灰', '橘黄', '磨砂蓝', '亚光灰', '铁红', '九号蓝', '蓝灰']
        
        # 定义产品类型关键词
        product_keywords = ['鑫阳光', '福迩家', '星月祥', '劲彩', '玖玉', '花脊座', '人字脊', 
                        '边瓦', '长沟瓦', '脊瓦', '大脊瓦', '短沟瓦']
        
        def extract_product_and_color(text):
            if pd.isna(text) or text == "":
                return "", ""
            
            text = str(text).strip()
            
            # 处理特殊情况："壹"作为等级
            if text.endswith('壹'):
                text = text[:-1]  # 移除末尾的"壹"
            
            # 尝试从常见颜色中匹配
            for color in colors:
                if color in text:
                    product_name = text.replace(color, "").strip()
                    # 清理多余的空格和标点
                    product_name = re.sub(r'\s+', ' ', product_name).strip()
                    product_name = re.sub(r'^\s*[、，,]\s*', '', product_name)
                    return product_name, color
            
            # 如果没有找到明确的颜色，尝试基于产品关键词拆分
            for keyword in product_keywords:
                if keyword in text:
                    parts = text.split(keyword, 1)
                    if len(parts) > 1:
                        product_name = keyword + parts[1].split()[0] if parts[1].strip() else keyword
                        color_part = parts[1].replace(parts[1].split()[0] if parts[1].strip() else "", "").strip()
                        return product_name, color_part
            
            # 如果以上方法都不行，使用简单的空格拆分
            parts = text.split()
            if len(parts) >= 2:
                color_found = parts[-1]
                product_name = ' '.join(parts[:-1])
                return product_name, color_found
            else:
                return text, ""
        
        # 应用拆分函数
        split_results = df['颜色'].apply(extract_product_and_color)
        df['产品名称'] = split_results.apply(lambda x: x[0])
        df['颜色'] = split_results.apply(lambda x: x[1])
        
        return df
    
    def _validate_data(self, df):
        """数据验证"""
        required_columns = ['customer_name', 'finance_id', 'color']
        for col in required_columns:
            if col not in df.columns or df[col].isnull().any():
                return False, f"列 '{col}' 中存在空值或缺失，请检查数据"
        
        # 检查关键数值列的合理性
        # if 'amount' in df.columns:
        #     negative_amounts = df[df['amount'] < 0]
        #     if len(negative_amounts) > 0:
        #         return False, f"发现 {len(negative_amounts)} 条记录的金额为负数"
        
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
                
                # 导入销售记录 - 修正占位符数量
                for _, row in df.iterrows():
                    cursor.execute('''
                        INSERT INTO sales_records 
                        (customer_name, finance_id, sub_customer_name, year, month, day, 
                         product_name, color, grade, quantity, unit_price, amount, 
                         ticket_number, remark, production_line, record_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['customer_name'],
                        row['finance_id'],
                        row['sub_customer_name'],
                        int(row['year']) if pd.notna(row['year']) else None,
                        int(row['month']) if pd.notna(row['month']) else None,
                        int(row['day']) if pd.notna(row['day']) else None,
                        row.get('product_name', ''),
                        row['color'],
                        row['grade'],
                        float(row['quantity']) if pd.notna(row['quantity']) else None,
                        float(row['unit_price']) if pd.notna(row['unit_price']) else None,
                        float(row['amount']) if pd.notna(row['amount']) else None,
                        row['ticket_number'],
                        row['remark'],
                        row['production_line'],
                        row['record_date']
                    ))
                
                # 获取统计信息
                customer_count = len(customers_data)
                record_count = len(df)
                product_varieties = df['product_name'].nunique() if 'product_name' in df.columns else 0
                color_varieties = df['color'].nunique() if 'color' in df.columns else 0
                
                return True, (f"数据导入成功！"
                            f"导入客户数: {customer_count}, "
                            f"销售记录数: {record_count}, "
                            f"产品种类: {product_varieties}, "
                            f"颜色种类: {color_varieties}")
                
            except Exception as e:
                return False, f"数据库导入失败: {str(e)}"
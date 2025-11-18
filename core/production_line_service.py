import pandas as pd
import re
from core.database import get_connection
import logging

logger = logging.getLogger(__name__)

class ProductionLineService:
    def __init__(self):
        # 生产线分组配置
        self.phase_configs = {
            '一期': {
                'keywords': ["一二线", "三线"],
                'description': '一期生产线'
            },
            '二期': {
                'keywords': ["五线", "六线", "七线", "八线", "九线"],
                'description': '二期生产线'
            }
        }
        
        # 编译正则表达式模式以提高性能
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式模式"""
        self.patterns = {}
        for phase, config in self.phase_configs.items():
            patterns = []
            for keyword in config['keywords']:
                # 创建模糊匹配模式，匹配包含关键词的任何字符串
                pattern = re.compile(f'.*{re.escape(keyword)}.*', re.IGNORECASE)
                patterns.append(pattern)
            self.patterns[phase] = patterns
    
    def classify_production_line(self, production_line):
        """
        分类生产线到一期或二期
        
        Args:
            production_line (str): 生产线名称
            
        Returns:
            str: '一期', '二期' 或 None（无法分类）
        """
        if not production_line or pd.isna(production_line):
            return None
        
        production_line = str(production_line).strip()
        
        # 使用正则表达式进行模糊匹配
        for phase, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern.match(production_line):
                    return phase
        
        return None
    
    def get_production_line_statistics(self):
        """
        获取生产线分类统计信息
        
        Returns:
            dict: 统计信息
        """
        stats = {
            'total_records': 0,
            'classified_records': 0,
            'unclassified_records': 0,
            'phase_breakdown': {},
            'unclassified_examples': [],
            'production_line_details': {}
        }
        
        with get_connection() as conn:
            # 获取所有生产线及其记录数
            query = """
                SELECT 
                    production_line,
                    COUNT(*) as record_count,
                    SUM(amount) as total_amount,
                    AVG(unit_price) as avg_price,
                    SUM(quantity) as total_quantity
                FROM sales_records 
                WHERE production_line IS NOT NULL AND production_line != ''
                GROUP BY production_line
                ORDER BY record_count DESC
            """
            
            df = pd.read_sql_query(query, conn)
            stats['total_records'] = df['record_count'].sum()
            
            # 分类统计
            classified_count = 0
            phase_counts = {phase: 0 for phase in self.phase_configs.keys()}
            phase_details = {phase: [] for phase in self.phase_configs.keys()}
            unclassified_examples = []
            
            for _, row in df.iterrows():
                production_line = row['production_line']
                record_count = row['record_count']
                
                phase = self.classify_production_line(production_line)
                
                if phase:
                    classified_count += record_count
                    phase_counts[phase] += record_count
                    phase_details[phase].append({
                        'production_line': production_line,
                        'record_count': record_count,
                        'total_amount': row['total_amount'],
                        'avg_price': row['avg_price'],
                        'total_quantity': row['total_quantity']
                    })
                else:
                    # 记录未分类的生产线示例（最多记录10个）
                    if len(unclassified_examples) < 10:
                        unclassified_examples.append({
                            'production_line': production_line,
                            'record_count': record_count
                        })
            
            stats['classified_records'] = classified_count
            stats['unclassified_records'] = stats['total_records'] - classified_count
            stats['phase_breakdown'] = phase_counts
            stats['unclassified_examples'] = unclassified_examples
            stats['production_line_details'] = phase_details
            
            # 计算比例
            if stats['total_records'] > 0:
                stats['classified_percentage'] = (classified_count / stats['total_records']) * 100
                stats['unclassified_percentage'] = (stats['unclassified_records'] / stats['total_records']) * 100
                
                for phase in self.phase_configs.keys():
                    stats['phase_breakdown_percentage'] = stats['phase_breakdown_percentage'] = {
                        phase: (count / stats['total_records']) * 100 
                        for phase, count in phase_counts.items()
                    }
            else:
                stats['classified_percentage'] = 0
                stats['unclassified_percentage'] = 0
                stats['phase_breakdown_percentage'] = {}
        
        return stats
    
    def get_phase_data(self, phase, start_date=None, end_date=None):
        """
        获取指定阶段的生产线数据
        
        Args:
            phase (str): '一期' 或 '二期'
            start_date (str): 开始日期 (YYYY-MM-DD)
            end_date (str): 结束日期 (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: 阶段数据
        """
        if phase not in self.phase_configs:
            raise ValueError(f"无效的阶段: {phase}")
        
        conditions = []
        params = []
        
        # 构建生产线条件
        phase_conditions = []
        for keyword in self.phase_configs[phase]['keywords']:
            phase_conditions.append("production_line LIKE ?")
            params.append(f'%{keyword}%')
        
        conditions.append(f"({' OR '.join(phase_conditions)})")
        
        # 日期条件
        if start_date:
            conditions.append("record_date >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("record_date <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT 
                *,
                strftime('%Y-%m', record_date) as month,
                strftime('%Y', record_date) as year
            FROM sales_records 
            WHERE {where_clause}
            ORDER BY record_date DESC
        """
        
        with get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        return df
    
    def get_phase_summary_stats(self, phase):
        """
        获取阶段汇总统计
        
        Args:
            phase (str): '一期' 或 '二期'
            
        Returns:
            dict: 汇总统计信息
        """
        if phase not in self.phase_configs:
            raise ValueError(f"无效的阶段: {phase}")
        
        # 构建生产线条件
        phase_conditions = []
        params = []
        for keyword in self.phase_configs[phase]['keywords']:
            phase_conditions.append("production_line LIKE ?")
            params.append(f'%{keyword}%')
        
        where_clause = f"({' OR '.join(phase_conditions)})"
        
        # 分别执行查询，避免复杂的子查询参数问题
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                
                # 基础统计查询
                base_query = f"""
                    SELECT 
                        COUNT(*) as total_records,
                        COALESCE(SUM(amount), 0) as total_amount,
                        COALESCE(SUM(quantity), 0) as total_quantity,
                        COALESCE(AVG(unit_price), 0) as avg_price,
                        COUNT(DISTINCT product_name) as product_count,
                        COUNT(DISTINCT color) as color_count,
                        MIN(record_date) as start_date,
                        MAX(record_date) as end_date
                    FROM sales_records 
                    WHERE {where_clause}
                """
                cursor.execute(base_query, params)
                base_result = cursor.fetchone()
                
                # 主客户数查询（唯一 customer_name, finance_id）
                main_customer_query = f"""
                    SELECT COUNT(*) as main_customer_count
                    FROM (
                        SELECT DISTINCT customer_name, finance_id
                        FROM sales_records 
                        WHERE {where_clause}
                        AND customer_name IS NOT NULL
                        AND finance_id IS NOT NULL
                    )
                """
                cursor.execute(main_customer_query, params)
                main_customer_result = cursor.fetchone()
                
                # 子客户数查询（唯一 customer_name, finance_id, sub_customer_name）
                sub_customer_query = f"""
                    SELECT COUNT(*) as sub_customer_count
                    FROM (
                        SELECT DISTINCT customer_name, finance_id, sub_customer_name
                        FROM sales_records 
                        WHERE {where_clause}
                        AND customer_name IS NOT NULL 
                        AND finance_id IS NOT NULL 
                        AND sub_customer_name IS NOT NULL
                    )
                """
                cursor.execute(sub_customer_query, params)
                sub_customer_result = cursor.fetchone()
            
            if base_result and base_result['total_records'] > 0:
                stats = {
                    'total_records': base_result['total_records'],
                    'total_amount': float(base_result['total_amount']) if base_result['total_amount'] else 0,
                    'total_quantity': base_result['total_quantity'],
                    'avg_price': float(base_result['avg_price']) if base_result['avg_price'] else 0,
                    'customer_count': main_customer_result['main_customer_count'] if main_customer_result else 0,  # 保持原字段名
                    'product_count': base_result['product_count'],
                    'color_count': base_result['color_count'],
                    'date_range': {
                        'start': base_result['start_date'],
                        'end': base_result['end_date']
                    },
                    # 额外返回子客户数用于调试
                    'sub_customer_count': sub_customer_result['sub_customer_count'] if sub_customer_result else 0
                }
            else:
                stats = {
                    'total_records': 0,
                    'total_amount': 0,
                    'total_quantity': 0,
                    'avg_price': 0,
                    'customer_count': 0,
                    'product_count': 0,
                    'color_count': 0,
                    'date_range': None,
                    'sub_customer_count': 0
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取阶段 {phase} 汇总统计时出错: {e}")
            return {
                'total_records': 0,
                'total_amount': 0,
                'total_quantity': 0,
                'avg_price': 0,
                'customer_count': 0,
                'product_count': 0,
                'color_count': 0,
                'date_range': None,
                'sub_customer_count': 0
            }
    
    def validate_classification(self, sample_size=100):
        """
        验证分类算法的准确性
        
        Args:
            sample_size (int): 样本大小
            
        Returns:
            dict: 验证结果
        """
        with get_connection() as conn:
            query = """
                SELECT DISTINCT production_line 
                FROM sales_records 
                WHERE production_line IS NOT NULL AND production_line != ''
                LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=[sample_size])
        
        results = []
        for production_line in df['production_line']:
            classification = self.classify_production_line(production_line)
            results.append({
                'production_line': production_line,
                'classification': classification,
                'is_correct': self._validate_single_classification(production_line, classification)
            })
        
        accuracy = sum(1 for r in results if r['is_correct']) / len(results) if results else 0
        
        return {
            'accuracy': accuracy,
            'sample_size': len(results),
            'results': results
        }
    
    def _validate_single_classification(self, production_line, classification):
        """
        验证单个生产线的分类结果
        """
        if not classification:
            return True  # 无法分类的情况视为正确
        
        production_line_lower = production_line.lower()
        
        if classification == '一期':
            return any(keyword in production_line_lower for keyword in ['一二线', '三线'])
        elif classification == '二期':
            return any(keyword in production_line_lower for keyword in ['五线', '六线', '七线', '八线', '九线'])
        
        return False
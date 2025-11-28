import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
from core.database import get_connection, init_database

class AuthSystem:
    def __init__(self):
        self.ensure_tables_exist()
    
    def ensure_tables_exist(self):
        """确保用户表存在"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                if not cursor.fetchone():
                    init_database()
        except Exception as e:
            st.error(f"数据库检查失败: {e}")
            try:
                init_database()
            except Exception as init_error:
                st.error(f"数据库初始化失败: {init_error}")
    
    def _hash_password(self, password):
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def login(self, username, password):
        """用户登录"""
        self.ensure_tables_exist()
        password_hash = self._hash_password(password)
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, role, full_name, department 
                    FROM users 
                    WHERE username = ? AND password_hash = ? AND is_active = TRUE
                ''', (username, password_hash))
                
                user = cursor.fetchone()
                
                if user:
                    cursor.execute('UPDATE users SET last_login = ? WHERE id = ?', 
                                 (datetime.now(), user[0]))
                    conn.commit()
                    return {
                        'id': user[0],
                        'username': user[1],
                        'role': user[2],
                        'full_name': user[3],
                        'department': user[4]
                    }
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                st.error("数据库表不存在，正在重新初始化...")
                init_database()
                return self.login(username, password)
            else:
                st.error(f"数据库错误: {e}")
        except Exception as e:
            st.error(f"登录失败: {e}")
        return None
    
    def create_user(self, username, password, role, full_name, department):
        """创建新用户"""
        if role not in ['admin', 'manager', 'user']:
            return False, "角色无效"
        
        password_hash = self._hash_password(password)
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users 
                    (username, password_hash, role, full_name, department)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, password_hash, role, full_name, department))
            return True, "用户创建成功"
        except sqlite3.IntegrityError:
            return False, "用户名已存在"
        except Exception as e:
            return False, f"创建用户失败: {e}"
    
    def get_all_users(self):
        """获取所有用户"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, role, full_name, department, is_active, 
                       created_date, last_login
                FROM users
                ORDER BY 
                    CASE role 
                        WHEN 'admin' THEN 1
                        WHEN 'manager' THEN 2 
                        WHEN 'user' THEN 3
                    END,
                    username
            ''')
            return cursor.fetchall()
    
    def update_user_role(self, user_id, new_role):
        """更新用户角色"""
        if new_role not in ['admin', 'manager', 'user']:
            return False, "角色无效"
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
            return True, "用户角色更新成功"
        except Exception as e:
            return False, f"更新失败: {e}"
    
    def update_user_info(self, user_id, full_name, department, is_active):
        """更新用户信息"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET full_name = ?, department = ?, is_active = ?
                    WHERE id = ?
                ''', (full_name, department, is_active, user_id))
            return True, "用户信息更新成功"
        except Exception as e:
            return False, f"更新失败: {e}"
    
    def delete_user(self, user_id):
        """删除用户（不能删除默认用户）"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # 检查是否为默认用户
                cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
                user = cursor.fetchone()
                if user and user[0] in ['admin', 'manager', 'user']:
                    return False, "不能删除系统默认用户"
                
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            return True, "用户删除成功"
        except Exception as e:
            return False, f"删除失败: {e}"

def require_login():
    """要求登录装饰器"""
    if 'user' not in st.session_state:
        st.error("🔐 请先登录系统")
        st.stop()

def check_permission(required_role):
    """检查用户权限"""
    if 'user' not in st.session_state:
        return False
    
    user_role = st.session_state.user['role']
    role_hierarchy = {'user': 0, 'manager': 1, 'admin': 2}
    return role_hierarchy[user_role] >= role_hierarchy[required_role]

def get_role_display_name(role):
    """获取角色的显示名称"""
    role_mapping = {
        'admin': '👑 系统管理员',
        'manager': '👔 部门经理', 
        'user': '👤 普通用户'
    }
    return role_mapping.get(role, role)

def format_datetime(dt_value):
    """格式化日期时间显示"""
    if dt_value is None:
        return "从未登录"
    
    if isinstance(dt_value, str):
        # 如果是字符串，尝试解析
        try:
            # 移除微秒部分
            return dt_value.split('.')[0]
        except:
            return dt_value
    elif isinstance(dt_value, datetime):
        # 如果是datetime对象，格式化为字符串
        return dt_value.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return str(dt_value)

def login_form():
    """登录表单组件"""
    with st.form("login_form", clear_on_submit=True):
        st.subheader("🔐 系统登录")
        
        username = st.text_input("用户名", placeholder="请输入用户名")
        password = st.text_input("密码", type="password", placeholder="请输入密码")
        
        submit = st.form_submit_button("登录", width='stretch')
        
        if submit:
            if not username or not password:
                st.error("请输入用户名和密码")
                return False
            
            auth = AuthSystem()
            user = auth.login(username, password)
            if user:
                st.session_state.user = user
                st.session_state.logged_in = True
                st.toast(f"Hooray! {user['full_name']}", icon="🎉")
                st.rerun()
            else:
                st.error("用户名或密码错误")
                return False
    
    return True
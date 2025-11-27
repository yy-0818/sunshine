def get_role_badge(role):
    """获取角色的徽章显示"""
    role_config = {
        'admin': {'label': '👑 系统管理员', 'color': 'red'},
        'manager': {'label': '👔 部门经理', 'color': 'orange'}, 
        'user': {'label': '👤 普通用户', 'color': 'blue'}
    }
    return role_config.get(role, {'label': role, 'color': 'gray'})

def format_datetime(dt_string):
    """格式化日期时间显示"""
    if not dt_string:
        return "从未登录"
    try:
        # 移除微秒部分
        return dt_string.split('.')[0]
    except:
        return dt_string
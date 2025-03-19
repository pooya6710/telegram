import time
import threading
from typing import Dict, Any, List, Optional, Tuple, Set
from config import UserRole, ADMIN_IDS
from database import (
    add_or_update_user, 
    get_user, 
    update_user_role, 
    get_all_users,
    get_active_downloads_count
)
from debug_logger import debug_log, debug_decorator

# کش کاربران برای بهبود کارایی
user_cache = {}
user_cache_lock = threading.RLock()
USER_CACHE_TIMEOUT = 300  # مدت زمان اعتبار کش به ثانیه

# کاربران مسدود شده
blocked_users = set()
blocked_users_lock = threading.RLock()

@debug_decorator
def update_user_info(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
    """
    به‌روزرسانی اطلاعات کاربر
    
    Args:
        user_id: شناسه کاربر
        username: نام کاربری
        first_name: نام
        last_name: نام خانوادگی
        
    Returns:
        True در صورت موفقیت
    """
    # به‌روزرسانی در دیتابیس
    success = add_or_update_user(user_id, username, first_name, last_name)
    
    if success:
        # به‌روزرسانی کش
        update_user_cache(user_id)
    
    return success

@debug_decorator
def get_user_info(user_id: int, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    دریافت اطلاعات کاربر
    
    Args:
        user_id: شناسه کاربر
        use_cache: استفاده از کش
        
    Returns:
        دیکشنری اطلاعات کاربر یا None
    """
    # بررسی کش
    if use_cache:
        with user_cache_lock:
            cache_entry = user_cache.get(user_id)
            if cache_entry and (time.time() - cache_entry.get('timestamp', 0) < USER_CACHE_TIMEOUT):
                return cache_entry.get('data')
    
    # دریافت از دیتابیس
    user_info = get_user(user_id)
    
    if user_info:
        # به‌روزرسانی کش
        with user_cache_lock:
            user_cache[user_id] = {
                'data': user_info,
                'timestamp': time.time()
            }
    
    return user_info

@debug_decorator
def update_user_cache(user_id: int) -> None:
    """
    به‌روزرسانی کش کاربر
    
    Args:
        user_id: شناسه کاربر
    """
    # حذف ورودی قبلی از کش
    with user_cache_lock:
        if user_id in user_cache:
            del user_cache[user_id]

@debug_decorator
def clear_user_cache() -> None:
    """پاکسازی کامل کش کاربران"""
    with user_cache_lock:
        user_cache.clear()

@debug_decorator
def set_user_role(user_id: int, role: int) -> bool:
    """
    تنظیم نقش کاربر
    
    Args:
        user_id: شناسه کاربر
        role: نقش جدید
        
    Returns:
        True در صورت موفقیت
    """
    # به‌روزرسانی در دیتابیس
    success = update_user_role(user_id, role)
    
    if success:
        # به‌روزرسانی کش
        update_user_cache(user_id)
        
        # اگر کاربر مسدود شده است
        if role == UserRole.BLOCKED:
            with blocked_users_lock:
                blocked_users.add(user_id)
        # اگر کاربر آزاد شده است
        elif role != UserRole.BLOCKED:
            with blocked_users_lock:
                if user_id in blocked_users:
                    blocked_users.remove(user_id)
    
    return success

@debug_decorator
def is_user_blocked(user_id: int) -> bool:
    """
    بررسی مسدود بودن کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True اگر کاربر مسدود است
    """
    # بررسی کش
    with blocked_users_lock:
        if user_id in blocked_users:
            return True
    
    # بررسی از طریق دیتابیس
    user_info = get_user_info(user_id)
    
    if user_info and user_info.get('role') == UserRole.BLOCKED:
        # به‌روزرسانی کش
        with blocked_users_lock:
            blocked_users.add(user_id)
        return True
    
    return False

@debug_decorator
def block_user(user_id: int) -> bool:
    """
    مسدود کردن کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True در صورت موفقیت
    """
    return set_user_role(user_id, UserRole.BLOCKED)

@debug_decorator
def unblock_user(user_id: int) -> bool:
    """
    رفع مسدودیت کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True در صورت موفقیت
    """
    return set_user_role(user_id, UserRole.NORMAL)

@debug_decorator
def get_user_role(user_id: int) -> int:
    """
    دریافت نقش کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        نقش کاربر یا UserRole.NORMAL در صورت عدم وجود
    """
    user_info = get_user_info(user_id)
    
    if user_info:
        return user_info.get('role', UserRole.NORMAL)
    else:
        return UserRole.NORMAL

@debug_decorator
def is_admin(user_id: int) -> bool:
    """
    بررسی ادمین بودن کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True اگر کاربر ادمین است
    """
    # ادمین‌های ثابت از طریق متغیر محیطی
    if user_id in ADMIN_IDS:
        return True
    
    # بررسی از طریق دیتابیس
    role = get_user_role(user_id)
    return role >= UserRole.ADMIN

@debug_decorator
def is_premium(user_id: int) -> bool:
    """
    بررسی ویژه بودن کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True اگر کاربر ویژه است
    """
    # ادمین‌ها نیز امکانات ویژه دارند
    if is_admin(user_id):
        return True
    
    # بررسی از طریق دیتابیس
    role = get_user_role(user_id)
    return role >= UserRole.PREMIUM

@debug_decorator
def set_admin(user_id: int) -> bool:
    """
    تنظیم کاربر به عنوان ادمین
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True در صورت موفقیت
    """
    return set_user_role(user_id, UserRole.ADMIN)

@debug_decorator
def set_premium(user_id: int) -> bool:
    """
    تنظیم کاربر به عنوان ویژه
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True در صورت موفقیت
    """
    return set_user_role(user_id, UserRole.PREMIUM)

@debug_decorator
def set_normal(user_id: int) -> bool:
    """
    تنظیم کاربر به عنوان عادی
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True در صورت موفقیت
    """
    return set_user_role(user_id, UserRole.NORMAL)

@debug_decorator
def check_user_limits(user_id: int, config) -> Tuple[bool, str]:
    """
    بررسی محدودیت‌های کاربر
    
    Args:
        user_id: شناسه کاربر
        config: تنظیمات برنامه
        
    Returns:
        (وضعیت مجاز بودن، پیام خطا)
    """
    # بررسی مسدود بودن
    if is_user_blocked(user_id):
        return False, "شما مسدود شده‌اید و اجازه استفاده از ربات را ندارید."
    
    # بررسی محدودیت تعداد دانلود همزمان
    max_downloads = config.MAX_DOWNLOADS_PER_USER
    
    # افزایش محدودیت برای کاربران ویژه
    if is_premium(user_id):
        max_downloads *= 2
    
    active_count = get_active_downloads_count(user_id)
    
    if active_count >= max_downloads:
        return False, f"شما در حال حاضر {active_count} دانلود فعال دارید. لطفاً منتظر بمانید تا دانلودهای قبلی تمام شوند."
    
    return True, ""

@debug_decorator
def format_user_info(user: Dict[str, Any]) -> str:
    """
    فرمت‌بندی اطلاعات کاربر
    
    Args:
        user: دیکشنری اطلاعات کاربر
        
    Returns:
        متن فرمت‌بندی شده
    """
    role_text = "نامشخص"
    
    if user['role'] == UserRole.BLOCKED:
        role_text = "🚫 مسدود شده"
    elif user['role'] == UserRole.NORMAL:
        role_text = "👤 عادی"
    elif user['role'] == UserRole.PREMIUM:
        role_text = "⭐ ویژه"
    elif user['role'] == UserRole.ADMIN:
        role_text = "🛡 ادمین"
    elif user['role'] == UserRole.SUPERADMIN:
        role_text = "👑 سوپر ادمین"
    
    user_text = f"🆔 شناسه: {user['id']}\n"
    
    if user.get('username'):
        user_text += f"🔤 نام کاربری: @{user['username']}\n"
    
    if user.get('first_name'):
        name_parts = []
        if user.get('first_name'):
            name_parts.append(user['first_name'])
        if user.get('last_name'):
            name_parts.append(user['last_name'])
        
        user_text += f"👤 نام: {' '.join(name_parts)}\n"
    
    user_text += f"🏅 نقش: {role_text}\n"
    
    if user.get('join_date'):
        user_text += f"📅 تاریخ عضویت: {user['join_date'][:10]}\n"
    
    if user.get('last_activity'):
        user_text += f"⏱ آخرین فعالیت: {user['last_activity'][:10]}\n"
    
    user_text += f"📊 تعداد دانلود: {user.get('download_count', 0)}"
    
    return user_text

@debug_decorator
def format_users_list(users: List[Dict[str, Any]]) -> str:
    """
    فرمت‌بندی لیست کاربران
    
    Args:
        users: لیست دیکشنری‌های اطلاعات کاربران
        
    Returns:
        متن فرمت‌بندی شده
    """
    if not users:
        return "هیچ کاربری یافت نشد."
    
    result = f"📊 *لیست کاربران ({len(users)} کاربر)*\n\n"
    
    for i, user in enumerate(users, 1):
        role_symbol = "🚫" if user['role'] == UserRole.BLOCKED else (
            "⭐" if user['role'] == UserRole.PREMIUM else (
            "🛡" if user['role'] == UserRole.ADMIN else "👤"
        ))
        
        name_parts = []
        if user.get('first_name'):
            name_parts.append(user['first_name'])
        if user.get('last_name'):
            name_parts.append(user['last_name'])
        
        display_name = ' '.join(name_parts) if name_parts else "بدون نام"
        
        username = f"@{user['username']}" if user.get('username') else "بدون یوزرنیم"
        
        result += f"{i}. {role_symbol} `{user['id']}` - {display_name} ({username})\n"
        
        # برای جلوگیری از پیام خیلی طولانی
        if i >= 50:
            result += f"\n... و {len(users) - 50} کاربر دیگر"
            break
    
    return result

@debug_decorator
def load_blocked_users_from_db() -> None:
    """
    بارگذاری کاربران مسدود شده از دیتابیس به کش
    """
    try:
        # دریافت همه کاربران
        users = get_all_users(limit=1000)
        
        # پیدا کردن کاربران مسدود شده
        blocked = set()
        
        for user in users:
            if user.get('role') == UserRole.BLOCKED:
                blocked.add(user['id'])
        
        # به‌روزرسانی کش
        with blocked_users_lock:
            global blocked_users
            blocked_users = blocked
            
        debug_log(f"{len(blocked_users)} کاربر مسدود شده از دیتابیس بارگذاری شد", "INFO")
        
    except Exception as e:
        debug_log(f"خطا در بارگذاری کاربران مسدود: {str(e)}", "ERROR")

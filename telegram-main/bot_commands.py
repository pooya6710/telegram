from telebot import types
from debug_logger import debug_log, debug_decorator
from config import UserRole

@debug_decorator
def register_commands(bot):
    """
    ثبت دستورات ربات در منوی تلگرام

    Args:
        bot: نمونه ربات تلگرام
    """
    try:
        # دستورات عمومی برای همه کاربران
        commands = [
            types.BotCommand("start", "شروع ربات و دریافت پیام خوش‌آمدگویی"),
            types.BotCommand("help", "راهنمای استفاده از ربات"),
            types.BotCommand("download", "دانلود ویدیو از یوتیوب"),
            types.BotCommand("status", "مشاهده وضعیت سیستم"),
            types.BotCommand("mydownloads", "مشاهده دانلودهای من"),
        ]

        # دستورات ادمین
        admin_commands = commands + [
            types.BotCommand("admin_help", "راهنمای دستورات مدیریتی"),
            types.BotCommand("users", "مشاهده لیست کاربران"),
            types.BotCommand("block", "مسدود کردن کاربر"),
            types.BotCommand("unblock", "رفع مسدودیت کاربر"),
            types.BotCommand("setadmin", "تنظیم کاربر به عنوان ادمین"),
            types.BotCommand("setpremium", "تنظیم کاربر به عنوان ویژه"),
            types.BotCommand("sysinfo", "مشاهده اطلاعات سیستم"),
            types.BotCommand("logs", "مشاهده لاگ‌های اخیر"),
            types.BotCommand("broadcast", "ارسال پیام به همه کاربران"),
            types.BotCommand("downloads", "مشاهده همه دانلودها"),
            types.BotCommand("cancelall", "لغو همه دانلودهای در حال انجام"),
        ]

        # تنظیم دستورات عمومی
        bot.set_my_commands(commands)

        # تنظیم دستورات ادمین برای ادمین‌ها (اگر API پشتیبانی کند)
        try:
            # این قابلیت در نسخه‌های جدیدتر تلگرام وجود دارد
            bot.set_my_commands(
                admin_commands,
                types.BotCommandScopeChat(config.ADMIN_IDS[0]) if config.ADMIN_IDS else None
            )
        except Exception:
            # اگر API پشتیبانی نکرد، نادیده می‌گیریم
            pass

        debug_log("دستورات ربات با موفقیت ثبت شدند", "INFO")

    except Exception as e:
        debug_log(f"خطا در ثبت دستورات ربات: {str(e)}", "ERROR")

@debug_decorator
def generate_help_message(user_role: int = UserRole.NORMAL) -> str:
    """
    تولید پیام راهنما بر اساس نقش کاربر

    Args:
        user_role: نقش کاربر

    Returns:
        متن راهنما
    """
    # پیام راهنمای عمومی
    help_msg = """📱 *راهنمای جامع ربات دانلود ویدیو:*

🎥 *دانلود ویدیو:*
• لینک یوتیوب را مستقیماً ارسال کنید
• یا از دستور `/download لینک` استفاده کنید
• لینک‌های کوتاه و عادی پشتیبانی می‌شوند
• پشتیبانی از Shorts و ویدیوهای عادی
• امکان انتخاب کیفیت دلخواه
• قابلیت لغو دانلود در حال انجام

📊 *دستورات اصلی:*
• `/start` - شروع ربات
• `/help` - نمایش راهنما
• `/status` - وضعیت سیستم
• `/mydownloads` - لیست دانلودها

⚙️ *امکانات:*
• پشتیبانی از ویدیوهای یوتیوب
• انتخاب کیفیت دلخواه
• نمایش پیشرفت دانلود
• مدیریت دانلودهای همزمان"""

    # اضافه کردن راهنمای ویژه برای کاربران ویژه
    if user_role >= UserRole.PREMIUM:
        help_msg += """

◾️ *امکانات ویژه شما:*
  • امکان دانلود همزمان بیشتر
  • دانلود فایل‌های با حجم بالاتر
  • اولویت در صف دانلود"""

    # اضافه کردن راهنمای ادمین برای ادمین‌ها
    if user_role >= UserRole.ADMIN:
        help_msg += """

◾️ *دستورات مدیریتی:*
  `/admin_help` - راهنمای کامل دستورات مدیریتی
  `/users` - مشاهده لیست کاربران
  `/block` - مسدود کردن کاربر
  `/unblock` - رفع مسدودیت کاربر
  `/sysinfo` - اطلاعات سیستم
  `/logs` - مشاهده لاگ‌ها"""

    # پیام انتهایی
    help_msg += """

📌 در صورت بروز مشکل با ادمین تماس بگیرید."""

    return help_msg

@debug_decorator
def generate_admin_help() -> str:
    """
    تولید پیام راهنمای ادمین

    Returns:
        متن راهنمای ادمین
    """
    admin_help = """🔍 *راهنمای دستورات مدیریتی:*

◾️ *مدیریت کاربران:*
  `/users` - مشاهده لیست کاربران
  `/block [user_id]` - مسدود کردن کاربر
  `/unblock [user_id]` - رفع مسدودیت کاربر
  `/setadmin [user_id]` - تنظیم کاربر به عنوان ادمین
  `/setpremium [user_id]` - تنظیم کاربر به عنوان ویژه

◾️ *مدیریت سیستم:*
  `/sysinfo` - مشاهده اطلاعات سیستم
  `/logs [count]` - مشاهده لاگ‌های اخیر
  `/broadcast [message]` - ارسال پیام به همه کاربران

◾️ *مدیریت دانلودها:*
  `/downloads` - مشاهده همه دانلودها
  `/cancelall` - لغو همه دانلودهای در حال انجام"""

    return admin_help
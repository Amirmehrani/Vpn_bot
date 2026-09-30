import os
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServerfrom datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# تنظیمات
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CARD_NUMBER = "6037997440442425"
CARD_OWNER = "امیر محمد مهرانی"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN تنظیم نشده است.")

if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID تنظیم نشده است.")


# =========================================================
# قیمت‌ها
# =========================================================

PLANS = {
    "1m": {
        "title": "🗓️ یک ماهه",
        "items": {
            "30": {"volume": "۳۰ گیگ", "price": 300000},
            "50": {"volume": "۵۰ گیگ", "price": 400000},
            "110": {"volume": "۱۱۰ گیگ", "price": 600000},
        },
    },
    "3m": {
        "title": "🗓️ سه ماهه",
        "items": {
            "30": {"volume": "۳۰ گیگ", "price": 400000},
            "50": {"volume": "۵۰ گیگ", "price": 500000},
            "110": {"volume": "۱۱۰ گیگ", "price": 700000},
        },
    },
}


# =========================================================
# دیتابیس
# =========================================================

DB_FILE =DB_FILE = "/tmp/vpn_bot.db"


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            vpn_username TEXT NOT NULL,
            duration TEXT NOT NULL,
            volume TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def create_order(
    user_id,
    username,
    vpn_username,
    duration,
    volume,
    price
):
    conn = db()

    cursor = conn.execute("""
        INSERT INTO orders
        (
            user_id,
            username,
            vpn_username,
            duration,
            volume,
            price,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        vpn_username,
        duration,
        volume,
        price,
        "در انتظار رسید",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return order_id


def get_order(order_id):
    conn = db()

    row = conn.execute(
        "SELECT * FROM orders WHERE id = ?",
        (order_id,)
    ).fetchone()

    conn.close()

    return row


def update_order_status(order_id, status):
    conn = db()

    conn.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        (status, order_id)
    )

    conn.commit()
    conn.close()


# =========================================================
# کیبورد اصلی
# =========================================================

def main_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "🛒 خرید VPN",
                callback_data="buy"
            )
        ],
        [
            InlineKeyboardButton(
                "🆘 پشتیبانی",
                callback_data="support"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# منوی مدت
# =========================================================

def duration_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "🗓️ یک ماهه",
                callback_data="duration_1m"
            )
        ],
        [
            InlineKeyboardButton(
                "🗓️ سه ماهه",
                callback_data="duration_3m"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت",
                callback_data="back_main"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# منوی حجم
# =========================================================

def volume_menu(duration):
    plan = PLANS[duration]

    keyboard = []

    for volume_key, item in plan["items"].items():
        text = (
            f"📦 {item['volume']} | "
            f"{item['price']:,} تومان"
        )

        keyboard.append([
            InlineKeyboardButton(
                text,
                callback_data=f"volume_{duration}_{volume_key}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="buy"
        )
    ])

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# تأیید سفارش
# =========================================================

def confirm_menu():
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ تأیید سفارش",
                callback_data="confirm_order"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 اصلاح سفارش",
                callback_data="buy"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# دکمه‌های ادمین
# =========================================================

def admin_order_menu(order_id):
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ تأیید پرداخت",
                callback_data=f"approve_{order_id}"
            ),
            InlineKeyboardButton(
                "❌ رد پرداخت",
                callback_data=f"reject_{order_id}"
            ),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# /start
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "👋 به ربات فروش VPN خوش آمدید.\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=main_menu()
    )


# =========================================================
# /myid
# =========================================================

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆔 شناسه عددی شما:\n\n"
        f"{update.effective_user.id}"
    )


# =========================================================
# /cancel
# =========================================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ عملیات لغو شد.\n\n"
        "منوی اصلی:",
        reply_markup=main_menu()
    )


# =========================================================
# کلیک روی دکمه‌ها
# =========================================================

async def callbacks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    data = query.data

    # =====================================================
    # خرید
    # =====================================================

    if data == "buy":

        context.user_data.clear()

        await query.edit_message_text(
            "🛒 خرید VPN\n\n"
            "مدت سرویس را انتخاب کنید:",
            reply_markup=duration_menu()
        )

        return

    # =====================================================
    # انتخاب مدت
    # =====================================================

    if data.startswith("duration_"):

        duration = data.replace("duration_", "")

        if duration not in PLANS:
            return

        context.user_data["duration"] = duration

        await query.edit_message_text(
            f"{PLANS[duration]['title']}\n\n"
            "حجم سرویس را انتخاب کنید:",
            reply_markup=volume_menu(duration)
        )

        return

    # =====================================================
    # انتخاب حجم
    # =====================================================

    if data.startswith("volume_"):

        parts = data.split("_")

        if len(parts) != 3:
            return

        _, duration, volume_key = parts

        if duration not in PLANS:
            return

        if volume_key not in PLANS[duration]["items"]:
            return

        item = PLANS[duration]["items"][volume_key]

        context.user_data["duration"] = duration
        context.user_data["volume_key"] = volume_key
        context.user_data["volume"] = item["volume"]
        context.user_data["price"] = item["price"]
        context.user_data["state"] = "waiting_vpn_username"

        await query.edit_message_text(
            f"📦 حجم انتخابی: {item['volume']}\n"
            f"💰 مبلغ: {item['price']:,} تومان\n\n"
            "👤 حالا نام کاربری VPN خود را وارد کنید.\n\n"
            "فقط حروف انگلیسی و اعداد مجاز هستند.\n"
            "حداقل ۳ و حداکثر ۲۰ کاراکتر.\n\n"
            "مثال: Ali123"
        )

        return

    # =====================================================
    # تأیید سفارش
    # =====================================================

    if data == "confirm_order":

        required = [
            "duration",
            "volume",
            "price",
            "vpn_username",
        ]

        if not all(
            key in context.user_data
            for key in required
        ):
            await query.edit_message_text(
                "❌ اطلاعات سفارش ناقص است.\n\n"
                "لطفاً دوباره از منوی خرید شروع کنید.",
                reply_markup=main_menu()
            )
            return

        duration = context.user_data["duration"]
        volume = context.user_data["volume"]
        price = context.user_data["price"]
        vpn_username = context.user_data["vpn_username"]

        telegram_username = (
            update.effective_user.username or "ندارد"
        )

        order_id = create_order(
            user_id=update.effective_user.id,
            username=telegram_username,
            vpn_username=vpn_username,
            duration=PLANS[duration]["title"],
            volume=volume,
            price=price,
        )

        context.user_data["order_id"] = order_id
        context.user_data["state"] = "waiting_receipt"

        await query.edit_message_text(
            f"💳 پرداخت سفارش #{order_id}\n\n"
            f"📦 حجم: {volume}\n"
            f"🗓️ مدت: {PLANS[duration]['title']}\n"
            f"👤 نام کاربری VPN: {vpn_username}\n"
            f"👥 کاربر: نامحدود\n"
            f"💰 مبلغ: {price:,} تومان\n\n"
            "💳 شماره کارت:\n"
            f"`{CARD_NUMBER}`\n\n"
            f"👤 به نام: {CARD_OWNER}\n\n"
            "📸 بعد از کارت‌به‌کارت، "
            "عکس رسید پرداخت را همینجا ارسال کنید."
        ,
            parse_mode="Markdown"
        )

        return

    # =====================================================
    # پشتیبانی
    # =====================================================

    if data == "support":

        context.user_data["state"] = "support"

        await query.edit_message_text(
            "🆘 پشتیبانی\n\n"
            "📝 مشکل یا درخواست خود را بنویسید.\n\n"
            "پیام شما برای پشتیبانی ارسال می‌شود "
            "و پاسخ را همینجا دریافت می‌کنید."
        )

        return

    # =====================================================
    # بازگشت به منوی اصلی
    # =====================================================

    if data == "back_main":

        context.user_data.clear()

        await query.edit_message_text(
            "🏠 منوی اصلی",
            reply_markup=main_menu()
        )

        return

    # =====================================================
    # تأیید پرداخت توسط ادمین
    # =====================================================

    if data.startswith("approve_"):

        if update.effective_user.id != ADMIN_ID:
            await query.answer(
                "⛔ دسترسی ندارید.",
                show_alert=True
            )
            return

        order_id = int(data.replace("approve_", ""))

        order = get_order(order_id)

        if not order:
            await query.edit_message_text(
                "❌ سفارش پیدا نشد."
            )
            return

        update_order_status(
            order_id,
            "پرداخت تأیید شد"
        )

        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"✅ پرداخت سفارش #{order_id} تأیید شد.\n\n"
                    f"📦 حجم: {order['volume']}\n"
                    f"🗓️ مدت: {order['duration']}\n"
                    f"👤 نام کاربری VPN: {order['vpn_username']}\n\n"
                    "🎉 سفارش شما تأیید شد."
                )
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"✅ سفارش #{order_id} تأیید شد."
        )

        return

    # =====================================================
    # رد پرداخت توسط ادمین
    # =====================================================

    if data.startswith("reject_"):

        if update.effective_user.id != ADMIN_ID:
            await query.answer(
                "⛔ دسترسی ندارید.",
                show_alert=True
            )
            return

        order_id = int(data.replace("reject_", ""))

        order = get_order(order_id)

        if not order:
            await query.edit_message_text(
                "❌ سفارش پیدا نشد."
            )
            return

        update_order_status(
            order_id,
            "پرداخت رد شد"
        )

        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"❌ پرداخت سفارش #{order_id} رد شد.\n\n"
                    "لطفاً رسید صحیح را ارسال کنید "
                    "یا با پشتیبانی تماس بگیرید."
                )
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"❌ سفارش #{order_id} رد شد."
        )

        return


# =========================================================
# دریافت نام کاربری VPN
# =========================================================

async def handle_vpn_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    state = context.user_data.get("state")

    if state != "waiting_vpn_username":
        return False

    if not update.message.text:
        return True

    vpn_username = update.message.text.strip()

    if not re.fullmatch(
        r"[A-Za-z0-9]{3,20}",
        vpn_username
    ):
        await update.message.reply_text(
            "❌ نام کاربری نامعتبر است.\n\n"
            "نام کاربری باید فقط شامل حروف انگلیسی و اعداد باشد.\n"
            "حداقل ۳ و حداکثر ۲۰ کاراکتر.\n\n"
            "مثال صحیح: Ali123"
        )

        return True

    context.user_data["vpn_username"] = vpn_username
    context.user_data["state"] = "confirming"

    duration = context.user_data["duration"]
    volume = context.user_data["volume"]
    price = context.user_data["price"]

    await update.message.reply_text(
        "🧾 تأیید سفارش\n\n"
        f"👤 نام کاربری VPN: {vpn_username}\n"
        f"🗓️ مدت: {PLANS[duration]['title']}\n"
        f"📦 حجم: {volume}\n"
        "👥 تعداد کاربر: نامحدود\n"
        f"💰 مبلغ: {price:,} تومان\n\n"
        "آیا اطلاعات سفارش درست است؟",
        reply_markup=confirm_menu()
    )

    return True


# =========================================================
# دریافت رسید
# =========================================================

async def handle_receipt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    state = context.user_data.get("state")

    if state != "waiting_receipt":
        return False

    order_id = context.user_data.get("order_id")

    if not order_id:
        await update.message.reply_text(
            "❌ سفارش پیدا نشد.\n"
            "لطفاً دوباره از /start شروع کنید."
        )

        return True

    order = get_order(order_id)

    if not order:
        await update.message.reply_text(
            "❌ سفارش پیدا نشد."
        )

        return True

    # -----------------------------------------------------
    # اگر عکس باشد
    # -----------------------------------------------------

    if update.message.photo:

        photo = update.message.photo[-1]

        caption = (
            f"💳 رسید پرداخت جدید\n\n"
            f"🆔 سفارش: #{order['id']}\n"
            f"👤 کاربر: {order['username']}\n"
            f"🆔 Telegram ID: {order['user_id']}\n"
            f"👤 نام کاربری VPN: {order['vpn_username']}\n"
            f"🗓️ مدت: {order['duration']}\n"
            f"📦 حجم: {order['volume']}\n"
            f"💰 مبلغ: {order['price']:,} تومان\n"
            f"📅 زمان: {order['created_at']}\n\n"
            "لطفاً رسید را بررسی کنید."
        )

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=caption,
            reply_markup=admin_order_menu(order_id)
        )

        update_order_status(
            order_id,
            "رسید دریافت شد"
        )

        context.user_data["state"] = "waiting_admin"

        await update.message.reply_text(
            f"✅ رسید سفارش #{order_id} دریافت شد.\n\n"
            "⏳ رسید برای پشتیبانی ارسال شد.\n"
            "بعد از بررسی، نتیجه برای شما ارسال می‌شود."
        )

        return True

    # -----------------------------------------------------
    # اگر فایل باشد
    # -----------------------------------------------------

    if update.message.document:

        document = update.message.document

        caption = (
            f"💳 رسید پرداخت جدید\n\n"
            f"🆔 سفارش: #{order['id']}\n"
            f"👤 کاربر: {order['username']}\n"
            f"🆔 Telegram ID: {order['user_id']}\n"
            f"👤 نام کاربری VPN: {order['vpn_username']}\n"
            f"🗓️ مدت: {order['duration']}\n"
            f"📦 حجم: {order['volume']}\n"
            f"💰 مبلغ: {order['price']:,} تومان"
        )

        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=document.file_id,
            caption=caption,
            reply_markup=admin_order_menu(order_id)
        )

        update_order_status(
            order_id,
            "رسید دریافت شد"
        )

        context.user_data["state"] = "waiting_admin"

        await update.message.reply_text(
            f"✅ رسید سفارش #{order_id} دریافت شد."
        )

        return True

    await update.message.reply_text(
        "❌ لطفاً عکس رسید پرداخت را ارسال کنید."
    )

    return True


# =========================================================
# پشتیبانی
# =========================================================

async def handle_support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    state = context.user_data.get("state")

    if state != "support":
        return False

    user = update.effective_user

    if update.message.text:

        message_text = update.message.text

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "🆘 پیام جدید پشتیبانی\n\n"
                f"👤 کاربر: "
                f"@{user.username if user.username else 'ندارد'}\n"
                f"🆔 Telegram ID: {user.id}\n\n"
                f"💬 پیام:\n{message_text}"
            )
        )

        await update.message.reply_text(
            "✅ پیام شما برای پشتیبانی ارسال شد.\n\n"
            "پاسخ پشتیبانی از همین ربات برای شما ارسال می‌شود."
        )

        return True

    return True


# =========================================================
# پاسخ ادمین به کاربر
#
# ادمین باید پیام را به شکل زیر ارسال کند:
#
# /reply USER_ID متن پیام
# =========================================================

async def admin_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ شما دسترسی ادمین ندارید."
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "فرمت صحیح:\n\n"
            "/reply USER_ID پیام شما"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ USER_ID باید عددی باشد."
        )
        return

    message = " ".join(context.args[1:])

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "🆘 پاسخ پشتیبانی:\n\n"
                f"{message}"
            )
        )

        await update.message.reply_text(
            "✅ پیام برای کاربر ارسال شد."
        )

    except Exception as e:

        await update.message.reply_text(
            "❌ ارسال پیام انجام نشد.\n\n"
            f"خطا: {e}"
        )


# =========================================================
# پیام‌های معمولی
# =========================================================

async def messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if await handle_vpn_username(update, context):
        return

    if await handle_receipt(update, context):
        return

    if await handle_support(update, context):
        return

    await update.message.reply_text(
        "لطفاً از منوی ربات استفاده کنید.",
        reply_markup=main_menu()
    )


# =========================================================
# خطاها
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "ERROR:",
        context.error
    )


# =========================================================
# اجرای ربات
# =========================================================

def main():

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("myid", myid)
    )

    application.add_handler(
        CommandHandler("cancel", cancel)
    )

    application.add_handler(
        CommandHandler("reply", admin_reply)
    )

    application.add_handler(
        CallbackQueryHandler(callbacks)
    )

    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            messages
        )
    )

    application.add_error_handler(
        error_handler
    )

    print("🤖 Bot is running...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 3000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


threading.Thread(target=start_health_server, daemon=True).start()
    main()

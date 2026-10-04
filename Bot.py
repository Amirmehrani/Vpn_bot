import os
import re
import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "0")

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    ADMIN_ID = 0

CARD_NUMBER = "6037997440442425"
CARD_OWNER = "امیر محمد مهرانی"
DB_FILE = os.getenv("DB_FILE", "/data/vpn_bot.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN تنظیم نشده است.")

PLANS = {
    "1m": {
        "title": "🗓️ یک ماهه",
        "items": {
            "30": {"volume": "۳۰ گیگ", "price": 350000},
            "50": {"volume": "۵۰ گیگ", "price": 450000},
            "110": {"volume": "۱۱۰ گیگ", "price": 800000},
        },
    },
    "3m": {
        "title": "🗓️ سه ماهه",
        "items": {
            "30": {"volume": "۳۰ گیگ", "price": 450000},
            "50": {"volume": "۵۰ گیگ", "price": 550000},
            "110": {"volume": "۱۱۰ گیگ", "price": 800000},
        },
    },
}


def db():
    Path("/data").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            telegram_username TEXT,
            vpn_username TEXT NOT NULL,
            duration TEXT NOT NULL,
            volume TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            admin_message_id INTEGER,
            user_message_id INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def create_order(user_id, telegram_username, vpn_username, duration, volume, price):
    conn = db()
    cur = conn.execute(
        """
        INSERT INTO orders
        (user_id, telegram_username, vpn_username, duration, volume, price, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            telegram_username,
            vpn_username,
            duration,
            volume,
            price,
            "در انتظار رسید",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def update_order_status(order_id, status):
    conn = db()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def save_support_mapping(user_id, admin_message_id, user_message_id):
    conn = db()
    conn.execute(
        """
        INSERT INTO support_messages
        (user_id, admin_message_id, user_message_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            admin_message_id,
            user_message_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def find_support_user(admin_message_id):
    conn = db()
    row = conn.execute(
        """
        SELECT user_id
        FROM support_messages
        WHERE admin_message_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (admin_message_id,),
    ).fetchone()
    conn.close()
    return int(row["user_id"]) if row else None


def main_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛒 خرید VPN", callback_data="buy")],
            [InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
    )
def back_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🔙 بازگشت")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def duration_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗓️ یک ماهه", callback_data="duration_1m")],
            [InlineKeyboardButton("🗓️ سه ماهه", callback_data="duration_3m")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
    )


def volume_menu(duration):
    buttons = []
    for key, item in PLANS[duration]["items"].items():
        buttons.append(
            [
                InlineKeyboardButton(
                    f"📦 {item['volume']} | {item['price']:,} تومان",
                    callback_data=f"volume_{duration}_{key}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="buy")])
    return InlineKeyboardMarkup(buttons)


def confirm_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ تأیید سفارش", callback_data="confirm_order")],
            [InlineKeyboardButton("🔙 اصلاح سفارش", callback_data="buy")],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "⚡️به ربات FAST VPN خوش آمدید.⚡️\n"
        "📍بدون محدودیت کاربر(اشتراک‌ خانواده)\n"
        "📍تضمین اتصال و سرعت تا روز آخر\n"
        "📍مولتی لوکیشن 🇺🇸🇩🇪🇮🇷🇹🇷🇫🇮\n"
        "📍پینگ عالی مناسب گیمینگ\n"
        "📍بدون لگ و تاخیر مناسب اینستاگرام\n"
        "📍لوکیشن‌های ثابت مناسب ترید\n"
        "📍رفع تحریم هوش‌مصنوعی و اسپاتیفای",
        reply_markup=main_menu(),
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 شناسه عددی شما:\n\n{update.effective_user.id}"
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "buy":
        context.user_data.clear()
        await query.edit_message_text(
            "🛒 خرید VPN\n\nمدت سرویس را انتخاب کنید:",
            reply_markup=duration_menu(),
        )
        return

    if data.startswith("duration_"):
        duration = data.replace("duration_", "")
        context.user_data["duration"] = duration
        await query.edit_message_text(
            f"{PLANS[duration]['title']}\n\nحجم سرویس را انتخاب کنید:",
            reply_markup=volume_menu(duration),
        )
        return

    if data.startswith("volume_"):
        _, duration, volume_key = data.split("_")
        item = PLANS[duration]["items"][volume_key]
        context.user_data.update(
            {
                "duration": duration,
                "volume": item["volume"],
                "price": item["price"],
                "state": "waiting_vpn_username",
            }
        )
        await query.edit_message_text(
            f"📦 حجم انتخابی: {item['volume']}\n"
            f"💰 مبلغ: {item['price']:,} تومان\n\n"
            "👤 نام کاربری VPN خود را وارد کنید.\n\n"
            "فقط حروف انگلیسی و اعداد مجاز هستند.\n"
            "بین ۳ تا ۲۰ کاراکتر.\n"
            "مثال: Ali123"
        )
        return

    if data == "confirm_order":
        required = ("duration", "volume", "price", "vpn_username")
        if any(key not in context.user_data for key in required):
            await query.edit_message_text(
                "❌ اطلاعات سفارش ناقص است. لطفاً دوباره از خرید VPN شروع کنید.",
                reply_markup=main_menu(),
            )
            return

        duration = context.user_data["duration"]
        volume = context.user_data["volume"]
        price = context.user_data["price"]
        vpn_username = context.user_data["vpn_username"]
        tg_username = update.effective_user.username or "ندارد"

        order_id = create_order(
            update.effective_user.id,
            tg_username,
            vpn_username,
            PLANS[duration]["title"],
            volume,
            price,
        )
        context.user_data.update(
            {"order_id": order_id, "state": "waiting_receipt"}
        )

        await query.edit_message_text(
            f"💳 پرداخت سفارش #{order_id}\n\n"
            f"📦 حجم: {volume}\n"
            f"🗓️ مدت: {PLANS[duration]['title']}\n"
            f"👤 نام کاربری VPN: {vpn_username}\n"
            "👥 تعداد کاربر: نامحدود\n"
            f"💰 مبلغ: {price:,} تومان\n\n"
            "💳 شماره کارت:\n"
            f"`{CARD_NUMBER}`\n\n"
            f"👤 به نام: {CARD_OWNER}\n\n"
            "📸 بعد از کارت‌به‌کارت، عکس رسید را همینجا ارسال کنید.",
            parse_mode="Markdown",
        )
        return

    if data == "support":
        context.user_data["state"] = "support"
        await query.edit_message_text(
            "🆘 پشتیبانی\n\n"
            "📝 مشکل یا درخواست خود را بنویسید.\n"
            "پیام شما برای پشتیبانی ارسال می‌شود و پاسخ را همین‌جا دریافت می‌کنید."
        )
        return

    if data == "back_main":
        context.user_data.clear()
        await query.edit_message_text(
            "🏠 منوی اصلی", reply_markup=main_menu()
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    if text == "🔙 بازگشت":
        context.user_data.clear()

        await update.message.reply_text(
            "🏠 به منوی اصلی برگشتید.",
            reply_markup=main_menu(),
        )
        return
    # Admin reply routing: reply directly to a support message in the admin chat.
    if ADMIN_ID and user and user.id == ADMIN_ID and update.message.reply_to_message:
        target_user_id = find_support_user(update.message.reply_to_message.message_id)
        if target_user_id:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🆘 پاسخ پشتیبانی:\n\n{text}",
            )
            await update.message.reply_text("✅ پاسخ برای کاربر ارسال شد.")
            return

    state = context.user_data.get("state")

    if state == "waiting_vpn_username":
        if not re.fullmatch(r"[A-Za-z0-9]{3,20}", text):
            await update.message.reply_text(
                "❌ نام کاربری نامعتبر است.\n\n"
                "فقط حروف انگلیسی و اعداد، بین ۳ تا ۲۰ کاراکتر.\n"
                "مثال: Ali123"
            )
            return

        context.user_data["vpn_username"] = text
        context.user_data["state"] = "confirming"
        duration = context.user_data["duration"]
        await update.message.reply_text(
            "🧾 تأیید سفارش\n\n"
            f"👤 نام کاربری VPN: `{text}`\n"
            f"🗓️ مدت: {PLANS[duration]['title']}\n"
            f"📦 حجم: {context.user_data['volume']}\n"
            "👥 تعداد کاربر: نامحدود\n"
            f"💰 مبلغ: {context.user_data['price']:,} تومان\n\n"
            "آیا اطلاعات سفارش درست است؟",
            parse_mode="Markdown",
            reply_markup=confirm_menu(),
        )
        return

    if state == "support":
        if not ADMIN_ID:
            await update.message.reply_text(
                "⚠️ پشتیبانی هنوز تنظیم نشده است."
            )
            return

        msg = (
            "🆘 پیام پشتیبانی جدید\n\n"
            f"👤 نام: {user.full_name}\n"
            f"🔗 یوزرنیم تلگرام: @{user.username if user.username else 'ندارد'}\n"
            f"🆔 ID: {user.id}\n\n"
            f"💬 پیام:\n{text}\n\n"
            "↩️ برای پاسخ، همین پیام را Reply کنید."
        )
        admin_msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=msg,
        )
        save_support_mapping(
            user.id,
            admin_msg.message_id,
            update.message.message_id,
        )
        await update.message.reply_text(
            "✅ پیام شما برای پشتیبانی ارسال شد.\n"
            "پاسخ را همینجا دریافت می‌کنید."
        )
        return

    await update.message.reply_text(
        "لطفاً از منوی اصلی یکی از گزینه‌ها را انتخاب کنید.",
        reply_markup=main_menu(),
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if text == "🔙 بازگشت":
        context.user_data.clear()

        await update.message.reply_text(
            "🏠 به منوی اصلی برگشتید.",
            reply_markup=main_menu(),
        )
        return
    # Admin reply with photo -> send photo + caption to customer
    if ADMIN_ID and user and user.id == ADMIN_ID and update.message.reply_to_message:
        target_user_id = find_support_user(
            update.message.reply_to_message.message_id
        )

        if target_user_id:
            caption = update.message.caption or ""

            await context.bot.send_photo(
                chat_id=target_user_id,
                photo=update.message.photo[-1].file_id,
                caption=caption,
            )

            await update.message.reply_text(
                "✅ عکس و متن برای مشتری ارسال شد."
            )
            return

    state = context.user_data.get("state")

    if state == "waiting_receipt":
        order_id = context.user_data.get("order_id")

        if not order_id:
            await update.message.reply_text(
                "❌ سفارش پیدا نشد. دوباره از خرید VPN شروع کنید."
            )
            return

        update_order_status(order_id, "رسید ارسال شد")
        caption = update.message.caption or ""
        user = update.effective_user

        if ADMIN_ID:
            admin_msg = await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=update.message.photo[-1].file_id,
                caption=(
                    f"📸 رسید پرداخت سفارش #{order_id}\n\n"
                    f"👤 کاربر: {user.full_name}\n"
                    f"🆔 ID: {user.id}\n"
                    f"🔗 @{user.username if user.username else 'ندارد'}\n"
                    f"📝 توضیح: {caption or 'ندارد'}\n\n"
                    "↩️ برای ارسال پاسخ، روی همین عکس Reply کنید."
                ),
            )

            save_support_mapping(
                user.id,
                admin_msg.message_id,
                update.message.message_id,
            )

        await update.message.reply_text(
            "✅ رسید شما دریافت شد.\n\n"
            "⏳ پس از بررسی پرداخت، سرویس شما تأیید می‌شود و "
            "کانفیگ توسط پشتیبانی برایتان ارسال خواهد شد."
        )

        context.user_data["state"] = "done"
        return

    await update.message.reply_text(
        "لطفاً ابتدا یک سفارش ثبت کنید."
    )

web_app = Flask(__name__)

@web_app.route("/")
def health():
    return "Bot is running", 200

def run_web():
    port = int(os.getenv("PORT", "8080"))
    web_app.run(host="0.0.0.0", port=port)
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("VPN Fast Bot is running...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    main()

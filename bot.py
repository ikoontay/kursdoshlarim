import asyncio
import logging
import requests
import os
from datetime import datetime, date, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web  # Render tekin ishlashi uchun veb-server

# BotFather'dan olingan token
TOKEN = "8721855561:AAHcOCgVMER6EBmeSf1gmELEtnyAkxHatGk"

# Asosiy admin ID raqamingiz
ADMIN_ID = 8973505803 

APPROVED_USERS = [ADMIN_ID]
ADMINS = [ADMIN_ID]

HOMEWORKS = []
STATS = {"total_requests": 0}

HEMIS_URL = "https://student.karsu.uz"
HEMIS_LOGIN = "346241105649"
HEMIS_PASSWORD = "Mens2004wwww"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

_hemis_cache = {
    "date": None,
    "token": None,
    "token_time": 0,
    "lessons": []
}

def get_hemis_token():
    import time
    if _hemis_cache["token"] and (time.time() - _hemis_cache["token_time"] < 3600):
        return _hemis_cache["token"]
        
    try:
        url = f"{HEMIS_URL}/rest/v1/auth/login"
        response = requests.post(url, data={
            "login": HEMIS_LOGIN,
            "password": HEMIS_PASSWORD
        }, timeout=10)
        data = response.json()
        if data.get("success"):
            _hemis_cache["token"] = data["data"]["token"]
            _hemis_cache["token_time"] = time.time()
            return _hemis_cache["token"]
    except Exception as e:
        logging.error(f"HEMIS token olishda xatolik: {e}")
    return None

def update_schedule_cache():
    token = get_hemis_token()
    if not token:
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        url = f"{HEMIS_URL}/rest/v1/education/schedule"
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        
        if data.get("success") and data.get("data"):
            _hemis_cache["lessons"] = data["data"]
            _hemis_cache["date"] = date.today()
            logging.info("HEMIS ma'lumotlari muvaffaqiyatli keshlandi.")
            return True
    except Exception as e:
        logging.error(f"Keshni yangilashda xatolik: {e}")
    return False

def get_schedule_text(start_date: date, end_date: date, mode: str):
    today = date.today()
    if not _hemis_cache["lessons"] or _hemis_cache["date"] != today:
        update_schedule_cache()

    lessons = _hemis_cache["lessons"]
    start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp())
    
    token = get_hemis_token()
    if token:
        try:
            url = f"{HEMIS_URL}/rest/v1/education/schedule?start={start_timestamp}&end={end_timestamp}"
            response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
            data = response.json()
            if data.get("success") and data.get("data"):
                fetched_lessons = data["data"]
                existing_ids = {item.get("id") for item in lessons}
                for item in fetched_lessons:
                    if item.get("id") not in existing_ids:
                        lessons.append(item)
        except Exception as e:
            logging.error(f"Sana bo'yicha HEMISdan olishda xatolik: {e}")

    if mode == "today":
        result_text = f"🌟 <b>BUGUNGI DARS JADVALI</b>\n📅 Sana: <b>{start_date.strftime('%d.%m.%Y')}</b>\n\n"
    elif mode == "tomorrow":
        result_text = f"🌟 <b>ERTANGI DARS JADVALI</b>\n📅 Sana: <b>{start_date.strftime('%d.%m.%Y')}</b>\n\n"
    elif mode == "custom":
        result_text = f"🔍 <b>TANLANGAN SANA JADVALI</b>\n📅 Sana: <b>{start_date.strftime('%d.%m.%Y')}</b>\n\n"
    else:
        result_text = f"📊 <b>SHU HAFTA TO'LIQ JADVALI</b>\n🗓 ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}):\n\n"
    
    schedule_by_date = {}
    for item in lessons:
        raw_date = item.get("lesson_date", item.get("date"))
        if not raw_date:
            continue
        try:
            lesson_dt = datetime.fromtimestamp(int(raw_date))
            d_str = lesson_dt.strftime('%d.%m.%Y')
        except:
            continue
        
        if not (start_date <= lesson_dt.date() <= end_date):
            continue
            
        if d_str not in schedule_by_date:
            schedule_by_date[d_str] = []
        schedule_by_date[d_str].append(item)
        
    if not schedule_by_date:
        if mode == "today":
            result_text += "🎉 Bugun darslar yo'q! Dam olish kuni. ☕\n\n"
        elif mode == "tomorrow":
            result_text += "🎉 Ertaga darslar yo'q! Dam olish kuni. ☕\n\n"
        elif mode == "custom":
            result_text += f"🎉 {start_date.strftime('%d.%m.%Y')} sanasida darslar yo'q.\n\n"
        else:
            return "📭 Bu hafta uchun darslar topilmadi."

    for d_str, day_lessons in schedule_by_date.items():
        if mode == "week":
            result_text += f"📌 <b>--- {d_str} ---</b>\n"
        
        day_lessons.sort(key=lambda x: x.get("lessonPair", {}).get("start_time", ""))
        
        for index, item in enumerate(day_lessons, start=1):
            subject = item.get("subject", {}).get("name", "Fan nomi")
            lesson_type = item.get("trainingType", {}).get("name", "Dars")
            pair_info = item.get("lessonPair", {})
            start_time = pair_info.get("start_time", "")
            end_time = pair_info.get("end_time", "")
            
            auditorium = item.get("auditorium")
            aud_name = auditorium.get("name", "Ko'rsatilmagan") if auditorium else "Ko'rsatilmagan"
            
            emp_data = item.get("employee") or item.get("teacher") or item.get("staff")
            teacher = "Ko'rsatilmagan"
            if emp_data:
                if isinstance(emp_data, dict):
                    t_name = emp_data.get("name")
                    t_first = emp_data.get("first_name", "") or emp_data.get("firstname", "")
                    t_last = emp_data.get("last_name", "") or emp_data.get("lastname", "")
                    if t_name:
                        teacher = t_name
                    elif t_first or t_last:
                        teacher = f"{t_last} {t_first}".strip()
                elif isinstance(emp_data, str):
                    teacher = emp_data
            
            result_text += f"🔹 <b>{index}-para</b> <i>({start_time} - {end_time})</i>\n"
            result_text += f"  📚 <b>Fan:</b> {subject} ({lesson_type})\n"
            result_text += f"  🏛 <b>Auditoriya:</b> {aud_name}\n"
            result_text += f"  👨‍🏫 <b>O'qituvchi:</b> {teacher}\n\n"
            
        current_check_date = start_date if mode in ["today", "tomorrow", "custom"] else datetime.strptime(d_str, '%d.%m.%Y').date()
        matching_hws = [hw for hw in HOMEWORKS if hw["deadline"] == current_check_date]
        if matching_hws:
            result_text += f"📝 <b>Uyga vazifalar (Topshirish muddati: {d_str}):</b>\n"
            for hw in matching_hws:
                result_text += f"  • <b>{hw['subject']}</b> <i>({hw['target']})</i>: {hw['text']}\n"
            result_text += "\n"

    return result_text

def get_schedule_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📚 Bugungi dars jadvali", callback_data="btn_today"),
        InlineKeyboardButton("📅 Ertangi dars jadvali", callback_data="btn_tomorrow"),
        InlineKeyboardButton("📊 Shu hafta to'liq jadvali", callback_data="btn_week"),
        InlineKeyboardButton("🔍 Aniq bir sanani tanlash", callback_data="btn_custom_prompt"),
        InlineKeyboardButton("📝 Faol uyga vazifalar", callback_data="btn_homeworks"),
        InlineKeyboardButton("📊 Bot statistikasi", callback_data="btn_stats")
    )
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔙 Asosiy menyuga qaytish", callback_data="btn_main_menu"))
    return keyboard

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in APPROVED_USERS:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📩 Adminga ruxsat so'rovini yuborish", callback_data=f"req_{user_id}"))
        await message.answer(
            "⛔ <b>Kechirasiz, sizda bu botdan foydalanish huquqi yo'q.</b>\n\n"
            "Botdan foydalanish uchun admin ruxsati kerak. Quyidagi tugmani bosib ruxsat so'rashingiz mumkin:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return
    
    await message.answer(
        "👋 Assalomu alaykum! Kursdoshlar yordamchi botiga xush kelibsiz.\n"
        "Kerakli bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=get_schedule_keyboard()
    )

@dp.message_handler(commands=["send"])
async def cmd_send(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    text_to_send = message.text.replace("/send", "").strip()
    if not text_to_send:
        await message.reply("⚠️ Xabar matni kiritilmadi!", parse_mode="HTML")
        return
    
    for uid in APPROVED_USERS:
        try:
            await bot.send_message(uid, f"📢 <b>Admindan e'lon:</b>\n\n{text_to_send}", parse_mode="HTML")
            await asyncio.sleep(0.1)
        except:
            pass
    await message.reply("✅ Xabar tarqatildi!", parse_mode="HTML")

@dp.message_handler(commands=["hw"])
async def cmd_add_homework(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.reply("⛔ Bu buyruq faqat adminlar uchun!")
        return
        
    text = message.text.replace("/hw", "").strip()
    parts = text.split("|")
    
    if len(parts) < 4:
        await message.reply(
            "⚠️ <b>Noto'g'ri format!</b>\n"
            "Ishlatilishi:\n"
            "<code>/hw Fan nomi | Vazifa matni | Kimlar uchun | DD.MM.YYYY</code>",
            parse_mode="HTML"
        )
        return
        
    subject = parts[0].strip()
    hw_text = parts[1].strip()
    target = parts[2].strip()
    date_str = parts[3].strip()
    
    try:
        deadline_date = datetime.strptime(date_str, '%d.%m.%Y').date()
    except ValueError:
        await message.reply("⚠️ Sana formati noto'g'ri! Masalan: <code>15.10.2026</code>", parse_mode="HTML")
        return
        
    new_hw = {
        "subject": subject,
        "text": hw_text,
        "target": target,
        "deadline": deadline_date,
        "notified_day_before": False
    }
    HOMEWORKS.append(new_hw)
    
    announcement = (
        f"📝 <b>YANGI UYGA VAZIFA QO'SHILDI!</b>\n\n"
        f"📚 <b>Fan:</b> {subject}\n"
        f"📌 <b>Vazifa:</b> {hw_text}\n"
        f"👥 <b>Kimlar uchun:</b> {target}\n"
        f"⏰ <b>Topshirish muddati:</b> {date_str}"
    )
    
    for uid in APPROVED_USERS:
        try:
            await bot.send_message(uid, announcement, parse_mode="HTML")
        except:
            pass
            
    await message.reply("✅ Uyga vazifa qo'shildi va e'lon qilindi!")

@dp.message_handler(commands=["addadmin"])
async def cmd_add_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        return
    try:
        new_admin_id = int(args[1])
        if new_admin_id not in ADMINS:
            ADMINS.append(new_admin_id)
            if new_admin_id not in APPROVED_USERS:
                APPROVED_USERS.append(new_admin_id)
            await message.reply(f"✅ {new_admin_id} admin qilindi!")
    except ValueError:
        pass

@dp.message_handler(commands=["stats"])
async def cmd_stats(message: types.Message):
    if message.from_user.id not in APPROVED_USERS:
        return
    await message.reply(
        f"📊 <b>Bot statistikasi:</b>\n\n"
        f"👥 Tasdiqlanganlar: <b>{len(APPROVED_USERS)} ta</b>\n"
        f"👑 Adminlar: <b>{len(ADMINS)} ta</b>\n"
        f"📝 Faol vazifalar: <b>{len(HOMEWORKS)} ta</b>\n"
        f"🔄 So'rovlar: <b>{STATS['total_requests']} ta</b>",
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data.startswith("req_"))
async def process_access_request(callback_query: types.CallbackQuery):
    user_id_to_allow = int(callback_query.data.split("_")[1])
    user = callback_query.from_user
    admin_keyboard = InlineKeyboardMarkup()
    admin_keyboard.add(InlineKeyboardButton("✅ Ruxsat berish", callback_data=f"allow_{user_id_to_allow}"))
    try:
        await bot.send_message(ADMIN_ID, f"🔔 <b>Yangi so'rov!</b> ID: <code>{user_id_to_allow}</code>", parse_mode="HTML", reply_markup=admin_keyboard)
        await bot.answer_callback_query(callback_query.id, "✅ Adminga yuborildi!", show_alert=True)
    except:
        await bot.answer_callback_query(callback_query.id, "⚠️ Xatolik.", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("allow_"))
async def process_admin_allow(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    allowed_id = int(callback_query.data.split("_")[1])
    if allowed_id not in APPROVED_USERS:
        APPROVED_USERS.append(allowed_id)
    await bot.answer_callback_query(callback_query.id, f"✅ Tasdiqlandi!")
    try:
        await bot.send_message(allowed_id, "🎉 Admin ruxsat berdi! /start ni bosing.", parse_mode="HTML")
    except:
        pass
    await callback_query.message.edit_text(callback_query.message.text + "\n\n<b>✅ TASDIQLANDI</b>", parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data in ["btn_today", "btn_tomorrow", "btn_week", "btn_custom_prompt", "btn_homeworks", "btn_stats", "btn_main_menu"])
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in APPROVED_USERS:
        await bot.answer_callback_query(callback_query.id, "Huquq yo'q!")
        return
    
    await bot.answer_callback_query(callback_query.id)
    STATS["total_requests"] += 1
    today = datetime.now().date()
    
    if callback_query.data == "btn_main_menu":
        await bot.send_message(callback_query.message.chat.id, "👋 Asosiy menyu:", parse_mode="HTML", reply_markup=get_schedule_keyboard())
        return
        
    if callback_query.data == "btn_homeworks":
        active_hws = [hw for hw in HOMEWORKS if hw["deadline"] >= today]
        if not active_hws:
            hw_text = "📭 Hozircha faol uyga vazifalar yo'q."
        else:
            hw_text = "📝 <b>Barcha faol uyga vazifalar:</b>\n\n"
            for hw in active_hws:
                hw_text += f"📚 <b>{hw['subject']}</b>\n👥 {hw['target']}\n📌 {hw['text']}\n⏰ Muddati: {hw['deadline'].strftime('%d.%m.%Y')}\n-------------------\n"
        await bot.send_message(callback_query.message.chat.id, hw_text, parse_mode="HTML", reply_markup=get_back_keyboard())
        return
        
    if callback_query.data == "btn_stats":
        stats_text = f"📊 <b>Statistika:</b>\n👥 Tasdiqlanganlar: {len(APPROVED_USERS)}\n📝 Vazifalar: {len(HOMEWORKS)}"
        await bot.send_message(callback_query.message.chat.id, stats_text, parse_mode="HTML", reply_markup=get_schedule_keyboard())
        return
    
    if callback_query.data == "btn_custom_prompt":
        await bot.send_message(callback_query.message.chat.id, "📅 Sanani yuboring (masalan: <code>15.10.2026</code>):", parse_mode="HTML")
        return
    
    if callback_query.data == "btn_today":
        schedule = get_schedule_text(today, today, "today")
    elif callback_query.data == "btn_tomorrow":
        tomorrow = today + timedelta(days=1)
        schedule = get_schedule_text(tomorrow, tomorrow, "tomorrow")
    elif callback_query.data == "btn_week":
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        schedule = get_schedule_text(start_of_week, end_of_week, "week")
    else:
        schedule = "Ma'lumot topilmadi."
        
    if len(schedule) > 4000:
        schedule = schedule[:4000]
    await bot.send_message(callback_query.message.chat.id, schedule, parse_mode="HTML", reply_markup=get_schedule_keyboard())

async def homework_reminder_scheduler():
    while True:
        try:
            now = datetime.now()
            if now.strftime("%H:%M") == "09:00":
                tomorrow = now.date() + timedelta(days=1)
                for hw in HOMEWORKS:
                    if hw["deadline"] == tomorrow and not hw["notified_day_before"]:
                        hw["notified_day_before"] = True
                        alert_msg = f"⏰ <b>ESLATMA! Ertaga oxirgi kun!</b>\n\n📚 {hw['subject']}\n👥 {hw['target']}\n📌 {hw['text']}"
                        for uid in APPROVED_USERS:
                            try:
                                await bot.send_message(uid, alert_msg, parse_mode="HTML")
                            except:
                                pass
            await asyncio.sleep(60)
        except Exception as e:
            logging.error(f"Xatolik: {e}")
            await asyncio.sleep(60)

@dp.message_handler(lambda message: message.text and not message.text.startswith("/"))
async def handle_text_query(message: types.Message):
    if message.from_user.id not in APPROVED_USERS:
        return
    target_date = None
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            target_date = datetime.strptime(message.text.strip(), fmt).date()
            break
        except ValueError:
            continue
    if target_date:
        STATS["total_requests"] += 1
        schedule = get_schedule_text(target_date, target_date, "custom")
        await message.answer(schedule, parse_mode="HTML", reply_markup=get_schedule_keyboard())
        return
    await message.answer("⚠️ Noma'lum buyruq.", reply_markup=get_schedule_keyboard())

# --- RENDER UCHUN VEB-SERVER ---
async def handle_web(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    print("Bot va veb-server ishga tushdi...")
    update_schedule_cache()
    asyncio.create_task(homework_reminder_scheduler())
    asyncio.create_task(web_server())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
import os
import asyncio
import logging
import re
from mcrcon import MCRcon
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# --- Настройка логирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Переменные окружения ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.environ.get("ADMIN_IDS", "").split(',') if id.strip()]

RCON_HOST = os.environ.get("RCON_HOST", "localhost")
RCON_PORT = int(os.environ.get("RCON_PORT", 25575))
RCON_PASS = os.environ.get("RCON_PASSWORD")

# Проверка наличия обязательных переменных
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан!")
if not RCON_PASS:
    raise ValueError("❌ RCON_PASSWORD не задан!")
if not ADMIN_IDS:
    logger.warning("⚠️ ADMIN_IDS не заданы! Админ-команды будут недоступны.")

# --- Функция отправки команд через RCON ---
async def send_rcon_command(command: str) -> str:
    """Отправляет команду на сервер Minecraft через RCON."""
    try:
        def _execute():
            with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT, timeout=10) as mcr:
                # Убираем слеш в начале, если есть
                if command.startswith('/'):
                    command = command[1:]
                response = mcr.command(command)
                # Очищаем от цветовых кодов Minecraft
                if response:
                    response = re.sub(r'§[0-9a-fA-Fklmnor]', '', response)
                return response if response else "✅ Команда выполнена."
        
        response = await asyncio.to_thread(_execute)
        return response
    except Exception as e:
        logger.error(f"RCON Error: {e}")
        return f"❌ Ошибка подключения к серверу: {str(e)}"

# --- Проверка прав администратора ---
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# --- Обработчики команд ---

# /start - Главное меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👥 Онлайн", callback_data='online')],
        [InlineKeyboardButton("📋 Помощь", callback_data='help')],
    ]
    if is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data='admin')])
    keyboard.append([InlineKeyboardButton("🛑 Выключить сервер", callback_data='stop_server')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎮 **Minecraft Server Bot**\n\n"
        "Управляй сервером прямо из Telegram!\n"
        "Используй кнопки или команды.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# /online - Список игроков
async def online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Проверяю кто на сервере...")
    response = await send_rcon_command("list")
    await update.message.reply_text(f"👥 **Онлайн игроки:**\n{response}", parse_mode='Markdown')

# /off - Выключение сервера
async def stop_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ **Выключение сервера...**")
    await send_rcon_command("say Сервер выключается по запросу из Telegram!")
    await asyncio.sleep(1)
    response = await send_rcon_command("stop")
    await update.message.reply_text(f"🛑 **Сервер остановлен.**\n{response}", parse_mode='Markdown')

# /say - Отправить сообщение в игровой чат
async def say(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: `/say <текст>`", parse_mode='Markdown')
        return
    message = " ".join(context.args)
    response = await send_rcon_command(f"say [TG] {message}")
    await update.message.reply_text(f"💬 **Сообщение отправлено в чат.**\n{response}", parse_mode='Markdown')

# /op - Выдать оператора
async def op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: `/op <ник>`", parse_mode='Markdown')
        return
    player = context.args[0]
    response = await send_rcon_command(f"op {player}")
    await update.message.reply_text(f"⭐ **Оператор выдан:** `{player}`\n{response}", parse_mode='Markdown')

# /deop - Забрать оператора
async def deop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: `/deop <ник>`", parse_mode='Markdown')
        return
    player = context.args[0]
    response = await send_rcon_command(f"deop {player}")
    await update.message.reply_text(f"🔽 **Оператор забран:** `{player}`\n{response}", parse_mode='Markdown')

# /kick - Кикнуть игрока
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: `/kick <ник> [причина]`", parse_mode='Markdown')
        return
    player = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Забанен через Telegram"
    response = await send_rcon_command(f"kick {player} {reason}")
    await update.message.reply_text(f"👢 **Игрок кикнут:** `{player}`\nПричина: {reason}\n{response}", parse_mode='Markdown')

# /ban - Забанить игрока
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: `/ban <ник> [причина]`", parse_mode='Markdown')
        return
    player = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Забанен через Telegram"
    response = await send_rcon_command(f"ban {player} {reason}")
    await update.message.reply_text(f"🔨 **Игрок забанен:** `{player}`\nПричина: {reason}\n{response}", parse_mode='Markdown')

# /unban - Разбанить игрока
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: `/unban <ник>`", parse_mode='Markdown')
        return
    player = context.args[0]
    response = await send_rcon_command(f"pardon {player}")
    await update.message.reply_text(f"✅ **Игрок разбанен:** `{player}`\n{response}", parse_mode='Markdown')

# /time - Управление временем
async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование:\n"
            "`/time set day` - день\n"
            "`/time set night` - ночь\n"
            "`/time set 1000` - утро",
            parse_mode='Markdown'
        )
        return
    args = " ".join(context.args)
    response = await send_rcon_command(f"time {args}")
    await update.message.reply_text(f"⏰ **Время изменено:** `{args}`\n{response}", parse_mode='Markdown')

# /kill - Убить игрока
async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: `/kill <ник>`", parse_mode='Markdown')
        return
    player = context.args[0]
    response = await send_rcon_command(f"kill {player}")
    await update.message.reply_text(f"💀 **Игрок убит:** `{player}`\n{response}", parse_mode='Markdown')

# /whitelist - Управление вайтлистом
async def whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование:\n"
            "`/whitelist add <ник>` - добавить\n"
            "`/whitelist remove <ник>` - удалить\n"
            "`/whitelist list` - список\n"
            "`/whitelist on` - включить\n"
            "`/whitelist off` - выключить",
            parse_mode='Markdown'
        )
        return
    args = " ".join(context.args)
    response = await send_rcon_command(f"whitelist {args}")
    await update.message.reply_text(f"📋 **Вайтлист:** `{args}`\n{response}", parse_mode='Markdown')

# /gamemode - Сменить режим игры
async def gamemode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "ℹ️ Использование: `/gamemode <режим> <ник>`\n"
            "Режимы: survival, creative, adventure, spectator",
            parse_mode='Markdown'
        )
        return
    mode = context.args[0]
    player = context.args[1]
    response = await send_rcon_command(f"gamemode {mode} {player}")
    await update.message.reply_text(f"🎮 **Режим игры изменен:** `{player}` → `{mode}`\n{response}", parse_mode='Markdown')

# --- Обработчик кнопок ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == 'online':
        await query.edit_message_text("🔄 Проверяю онлайн...")
        response = await send_rcon_command("list")
        await query.edit_message_text(f"👥 **Онлайн игроки:**\n{response}", parse_mode='Markdown')
    
    elif data == 'help':
        help_text = (
            "📖 **Доступные команды:**\n\n"
            "**Для всех:**\n"
            "/start - Главное меню\n"
            "/online - Кто на сервере\n"
            "/off - Выключить сервер\n\n"
            "**Для админов:**\n"
            "/say <текст> - Сообщение в игру\n"
            "/op <ник> - Выдать оператора\n"
            "/deop <ник> - Забрать оператора\n"
            "/kick <ник> - Кикнуть игрока\n"
            "/ban <ник> - Забанить\n"
            "/unban <ник> - Разбанить\n"
            "/time set day/night - Сменить время\n"
            "/kill <ник> - Убить игрока\n"
            "/whitelist add/remove <ник> - Вайтлист\n"
            "/gamemode <режим> <ник> - Сменить режим"
        )
        await query.edit_message_text(help_text, parse_mode='Markdown')
    
    elif data == 'admin':
        if not is_admin(user_id):
            await query.edit_message_text("❌ У вас нет прав для этой панели.")
            return
        keyboard = [
            [InlineKeyboardButton("📋 Онлайн", callback_data='online')],
            [InlineKeyboardButton("💬 Сказать в игре", callback_data='say_prompt')],
            [InlineKeyboardButton("⭐ Выдать OP", callback_data='op_prompt')],
            [InlineKeyboardButton("⏰ Сменить время", callback_data='time_prompt')],
            [InlineKeyboardButton("👢 Кикнуть", callback_data='kick_prompt')],
            [InlineKeyboardButton("🔨 Забанить", callback_data='ban_prompt')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("⚙️ **Админ-панель**", reply_markup=reply_markup, parse_mode='Markdown')
    
    elif data == 'stop_server':
        await query.edit_message_text("⚠️ **Выключение сервера...**")
        await send_rcon_command("say Сервер выключается по запросу из Telegram!")
        await asyncio.sleep(1)
        response = await send_rcon_command("stop")
        await query.edit_message_text(f"🛑 **Сервер остановлен.**\n{response}", parse_mode='Markdown')
    
    elif data == 'back':
        keyboard = [
            [InlineKeyboardButton("👥 Онлайн", callback_data='online')],
            [InlineKeyboardButton("📋 Помощь", callback_data='help')],
        ]
        if is_admin(user_id):
            keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data='admin')])
        keyboard.append([InlineKeyboardButton("🛑 Выключить сервер", callback_data='stop_server')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎮 **Minecraft Server Bot**\n\nУправляй сервером прямо из Telegram!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Обработка prompt-кнопок (просто подсказка, как использовать команду)
    elif data == 'say_prompt':
        await query.edit_message_text(
            "💬 Используйте команду:\n`/say <текст>`\n\n"
            "Пример: `/say Привет всем!`",
            parse_mode='Markdown'
        )
    elif data == 'op_prompt':
        await query.edit_message_text(
            "⭐ Используйте команду:\n`/op <ник>`\n\n"
            "Пример: `/op Steve`",
            parse_mode='Markdown'
        )
    elif data == 'time_prompt':
        await query.edit_message_text(
            "⏰ Используйте команду:\n"
            "`/time set day` - день\n"
            "`/time set night` - ночь\n"
            "`/time set 1000` - утро",
            parse_mode='Markdown'
        )
    elif data == 'kick_prompt':
        await query.edit_message_text(
            "👢 Используйте команду:\n`/kick <ник> [причина]`\n\n"
            "Пример: `/kick Steve За спам`",
            parse_mode='Markdown'
        )
    elif data == 'ban_prompt':
        await query.edit_message_text(
            "🔨 Используйте команду:\n`/ban <ник> [причина]`\n\n"
            "Пример: `/ban Steve За нарушение`",
            parse_mode='Markdown'
        )

# --- Команда для прямого выполнения любой консольной команды (только для админов) ---
async def console(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Использование: `/console <команда>`\nПример: `/console save-all`", parse_mode='Markdown')
        return
    command = " ".join(context.args)
    response = await send_rcon_command(command)
    await update.message.reply_text(f"📟 **Консоль:** `{command}`\n\n{response}", parse_mode='Markdown')

# --- Запуск бота ---
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Создаем приложение
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("online", online))
    app.add_handler(CommandHandler("off", stop_server))
    app.add_handler(CommandHandler("say", say))
    app.add_handler(CommandHandler("op", op))
    app.add_handler(CommandHandler("deop", deop))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("kill", kill))
    app.add_handler(CommandHandler("whitelist", whitelist))
    app.add_handler(CommandHandler("gamemode", gamemode))
    app.add_handler(CommandHandler("console", console))
    
    # Обработчик кнопок
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
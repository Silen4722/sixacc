import asyncio
from datetime import datetime
import logging
from telethon import TelegramClient
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time

# === Конфигурация ===
ACCOUNTS = [
    {
        'api_id': 29229629,
        'api_hash': '377e49103c36fa08cbdaf9bb6b7e7001',
        'phone': '+17048286887',
        'session_name': 'account1'
    },
    {
        'api_id': 20092299,
        'api_hash': '3fd269a1254dbfb6116b04c9b76b8fa3',
        'phone': '+17048287153',
        'session_name': 'account2'
    },
    {
        'api_id': 24472406,
        'api_hash': '3256ff2d688ab2644f5b1e26cfd9cc77',
        'phone': '+17048288442',
        'session_name': 'account3'
    },
    {
        'api_id': 28788132,
        'api_hash': '412762dd2adfda4bd4cc497afa201b22',
        'phone': '+17048286761',
        'session_name': 'account4'
    },
    {
        'api_id': 20021961,
        'api_hash': '0dc2fbb740f731390e988c39d6a4aa28',
        'phone': '+17048288755',
        'session_name': 'account5'
    },
    {
        'api_id': 21763431,
        'api_hash': '4fd10a998804b9b3c5d990700151d689',
        'phone': '+17048287505',
        'session_name': 'account6'
    }
]

bot_token = '8154627364:AAG1YkrensrF2QqxrekUWDlo2V3dTz9_3LI'
source_chat = '@VitalikOnyshch'  # Чат для пересылки сообщений

# Инициализация
bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Состояния FSM
class Form(StatesGroup):
    set_text = State()
    set_interval = State()
    add_chat = State()
    remove_chat = State()
    forward_message = State()
    set_forward_id = State()  # Состояние для установки ID сообщения

class Account:
    def __init__(self, api_id, api_hash, phone, session_name):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.client = TelegramClient(session_name, api_id, api_hash)
        
        self.message_text = 'Привет!'
        self.send_interval = 60
        self.send_offset = 0
        self.is_scheduled = False
        
        self.forward_message_id = None
        self.cron_minute = 0
        self.is_forward_scheduled = False
        
        self.target_chats = []
        self.auth_attempts = 0
        self.max_auth_attempts = 3
        self.is_authenticated = False
    
    async def start(self):
        """Авторизация аккаунта с повторными попытками"""
        while self.auth_attempts < self.max_auth_attempts:
            try:
                await self.client.start(phone=self.phone)
                self.is_authenticated = True
                print(f"✅ {self.session_name} авторизован")
                return True
            except Exception as e:
                self.auth_attempts += 1
                if self.auth_attempts >= self.max_auth_attempts:
                    print(f"❌ {self.session_name}: Не удалось авторизоваться после {self.max_auth_attempts} попыток. Ошибка: {str(e)}")
                    return False
                
                wait_time = 60 * self.auth_attempts
                print(f"⚠️ {self.session_name}: Ошибка авторизации (попытка {self.auth_attempts}/{self.max_auth_attempts}). Ждем {wait_time} сек...")
                await asyncio.sleep(wait_time)
        return False
    
    async def send_message(self):
        """Отправка сообщения во все чаты аккаунта"""
        if not self.target_chats:
            print(f"❌ {self.session_name}: Нет чатов для рассылки!")
            return

        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"⏰ [{current_time}] {self.session_name}: Начало рассылки...")
        
        success_count = 0
        for chat in self.target_chats:
            try:
                await self.client.send_message(chat, self.message_text)
                print(f"✅ {self.session_name}: Отправлено в {chat}")
                success_count += 1
                await asyncio.sleep(1)  # Задержка между сообщениями
            except Exception as e:
                print(f"❌ {self.session_name}: Ошибка в {chat}: {e}")
        
        print(f"📊 {self.session_name}: Итог - {success_count}/{len(self.target_chats)} успешных отправок")
    
    async def forward_scheduled_message(self):
        """Пересылка сообщения во все чаты строго в назначенное время"""
        if not self.target_chats or self.forward_message_id is None:
            print(f"❌ {self.session_name}: Нет чатов или сообщения для пересылки!")
            return

        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"⏰ [{current_time}] {self.session_name}: Начало пересылки (по расписанию в :{self.cron_minute:02d})...")
        
        success_count = 0
        for chat in self.target_chats:
            try:
                await self.client.forward_messages(chat, self.forward_message_id, source_chat)
                print(f"✅ {self.session_name}: Переслано в {chat}")
                success_count += 1
                await asyncio.sleep(1)  # Задержка между пересылками
            except Exception as e:
                print(f"❌ {self.session_name}: Ошибка пересылки в {chat}: {e}")
        
        print(f"📊 {self.session_name}: Итог - {success_count}/{len(self.target_chats)} успешных пересылок")
    
    def set_send_offset(self, total_accounts, account_index):
        """Установка временного смещения для равномерного распределения"""
        self.send_offset = account_index * (self.send_interval // total_accounts)
        print(f"⏱ {self.session_name}: Установлено смещение {self.send_offset} мин.")
    
    async def disconnect(self):
        """Корректное отключение клиента"""
        if self.is_authenticated:
            await self.client.disconnect()
            print(f"🔌 {self.session_name}: Отключен")

# Инициализация аккаунтов
accounts = [Account(**acc) for acc in ACCOUNTS]

# Установка минут для каждого аккаунта (0, 10, 20, 30, 40, 50)
for i, account in enumerate(accounts):
    account.cron_minute = i * 10

# === Обработчики (УДАЛЕНЫ все обработчики, связанные с forward_interval) ===
@dp.callback_query(F.data == "forward_message")
async def inline_forward_message(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Аккаунт {i+1}", callback_data=f"set_id_{i}") for i in range(3)],
        [InlineKeyboardButton(text=f"Аккаунт {i+4}", callback_data=f"set_id_{i+3}") for i in range(3)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(
        "Выберите аккаунт для установки ID сообщения:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("set_id_"))
async def inline_set_account_id(callback: types.CallbackQuery, state: FSMContext):
    account_idx = int(callback.data.split("_")[2])
    await state.update_data(account_idx=account_idx)
    await callback.message.answer(f"Введите ID сообщения для аккаунта {account_idx+1}:")
    await state.set_state(Form.set_forward_id)
    await callback.answer()

@dp.message(Form.set_forward_id)
async def process_set_forward_id(message: Message, state: FSMContext):
    try:
        msg_id = int(message.text)
        data = await state.get_data()
        account_idx = data['account_idx']
        accounts[account_idx].forward_message_id = msg_id
        
        await message.answer(
            f"✅ Для аккаунта {account_idx+1} установлено ID: {msg_id}\n"
            f"🔄 Пересылка будет в :{accounts[account_idx].cron_minute:02d} минут"
        )
    except ValueError:
        await message.answer("❌ ID сообщения должно быть числом!")
    finally:
        await state.clear()

@dp.callback_query(F.data == "start_forward_schedule")
async def inline_start_forward_schedule(callback: types.CallbackQuery):
    # Проверяем, что для всех аккаунтов установлены ID
    for i, account in enumerate(accounts):
        if account.forward_message_id is None:
            await callback.answer(
                f"❌ Сначала установите ID сообщения для аккаунта {i+1}!",
                show_alert=True
            )
            return
    
    # Удаляем старые задания
    for account in accounts:
        job_id = f'auto_forward_{account.session_name}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    
    # Создаем новые задания
    for account in accounts:
        scheduler.add_job(
            account.forward_scheduled_message,
            'cron',
            minute=account.cron_minute,
            id=f'auto_forward_{account.session_name}'
        )
        account.is_forward_scheduled = True
    
    schedule_info = "\n".join([
        f"Аккаунт {i+1} (ID:{acc.forward_message_id}) → :{acc.cron_minute:02d} мин"
        for i, acc in enumerate(accounts)
    ])
    
    await callback.message.edit_text(
        f"🔄 Пересылка запущена по расписанию:\n\n{schedule_info}",
        reply_markup=get_main_keyboard()
    )

# Установка минут для каждого аккаунта (0, 10, 20, 30, 40, 50)
for i, account in enumerate(accounts):
    account.cron_minute = i * 10

# === Логирование ===
def log_action(action: str, account: Account):
    logging.info(f"{account.session_name} | {action} | Текст: '{account.message_text}' | Чаты: {len(account.target_chats)}")

# === Клавиатуры ===
def get_main_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📨 Отправить сейчас", callback_data="send_now")],
        [
            InlineKeyboardButton(text="▶️ Начать рассылку", callback_data="start_schedule"),
            InlineKeyboardButton(text="⏹️ Остановить", callback_data="stop_schedule")
        ],
        [
            InlineKeyboardButton(text="✏️ Изменить текст", callback_data="set_text"),
            InlineKeyboardButton(text="⏱ Интервал", callback_data="set_interval")
        ],
        [
            InlineKeyboardButton(text="➕ Добавить чат", callback_data="add_chat"),
            InlineKeyboardButton(text="➖ Удалить чат", callback_data="remove_chat"),
            InlineKeyboardButton(text="📋 Список чатов", callback_data="list_chats")
        ],
        [
            InlineKeyboardButton(text="🌐 Выбрать все чаты", callback_data="select_all_chats"),
            InlineKeyboardButton(text="↗️ Переслать сообщение", callback_data="forward_message")
        ],
        [
            InlineKeyboardButton(text="🔄 Начать пересылку", callback_data="start_forward_schedule"),
            InlineKeyboardButton(text="🛑 Стоп пересылку", callback_data="stop_forward_schedule")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# === Обработчики команд ===
@dp.message(Command('start'))
async def cmd_start(message: Message):
    account = accounts[0]
    schedule_info = "\n".join([f"Аккаунт {i+1} → :{acc.cron_minute:02d} мин" for i, acc in enumerate(accounts)])
    
    await message.answer(
        "📢 <b>Управление рассылкой</b>\n\n"
        f"📝 Текст: <code>{account.message_text}</code>\n"
        f"⏱ Интервал: <b>{account.send_interval} мин.</b>\n"
        f"📊 Чатов: <b>{len(account.target_chats)}</b>\n"
        f"🔁 Рассылка: <b>{'ВКЛ' if account.is_scheduled else 'ВЫКЛ'}</b>\n"
        f"🔄 Пересылка: <b>{'ВКЛ' if account.is_forward_scheduled else 'ВЫКЛ'}</b>\n\n"
        f"⏰ <b>Расписание пересылки:</b>\n{schedule_info}\n\n"
        "Для пересылки сообщений из @VitalikOnyshch:\n"
        "1. Нажмите <b>↗️ Переслать сообщение</b>\n"
        "2. Введите ID сообщения\n"
        "3. Запустите пересылку",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command('addchat'))
async def cmd_add_chat(message: Message):
    try:
        chat_link = message.text.split(maxsplit=1)[1]
        for account in accounts:
            if chat_link not in account.target_chats:
                account.target_chats.append(chat_link)
                log_action(f"CHAT_ADDED: {chat_link}", account)
        await message.answer(f"✅ Чат добавлен на все аккаунты: <code>{chat_link}</code>")
    except IndexError:
        await message.answer("❌ Укажите ссылку: /addchat <ссылка_на_чат>")

@dp.message(Command('removechat'))
async def cmd_remove_chat(message: Message):
    if not accounts[0].target_chats:
        await message.answer("❌ Список чатов пуст!")
        return

    try:
        chat_link = message.text.split(maxsplit=1)[1]
        for account in accounts:
            if chat_link in account.target_chats:
                account.target_chats.remove(chat_link)
                log_action(f"CHAT_REMOVED: {chat_link}", account)
        await message.answer(f"✅ Чат удален со всех аккаунтов: <code>{chat_link}</code>")
    except IndexError:
        await message.answer("❌ Укажите ссылку: /removechat <ссылка_на_чат>")

@dp.message(Command('listchats'))
async def cmd_list_chats(message: Message):
    if not accounts[0].target_chats:
        await message.answer("❌ Список чатов пуст!")
        return

    chats_list = "\n".join([f"{i+1}. {chat}" for i, chat in enumerate(accounts[0].target_chats)])
    await message.answer(f"📋 <b>Список чатов (первый аккаунт):</b>\n\n{chats_list}")

@dp.message(Command('settext'))
async def cmd_settext(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        for account in accounts:
            account.message_text = parts[1]
            log_action("TEXT_CHANGED", account)
        await message.answer(f"✅ Новый текст для всех аккаунтов:\n<code>{parts[1]}</code>")
    else:
        await message.answer("❌ Укажите текст: /settext <ваш_текст>")

@dp.message(Command('settime'))
async def cmd_settime(message: Message):
    try:
        new_interval = int(message.text.split()[1])
        if new_interval < 1:
            raise ValueError
        
        for account in accounts:
            account.send_interval = new_interval
            if account.is_scheduled:
                scheduler.reschedule_job(f'auto_send_{account.session_name}', trigger='interval', minutes=account.send_interval)
            log_action("INTERVAL_CHANGED", account)
        
        await message.answer(f"✅ Новый интервал для всех аккаунтов: <b>{new_interval} мин.</b>")
    except (IndexError, ValueError):
        await message.answer("❌ Укажите корректное количество минут: /settime <число>")

@dp.message(Command('forward'))
async def cmd_forward(message: Message):
    try:
        msg_id = int(message.text.split()[1])
        if not accounts[0].target_chats:
            await message.answer("❌ Нет чатов для пересылки!")
            return

        total_success = 0
        for account in accounts:
            if not account.target_chats:
                continue
                
            success = 0
            for chat in account.target_chats:
                try:
                    await account.client.forward_messages(chat, msg_id, source_chat)
                    success += 1
                except Exception as e:
                    print(f"❌ {account.session_name}: Ошибка пересылки в {chat}: {e}")
            
            total_success += success
            print(f"✅ {account.session_name}: Переслано в {success}/{len(account.target_chats)} чатов")

        await message.answer(f"✅ Переслано в {total_success}/{sum(len(acc.target_chats) for acc in accounts)} чатов!")
    except (IndexError, ValueError):
        await message.answer("❌ Используйте: /forward <ID_сообщения>")

# === Обработчики кнопок ===
@dp.callback_query(F.data == "send_now")
async def inline_send_now(callback: types.CallbackQuery):
    await asyncio.gather(*[account.send_message() for account in accounts])
    await callback.answer("✅ Сообщение отправлено во все чаты на всех аккаунтах!")

@dp.callback_query(F.data == "start_schedule")
async def inline_start_schedule(callback: types.CallbackQuery):
    for account in accounts:
        if not account.is_scheduled:
            scheduler.add_job(
                account.send_message, 
                'interval', 
                minutes=account.send_interval, 
                id=f'auto_send_{account.session_name}'
            )
            account.is_scheduled = True
            log_action("SCHEDULE_STARTED", account)
    
    await callback.message.edit_text(
        f"🔁 Рассылка <b>запущена</b> на всех аккаунтах (каждые {accounts[0].send_interval} мин.)",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "stop_schedule")
async def inline_stop_schedule(callback: types.CallbackQuery):
    for account in accounts:
        if account.is_scheduled:
            scheduler.remove_job(f'auto_send_{account.session_name}')
            account.is_scheduled = False
            log_action("SCHEDULE_STOPPED", account)
    
    await callback.message.edit_text(
        "⏹️ Рассылка <b>остановлена</b> на всех аккаунтах",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "set_text")
async def inline_set_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый текст сообщения для всех аккаунтов:")
    await state.set_state(Form.set_text)
    await callback.answer()

@dp.message(Form.set_text)
async def process_set_text(message: Message, state: FSMContext):
    for account in accounts:
        account.message_text = message.text
        log_action("TEXT_CHANGED", account)
    
    await message.answer(f"✅ Текст изменен на всех аккаунтах:\n<code>{message.text}</code>")
    await state.clear()

@dp.callback_query(F.data == "set_interval")
async def inline_set_interval(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый интервал в минутах для всех аккаунтов:")
    await state.set_state(Form.set_interval)
    await callback.answer()

@dp.message(Form.set_interval)
async def process_set_interval(message: Message, state: FSMContext):
    try:
        new_interval = int(message.text)
        if new_interval < 1:
            raise ValueError
            
        for account in accounts:
            account.send_interval = new_interval
            if account.is_scheduled:
                scheduler.reschedule_job(f'auto_send_{account.session_name}', trigger='interval', minutes=account.send_interval)
            log_action("INTERVAL_CHANGED", account)
        
        await message.answer(f"✅ Интервал изменен на {new_interval} минут для всех аккаунтов")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите целое число больше 0")
    finally:
        await state.clear()

@dp.callback_query(F.data == "add_chat")
async def inline_add_chat(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправьте юзернейм чата или ссылку для добавления на все аккаунты:")
    await state.set_state(Form.add_chat)
    await callback.answer()

@dp.message(Form.add_chat)
async def process_add_chat(message: Message, state: FSMContext):
    chat_link = message.text.strip()
    if chat_link.startswith(('https://t.me/', 't.me/')):
        chat_link = '@' + chat_link.split('/')[-1]
    
    for account in accounts:
        if chat_link not in account.target_chats:
            account.target_chats.append(chat_link)
            log_action(f"CHAT_ADDED: {chat_link}", account)
    
    await message.answer(f"✅ Чат добавлен на все аккаунты: <code>{chat_link}</code>")
    await state.clear()

@dp.callback_query(F.data == "remove_chat")
async def inline_remove_chat(callback: types.CallbackQuery, state: FSMContext):
    if not accounts[0].target_chats:
        await callback.answer("❌ Список чатов пуст!", show_alert=True)
        return
        
    chats_list = "\n".join([f"{i+1}. {chat}" for i, chat in enumerate(accounts[0].target_chats)])
    await callback.message.answer(
        f"📋 Текущие чаты (первый аккаунт):\n\n{chats_list}\n\nОтправьте номер чата для удаления со всех аккаунтов:"
    )
    await state.set_state(Form.remove_chat)
    await callback.answer()

@dp.message(Form.remove_chat)
async def process_remove_chat(message: Message, state: FSMContext):
    try:
        chat_num = int(message.text)
        if 1 <= chat_num <= len(accounts[0].target_chats):
            removed_chat = accounts[0].target_chats[chat_num-1]
            for account in accounts:
                if removed_chat in account.target_chats:
                    account.target_chats.remove(removed_chat)
                    log_action(f"CHAT_REMOVED: {removed_chat}", account)
            
            await message.answer(f"✅ Чат удален со всех аккаунтов: <code>{removed_chat}</code>")
        else:
            await message.answer("❌ Неверный номер чата!")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите номер чата")
    finally:
        await state.clear()

@dp.callback_query(F.data == "list_chats")
async def inline_list_chats(callback: types.CallbackQuery):
    if not accounts[0].target_chats:
        await callback.answer("❌ Список чатов пуст!", show_alert=True)
        return

    chats_list = "\n".join([f"{i+1}. {chat}" for i, chat in enumerate(accounts[0].target_chats)])
    await callback.message.edit_text(
        f"📋 <b>Список чатов (первый аккаунт):</b>\n\n{chats_list}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
        ])
    )

@dp.callback_query(F.data == "back_to_main")
async def inline_back_to_main(callback: types.CallbackQuery):
    account = accounts[0]
    await callback.message.edit_text(
        "📢 <b>Управление рассылкой</b>\n\n"
        f"📝 Текст: <code>{account.message_text}</code>\n"
        f"⏱ Интервал: <b>{account.send_interval} мин.</b>\n"
        f"📊 Чатов: <b>{len(account.target_chats)}</b>\n"
        f"🔁 Рассылка: <b>{'ВКЛ' if account.is_scheduled else 'ВЫКЛ'}</b>\n"
        f"🔄 Пересылка: <b>{'ВКЛ' if account.is_forward_scheduled else 'ВЫКЛ'}</b>",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "select_all_chats")
async def inline_select_all_chats(callback: types.CallbackQuery):
    try:
        for account in accounts:
            dialogs = await account.client.get_dialogs()
            all_chats = []
            
            for dialog in dialogs:
                entity = dialog.entity
                if hasattr(entity, 'username') and entity.username:
                    all_chats.append(f"@{entity.username}")
                elif hasattr(entity, 'id'):
                    try:
                        invite = await account.client.get_entity(entity)
                        if hasattr(invite, 'username') and invite.username:
                            all_chats.append(f"@{invite.username}")
                    except:
                        continue
            
            account.target_chats.clear()
            account.target_chats.extend(all_chats)
            
            log_action("SELECTED_ALL_CHATS", account)
        
        await callback.answer(f"✅ Добавлены все чаты для каждого аккаунта!", show_alert=True)
        
        await callback.message.edit_text(
            "📢 <b>Управление рассылкой</b>\n\n"
            f"📝 Текст: <code>{accounts[0].message_text}</code>\n"
            f"⏱ Интервал: <b>{accounts[0].send_interval} мин.</b>\n"
            f"📊 Чатов: <b>{len(accounts[0].target_chats)}</b>\n"
            f"🔁 Рассылка: <b>{'ВКЛ' if accounts[0].is_scheduled else 'ВЫКЛ'}</b>\n"
            f"🔄 Пересылка: <b>{'ВКЛ' if accounts[0].is_forward_scheduled else 'ВЫКЛ'}</b>",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@dp.callback_query(F.data == "forward_message")
async def inline_forward_message(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID сообщения для пересылки на все аккаунты:")
    await state.set_state(Form.forward_message)
    await callback.answer()

@dp.message(Form.forward_message)
async def process_forward_message(message: Message, state: FSMContext):
    try:
        msg_id = int(message.text)
        for account in accounts:
            account.forward_message_id = msg_id
        
        # Автоматически запускаем пересылку по расписанию
        for i, account in enumerate(accounts):
            account.cron_minute = i * 10  # 0, 10, 20, 30, 40, 50
            scheduler.add_job(
                account.forward_scheduled_message,
                'cron',
                minute=account.cron_minute,
                id=f'auto_forward_{account.session_name}'
            )
            account.is_forward_scheduled = True
            log_action("FORWARD_SCHEDULE_STARTED", account)
        
        schedule_info = "\n".join([f"Аккаунт {i+1} → :{i*10:02d} мин" for i in range(len(accounts))])
        
        await message.answer(
            f"✅ ID сообщения установлено: {msg_id}\n"
            f"🔄 Пересылка запущена по расписанию:\n\n{schedule_info}",
            reply_markup=get_main_keyboard()
        )
    except ValueError:
        await message.answer("❌ ID сообщения должно быть числом!")
    finally:
        await state.clear()

# Удаляем ненужные состояния и обработчики
Form.forward_interval = None  # Удаляем состояние интервала

@dp.callback_query(F.data == "set_forward_interval")
async def inline_set_forward_interval(callback: types.CallbackQuery):
    # Больше не запрашиваем интервал
    await callback.answer("ℹ️ Теперь интервал фиксированный: каждые 10 минут для каждого аккаунта", show_alert=True)

@dp.callback_query(F.data == "start_forward_schedule")
async def inline_start_forward_schedule(callback: types.CallbackQuery):
    if accounts[0].forward_message_id is None:
        await callback.answer("❌ Сначала установите ID сообщения для пересылки!", show_alert=True)
        return
    
    # Удаляем старые задания если они есть
    for account in accounts:
        job_id = f'auto_forward_{account.session_name}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    
    # Создаем новые задания с cron-триггером для каждого аккаунта
    for account in accounts:
        scheduler.add_job(
            account.forward_scheduled_message,
            'cron',
            minute=account.cron_minute,  # Уникальная минута для каждого аккаунта
            id=f'auto_forward_{account.session_name}'
        )
        account.is_forward_scheduled = True
        log_action("FORWARD_SCHEDULE_STARTED", account)
        print(f"⏰ {account.session_name}: пересылка будет в :{account.cron_minute:02d} минут каждого часа")
    
    schedule_info = "\n".join([f"Аккаунт {i+1} → :{acc.cron_minute:02d} мин" for i, acc in enumerate(accounts)])
    await callback.message.edit_text(
        f"🔄 Пересылка <b>запущена</b> по расписанию:\n\n{schedule_info}",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "stop_forward_schedule")
async def inline_stop_forward_schedule(callback: types.CallbackQuery):
    for account in accounts:
        job_id = f'auto_forward_{account.session_name}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            account.is_forward_scheduled = False
            log_action("FORWARD_SCHEDULE_STOPPED", account)
    
    await callback.message.edit_text(
        "🛑 Пересылка <b>остановлена</b> на всех аккаунтах",
        reply_markup=get_main_keyboard()
    )

# === Запуск ===
async def main():
    # Авторизация аккаунтов с задержкой
    for i, account in enumerate(accounts):
        print(f"⌛ Авторизация аккаунта {i+1}/{len(accounts)} ({account.phone})...")
        success = await account.start()
        
        if not success:
            print(f"⛔ Пропускаем аккаунт {account.phone} из-за ошибок авторизации")
            continue
            
        if i < len(accounts) - 1:
            delay = 3  # 3 секунды задержки
            print(f"⏳ Ждем {delay} секунд перед следующей авторизацией...")
            await asyncio.sleep(delay)
    
    print("✅ Все аккаунты обработаны")
    
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

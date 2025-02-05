# handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import RESOURCE_OPTIONS, TEMPLATE_SHIELD_PATH, TEMPLATE_PAINTING_PATH, PAINTING_COLORS, NEW_PAINTING_IMAGE_SIZES
from utils import process_image, process_shield, process_painting, create_resource_pack, create_zip_file
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = Router()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

# Пул потоков для выполнения тяжелых задач
executor = ThreadPoolExecutor(max_workers=5)

# Глобальные переменные для очереди и семафора Painting
painting_semaphore = asyncio.Semaphore(5)
painting_queue = asyncio.Queue()

# Асинхронная обертка для выполнения задач в пуле потоков
async def run_in_executor(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, func, *args)

class Form(StatesGroup):
    selected_resource = State()
    pack_name = State()
    waiting_for_image = State()

user_data = {}

def init_user_data(chat_id):
    user_data[chat_id] = {
        "selected_resource": None,
        "images": [],
        "pack_name": None,
        "in_process": False,
        "new_painting_images": {},
        "remaining_files": list(NEW_PAINTING_IMAGE_SIZES.keys()),
        "error_count": 0
    }

async def process_painting_queue():
    while True:
        task = await painting_queue.get()
        chat_id = task['chat_id']
        
        # Проверяем, активен ли процесс пользователя
        if not user_data.get(chat_id, {}).get("in_process", False):
            logging.info(f"Задача для chat_id {chat_id} отменена, пропускаем.")
            painting_queue.task_done()
            continue
        
        try:
            async with painting_semaphore:
                await task['message'].answer("🔄 Ваш запрос на обработку Painting начал выполняться. Пожалуйста, подождите...")
                
                processed = await run_in_executor(
                    process_painting, task['images'], TEMPLATE_PAINTING_PATH, PAINTING_COLORS
                )
                if processed is None:
                    raise ValueError("Ошибка обработки изображения картины")
                
                await task['message'].answer("Создание... Подождите...")
                await run_in_executor(
                    create_resource_pack, processed, task['pack_name'], 'painting'
                )
                
                zip_data = await run_in_executor(create_zip_file, task['pack_name'])
                await task['message'].answer_document(
                    BufferedInputFile(zip_data, filename=f"{task['pack_name']}.mcpack"),
                    caption="✅ Ваш ресурспак готов!"
                )
        except Exception as e:
            logging.error(f"Ошибка обработки Painting: {e}")
            await task['message'].answer(f"❌ Ошибка при обработке: {str(e)}")
        finally:
            init_user_data(chat_id)
            await task['state'].clear()
            painting_queue.task_done()

@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    chat_id = message.chat.id
    current_state = await state.get_state()
    if user_data.get(chat_id, {}).get("in_process", False) or current_state is not None:
        await message.answer("Завершите текущий процесс или используйте /cancel")
        return
    init_user_data(chat_id)
    keyboard = InlineKeyboardBuilder()
    for resource_name, resource_label in RESOURCE_OPTIONS.items():
        keyboard.button(text=resource_label, callback_data=resource_name)
    keyboard.adjust(2)
    await message.answer("Выберите тип ресурспака:", reply_markup=keyboard.as_markup())
    await state.set_state(Form.selected_resource)

@router.message(Command("help"))
async def help_command(message: Message):
    help_text = """
📖 *Рекомендации:*
[Рекомендации по созданию ресурспаков.](https://x.gd/recommendations)

🛠 *Доступные команды:*
/start - Начать создание ресурспака.
/help - Показать это сообщение.
/cancel - Отменить текущий процесс создания ресурспака.

⚙️ *Ограничения:*
- Изображения должны быть в формате PNG или JPEG
- Размер файла не должен превышать 4 МБ

🛑 Если у вас возникли проблемы, напишите сюда:
[Сообщить о проблеме](https://x.gd/bugs_bot)

❤️‍🩹 *Поддержать донатом...:*
[Поддержать донатом](https://yoomoney.ru/fundraise/17UU7PUVA77.250123)  
_(К сожалению, я не солнцеед)_
    """
    await message.answer(help_text, 
                         parse_mode="Markdown", 
                         disable_web_page_preview=True)

@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    chat_id = message.chat.id
    init_user_data(chat_id)
    await state.clear()
    await message.answer("Операция отменена")

@router.callback_query(Form.selected_resource)
async def select_resource(call: CallbackQuery, state: FSMContext):
    chat_id = call.message.chat.id
    resource = call.data
    user_data[chat_id]["selected_resource"] = resource
    user_data[chat_id]["in_process"] = True
    await call.message.answer("Введите название ресурспака:")
    await state.set_state(Form.pack_name)
    await call.answer()

@router.message(Form.pack_name)
async def process_pack_name(message: Message, state: FSMContext):
    chat_id = message.chat.id
    pack_name = message.text.strip()
    if not pack_name:
        await message.answer("⚠️ Название не может быть пустым! Введите снова:")
        return
    if len(pack_name) > 64:
        await message.answer("⚠️ Название слишком длинное (макс. 64 символа)! Введите снова:")
        return
    user_data[chat_id]["pack_name"] = pack_name
    resource = user_data[chat_id]["selected_resource"]
    if resource == "new_painting":
        await request_next_image(message, state)
    else:
        await message.answer("Отправьте первое изображение:")
        await state.set_state(Form.waiting_for_image)

@router.message(Form.waiting_for_image, F.photo | F.document)
async def handle_image(message: Message, state: FSMContext):
    chat_id = message.chat.id
    resource = user_data[chat_id]["selected_resource"]
    if not user_data[chat_id].get("in_process", False):
        await message.answer("Процесс завершен. Используйте /start")
        return
    try:
        file = await message.bot.get_file(
            message.document.file_id if message.document else message.photo[-1].file_id
        )
        downloaded = await message.bot.download_file(file.file_path)
        image_data = downloaded.read()

        if resource == "shield":
            if len(user_data[chat_id]["images"]) >= 2:
                await message.answer("✅ Все изображения получены! Идет обработка...")
                return
            user_data[chat_id]["images"].append(image_data)
            if len(user_data[chat_id]["images"]) < 2:
                await message.answer("Отправьте второе изображение:")
            else:
                processed = await run_in_executor(process_shield, *user_data[chat_id]["images"], TEMPLATE_SHIELD_PATH)
                if processed is None:
                    raise ValueError("Ошибка обработки изображения щита")
                await send_resource(message, processed, resource, state)

        elif resource == "painting":
            required = len(PAINTING_COLORS)
            if len(user_data[chat_id]["images"]) >= required:
                await message.answer("✅ Все изображения получены! Завершаю обработку...")
                return
            user_data[chat_id]["images"].append(image_data)
            if len(user_data[chat_id]["images"]) < required:
                await message.answer(f"Осталось изображений: {required - len(user_data[chat_id]['images'])}")
            else:
                task = {
                    'chat_id': chat_id,
                    'images': user_data[chat_id]["images"].copy(),
                    'pack_name': user_data[chat_id]["pack_name"],
                    'message': message,
                    'state': state
                }
                await painting_queue.put(task)
                queue_size = painting_queue.qsize()
                current_position = queue_size
                if current_position == 0:
                    await message.answer("🔄 Ваш запрос поставлен в очередь. Обработка начнется сразу.")
                else:
                    await message.answer(f"🚦 Ваша позиция в очереди: {current_position}. Вы получите уведомление, когда обработка начнется.")

        elif resource == "new_painting":
            if not user_data[chat_id]["remaining_files"]:
                await message.answer("✅ Все файлы загружены! Идет обработка...")
                return
            current_file = user_data[chat_id]["remaining_files"].pop(0)
            processed = await run_in_executor(process_image, image_data, resource, current_file)
            if processed is None:
                raise ValueError(f"Ошибка обработки файла {current_file}")
            user_data[chat_id]["new_painting_images"][current_file] = processed
            await request_next_image(message, state)

        else:
            if user_data[chat_id]["images"]:
                await message.answer("✅ Изображение уже получено! Идет обработка...")
                return
            user_data[chat_id]["images"].append(image_data)
            processed = await run_in_executor(process_image, image_data, resource)
            if processed is None:
                raise ValueError("Ошибка обработки изображения")
            await send_resource(message, processed, resource, state)

    except Exception as e:
        logging.error(f"Ошибка обработки: {e}")
        await message.answer(f"❌ Ошибка обработки файла: {str(e)}")
        await state.clear()
        init_user_data(chat_id)

async def request_next_image(message: Message, state: FSMContext):
    chat_id = message.chat.id
    resource = user_data[chat_id]["selected_resource"]
    if resource == "new_painting":
        required = set(NEW_PAINTING_IMAGE_SIZES.keys())
        uploaded = set(user_data[chat_id]["new_painting_images"].keys())
        if uploaded == required:
            await message.answer("Создание... Подождите...")
            await run_in_executor(
                create_resource_pack,
                user_data[chat_id]["new_painting_images"],
                user_data[chat_id]["pack_name"],
                resource
            )
            await send_zip(message)
            init_user_data(chat_id)
            await state.clear()
            return
        next_file = user_data[chat_id]["remaining_files"][0] if user_data[chat_id]["remaining_files"] else None
        if not next_file:
            await message.answer("❌ Ошибка: невозможно определить следующий файл")
            return
        size = NEW_PAINTING_IMAGE_SIZES[next_file]
        await message.answer(f"Отправьте изображение для {next_file} ({size[0]}x{size[1]})")
        await state.set_state(Form.waiting_for_image)

@router.message(Form.waiting_for_image)
async def handle_extra_images(message: Message):
    await message.answer("⚠️ Отправка файлов завершена! Используйте /start для нового процесса")

async def send_resource(message: Message, image_data: bytes, resource_type: str, state: FSMContext):
    chat_id = message.chat.id
    try:
        if not all([user_data[chat_id]["pack_name"], image_data]):
            raise ValueError("Отсутствуют данные для сборки")
        await message.answer("Создание... Подождите...")
        await run_in_executor(create_resource_pack, image_data, user_data[chat_id]["pack_name"], resource_type)
        await send_zip(message)
    except Exception as e:
        logging.error(f"Ошибка создания пакета: {e}")
        await message.answer(f"❌ Ошибка создания ресурспака: {str(e)}")
    finally:
        init_user_data(chat_id)
        await state.clear()

async def send_zip(message: Message):
    chat_id = message.chat.id
    try:
        zip_data = await run_in_executor(create_zip_file, user_data[chat_id]["pack_name"])
        await message.answer_document(
            BufferedInputFile(zip_data, filename=f"{user_data[chat_id]['pack_name']}.mcpack"),
            caption="✅ Ваш ресурспак готов!"
        )
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")
        await message.answer("❌ Ошибка отправки файла!")

# Запуск фоновой задачи при старте бота
@router.startup()
async def on_startup():
    asyncio.create_task(process_painting_queue())

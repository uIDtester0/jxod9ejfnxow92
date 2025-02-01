# handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import RESOURCE_OPTIONS, TEMPLATE_SHIELD_PATH, TEMPLATE_PAINTING_PATH, PAINTING_COLORS, NEW_PAINTING_IMAGE_SIZES
from utils import process_image, process_shield, process_painting, create_resource_pack, create_zip_file
import logging
import io

router = Router()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

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

@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    chat_id = message.chat.id
    if user_data.get(chat_id, {}).get("in_process", False):
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
    await message.answer("Операция отменена")
    await state.clear()

@router.callback_query(Form.selected_resource)
async def select_resource(call: CallbackQuery, state: FSMContext):
    chat_id = call.message.chat.id
    resource = call.data
    user_data[chat_id]["selected_resource"] = resource
    user_data[chat_id]["in_process"] = True

    cancel_kb = ReplyKeyboardBuilder()
    cancel_kb.button(text="/cancel")

    await call.message.answer("Введите название ресурспака:", reply_markup=cancel_kb.as_markup())
    await state.set_state(Form.pack_name)
    await call.answer()

@router.message(Form.pack_name)
async def process_pack_name(message: Message, state: FSMContext):
    chat_id = message.chat.id
    user_data[chat_id]["pack_name"] = message.text
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

        # Обработка для Shield
        if resource == "shield":
            if len(user_data[chat_id]["images"]) >= 2:
                await message.answer("✅ Все изображения получены! Идет обработка...")
                return
                
            user_data[chat_id]["images"].append(image_data)
            
            if len(user_data[chat_id]["images"]) < 2:
                await message.answer("Отправьте второе изображение:")
            else:
                user_data[chat_id]["in_process"] = False
                processed = process_shield(*user_data[chat_id]["images"], TEMPLATE_SHIELD_PATH)
                await send_resource(message, processed, resource, state)

        # Обработка для Painting
        elif resource == "painting":
            required = len(PAINTING_COLORS)
            if len(user_data[chat_id]["images"]) >= required:
                await message.answer("✅ Все изображения получены! Завершаю обработку...")
                return
                
            user_data[chat_id]["images"].append(image_data)
            
            if len(user_data[chat_id]["images"]) < required:
                await message.answer(f"Осталось изображений: {required - len(user_data[chat_id]['images'])}")
            else:
                user_data[chat_id]["in_process"] = False
                processed = process_painting(user_data[chat_id]["images"], TEMPLATE_PAINTING_PATH, PAINTING_COLORS)
                await send_resource(message, processed, resource, state)

        # Обработка для New Painting
        elif resource == "new_painting":
            if not user_data[chat_id]["remaining_files"]:
                await message.answer("✅ Все файлы загружены! Идет обработка...")
                return
                
            current_file = user_data[chat_id]["remaining_files"].pop(0)
            processed = process_image(image_data, resource, current_file)
            user_data[chat_id]["new_painting_images"][current_file] = processed
            await request_next_image(message, state)

        # Обработка других ресурсов (Totem, Ender Pearl)
        else:
            if user_data[chat_id]["images"]:
                await message.answer("✅ Изображение уже получено! Идет обработка...")
                return
                
            user_data[chat_id]["images"].append(image_data)
            user_data[chat_id]["in_process"] = False
            processed = process_image(image_data, resource)
            await send_resource(message, processed, resource, state)

    except Exception as e:
        logging.error(f"Ошибка обработки: {e}")
        await message.answer("❌ Ошибка обработки файла! Процесс прерван.")
        await state.clear()
        init_user_data(chat_id)

async def request_next_image(message: Message, state: FSMContext):
    chat_id = message.chat.id
    resource = user_data[chat_id]["selected_resource"]

    if resource == "new_painting":
        required = set(NEW_PAINTING_IMAGE_SIZES.keys())
        uploaded = set(user_data[chat_id]["new_painting_images"].keys())
        
        if uploaded == required:
            create_resource_pack(
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
        create_resource_pack(
            image_data,
            user_data[chat_id]["pack_name"],
            resource_type
        )
        await send_zip(message)
        init_user_data(chat_id)
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка создания пакета: {e}")
        await message.answer("❌ Ошибка создания ресурспака!")

async def send_zip(message: Message):
    chat_id = message.chat.id
    try:
        zip_data = create_zip_file(user_data[chat_id]["pack_name"])
        await message.answer_document(
            BufferedInputFile(zip_data, filename=f"{user_data[chat_id]['pack_name']}.mcpack"),
            caption="✅ Ваш ресурспак готов!"
        )
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")
        await message.answer("❌ Ошибка отправки файла!")

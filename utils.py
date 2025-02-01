# utils.py
from PIL import Image, ImageDraw, ImageOps
import io
import zipfile
import os
import uuid
import shutil
import json
import logging
from config import NEW_PAINTING_IMAGE_SIZES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

def validate_data(data):
    """Проверка и преобразование данных в bytes"""
    if isinstance(data, int):
        logging.error("Обнаружены целочисленные данные! Возвращаем пустые байты.")
        return b''
        
    if not isinstance(data, bytes):
        try:
            if data is None:
                return b''
            return bytes(data)
        except Exception as e:
            logging.error(f"Невозможно преобразовать данные в bytes: {e}")
            return b''
    return data

def process_image(image_bytes, selected_resource, filename=None):
    """Обработка изображения с гарантированным возвратом bytes"""
    try:
        image_bytes = validate_data(image_bytes)
        if not image_bytes:
            raise ValueError("Получены пустые данные изображения")
            
        if selected_resource == "new_painting" and not filename:
            raise ValueError("Требуется имя файла для New Painting")

        image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        
        if selected_resource == "ender_pearl":
            mask = Image.new("L", image.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, *image.size), fill=255)
            result = Image.new("RGBA", image.size)
            result.paste(image, (0, 0), mask)
            result = result.resize((256, 256))
            
        elif selected_resource == "totem":
            result = image.resize((256, 256))
            
        elif selected_resource == "new_painting":
            expected_size = NEW_PAINTING_IMAGE_SIZES.get(filename, (512, 512))
            result = ImageOps.fit(image, expected_size, Image.Resampling.LANCZOS)
            
        else:
            raise ValueError(f"Неизвестный ресурс: {selected_resource}")

        output = io.BytesIO()
        result.save(output, format="PNG", optimize=True)
        return output.getvalue()
        
    except Exception as e:
        logging.error(f"Ошибка обработки изображения: {e}")
        return b''

def process_shield(front_bytes, back_bytes, template_path):
    """Обработка щита с валидацией данных"""
    try:
        front_bytes = validate_data(front_bytes)
        back_bytes = validate_data(back_bytes)
        
        template = Image.open(template_path).convert("RGBA")
        front = Image.open(io.BytesIO(front_bytes)).convert("RGBA")
        back = Image.open(io.BytesIO(back_bytes)).convert("RGBA")

        red_rect = find_rectangle(template, (255, 0, 0, 255))
        green_rect = find_rectangle(template, (0, 255, 0, 255))

        if not red_rect or not green_rect:
            raise ValueError("Не найдены маркерные области на шаблоне")

        front = front.resize((red_rect[2]-red_rect[0], red_rect[3]-red_rect[1]))
        back = back.resize((green_rect[2]-green_rect[0], green_rect[3]-green_rect[1]))

        result = template.copy()
        result.paste(front, red_rect[:2], front)
        result.paste(back, green_rect[:2], back)

        output = io.BytesIO()
        result.save(output, format="PNG", optimize=True)
        return output.getvalue()
        
    except Exception as e:
        logging.error(f"Ошибка обработки щита: {e}")
        return b''

def process_painting(images_bytes, template_path, colors):
    """Обработка картины с валидацией данных"""
    try:
        validated_images = [validate_data(img) for img in images_bytes]
        template = Image.open(template_path).convert("RGBA")
        result = template.copy()
        
        for i, img_bytes in enumerate(validated_images):
            if i >= len(colors) or not img_bytes:
                continue
                
            try:
                color = tuple(int(colors[i][j:j+2], 16) for j in (1,3,5)) + (255,)
                rect = find_rectangle(template, color)
                
                if not rect:
                    continue
                    
                image = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                image = image.resize((rect[2]-rect[0], rect[3]-rect[1]))
                result.paste(image, rect[:2], image)

            except Exception as e:
                logging.error(f"Ошибка обработки изображения {i}: {e}")
                continue

        output = io.BytesIO()
        result.save(output, format="PNG", optimize=True)
        return output.getvalue()
        
    except Exception as e:
        logging.error(f"Ошибка обработки картины: {e}")
        return b''

def find_rectangle(image, target_color):
    """Поиск прямоугольной области по цвету"""
    try:
        pixels = image.load()
        width, height = image.size
        bounds = [width, height, 0, 0]
        
        for x in range(width):
            for y in range(height):
                if pixels[x, y] == target_color:
                    bounds[0] = min(bounds[0], x)
                    bounds[1] = min(bounds[1], y)
                    bounds[2] = max(bounds[2], x)
                    bounds[3] = max(bounds[3], y)
                    
        if bounds[0] > bounds[2] or bounds[1] > bounds[3]:
            return None
            
        return (bounds[0], bounds[1], bounds[2]+1, bounds[3]+1)
    except Exception as e:
        logging.error(f"Ошибка поиска прямоугольника: {e}")
        return None

def create_resource_pack(image_data, pack_name, resource_type, filenames=None):
    """Создание ресурспака с расширенной валидацией"""
    temp_dir = "temp_resourcepack"
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            
        os.makedirs(temp_dir, exist_ok=True)
        textures_dir = os.path.join(temp_dir, "textures")
        os.makedirs(textures_dir, exist_ok=True)

        # Создание поддиректорий в зависимости от типа ресурса
        if resource_type == "shield":
            os.makedirs(os.path.join(textures_dir, "entity"), exist_ok=True)
        elif resource_type in ("painting", "new_painting"):
            os.makedirs(os.path.join(textures_dir, "painting"), exist_ok=True)
        else:
            os.makedirs(os.path.join(textures_dir, "items"), exist_ok=True)

        # Обработка данных в зависимости от типа ресурса
        if resource_type == "new_painting":
            if not isinstance(image_data, dict):
                raise TypeError(f"Для new_painting ожидается dict, получено {type(image_data)}")
            
            for filename, data in image_data.items():
                data = validate_data(data)
                if not data:
                    raise ValueError(f"Пустые данные для файла {filename}")
                path = os.path.join(textures_dir, "painting", filename)
                with open(path, "wb") as f:
                    f.write(data)
                logging.info(f"Создан файл: {path} ({len(data)} байт)")
                
        elif resource_type == "painting":
            image_data = validate_data(image_data)
            if not image_data:
                raise ValueError("Пустые данные для изображения painting")
            
            path = os.path.join(textures_dir, "painting", "kz.png")
            with open(path, "wb") as f:
                f.write(image_data)
            logging.info(f"Создан файл: {path} ({len(image_data)} байт)")
            
        elif resource_type == "shield":
            image_data = validate_data(image_data)
            if not image_data:
                raise ValueError("Пустые данные для ресурса shield")
            
            path = os.path.join(textures_dir, "entity", "shield.png")
            with open(path, "wb") as f:
                f.write(image_data)
            logging.info(f"Создан файл: {path} ({len(image_data)} байт)")
            
        elif resource_type == "ender_pearl":
            image_data = validate_data(image_data)
            if not image_data:
                raise ValueError("Пустые данные для ресурса ender_pearl")
            
            path = os.path.join(textures_dir, "items", "ender_pearl.png")
            with open(path, "wb") as f:
                f.write(image_data)
            logging.info(f"Создан файл: {path} ({len(image_data)} байт)")
            
        elif resource_type == "totem":
            image_data = validate_data(image_data)
            if not image_data:
                raise ValueError("Пустые данные для ресурса totem")
            
            path = os.path.join(textures_dir, "items", "totem.png")
            with open(path, "wb") as f:
                f.write(image_data)
            logging.info(f"Создан файл: {path} ({len(image_data)} байт)")
            
        else:
            raise ValueError(f"Неизвестный тип ресурса: {resource_type}")

        # Создание манифеста
        manifest = {
            "format_version": 1,
            "header": {
                "description": "VK: https://vk.com/hentai_mcpack",
                "name": pack_name[:64],
                "uuid": str(uuid.uuid4()),
                "version": [6, 6, 6],
                "min_engine_version": [1, 2, 6]
            },
            "modules": [{
                "description": "VK: https://vk.com/hentai_mcpack",
                "type": "resources",
                "uuid": str(uuid.uuid4()),
                "version": [6, 6, 6]
            }]
        }
        
        manifest_path = os.path.join(temp_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            
        logging.info(f"Создан манифест: {manifest_path}")

    except Exception as e:
        logging.error(f"Ошибка создания ресурспака: {e}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise

def create_zip_file(pack_name):
    """Создание ZIP-архива с контролем ошибок"""
    temp_dir = "temp_resourcepack"
    zip_buffer = io.BytesIO()
    
    try:
        if not os.path.exists(temp_dir):
            raise FileNotFoundError("Временная директория не найдена")
            
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    path = os.path.join(root, file)
                    arcname = os.path.relpath(path, temp_dir)
                    zipf.write(path, arcname)
                    
        zip_size = len(zip_buffer.getvalue())
        logging.info(f"Размер ZIP-архива: {zip_size/1024:.2f} KB")
        
        if zip_size > 50 * 1024 * 1024:
            raise ValueError(f"Превышен лимит размера файла: {zip_size/1024/1024:.2f} MB")
            
    except Exception as e:
        logging.error(f"Ошибка создания ZIP: {e}")
        raise
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
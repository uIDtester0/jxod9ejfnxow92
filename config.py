# config.py

# Токен вашего бота
BOT_TOKEN = "7931680506:AAE5k1b3GJQ8iW4o2kTRr-rThP7ibmfzPsc"  # Замените на ваш токен

# Путь к локальному файлу с шаблоном щита
TEMPLATE_SHIELD_PATH = "shield_template.png"  # Убедитесь, что файл существует

# Путь к локальному файлу с шаблоном картины
TEMPLATE_PAINTING_PATH = "painting_template.png"  # Убедитесь, что файл существует

# Опции ресурсов
RESOURCE_OPTIONS = {
    "ender_pearl": "Ender Pearl",
    "totem": "Totem",
    "shield": "Shield",
    "painting": "Painting",
    "new_painting": "New Painting"  # Добавляем новый ресурс
}

# Цвета для каждой из 26 областей на шаблоне картины
PAINTING_COLORS = [
    "#FF0000",  # Красный
    "#FFA500",  # Оранжевый
    "#FFFF00",  # Жёлтый
    "#008000",  # Зелёный
    "#00FFFF",  # Голубой
    "#0000FF",  # Синий
    "#800080",  # Фиолетовый
    "#FFC0CB",  # Розовый
    "#A52A2A",  # Коричневый
    "#000000",  # Чёрный
    "#FFFFFF",  # Белый
    "#808080",  # Серый
    "#40E0D0",  # Бирюзовый
    "#800000",  # Бордовый
    "#E6E6FA",  # Лавандовый
    "#808000",  # Оливковый
    "#FFE5B4",  # Персиковый
    "#98FF98",  # Мятный
    "#4B0082",  # Индиго
    "#E2725B",  # Терракотовый
    "#0F52BA",  # Сапфировый
    "#FF7F50",  # Коралловый
    "#FFDB58",  # Горчичный
    "#FF00FF",  # Фуксия
    "#003737",  # Циан
    "#F7E7CE",  # Шампань
]

# Размеры изображений для New Painting (уменьшены в 2 раза)
NEW_PAINTING_IMAGE_SIZES = {
    "backyard.png": (512, 512),
    "baroque.png": (512, 512),
    "bouquet.png": (512, 512),
    "cavebird.png": (512, 512),
    "changing.png": (1024, 512),
    "cotan.png": (512, 512),
    "endboss.png": (512, 512),
    "fern.png": (512, 512),
    "finding.png": (1024, 512),
    "lowmist.png": (1024, 512),
    "passage.png": (1024, 512),
    "pond.png": (773, 1024),
    "prairie_ride.png": (256, 512),
    "humble.png": (512, 512),
    "meditative.png": (512, 512),
    "orb.png": (512, 512),
    "owlemons.png": (512, 512),
    "sunflowers.png": (512, 512),
    "tides.png": (512, 512),
    "unpacked.png": (512, 512),
}

# Логирование
LOGGING_CONFIG = {
    "level": "INFO",  # Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    "format": "%(asctime)s - %(levelname)s - %(message)s",  # Формат логов
    "filename": "bot.log"  # Имя файла для сохранения логов (необязательно)
}

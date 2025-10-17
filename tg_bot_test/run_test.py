#!/usr/bin/env python3
"""
Скрипт для запуска тестового бота
Загружает переменные окружения из .env.test файла
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def main():
    # Получаем путь к директории скрипта
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Ищем файл с переменными окружения
    env_files = [
        project_root / ".env",  # В корне проекта (основной)
        script_dir / "test_env_template.txt"  # Шаблон как fallback
    ]
    
    env_file = None
    for file_path in env_files:
        if file_path.exists():
            env_file = file_path
            break
    
    if env_file:
        print(f"📁 Загружаем переменные окружения из: {env_file}")
        load_dotenv(env_file)
    else:
        print("⚠️  Файл с переменными окружения не найден!")
        print("Создайте .env файл на основе env_template.txt")
        sys.exit(1)
    
    # Проверяем наличие обязательного токена
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_TEST")
    if not bot_token or bot_token == "your_test_bot_token_here":
        print("❌ TELEGRAM_BOT_TOKEN_TEST не настроен!")
        print("Отредактируйте .env файл и укажите токен тестового бота")
        sys.exit(1)
    
    print("✅ Переменные окружения загружены")
    print(f"🧪 Запускаем тестовый бот...")
    
    # Добавляем путь к модулю тестового бота
    sys.path.insert(0, str(script_dir))
    
    # Импортируем и запускаем основной модуль
    try:
        from main import main as bot_main
        import asyncio
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("\n🛑 Тестовый бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка при запуске тестового бота: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

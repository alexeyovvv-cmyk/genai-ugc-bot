"""Централизованное логирование для бота."""
import logging
import sys
from typing import Optional


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Настроить логгер с правильным форматированием.
    
    Args:
        name: Имя логгера (обычно __name__)
        level: Уровень логирования (по умолчанию INFO)
    
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    
    # Избегаем дублирования хэндлеров
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Создаем хэндлер для stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Форматирование: [время] [модуль] УРОВЕНЬ: сообщение
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    # Отключаем распространение на root logger
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер по имени.
    
    Args:
        name: Имя логгера
    
    Returns:
        Логгер
    """
    return logging.getLogger(name)


# Предустановленные логгеры для основных модулей
ugc_logger = setup_logger("ugc_creation")
tts_logger = setup_logger("tts")
falai_logger = setup_logger("falai")
r2_logger = setup_logger("r2")
admin_logger = setup_logger("admin")
stats_logger = setup_logger("statistics")

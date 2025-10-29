"""
Утилиты для измерения времени выполнения операций в процессе монтажа.
"""
import time
import logging
from contextlib import contextmanager
from typing import Optional, Generator
from functools import wraps


@contextmanager
def log_timing(logger: logging.Logger, operation_name: str, prefix: str = "MONTAGE") -> Generator[None, None, None]:
    """
    Context manager для логирования времени выполнения операции.
    
    Usage:
        with log_timing(logger, "download_file", prefix="AUTOPIPELINE"):
            download_file(url, path)
    
    Args:
        logger: логгер для вывода
        operation_name: название операции
        prefix: префикс для логов (по умолчанию MONTAGE)
    """
    start_time = time.time()
    logger.info(f"[{prefix}] ▶️ Starting {operation_name}")
    
    try:
        yield
    finally:
        duration = time.time() - start_time
        if duration > 60:
            # Для длительных операций показываем минуты
            minutes = int(duration // 60)
            seconds = duration % 60
            logger.info(f"[{prefix}] ⏱️ {operation_name} completed in {duration:.2f}s ({minutes}m {seconds:.1f}s)")
        elif duration > 10:
            # Для операций >10 секунд добавляем предупреждение
            logger.info(f"[{prefix}] ⏱️ {operation_name} completed in {duration:.2f}s ⚠️")
        else:
            logger.info(f"[{prefix}] ⏱️ {operation_name} completed in {duration:.2f}s")


def timed(prefix: str = "MONTAGE"):
    """
    Декоратор для автоматического логирования времени выполнения функции.
    
    Usage:
        @timed(prefix="AUTOPIPELINE")
        def my_function():
            pass
    
    Args:
        prefix: префикс для логов
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Пытаемся найти logger в модуле функции
            import sys
            module = sys.modules.get(func.__module__)
            logger = getattr(module, 'logger', None)
            
            if logger is None:
                # Если не нашли, создаем временный
                logger = logging.getLogger(func.__module__)
            
            start_time = time.time()
            func_name = func.__name__
            logger.info(f"[{prefix}] ▶️ Starting {func_name}")
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if duration > 60:
                    minutes = int(duration // 60)
                    seconds = duration % 60
                    logger.info(f"[{prefix}] ⏱️ {func_name} completed in {duration:.2f}s ({minutes}m {seconds:.1f}s)")
                elif duration > 10:
                    logger.info(f"[{prefix}] ⏱️ {func_name} completed in {duration:.2f}s ⚠️")
                else:
                    logger.info(f"[{prefix}] ⏱️ {func_name} completed in {duration:.2f}s")
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"[{prefix}] ❌ {func_name} failed after {duration:.2f}s: {e}")
                raise
        
        return wrapper
    return decorator


def format_size(size_bytes: int) -> str:
    """
    Форматировать размер файла в человекочитаемый вид.
    
    Args:
        size_bytes: размер в байтах
    
    Returns:
        строка вида "15.2MB" или "3.4GB"
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f}GB"


# statistics.py — модуль для сбора статистики
import os
from datetime import datetime, date
from typing import Optional
from sqlalchemy import select, text, func
from tg_bot.db import SessionLocal
from tg_bot.models import User, CreditLog, UserActivity


def get_moscow_time() -> datetime:
    """Получить текущее время в московской таймзоне"""
    import pytz
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)


def get_moscow_date() -> str:
    """Получить текущую дату в московской таймзоне в формате YYYY-MM-DD"""
    return get_moscow_time().strftime('%Y-%m-%d')


def track_user_activity(tg_id: int) -> None:
    """Записывает активность пользователя на текущую дату"""
    current_date = get_moscow_date()
    
    with SessionLocal() as db:
        # Получаем внутренний user_id
        user = db.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            print(f"[STATS] User {tg_id} not found for activity tracking")
            return
        
        # Проверяем, есть ли запись активности для этого пользователя
        existing_activity = db.scalar(
            select(UserActivity).where(UserActivity.user_id == user.id)
        )
        
        if existing_activity:
            # Обновляем дату активности
            existing_activity.last_activity_date = current_date
            print(f"[STATS] Updated activity for user {tg_id} to {current_date}")
        else:
            # Создаем новую запись
            new_activity = UserActivity(
                user_id=user.id,
                last_activity_date=current_date
            )
            db.add(new_activity)
            print(f"[STATS] Created new activity record for user {tg_id} on {current_date}")
        
        db.commit()


def get_new_users_count(target_date: str) -> int:
    """Количество новых пользователей за указанную дату"""
    try:
        print(f"[STATS] Getting new users count for date: {target_date}")
        with SessionLocal() as db:
            # Используем text() для совместимости с PostgreSQL и SQLite
            result = db.execute(text("""
                SELECT COUNT(*) 
                FROM users 
                WHERE DATE(created_at) = :target_date
            """), {"target_date": target_date}).scalar()
            
            count = result or 0
            print(f"[STATS] New users count: {count}")
            return count
    except Exception as e:
        print(f"[STATS] ❌ ERROR in get_new_users_count: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def get_active_users_count(target_date: str) -> int:
    """Количество активных пользователей за указанную дату"""
    try:
        print(f"[STATS] Getting active users count for date: {target_date}")
        with SessionLocal() as db:
            result = db.execute(text("""
                SELECT COUNT(DISTINCT user_id) 
                FROM user_activity 
                WHERE last_activity_date = :target_date
            """), {"target_date": target_date}).scalar()
            
            count = result or 0
            print(f"[STATS] Active users count: {count}")
            return count
    except Exception as e:
        print(f"[STATS] ❌ ERROR in get_active_users_count: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def get_credits_spent(target_date: str) -> int:
    """Количество потраченных кредитов за указанную дату"""
    try:
        print(f"[STATS] Getting credits spent for date: {target_date}")
        with SessionLocal() as db:
            result = db.execute(text("""
                SELECT COALESCE(SUM(ABS(delta)), 0) 
                FROM credit_log 
                WHERE delta < 0 AND DATE(created_at) = :target_date
            """), {"target_date": target_date}).scalar()
            
            spent = result or 0
            print(f"[STATS] Credits spent: {spent}")
            return spent
    except Exception as e:
        print(f"[STATS] ❌ ERROR in get_credits_spent: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def get_total_users_count() -> int:
    """Общее количество пользователей в базе"""
    try:
        print("[STATS] Getting total users count...")
        with SessionLocal() as db:
            result = db.execute(select(func.count(User.id))).scalar()
            count = result or 0
            print(f"[STATS] Total users count: {count}")
            return count
    except Exception as e:
        print(f"[STATS] ❌ ERROR in get_total_users_count: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def get_total_credits_given() -> int:
    """Общее количество выданных кредитов"""
    try:
        print("[STATS] Getting total credits given...")
        with SessionLocal() as db:
            result = db.execute(text("""
                SELECT COALESCE(SUM(delta), 0) 
                FROM credit_log 
                WHERE delta > 0
            """)).scalar()
            
            given = result or 0
            print(f"[STATS] Total credits given: {given}")
            return given
    except Exception as e:
        print(f"[STATS] ❌ ERROR in get_total_credits_given: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def get_total_credits_spent() -> int:
    """Общее количество потраченных кредитов"""
    try:
        print("[STATS] Getting total credits spent...")
        with SessionLocal() as db:
            result = db.execute(text("""
                SELECT COALESCE(SUM(ABS(delta)), 0) 
                FROM credit_log 
                WHERE delta < 0
            """)).scalar()
            
            spent = result or 0
            print(f"[STATS] Total credits spent: {spent}")
            return spent
    except Exception as e:
        print(f"[STATS] ❌ ERROR in get_total_credits_spent: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def generate_statistics_report(target_date: Optional[str] = None) -> str:
    """Формирует текстовый отчет со статистикой"""
    try:
        print("[STATS] Starting statistics report generation...")
        
        if target_date is None:
            target_date = get_moscow_date()
            print(f"[STATS] Using current date: {target_date}")
        else:
            print(f"[STATS] Using provided date: {target_date}")
        
        print("[STATS] Getting Moscow time...")
        current_time = get_moscow_time()
        print(f"[STATS] Current Moscow time: {current_time}")
        
        # Статистика за день
        print("[STATS] Collecting daily statistics...")
        new_users = get_new_users_count(target_date)
        active_users = get_active_users_count(target_date)
        credits_spent_today = get_credits_spent(target_date)
        
        # Общая статистика
        print("[STATS] Collecting total statistics...")
        total_users = get_total_users_count()
        total_credits_given = get_total_credits_given()
        total_credits_spent = get_total_credits_spent()
        
        print("[STATS] Formatting report...")
        # Форматируем отчет
        report = f"""📊 <b>Статистика бота</b>
🕐 Актуально на: {current_time.strftime('%Y-%m-%d %H:%M:%S')} MSK

📅 За сегодня ({target_date}):
👥 Новых пользователей: {new_users}
✨ Активных пользователей: {active_users}
💸 Потрачено кредитов: {credits_spent_today}

📈 Всего в базе:
👤 Пользователей: {total_users}
💰 Выдано кредитов: {total_credits_given}
📉 Потрачено кредитов: {total_credits_spent}"""
        
        print(f"[STATS] ✅ Report generated successfully (length: {len(report)} chars)")
        return report
        
    except Exception as e:
        error_msg = f"[STATS] ❌ CRITICAL ERROR in generate_statistics_report: {type(e).__name__}: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        # Возвращаем отчет об ошибке
        current_time = get_moscow_time()
        error_report = f"""❌ <b>Ошибка генерации статистики</b>

🕐 Время: {current_time.strftime('%Y-%m-%d %H:%M:%S')} MSK
🔍 Тип ошибки: {type(e).__name__}
📝 Сообщение: {str(e)}

📋 Детали:
<code>{traceback.format_exc()}</code>"""
        
        return error_report



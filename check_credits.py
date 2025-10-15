#!/usr/bin/env python3
"""
Скрипт для проверки состояния кредитов и истории операций
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from tg_bot.models import User, CreditLog

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("⚠️  Using local SQLite database")
    DATABASE_URL = "sqlite:///genai.db"

print(f"🔧 Connecting to database...")
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

def show_all_users():
    """Показать всех пользователей и их кредиты"""
    with Session() as session:
        users = session.execute(select(User)).scalars().all()
        
        if not users:
            print("\n❌ Нет пользователей в базе данных")
            return
        
        print("\n" + "="*80)
        print("👥 ПОЛЬЗОВАТЕЛИ И ИХ КРЕДИТЫ")
        print("="*80)
        
        for user in users:
            print(f"\n🆔 User ID: {user.id} | Telegram ID: {user.tg_id}")
            print(f"💰 Кредиты: {user.credits}")
            print(f"🎤 Выбранный голос: {user.selected_voice_id or 'не выбран'}")
            print(f"📅 Создан: {user.created_at}")
            
            # Показать последние 5 операций с кредитами
            logs = session.execute(
                select(CreditLog)
                .where(CreditLog.user_id == user.id)
                .order_by(CreditLog.created_at.desc())
                .limit(5)
            ).scalars().all()
            
            if logs:
                print(f"\n📊 Последние операции:")
                for log in logs:
                    sign = "+" if log.delta > 0 else ""
                    print(f"  {log.created_at} | {sign}{log.delta} кредитов | {log.reason}")
            else:
                print(f"\n📊 Нет операций с кредитами")
        
        print("\n" + "="*80)

def show_user_credit_history(tg_id: int):
    """Показать полную историю кредитов пользователя"""
    with Session() as session:
        user = session.execute(select(User).where(User.tg_id == tg_id)).scalar_one_or_none()
        
        if not user:
            print(f"\n❌ Пользователь с Telegram ID {tg_id} не найден")
            return
        
        print("\n" + "="*80)
        print(f"💰 ИСТОРИЯ КРЕДИТОВ - User {tg_id}")
        print("="*80)
        print(f"Текущий баланс: {user.credits} кредитов")
        print("-"*80)
        
        logs = session.execute(
            select(CreditLog)
            .where(CreditLog.user_id == user.id)
            .order_by(CreditLog.created_at.desc())
        ).scalars().all()
        
        if not logs:
            print("\n❌ Нет операций с кредитами")
            return
        
        total_added = 0
        total_spent = 0
        
        for log in logs:
            sign = "+" if log.delta > 0 else ""
            emoji = "📈" if log.delta > 0 else "📉"
            
            if log.delta > 0:
                total_added += log.delta
            else:
                total_spent += abs(log.delta)
            
            print(f"{emoji} {log.created_at} | {sign}{log.delta:3d} | {log.reason}")
        
        print("-"*80)
        print(f"📊 Статистика:")
        print(f"  Всего начислено: +{total_added} кредитов")
        print(f"  Всего потрачено: -{total_spent} кредитов")
        print(f"  Текущий баланс: {user.credits} кредитов")
        print(f"  Проверка: {total_added - total_spent} = {user.credits} ✅" if total_added - total_spent == user.credits else f"  ⚠️ НЕСООТВЕТСТВИЕ!")
        print("="*80 + "\n")

def check_database_status():
    """Проверить статус базы данных"""
    print("\n" + "="*80)
    print("🔍 СТАТУС БАЗЫ ДАННЫХ")
    print("="*80)
    
    try:
        with Session() as session:
            # Проверяем количество записей в каждой таблице
            user_count = session.execute(select(User)).scalars().all()
            credit_log_count = session.execute(select(CreditLog)).scalars().all()
            
            print(f"👥 Пользователей: {len(user_count)}")
            print(f"📊 Записей в credit_log: {len(credit_log_count)}")
            
            # Проверяем тип базы данных
            if "sqlite" in DATABASE_URL.lower():
                print(f"\n⚠️  Используется SQLite (локальная база данных)")
                print(f"   Путь: {DATABASE_URL}")
                print(f"   ⚠️  ВНИМАНИЕ: SQLite данные НЕ сохраняются при деплое на Railway!")
            elif "postgresql" in DATABASE_URL.lower():
                print(f"\n✅ Используется PostgreSQL (персистентная база данных)")
                # Скрываем пароль в URL
                safe_url = DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL
                print(f"   Подключение: ...@{safe_url}")
            else:
                print(f"\n❓ Неизвестный тип базы данных: {DATABASE_URL}")
            
            print("="*80 + "\n")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке базы данных: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    
    # Проверяем статус базы данных
    check_database_status()
    
    # Если указан telegram_id в аргументах, показываем историю конкретного пользователя
    if len(sys.argv) > 1:
        try:
            tg_id = int(sys.argv[1])
            show_user_credit_history(tg_id)
        except ValueError:
            print("❌ Неверный формат Telegram ID. Используйте: python check_credits.py <telegram_id>")
    else:
        # Иначе показываем всех пользователей
        show_all_users()





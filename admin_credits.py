#!/usr/bin/env python3
"""
Административная утилита для управления кредитами пользователей
"""
import os
import sys
from dotenv import load_dotenv
from tg_bot.utils.credits import add_credits, get_credits, ensure_user
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from tg_bot.models import User

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("⚠️  Using local SQLite database")
    DATABASE_URL = "sqlite:///genai.db"

engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

def add_credits_to_user(tg_id: int, amount: int, reason: str = "admin_add"):
    """Добавить кредиты пользователю"""
    print(f"\n🔧 Добавление {amount} кредитов пользователю {tg_id}...")
    
    # Проверяем, существует ли пользователь
    with Session() as session:
        user = session.execute(select(User).where(User.tg_id == tg_id)).scalar_one_or_none()
        if not user:
            print(f"❌ Пользователь с Telegram ID {tg_id} не найден в базе данных")
            print(f"💡 Пользователь будет создан при первом обращении к боту")
            return False
    
    # Получаем текущий баланс
    old_balance = get_credits(tg_id)
    print(f"📊 Текущий баланс: {old_balance} кредитов")
    
    # Добавляем кредиты
    add_credits(tg_id, amount, reason)
    
    # Проверяем новый баланс
    new_balance = get_credits(tg_id)
    print(f"✅ Новый баланс: {new_balance} кредитов")
    print(f"📈 Добавлено: {new_balance - old_balance} кредитов")
    
    return True

def set_credits_for_user(tg_id: int, amount: int):
    """Установить точное количество кредитов пользователю"""
    print(f"\n🔧 Установка баланса {amount} кредитов для пользователя {tg_id}...")
    
    with Session() as session:
        user = session.execute(select(User).where(User.tg_id == tg_id)).scalar_one_or_none()
        if not user:
            print(f"❌ Пользователь с Telegram ID {tg_id} не найден")
            return False
        
        old_balance = user.credits
        difference = amount - old_balance
        
        print(f"📊 Текущий баланс: {old_balance} кредитов")
        print(f"📊 Целевой баланс: {amount} кредитов")
        print(f"📊 Разница: {difference:+d} кредитов")
        
        if difference == 0:
            print("ℹ️  Баланс уже соответствует целевому значению")
            return True
        
        # Добавляем или вычитаем разницу
        if difference > 0:
            add_credits(tg_id, difference, "admin_set_balance")
            print(f"✅ Добавлено {difference} кредитов")
        else:
            # Для вычитания используем отрицательное значение
            from tg_bot.utils.credits import spend_credits
            if spend_credits(tg_id, abs(difference), "admin_set_balance"):
                print(f"✅ Списано {abs(difference)} кредитов")
            else:
                print(f"❌ Не удалось списать кредиты (недостаточно средств)")
                return False
        
        # Проверяем новый баланс
        new_balance = get_credits(tg_id)
        print(f"✅ Новый баланс: {new_balance} кредитов")
        
        return True

def list_all_users():
    """Показать список всех пользователей"""
    with Session() as session:
        users = session.execute(select(User)).scalars().all()
        
        if not users:
            print("\n❌ Нет пользователей в базе данных")
            return
        
        print("\n" + "="*80)
        print(f"👥 СПИСОК ПОЛЬЗОВАТЕЛЕЙ (всего: {len(users)})")
        print("="*80)
        
        for user in users:
            print(f"\n🆔 Telegram ID: {user.tg_id}")
            print(f"   💰 Кредиты: {user.credits}")
            print(f"   📅 Регистрация: {user.created_at}")

def show_help():
    """Показать справку"""
    print("""
╔════════════════════════════════════════════════════════════════════╗
║           АДМИНИСТРАТИВНАЯ УТИЛИТА ДЛЯ УПРАВЛЕНИЯ КРЕДИТАМИ        ║
╚════════════════════════════════════════════════════════════════════╝

КОМАНДЫ:

  📈 Добавить кредиты:
     python admin_credits.py add <telegram_id> <amount> [reason]
     
     Пример:
       python admin_credits.py add 123456789 50
       python admin_credits.py add 123456789 100 "promo_bonus"

  📊 Установить точный баланс:
     python admin_credits.py set <telegram_id> <amount>
     
     Пример:
       python admin_credits.py set 123456789 200

  👥 Показать всех пользователей:
     python admin_credits.py list

  💰 Показать баланс пользователя:
     python admin_credits.py balance <telegram_id>
     
     Пример:
       python admin_credits.py balance 123456789

  📋 Показать историю операций:
     python check_credits.py <telegram_id>

════════════════════════════════════════════════════════════════════

ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:

  # Добавить 50 кредитов пользователю
  python admin_credits.py add 123456789 50

  # Установить баланс в 1000 кредитов
  python admin_credits.py set 123456789 1000

  # Показать всех пользователей
  python admin_credits.py list

  # Проверить баланс пользователя
  python admin_credits.py balance 123456789

════════════════════════════════════════════════════════════════════
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "add":
        if len(sys.argv) < 4:
            print("❌ Недостаточно аргументов")
            print("Использование: python admin_credits.py add <telegram_id> <amount> [reason]")
            sys.exit(1)
        
        try:
            tg_id = int(sys.argv[2])
            amount = int(sys.argv[3])
            reason = sys.argv[4] if len(sys.argv) > 4 else "admin_add"
            
            if amount <= 0:
                print("❌ Количество кредитов должно быть положительным числом")
                sys.exit(1)
            
            add_credits_to_user(tg_id, amount, reason)
            
        except ValueError:
            print("❌ Неверный формат telegram_id или amount (должны быть числами)")
            sys.exit(1)
    
    elif command == "set":
        if len(sys.argv) < 4:
            print("❌ Недостаточно аргументов")
            print("Использование: python admin_credits.py set <telegram_id> <amount>")
            sys.exit(1)
        
        try:
            tg_id = int(sys.argv[2])
            amount = int(sys.argv[3])
            
            if amount < 0:
                print("❌ Количество кредитов не может быть отрицательным")
                sys.exit(1)
            
            set_credits_for_user(tg_id, amount)
            
        except ValueError:
            print("❌ Неверный формат telegram_id или amount (должны быть числами)")
            sys.exit(1)
    
    elif command == "list":
        list_all_users()
    
    elif command == "balance":
        if len(sys.argv) < 3:
            print("❌ Недостаточно аргументов")
            print("Использование: python admin_credits.py balance <telegram_id>")
            sys.exit(1)
        
        try:
            tg_id = int(sys.argv[2])
            balance = get_credits(tg_id)
            print(f"\n💰 Баланс пользователя {tg_id}: {balance} кредитов\n")
        except ValueError:
            print("❌ Неверный формат telegram_id (должен быть числом)")
            sys.exit(1)
    
    elif command in ["help", "-h", "--help"]:
        show_help()
    
    else:
        print(f"❌ Неизвестная команда: {command}")
        print("Используйте 'python admin_credits.py help' для справки")
        sys.exit(1)



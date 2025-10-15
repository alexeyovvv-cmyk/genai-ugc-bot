#!/usr/bin/env python3
"""
Сброс кредитов: очистка истории и установка стартовых кредитов всем пользователям.

Действия:
 1) DELETE FROM credit_log
 2) UPDATE users SET credits = DEFAULT_CREDITS
 3) (Опционально для аудита) Добавить по записи +DEFAULT_CREDITS с reason='reset_grant'
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from tg_bot.models import User, CreditLog
from tg_bot.utils.constants import DEFAULT_CREDITS


def main():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("⚠️  Using local SQLite database")
        database_url = "sqlite:///genai.db"

    print(f"🔧 Connecting to database...")
    engine = create_engine(database_url, echo=False)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        # 1) Очистка истории кредитов
        print("🧹 Deleting all credit_log records...")
        session.execute(text("DELETE FROM credit_log"))

        # 2) Установка баланса всем пользователям
        print(f"🔄 Setting users.credits = {DEFAULT_CREDITS}...")
        session.execute(text("UPDATE users SET credits = :c"), {"c": DEFAULT_CREDITS})

        # 3) Заполнение audit записей (по желанию - включено)
        print("📝 Writing reset_grant entries for all users...")
        users = session.execute(select(User)).scalars().all()
        for u in users:
            session.add(CreditLog(user_id=u.id, delta=+DEFAULT_CREDITS, reason="reset_grant"))

        session.commit()
        print("✅ Done. All users set to DEFAULT_CREDITS and audit entries added.")


if __name__ == "__main__":
    main()



# credits.py — атомарные операции с кредитами
from sqlalchemy import select
from tg_bot.db import SessionLocal
from tg_bot.models import User, CreditLog, UserState

def ensure_user(tg_id: int) -> User:
    """Гарантирует наличие пользователя и стартовые 100 кредитов при первом старте."""
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id))
        if u: 
            print(f"[CREDITS] User {tg_id} already exists, credits: {u.credits}", flush=True)
            # Убеждаемся, что есть запись в user_state
            ensure_user_state(db, u.id)
            return u
        u = User(tg_id=tg_id, credits=100)
        db.add(u); db.commit(); db.refresh(u)
        db.add(CreditLog(user_id=u.id, delta=+100, reason="signup_bonus"))
        # Создаем запись в user_state
        ensure_user_state(db, u.id)
        db.commit()
        print(f"[CREDITS] ✅ New user {tg_id} created with 100 credits", flush=True)
        return u

def ensure_user_state(db, user_id: int):
    """Гарантирует наличие записи в user_state для пользователя."""
    existing_state = db.scalar(select(UserState).where(UserState.user_id == user_id))
    if not existing_state:
        user_state = UserState(user_id=user_id)
        db.add(user_state)
        print(f"[CREDITS] ✅ Created user_state for user_id {user_id}", flush=True)
    else:
        print(f"[CREDITS] User_state already exists for user_id {user_id}", flush=True)

def get_credits(tg_id: int) -> int:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id))
        credits = u.credits if u else 0
        print(f"[CREDITS] User {tg_id} has {credits} credits", flush=True)
        return credits

def add_credits(tg_id: int, amount: int, reason: str):
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id))
        if not u: 
            print(f"[CREDITS] ❌ User {tg_id} not found for credit addition", flush=True)
            return
        old_credits = u.credits
        u.credits += amount
        db.add(CreditLog(user_id=u.id, delta=amount, reason=reason))
        db.commit()
        print(f"[CREDITS] ✅ User {tg_id}: +{amount} credits ({old_credits} → {u.credits}) [reason: {reason}]", flush=True)

def spend_credits(tg_id: int, amount: int, reason: str) -> bool:
    """Атомарно списывает amount. Возвращает True при успехе."""
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id)).__copy__() if False else None  # noqa
    # ↑ хитрость не нужна, ниже простой вариант с одной транзакцией:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id).with_for_update())
        if not u:
            print(f"[CREDITS] ❌ User {tg_id} not found for credit spending", flush=True)
            return False
        if u.credits < amount:
            print(f"[CREDITS] ❌ User {tg_id} has insufficient credits: {u.credits} < {amount}", flush=True)
            return False
        old_credits = u.credits
        u.credits -= amount
        db.add(CreditLog(user_id=u.id, delta=-amount, reason=reason))
        db.commit()
        print(f"[CREDITS] ✅ User {tg_id}: -{amount} credits ({old_credits} → {u.credits}) [reason: {reason}]", flush=True)
        return True

# credits.py — атомарные операции с кредитами
from sqlalchemy import select
from tg_bot.db import SessionLocal
from tg_bot.models import User, CreditLog, UserState
from tg_bot.utils.constants import DEFAULT_CREDITS

def ensure_user(tg_id: int) -> User:
    """Гарантирует наличие пользователя и стартовые DEFAULT_CREDITS при первом старте."""
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id))
        if u: 
            print(f"[CREDITS] User {tg_id} already exists, credits: {u.credits}", flush=True)
            # Убеждаемся, что есть запись в user_state
            ensure_user_state(db, u.id)
            return u
        u = User(tg_id=tg_id, credits=DEFAULT_CREDITS)
        db.add(u); db.commit(); db.refresh(u)
        db.add(CreditLog(user_id=u.id, delta=+DEFAULT_CREDITS, reason="signup_bonus"))
        # Создаем запись в user_state
        ensure_user_state(db, u.id)
        db.commit()
        print(f"[CREDITS] ✅ New user {tg_id} created with {DEFAULT_CREDITS} credits", flush=True)
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

def set_credits(tg_id: int, new_balance: int, reason: str = "admin_set"):
    """Устанавливает точный баланс пользователя, записывает delta в CreditLog."""
    from sqlalchemy import select
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id))
        if not u:
            print(f"[CREDITS] ❌ User {tg_id} not found for set_credits", flush=True)
            return
        delta = new_balance - u.credits
        if delta == 0:
            print(f"[CREDITS] ⚠️ set_credits no-op for user {tg_id}", flush=True)
            return
        u.credits = new_balance
        db.add(CreditLog(user_id=u.id, delta=delta, reason=reason))
        db.commit()
        print(f"[CREDITS] ✅ User {tg_id}: set to {new_balance} (delta {delta}) [reason: {reason}]", flush=True)

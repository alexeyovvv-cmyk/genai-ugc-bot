# credits.py — атомарные операции с кредитами
from sqlalchemy import select
from tg_bot.db import SessionLocal
from tg_bot.models import User, CreditLog

def ensure_user(tg_id: int) -> User:
    """Гарантирует наличие пользователя и стартовые 10 кредитов при первом старте."""
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id))
        if u: return u
        u = User(tg_id=tg_id, credits=10)
        db.add(u); db.commit(); db.refresh(u)
        db.add(CreditLog(user_id=u.id, delta=+10, reason="signup_bonus"))
        db.commit()
        return u

def get_credits(tg_id: int) -> int:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id))
        return u.credits if u else 0

def add_credits(tg_id: int, amount: int, reason: str):
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id))
        if not u: return
        u.credits += amount
        db.add(CreditLog(user_id=u.id, delta=amount, reason=reason))
        db.commit()

def spend_credits(tg_id: int, amount: int, reason: str) -> bool:
    """Атомарно списывает amount. Возвращает True при успехе."""
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id)).__copy__() if False else None  # noqa
    # ↑ хитрость не нужна, ниже простой вариант с одной транзакцией:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.tg_id == tg_id).with_for_update())
        if not u or u.credits < amount:
            return False
        u.credits -= amount
        db.add(CreditLog(user_id=u.id, delta=-amount, reason=reason))
        db.commit()
        return True

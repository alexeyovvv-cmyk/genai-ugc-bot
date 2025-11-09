from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from sqlalchemy import select

from tg_bot.db import SessionLocal
from tg_bot.models import RenderSession, User

DEFAULT_CIRCLE_SETTINGS = {
    "radius": 0.35,
    "center_x": 0.5,
    "center_y": 0.5,
    "auto_center": True,
}


def _get_user(db, tg_id: int) -> Optional[User]:
    return db.scalar(select(User).where(User.tg_id == tg_id))


def create_render_session(
    user_identifier: int,
    *,
    scenario: str,
    head_r2_key: Optional[str],
    background_r2_key: Optional[str],
    templates: Optional[Sequence[str]] = None,
    subtitle_settings: Optional[Dict[str, Any]] = None,
    intro_settings: Optional[Dict[str, Any]] = None,
    outro_settings: Optional[Dict[str, Any]] = None,
    circle_settings: Optional[Dict[str, Any]] = None,
) -> Optional[RenderSession]:
    """
    Persist initial render session settings so that user can re-render later.
    """
    with SessionLocal() as db:
        user = _get_user(db, user_identifier)
        if not user:
            return None

        circle_payload = dict(DEFAULT_CIRCLE_SETTINGS)
        if circle_settings:
            circle_payload.update(circle_settings)

        session = RenderSession(
            user_id=user.id,
            scenario=scenario,
            head_r2_key=head_r2_key,
            background_r2_key=background_r2_key,
            templates=list(templates or []),
            subtitle_settings=subtitle_settings,
            intro_settings=intro_settings,
            outro_settings=outro_settings,
            circle_settings=circle_payload,
            status="pending",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session


def update_render_session_result(
    session_id: int,
    *,
    status: str,
    result_r2_key: Optional[str] = None,
    result_url: Optional[str] = None,
    shotstack_url: Optional[str] = None,
    shotstack_render_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Optional[RenderSession]:
    with SessionLocal() as db:
        session = db.get(RenderSession, session_id)
        if not session:
            return None

        session.status = status
        if result_r2_key is not None:
            session.result_r2_key = result_r2_key
        if result_url is not None:
            session.result_url = result_url
        if shotstack_url is not None:
            session.shotstack_url = shotstack_url
        if shotstack_render_id is not None:
            session.shotstack_render_id = shotstack_render_id
        if error_message is not None:
            session.error_message = error_message

        db.commit()
        db.refresh(session)
        return session


def get_latest_render_session(tg_id: int, *, scenario: Optional[str] = None) -> Optional[RenderSession]:
    with SessionLocal() as db:
        user = _get_user(db, tg_id)
        if not user:
            return None
        stmt = select(RenderSession).where(RenderSession.user_id == user.id)
        if scenario:
            stmt = stmt.where(RenderSession.scenario == scenario)
        stmt = stmt.order_by(RenderSession.created_at.desc())
        return db.scalars(stmt).first()

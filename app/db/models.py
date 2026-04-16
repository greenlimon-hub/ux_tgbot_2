from sqlalchemy import BigInteger, Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    place_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    place_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    end_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    chat_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    join_mode: Mapped[str] = mapped_column(String(32), default="invite_link", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class Organizer(TimestampMixin, Base):
    __tablename__ = "organizers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(32), default="organizer", nullable=False)
    can_announce: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_poll: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_view_private_profiles: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_manage_invites: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_launch_games: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EventParticipant(TimestampMixin, Base):
    __tablename__ = "event_participants"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_participants_event_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="started", nullable=False)
    questionnaire_completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    joined_chat_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invite_sent_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attendance_status: Mapped[str | None] = mapped_column(String(32), nullable=True)


class QuestionnaireAnswer(TimestampMixin, Base):
    __tablename__ = "questionnaire_answers"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", "question_code", name="uq_answers_event_user_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_code: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), default="public", nullable=False)


class QuestionnaireProfile(TimestampMixin, Base):
    __tablename__ = "questionnaire_profiles"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_profiles_event_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    public_profile_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    organizer_profile_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    organizer_profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class GamePack(TimestampMixin, Base):
    __tablename__ = "game_packs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GameItem(TimestampMixin, Base):
    __tablename__ = "game_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_pack_id: Mapped[int] = mapped_column(ForeignKey("game_packs.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class SupportRequest(TimestampMixin, Base):
    __tablename__ = "support_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    issue_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    claimed_by_admin_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    closed_by_admin_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class SupportAdminNotification(TimestampMixin, Base):
    __tablename__ = "support_admin_notifications"
    __table_args__ = (
        UniqueConstraint("request_id", "admin_telegram_id", name="uq_support_request_admin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("support_requests.id", ondelete="CASCADE"), nullable=False)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
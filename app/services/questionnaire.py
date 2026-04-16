from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Event,
    EventParticipant,
    QuestionnaireAnswer,
    QuestionnaireProfile,
    User,
)
from app.questionnaire.definitions import QUESTIONNAIRE, get_question_by_code
from app.questionnaire.render import (
    build_organizer_profile_json,
    build_organizer_profile_text,
    build_public_profile_json,
    build_public_profile_text,
)


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def ensure_event_participant(
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> EventParticipant:
    stmt = select(EventParticipant).where(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user_id,
    )
    result = await session.execute(stmt)
    participant = result.scalar_one_or_none()

    if participant is None:
        participant = EventParticipant(
            event_id=event_id,
            user_id=user_id,
            status="questionnaire_in_progress",
        )
        session.add(participant)
        await session.commit()
        await session.refresh(participant)
        return participant

    if participant.status == "started":
        participant.status = "questionnaire_in_progress"
        await session.commit()
        await session.refresh(participant)

    return participant


async def get_answers_map(
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> dict[str, QuestionnaireAnswer]:
    stmt = select(QuestionnaireAnswer).where(
        QuestionnaireAnswer.event_id == event_id,
        QuestionnaireAnswer.user_id == user_id,
    )
    result = await session.execute(stmt)
    answers = result.scalars().all()
    return {answer.question_code: answer for answer in answers}


async def get_next_unanswered_question_index(
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> int | None:
    answers_map = await get_answers_map(session, event_id, user_id)

    for index, question in enumerate(QUESTIONNAIRE):
        if question.code not in answers_map:
            return index

    return None


async def upsert_answer(
    session: AsyncSession,
    event_id: int,
    user_id: int,
    question_code: str,
    answer_text: str | None,
    answer_json: dict | list | None,
    visibility: str | None = None,
) -> QuestionnaireAnswer:
    stmt = select(QuestionnaireAnswer).where(
        QuestionnaireAnswer.event_id == event_id,
        QuestionnaireAnswer.user_id == user_id,
        QuestionnaireAnswer.question_code == question_code,
    )
    result = await session.execute(stmt)
    answer = result.scalar_one_or_none()

    if answer is None:
        answer = QuestionnaireAnswer(
            event_id=event_id,
            user_id=user_id,
            question_code=question_code,
            answer_text=answer_text,
            answer_json=answer_json,
            visibility=visibility or "organizers_only",
        )
        session.add(answer)
    else:
        answer.answer_text = answer_text
        answer.answer_json = answer_json
        if visibility is not None:
            answer.visibility = visibility

    await session.commit()
    await session.refresh(answer)
    return answer


async def set_answer_visibility(
    session: AsyncSession,
    event_id: int,
    user_id: int,
    question_code: str,
    visibility: str,
) -> None:
    stmt = select(QuestionnaireAnswer).where(
        QuestionnaireAnswer.event_id == event_id,
        QuestionnaireAnswer.user_id == user_id,
        QuestionnaireAnswer.question_code == question_code,
    )
    result = await session.execute(stmt)
    answer = result.scalar_one_or_none()

    if answer is None:
        return

    answer.visibility = visibility
    await session.commit()


async def build_and_save_profiles(
    session: AsyncSession,
    event_id: int,
    user: User,
) -> QuestionnaireProfile:
    answers_map = await get_answers_map(session, event_id, user.id)

    public_text = build_public_profile_text(user, answers_map)
    organizer_text = build_organizer_profile_text(user, answers_map)
    public_json = build_public_profile_json(user, answers_map)
    organizer_json = build_organizer_profile_json(user, answers_map)

    stmt = select(QuestionnaireProfile).where(
        QuestionnaireProfile.event_id == event_id,
        QuestionnaireProfile.user_id == user.id,
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = QuestionnaireProfile(
            event_id=event_id,
            user_id=user.id,
            public_profile_text=public_text,
            organizer_profile_text=organizer_text,
            public_profile_json=public_json,
            organizer_profile_json=organizer_json,
            is_confirmed=False,
        )
        session.add(profile)
    else:
        profile.public_profile_text = public_text
        profile.organizer_profile_text = organizer_text
        profile.public_profile_json = public_json
        profile.organizer_profile_json = organizer_json

    await session.commit()
    await session.refresh(profile)
    return profile


async def confirm_questionnaire(
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> None:
    participant_stmt = select(EventParticipant).where(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user_id,
    )
    participant_result = await session.execute(participant_stmt)
    participant = participant_result.scalar_one_or_none()

    if participant is not None:
        participant.status = "questionnaire_completed"
        participant.questionnaire_completed_at = utc_iso_now()

    profile_stmt = select(QuestionnaireProfile).where(
        QuestionnaireProfile.event_id == event_id,
        QuestionnaireProfile.user_id == user_id,
    )
    profile_result = await session.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    if profile is not None:
        profile.is_confirmed = True

    await session.commit()


async def get_profile_for_event(
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> QuestionnaireProfile | None:
    stmt = select(QuestionnaireProfile).where(
        QuestionnaireProfile.event_id == event_id,
        QuestionnaireProfile.user_id == user_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_profiles_for_user(
    session: AsyncSession,
    user_id: int,
) -> list[tuple[QuestionnaireProfile, Event]]:
    stmt = (
        select(QuestionnaireProfile, Event)
        .join(Event, QuestionnaireProfile.event_id == Event.id)
        .where(QuestionnaireProfile.user_id == user_id)
        .order_by(Event.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.all())


async def reset_questionnaire_for_event(
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> None:
    answers_stmt = select(QuestionnaireAnswer).where(
        QuestionnaireAnswer.event_id == event_id,
        QuestionnaireAnswer.user_id == user_id,
    )
    answers_result = await session.execute(answers_stmt)
    answers = answers_result.scalars().all()

    for answer in answers:
        await session.delete(answer)

    profile_stmt = select(QuestionnaireProfile).where(
        QuestionnaireProfile.event_id == event_id,
        QuestionnaireProfile.user_id == user_id,
    )
    profile_result = await session.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    if profile is not None:
        await session.delete(profile)

    participant_stmt = select(EventParticipant).where(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user_id,
    )
    participant_result = await session.execute(participant_stmt)
    participant = participant_result.scalar_one_or_none()

    if participant is not None:
        participant.status = "questionnaire_in_progress"
        participant.questionnaire_completed_at = None

    await session.commit()


async def get_confirmed_profile(
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> QuestionnaireProfile | None:
    stmt = select(QuestionnaireProfile).where(
        QuestionnaireProfile.event_id == event_id,
        QuestionnaireProfile.user_id == user_id,
        QuestionnaireProfile.is_confirmed.is_(True),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def mark_participant_joined(
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> bool:
    stmt = select(EventParticipant).where(
        EventParticipant.event_id == event_id,
        EventParticipant.user_id == user_id,
    )
    result = await session.execute(stmt)
    participant = result.scalar_one_or_none()

    if participant is None:
        return False

    if participant.status == "joined_chat" and participant.joined_chat_at:
        return False

    participant.status = "joined_chat"
    participant.joined_chat_at = utc_iso_now()
    await session.commit()
    return True


async def list_user_event_chats(
    session: AsyncSession,
    user_id: int,
) -> list[Event]:
    stmt = (
        select(Event)
        .join(EventParticipant, EventParticipant.event_id == Event.id)
        .where(EventParticipant.user_id == user_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_all_user_profiles_and_participation(
    session: AsyncSession,
    user_id: int,
) -> None:
    answers_stmt = select(QuestionnaireAnswer).where(
        QuestionnaireAnswer.user_id == user_id,
    )
    answers_result = await session.execute(answers_stmt)
    answers = answers_result.scalars().all()

    for answer in answers:
        await session.delete(answer)

    profiles_stmt = select(QuestionnaireProfile).where(
        QuestionnaireProfile.user_id == user_id,
    )
    profiles_result = await session.execute(profiles_stmt)
    profiles = profiles_result.scalars().all()

    for profile in profiles:
        await session.delete(profile)

    participants_stmt = select(EventParticipant).where(
        EventParticipant.user_id == user_id,
    )
    participants_result = await session.execute(participants_stmt)
    participants = participants_result.scalars().all()

    for participant in participants:
        await session.delete(participant)

    await session.commit()


async def build_profile_previews_from_draft(
    session: AsyncSession,
    event_id: int,
    user: User,
    draft_answers: dict,
) -> tuple[str, str]:
    answers_map = await get_answers_map(session, event_id, user.id)
    merged_answers = dict(answers_map)

    for question_code, payload in draft_answers.items():
        existing = merged_answers.get(question_code)
        visibility = payload.get("visibility")

        if visibility is None:
            if existing is not None:
                visibility = existing.visibility
            else:
                visibility = get_question_by_code(question_code).default_visibility

        merged_answers[question_code] = SimpleNamespace(
            answer_text=payload.get("answer_text"),
            answer_json=payload.get("answer_json"),
            visibility=visibility,
        )

    public_text = build_public_profile_text(user, merged_answers)
    organizer_text = build_organizer_profile_text(user, merged_answers)
    return public_text, organizer_text


async def apply_draft_answers(
    session: AsyncSession,
    event_id: int,
    user_id: int,
    draft_answers: dict,
) -> None:
    for question_code, payload in draft_answers.items():
        await upsert_answer(
            session=session,
            event_id=event_id,
            user_id=user_id,
            question_code=question_code,
            answer_text=payload.get("answer_text"),
            answer_json=payload.get("answer_json"),
            visibility=payload.get("visibility"),
        )
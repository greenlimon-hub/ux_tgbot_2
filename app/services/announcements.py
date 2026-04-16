from html import escape


def split_pipe_args(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("|") if part.strip()]


def render_announce_message(text: str) -> str:
    return (
        "📢 <b>Сообщение от организаторов</b>\n\n"
        f"{escape(text.strip())}"
    )


def render_meeting_message(date_time: str, place: str, description: str) -> str:
    return (
        "📌 <b>Объявление по встрече</b>\n"
        f"<b>Когда:</b> {escape(date_time)}\n"
        f"<b>Где:</b> {escape(place)}\n"
        f"<b>Что будет:</b> {escape(description)}"
    )


def render_where_message(place: str, comment: str | None = None) -> str:
    text = (
        "📍 <b>Обновление по месту встречи</b>\n"
        f"<b>Новое место:</b> {escape(place)}"
    )

    if comment:
        text += f"\n<b>Комментарий:</b> {escape(comment)}"

    return text


def render_when_message(date_time: str, comment: str | None = None) -> str:
    text = (
        "⏰ <b>Обновление по времени</b>\n"
        f"<b>Новое время:</b> {escape(date_time)}"
    )

    if comment:
        text += f"\n<b>Комментарий:</b> {escape(comment)}"

    return text


def render_important_message(text: str) -> str:
    return (
        "⚠️ <b>Важно</b>\n\n"
        f"{escape(text.strip())}"
    )


def parse_meeting_args(raw: str) -> tuple[str, str, str]:
    parts = split_pipe_args(raw)
    if len(parts) != 3:
        raise ValueError(
            "Неверный формат.\n"
            "Используй:\n"
            "<code>/meeting Когда | Где | Что будет</code>"
        )

    return parts[0], parts[1], parts[2]


def parse_where_args(raw: str) -> tuple[str, str | None]:
    parts = split_pipe_args(raw)
    if not parts:
        raise ValueError(
            "Неверный формат.\n"
            "Используй:\n"
            "<code>/where Место | Комментарий</code>"
        )

    if len(parts) == 1:
        return parts[0], None

    return parts[0], parts[1]


def parse_when_args(raw: str) -> tuple[str, str | None]:
    parts = split_pipe_args(raw)
    if not parts:
        raise ValueError(
            "Неверный формат.\n"
            "Используй:\n"
            "<code>/when Время | Комментарий</code>"
        )

    if len(parts) == 1:
        return parts[0], None

    return parts[0], parts[1]


def parse_poll_args(raw: str) -> tuple[str, list[str]]:
    parts = split_pipe_args(raw)

    if len(parts) < 3:
        raise ValueError(
            "Неверный формат.\n"
            "Используй:\n"
            "<code>/poll_custom Вопрос | Вариант 1 | Вариант 2 | Вариант 3</code>"
        )

    question = parts[0].strip()
    options = [option.strip() for option in parts[1:] if option.strip()]

    if not question:
        raise ValueError("Вопрос опроса не должен быть пустым.")

    if len(question) > 300:
        raise ValueError("Вопрос опроса слишком длинный. Максимум: 300 символов.")

    if len(options) < 2:
        raise ValueError("У опроса должно быть минимум 2 варианта ответа.")

    if len(options) > 12:
        raise ValueError("У опроса может быть максимум 12 вариантов ответа.")

    return question, options
from html import escape

from app.questionnaire.definitions import QUESTIONNAIRE, get_question_by_code


def format_question_text(question, index: int, total: int) -> str:
    lines = [
        f"<b>Анкета • вопрос {index + 1}/{total}</b>",
        "",
        escape(question.prompt),
    ]

    if question.kind == "number":
        lines.append("")
        lines.append("Отправь число сообщением.")

    if question.kind == "multi_select" and question.options:
        lines.append("")
        lines.append("Выбери один или несколько вариантов и отправь номера через запятую.")
        lines.append("Например: <code>1,3,5</code>")
        lines.append("")
        for idx, option in enumerate(question.options, start=1):
            lines.append(f"{idx}. {escape(option)}")

    if question.kind == "text":
        lines.append("")
        lines.append("Ответь обычным сообщением.")

    if question.kind == "textarea":
        lines.append("")
        lines.append("Можно ответить в свободной форме одним сообщением.")

    if question.kind == "photo":
        lines.append("")
        lines.append("Отправь одну фотографию.")
        if not question.required:
            lines.append("Если хочешь пропустить вопрос, отправь <code>-</code>.")

    if question.kind in {"single_select", "yes_no"}:
        lines.append("")
        lines.append("Выбери вариант кнопкой ниже.")

    if not question.required and question.kind != "photo":
        lines.append("")
        lines.append("Если хочешь пропустить вопрос, отправь <code>-</code>.")

    return "\n".join(lines)


def answer_has_content(answer) -> bool:
    if answer is None:
        return False

    answer_json = answer.answer_json or {}
    if isinstance(answer_json, dict) and answer_json.get("skipped") is True:
        return False

    if answer.answer_text is None:
        return False

    return bool(str(answer.answer_text).strip())


def build_privacy_queue(answers_map: dict) -> list[str]:
    result: list[str] = []

    for question in QUESTIONNAIRE:
        if not question.privacy_configurable:
            continue

        answer = answers_map.get(question.code)
        if answer_has_content(answer):
            result.append(question.code)

    return result


def format_visibility_label(value: str) -> str:
    mapping = {
        "public": "Видно всем участникам",
        "organizers_only": "Видно только организаторам",
        "private_hidden": "Скрыто",
    }
    return mapping.get(value, value)


def _visible(answer, target: str) -> bool:
    if answer is None:
        return False

    if not answer_has_content(answer):
        return False

    if target == "public":
        return answer.visibility == "public"

    if target == "organizer":
        return answer.visibility in {"public", "organizers_only"}

    return False


def _display_answer(question, answer) -> str | None:
    if answer is None or not answer_has_content(answer):
        return None

    if question.kind == "photo":
        return "Фото загружено"

    return answer.answer_text


def build_public_profile_text(user, answers_map: dict) -> str:
    name_answer = answers_map.get("name")
    age_answer = answers_map.get("age")

    header_name = "Новый участник"
    if _visible(name_answer, "public"):
        header_name = escape(name_answer.answer_text)

    header = f"<b>{header_name}</b>"

    if _visible(age_answer, "public"):
        header += f", {escape(age_answer.answer_text)}"

    lines = [header]

    if user.username:
        lines.append(f"<b>Username:</b> @{escape(user.username)}")

    for question in QUESTIONNAIRE:
        if question.code in {"name", "age"}:
            continue

        answer = answers_map.get(question.code)
        if not _visible(answer, "public"):
            continue

        display_value = _display_answer(question, answer)
        if display_value is None:
            continue

        lines.append(f"<b>{escape(question.label)}:</b> {escape(display_value)}")

    return "\n".join(lines)


def build_organizer_profile_text(user, answers_map: dict) -> str:
    name_answer = answers_map.get("name")
    age_answer = answers_map.get("age")

    header_name = user.first_name or "Без имени"
    if answer_has_content(name_answer):
        header_name = name_answer.answer_text

    header = f"<b>{escape(header_name)}</b>"

    if answer_has_content(age_answer):
        header += f", {escape(age_answer.answer_text)}"

    lines = [header]

    if user.username:
        lines.append(f"<b>Username:</b> @{escape(user.username)}")

    for question in QUESTIONNAIRE:
        if question.code in {"name", "age"}:
            continue

        answer = answers_map.get(question.code)
        if not _visible(answer, "organizer"):
            continue

        display_value = _display_answer(question, answer)
        if display_value is None:
            continue

        lines.append(f"<b>{escape(question.label)}:</b> {escape(display_value)}")

    return "\n".join(lines)


def build_public_profile_json(user, answers_map: dict) -> dict:
    data: dict[str, str | dict] = {}

    if user.username:
        data["username"] = f"@{user.username}"

    for question in QUESTIONNAIRE:
        answer = answers_map.get(question.code)
        if not _visible(answer, "public"):
            continue

        if question.kind == "photo":
            answer_json = answer.answer_json or {}
            file_id = answer_json.get("file_id") if isinstance(answer_json, dict) else None
            if file_id:
                data[question.code] = {"file_id": file_id}
            continue

        data[question.code] = answer.answer_text

    return data


def build_organizer_profile_json(user, answers_map: dict) -> dict:
    data: dict[str, str | dict] = {}

    if user.username:
        data["username"] = f"@{user.username}"

    for question in QUESTIONNAIRE:
        answer = answers_map.get(question.code)
        if not _visible(answer, "organizer"):
            continue

        if question.kind == "photo":
            answer_json = answer.answer_json or {}
            file_id = answer_json.get("file_id") if isinstance(answer_json, dict) else None
            if file_id:
                data[question.code] = {"file_id": file_id}
            continue

        data[question.code] = answer.answer_text

    return data
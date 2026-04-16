from html import escape


def render_games_menu(chat_type: str) -> str:
    if chat_type == "private":
        return (
            "🎲 <b>Мини-игры и вопросы</b>\n\n"
            "Доступные команды в ЛС:\n"
            "/question — случайный вопрос\n"
            "/topics — 3 темы для разговора\n"
            "/jeff — дилемма для обсуждения"
        )

    return (
        "🎲 <b>Мини-игры для знакомства</b>\n\n"
        "Доступные команды:\n"
        "/question — случайный вопрос\n"
        "/topics — 3 темы для разговора\n"
        "/match — игра «Найди совпадение»\n"
        "/match_results — собрать ответы по текущей игре\n"
        "/jeff — дилемма для обсуждения"
    )


def render_random_question(question: str) -> str:
    return (
        "💬 <b>Вопрос для знакомства</b>\n\n"
        f"{escape(question)}"
    )


def render_topics(topics: list[str]) -> str:
    lines = ["🗂 <b>3 темы для разговора</b>", ""]
    for idx, topic in enumerate(topics, start=1):
        lines.append(f"{idx}. {escape(topic)}")
    return "\n".join(lines)


def render_match_start(topic: str) -> str:
    return (
        "🔎 <b>Игра «Найди совпадение»</b>\n\n"
        f"<b>Тема:</b> {escape(topic)}\n\n"
        "Каждый отвечает <b>реплаем на это сообщение</b> одним коротким сообщением.\n"
        "Потом используйте /match_results, чтобы собрать ответы."
    )


def render_match_results(topic: str, answers: list[str]) -> str:
    lines = [
        f"📋 <b>Ответы по теме:</b> {escape(topic)}",
        "",
    ]

    if not answers:
        lines.append("Пока никто не ответил.")
        return "\n".join(lines)

    for idx, answer in enumerate(answers, start=1):
        lines.append(f"{idx}. {escape(answer)}")

    lines.append("")
    lines.append("Попробуйте найти человека с похожим ответом и начать разговор с этого.")
    return "\n".join(lines)


def render_jeff_card(title: str, followup: str) -> str:
    return (
        "🧠 <b>Джеффа</b>\n\n"
        f"<b>Дилемма:</b> {escape(title)}\n\n"
        "Обсудите вслух, какой вариант вам ближе и почему.\n\n"
        f"<b>Вопрос для обсуждения:</b>\n{escape(followup)}"
    )
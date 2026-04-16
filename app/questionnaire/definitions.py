from dataclasses import dataclass, field


@dataclass(slots=True)
class QuestionSpec:
    code: str
    label: str
    prompt: str
    kind: str  # text | textarea | number | single_select | multi_select | yes_no
    required: bool = True
    options: list[str] = field(default_factory=list)
    min_value: int | None = None
    max_value: int | None = None
    max_length: int | None = None
    default_visibility: str = "organizers_only"
    privacy_configurable: bool = False


QUESTIONNAIRE: list[QuestionSpec] = [
    QuestionSpec(
        code="name",
        label="Имя",
        prompt="Как тебя зовут?",
        kind="text",
        max_length=40,
        default_visibility="public",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="age",
        label="Возраст",
        prompt="Сколько тебе лет?",
        kind="number",
        min_value=16,
        max_value=99,
        default_visibility="public",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="city",
        label="Город",
        prompt="В каком ты городе?",
        kind="text",
        max_length=80,
        default_visibility="public",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="university",
        label="Вуз",
        prompt="В каком вузе ты учишься?",
        kind="text",
        max_length=120,
        default_visibility="public",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="field_of_study",
        label="Сфера / направление",
        prompt="На каком направлении, факультете или специальности ты учишься?",
        kind="text",
        max_length=120,
        default_visibility="public",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="about_self",
        label="О себе",
        prompt="Расскажи о себе в 1–3 предложениях.",
        kind="textarea",
        max_length=300,
        default_visibility="public",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="interests_text",
        label="Интересы",
        prompt="Какие у тебя интересы? Напиши в свободной форме.",
        kind="textarea",
        max_length=250,
        default_visibility="organizers_only",
        privacy_configurable=True,
    ),
    QuestionSpec(
        code="fun_fact",
        label="Интересный факт",
        prompt="Назови 1 интересный факт о себе.",
        kind="text",
        required=False,
        max_length=150,
        default_visibility="organizers_only",
        privacy_configurable=True,
    ),
    QuestionSpec(
        code="social_style",
        label="В каком коллективе проще знакомиться",
        prompt="В каком коллективе тебе проще всего находить общий язык?",
        kind="single_select",
        options=[
            "Один на один",
            "До 3 человек",
            "До 5 человек",
            "До 10 человек",
            "Другое",
        ],
        default_visibility="organizers_only",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="helps_to_open_up",
        label="Что помогает разговориться",
        prompt="Что помогает тебе разговориться на первой встрече?",
        kind="textarea",
        max_length=250,
        default_visibility="organizers_only",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="comfort_conditions",
        label="Что делает встречу комфортной",
        prompt="Что делает первую встречу для тебя комфортной?",
        kind="textarea",
        required=False,
        max_length=250,
        default_visibility="organizers_only",
        privacy_configurable=True,
    ),
    QuestionSpec(
        code="barriers",
        label="Что может мешать",
        prompt="Что может смущать или мешать тебе на первой встрече?",
        kind="textarea",
        required=False,
        max_length=250,
        default_visibility="organizers_only",
        privacy_configurable=True,
    ),
    QuestionSpec(
        code="sociability_level",
        label="Насколько ты общительный(ая)",
        prompt="Насколько ты общительный человек?",
        kind="single_select",
        options=[
            "Очень легко знакомлюсь",
            "Скорее общительный(ая)",
            "Зависит от атмосферы",
            "Сначала осторожничаю",
            "Раскрываюсь не сразу",
            "Другое",
        ],
        default_visibility="organizers_only",
        privacy_configurable=True,
    ),
    QuestionSpec(
        code="communication_style",
        label="Формат общения",
        prompt="Какой формат общения тебе ближе?",
        kind="single_select",
        options=[
            "Легкий small talk",
            "Смешные истории",
            "Глубокие разговоры",
            "Обсуждение интересов",
            "Совместная активность важнее слов",
            "Другое",
        ],
        default_visibility="organizers_only",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="attendance_probability",
        label="Вероятность прихода",
        prompt="Насколько вероятно, что ты придешь?",
        kind="single_select",
        options=[
            "Точно приду",
            "Скорее приду",
            "Пока не уверен(а)",
            "Другое",
        ],
        default_visibility="organizers_only",
        privacy_configurable=True,
    ),
    QuestionSpec(
        code="preferred_activities",
        label="Что интересно на первой встрече",
        prompt="Что тебе было бы интереснее на первой встрече?",
        kind="multi_select",
        options=[
            "Просто пообщаться",
            "Поесть вместе",
            "Настольные игры",
            "Прогулка",
            "Мини-игры на знакомство",
            "Обсуждение интересных тем",
            "Кафе",
            "Парк",
            "Антикафе",
            "Спокойное место",
            "Другое",
        ],
        default_visibility="organizers_only",
        privacy_configurable=True,
    ),
    QuestionSpec(
        code="food_restrictions",
        label="Ограничения по еде",
        prompt="Есть ли ограничения по еде?",
        kind="text",
        required=False,
        max_length=200,
        default_visibility="organizers_only",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="place_restrictions",
        label="Ограничения по месту / формату",
        prompt="Есть ли ограничения по месту или формату?",
        kind="textarea",
        required=False,
        max_length=250,
        default_visibility="organizers_only",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="arrival_style",
        label="Когда удобно прийти",
        prompt="Во сколько примерно тебе удобнее прийти?",
        kind="single_select",
        required=False,
        options=[
            "Раньше всех",
            "Вовремя",
            "Могу немного опоздать",
            "Зависит от дня",
            "Другое",
        ],
        default_visibility="organizers_only",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="photo_permission",
        label="Можно ли фотографировать",
        prompt="Можно ли тебя фотографировать на встрече?",
        kind="single_select",
        options=[
            "Да",
            "Лучше сначала спросить",
            "Нет",
            "Другое",
        ],
        default_visibility="organizers_only",
        privacy_configurable=True,
    ),
    QuestionSpec(
        code="heard_about_bot",
        label="Как узнал(а) о боте",
        prompt="Как ты узнал(а) о боте?",
        kind="text",
        required=False,
        max_length=200,
        default_visibility="organizers_only",
        privacy_configurable=False,
    ),
    QuestionSpec(
        code="important_to_know",
        label="Что важно знать заранее",
        prompt="Что бы ты хотел(а), чтобы организаторы знали о тебе заранее?",
        kind="textarea",
        required=False,
        max_length=250,
        default_visibility="organizers_only",
        privacy_configurable=False,
    ),
]


QUESTIONNAIRE_BY_CODE: dict[str, QuestionSpec] = {
    question.code: question for question in QUESTIONNAIRE
}


SKIP_TOKENS = {"-", "пропустить", "skip", "пропуск"}


def get_question_by_code(code: str) -> QuestionSpec:
    return QUESTIONNAIRE_BY_CODE[code]
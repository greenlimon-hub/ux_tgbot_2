import random

from app.games.data import JEFF_CARDS, MATCH_TOPICS, RANDOM_QUESTIONS, TOPIC_SETS


def get_random_question() -> str:
    return random.choice(RANDOM_QUESTIONS)


def get_random_topics() -> list[str]:
    return random.choice(TOPIC_SETS)


def get_random_match_topic() -> str:
    return random.choice(MATCH_TOPICS)


def get_random_jeff_card() -> tuple[int, dict]:
    index = random.randrange(len(JEFF_CARDS))
    return index, JEFF_CARDS[index]


def get_jeff_card_by_index(index: int) -> dict | None:
    if 0 <= index < len(JEFF_CARDS):
        return JEFF_CARDS[index]
    return None
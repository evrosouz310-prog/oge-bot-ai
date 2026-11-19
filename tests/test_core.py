import asyncio
import json
import os
import tempfile

import pytest

from ai_service import AIError, AIService
from data import QUESTIONS, QUESTIONS_BY_ID, THEORY
from database import Database


def test_questions_count():
    assert len(QUESTIONS) >= 20


def test_question_ids_unique():
    assert len(QUESTIONS_BY_ID) == len(QUESTIONS)


def test_question_options_range():
    for q in QUESTIONS:
        assert 2 <= len(q.options) <= 6, f"Вопрос {q.id}: неверное число вариантов"


def test_question_correct_index():
    for q in QUESTIONS:
        assert 0 <= q.correct < len(q.options), f"Вопрос {q.id}: индекс ответа вне диапазона"


def test_question_options_unique():
    for q in QUESTIONS:
        assert len(set(q.options)) == len(q.options), f"Вопрос {q.id}: повторяющиеся варианты"


def test_question_explanation_not_empty():
    for q in QUESTIONS:
        assert q.explanation.strip(), f"Вопрос {q.id}: пустое объяснение"


def test_theory_topics_count():
    assert len(THEORY) == 6


def test_theory_all_have_text():
    for key, topic in THEORY.items():
        assert topic.title.strip(), f"Тема {key}: пустой заголовок"
        assert topic.text.strip(), f"Тема {key}: пустой текст"


def _make_ai() -> AIService:
    return AIService(api_key="test", base_url="http://localhost", model="test")


def test_parse_valid_question():
    ai = _make_ai()
    payload = {
        "question": "Сколько будет 2 + 2?",
        "options": ["1", "2", "3", "4"],
        "correct": 3,
        "explanation": "2 + 2 = 4",
    }
    parsed = ai._parse_question(json.dumps(payload))
    assert parsed["correct"] == 3
    assert len(parsed["options"]) == 4


def test_parse_strips_markdown_fence():
    ai = _make_ai()
    payload = json.dumps({
        "question": "Вопрос?",
        "options": ["A", "B"],
        "correct": 0,
        "explanation": "Объяснение",
    })
    parsed = ai._parse_question(f"```json\n{payload}\n```")
    assert parsed["question"] == "Вопрос?"


def test_parse_rejects_non_json():
    ai = _make_ai()
    with pytest.raises(AIError):
        ai._parse_question("просто текст, а не JSON")


def test_parse_rejects_bad_correct_index():
    ai = _make_ai()
    payload = {
        "question": "Вопрос?",
        "options": ["A", "B"],
        "correct": 5,
        "explanation": "Объяснение",
    }
    with pytest.raises(AIError):
        ai._parse_question(json.dumps(payload))


def test_parse_rejects_duplicate_options():
    ai = _make_ai()
    payload = {
        "question": "Вопрос?",
        "options": ["A", "A", "B"],
        "correct": 0,
        "explanation": "Объяснение",
    }
    with pytest.raises(AIError):
        ai._parse_question(json.dumps(payload))


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_database_progress_roundtrip(db_path):
    async def scenario():
        db = Database(sqlite_path=db_path)
        await db.init()
        try:
            await db.upsert_user(1, "test", "Тест")
            await db.record_answer(1, 1, True)
            await db.record_answer(1, 1, False)
            progress = await db.get_progress(1)
            assert progress[1]["attempts"] == 2
            assert progress[1]["correct"] == 1
            assert progress[1]["last_correct"] == 0
            wrong = await db.get_wrong_ids(1)
            assert 1 in wrong
            solved = await db.get_solved_ids(1)
            assert 1 not in solved
        finally:
            await db.close()
    asyncio.run(scenario())

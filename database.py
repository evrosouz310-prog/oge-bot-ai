"""
database.py — хранение пользователей и прогресса.

По умолчанию используется SQLite (файл создаётся автоматически).
Если задана переменная DATABASE_URL — используется PostgreSQL (asyncpg).

ВАЖНО про бесплатный Render: файловая система там «временная», и файл SQLite
стирается при каждом перезапуске/деплое. Для постоянного хранения прогресса
подключите бесплатную PostgreSQL (например, Neon.tech) через DATABASE_URL.

Все SQL-запросы написаны переносимо (работают и в SQLite, и в PostgreSQL).
Параметры обозначаются «?», для PostgreSQL они автоматически заменяются на $1, $2…
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import aiosqlite

try:
    import asyncpg
except ImportError:  # asyncpg нужен только для PostgreSQL
    asyncpg = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

# Схема: две таблицы. Создаётся автоматически при первом запуске (IF NOT EXISTS).
SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id      BIGINT PRIMARY KEY,
        username     TEXT,
        first_name   TEXT,
        ai_requests  INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS progress (
        user_id        BIGINT  NOT NULL,
        question_id    INTEGER NOT NULL,
        attempts       INTEGER NOT NULL DEFAULT 0,  -- сколько раз отвечал
        correct_count  INTEGER NOT NULL DEFAULT 0,  -- сколько из них верно
        last_correct   INTEGER NOT NULL DEFAULT 0,  -- 1, если последний ответ верный
        updated_at     TEXT NOT NULL,
        PRIMARY KEY (user_id, question_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_usage (
        user_id BIGINT  NOT NULL,
        day     TEXT    NOT NULL,  -- дата в формате ГГГГ-ММ-ДД (UTC)
        count   INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, day)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_cache (
        prompt_hash TEXT PRIMARY KEY,
        answer      TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_pg(query: str) -> str:
    """Заменить плейсхолдеры «?» на $1, $2, … (формат PostgreSQL)."""
    out: list[str] = []
    n = 0
    for ch in query:
        if ch == "?":
            n += 1
            out.append(f"${n}")
        else:
            out.append(ch)
    return "".join(out)


class Database:
    """Тонкая асинхронная обёртка над SQLite или PostgreSQL."""

    def __init__(self, sqlite_path: str, database_url: str = "") -> None:
        self._sqlite_path = sqlite_path
        self._database_url = database_url
        self._conn: aiosqlite.Connection | None = None
        self._pool: Any = None  # asyncpg.Pool

    # ------------------------------------------------------------------ служебное

    @property
    def backend(self) -> str:
        return "PostgreSQL" if self._database_url else "SQLite"

    async def init(self) -> None:
        """Открыть соединение и создать таблицы, если их ещё нет."""
        if self._database_url:
            if asyncpg is None:
                raise RuntimeError("Для DATABASE_URL нужна библиотека asyncpg (см. requirements.txt).")
            self._pool = await asyncpg.create_pool(
                dsn=self._database_url,
                min_size=1,
                max_size=5,
                command_timeout=30,
                statement_cache_size=0,  # совместимость с пулерами соединений (Neon/pgbouncer)
            )
        else:
            folder = os.path.dirname(self._sqlite_path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            self._conn = await aiosqlite.connect(self._sqlite_path)

        for statement in SCHEMA:
            await self._execute(statement)
        log.info("База данных готова (%s).", self.backend)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _execute(self, query: str, params: tuple = ()) -> None:
        if self._pool is not None:
            await self._pool.execute(_to_pg(query), *params)
        elif self._conn is not None:
            await self._conn.execute(query, params)
            await self._conn.commit()
        else:
            raise RuntimeError("База данных не инициализирована (вызовите init()).")

    async def _fetchall(self, query: str, params: tuple = ()) -> list[tuple]:
        if self._pool is not None:
            rows = await self._pool.fetch(_to_pg(query), *params)
            return [tuple(r) for r in rows]
        if self._conn is not None:
            async with self._conn.execute(query, params) as cursor:
                return [tuple(r) for r in await cursor.fetchall()]
        raise RuntimeError("База данных не инициализирована (вызовите init()).")

    # ------------------------------------------------------------------ пользователи

    async def upsert_user(self, user_id: int, username: str | None, first_name: str | None) -> None:
        """Создать пользователя или обновить его имя."""
        await self._execute(
            """
            INSERT INTO users (user_id, username, first_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name
            """,
            (user_id, username, first_name, _now()),
        )

    async def increment_ai_requests(self, user_id: int) -> None:
        """Увеличить счётчик вопросов к нейросети."""
        await self._execute(
            "UPDATE users SET ai_requests = ai_requests + 1 WHERE user_id = ?", (user_id,)
        )

    # ------------------------------------------------------------------ лимиты и кэш ИИ

    async def get_ai_used(self, user_id: int, day: str) -> int:
        """Сколько запросов к нейросети пользователь сделал за указанный день."""
        rows = await self._fetchall(
            "SELECT count FROM ai_usage WHERE user_id = ? AND day = ?", (user_id, day)
        )
        return int(rows[0][0]) if rows else 0

    async def increment_ai_used(self, user_id: int, day: str) -> None:
        """Увеличить дневной счётчик запросов к нейросети."""
        await self._execute(
            """
            INSERT INTO ai_usage (user_id, day, count)
            VALUES (?, ?, 1)
            ON CONFLICT (user_id, day) DO UPDATE SET count = ai_usage.count + 1
            """,
            (user_id, day),
        )

    async def get_cached_answer(self, prompt_hash: str, max_age_hours: int = 168) -> str | None:
        """Вернуть сохранённый ответ нейросети, если он не старше max_age_hours."""
        rows = await self._fetchall(
            "SELECT answer, created_at FROM ai_cache WHERE prompt_hash = ?", (prompt_hash,)
        )
        if not rows:
            return None
        answer, created_at = rows[0]
        try:
            created = datetime.fromisoformat(str(created_at))
        except ValueError:
            return None
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        if age_hours > max_age_hours:
            await self._execute("DELETE FROM ai_cache WHERE prompt_hash = ?", (prompt_hash,))
            return None
        return str(answer)

    async def save_cached_answer(self, prompt_hash: str, answer: str) -> None:
        """Сохранить ответ нейросети в кэш."""
        await self._execute(
            """
            INSERT INTO ai_cache (prompt_hash, answer, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT (prompt_hash) DO UPDATE SET
                answer     = excluded.answer,
                created_at = excluded.created_at
            """,
            (prompt_hash, answer, _now()),
        )

    # ------------------------------------------------------------------ прогресс

    async def record_answer(self, user_id: int, question_id: int, is_correct: bool) -> None:
        """Записать ответ пользователя на вопрос (с накоплением статистики)."""
        flag = 1 if is_correct else 0
        await self._execute(
            """
            INSERT INTO progress (user_id, question_id, attempts, correct_count, last_correct, updated_at)
            VALUES (?, ?, 1, ?, ?, ?)
            ON CONFLICT (user_id, question_id) DO UPDATE SET
                attempts      = progress.attempts + 1,
                correct_count = progress.correct_count + excluded.correct_count,
                last_correct  = excluded.last_correct,
                updated_at    = excluded.updated_at
            """,
            (user_id, question_id, flag, flag, _now()),
        )

    async def get_solved_ids(self, user_id: int) -> set[int]:
        """Номера вопросов, на которые пользователь в последний раз ответил верно."""
        rows = await self._fetchall(
            "SELECT question_id FROM progress WHERE user_id = ? AND last_correct = 1", (user_id,)
        )
        return {int(r[0]) for r in rows}

    async def get_wrong_ids(self, user_id: int) -> set[int]:
        """Номера вопросов, на которые пользователь последний раз ответил неверно."""
        rows = await self._fetchall(
            """
            SELECT question_id FROM progress
            WHERE user_id = ? AND last_correct = 0 AND attempts > 0
            """,
            (user_id,),
        )
        return {int(r[0]) for r in rows}

    async def get_progress(self, user_id: int) -> dict[int, dict[str, int]]:
        """Детальный прогресс по каждому вопросу."""
        rows = await self._fetchall(
            """
            SELECT question_id, attempts, correct_count, last_correct
            FROM progress WHERE user_id = ?
            """,
            (user_id,),
        )
        return {
            int(r[0]): {
                "attempts": int(r[1]),
                "correct": int(r[2]),
                "last_correct": int(r[3]),
            }
            for r in rows
        }

    async def get_stats(self, user_id: int) -> dict[str, int]:
        """Сводная статистика пользователя."""
        rows = await self._fetchall(
            """
            SELECT COALESCE(SUM(attempts), 0),
                   COALESCE(SUM(correct_count), 0),
                   COALESCE(SUM(last_correct), 0),
                   COUNT(*)
            FROM progress WHERE user_id = ?
            """,
            (user_id,),
        )
        attempts, correct, solved, seen = (int(x) for x in rows[0])
        ai_rows = await self._fetchall("SELECT ai_requests FROM users WHERE user_id = ?", (user_id,))
        ai_requests = int(ai_rows[0][0]) if ai_rows else 0
        return {
            "attempts": attempts,
            "correct": correct,
            "solved": solved,
            "seen": seen,
            "ai_requests": ai_requests,
        }

    async def reset_progress(self, user_id: int) -> None:
        """Стереть прогресс пользователя по тестам."""
        await self._execute("DELETE FROM progress WHERE user_id = ?", (user_id,))

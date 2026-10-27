"""独立连接和显式事务，保证容量检查与写入原子执行。"""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 100),
    club_name TEXT NOT NULL CHECK(length(trim(club_name)) BETWEEN 1 AND 100),
    category TEXT NOT NULL CHECK(category IN ('学术科技', '文艺体育', '志愿公益', '实践交流', '其他')),
    location TEXT NOT NULL CHECK(length(trim(location)) BETWEEN 1 AND 200),
    description TEXT NOT NULL CHECK(length(trim(description)) BETWEEN 1 AND 5000),
    capacity INTEGER NOT NULL CHECK(typeof(capacity) = 'integer' AND capacity BETWEEN 1 AND 100000),
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    registration_deadline TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(ends_at > starts_at),
    CHECK(registration_deadline <= starts_at)
);
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 50),
    student_id TEXT NOT NULL CHECK(length(student_id) BETWEEN 1 AND 32),
    contact TEXT NOT NULL CHECK(length(trim(contact)) BETWEEN 1 AND 100),
    created_at TEXT NOT NULL,
    UNIQUE(activity_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_activities_category_start ON activities(category, starts_at, id);
CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(starts_at, id);
"""


class Database:
    def __init__(self, path: str | Path):
        if str(path) == ":memory:":
            raise ValueError("请使用文件数据库；每次请求使用独立连接。")
        self.path = Path(path).resolve()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def transaction(self, *, write: bool = False):
        with self.connect() as connection:
            # 读事务保证列表总数、统计与明细来自同一快照。
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield connection
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

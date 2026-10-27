"""业务层：数据库是真实数据的唯一来源。"""

from datetime import datetime, timezone
import sqlite3

from .db import Database
from .errors import BusinessError
from .schemas import ActivityInput, Category, RegistrationInput

ACTIVITY_SELECT = """
SELECT a.*, (SELECT COUNT(*) FROM registrations r WHERE r.activity_id = a.id) AS registration_count
FROM activities a
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    # 固定精度及 UTC 偏移量，使 SQLite 文本时间比较与真实时间顺序一致。
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def activity_values(data: ActivityInput) -> dict:
    result = data.model_dump()
    result["category"] = data.category.value
    for field in ("starts_at", "ends_at", "registration_deadline"):
        result[field] = timestamp(result[field])
    return result


def require_activity(connection, activity_id: int):
    row = connection.execute(ACTIVITY_SELECT + " WHERE a.id = ?", (activity_id,)).fetchone()
    if row is None:
        raise BusinessError(404, "ACTIVITY_NOT_FOUND", "活动不存在。")
    return row


def activity_view(row) -> dict:
    result = dict(row)
    now = utc_now()
    result["remaining_capacity"] = result["capacity"] - result["registration_count"]
    if now >= datetime.fromisoformat(row["registration_deadline"]) or now >= datetime.fromisoformat(row["starts_at"]):
        result["registration_status"] = "closed"
    elif result["remaining_capacity"] == 0:
        result["registration_status"] = "full"
    else:
        result["registration_status"] = "open"
    return result


class ActivityService:
    def __init__(self, database: Database):
        self.database = database

    def list_activities(self, q: str | None, category: Category | None, page: int, page_size: int):
        conditions, parameters = [], []
        if q:
            # 将 %、_ 作为普通字符搜索；所有用户值均通过参数绑定。
            pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            conditions.append("(a.title LIKE ? ESCAPE '\\' OR a.club_name LIKE ? ESCAPE '\\' OR a.description LIKE ? ESCAPE '\\')")
            parameters.extend([pattern] * 3)
        if category is not None:
            conditions.append("a.category = ?")
            parameters.append(category.value)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self.database.transaction() as connection:
            total = connection.execute("SELECT COUNT(*) FROM activities a" + where, parameters).fetchone()[0]
            rows = connection.execute(
                ACTIVITY_SELECT + where + " ORDER BY a.starts_at ASC, a.id ASC LIMIT ? OFFSET ?",
                [*parameters, page_size, (page - 1) * page_size],
            ).fetchall()
        return {"items": [activity_view(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    def get_activity(self, activity_id: int):
        with self.database.connect() as connection:
            return activity_view(require_activity(connection, activity_id))

    def create_activity(self, data: ActivityInput):
        values = activity_values(data)
        values["created_at"] = values["updated_at"] = timestamp(utc_now())
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute("""
                INSERT INTO activities(title, club_name, category, location, description, capacity,
                    starts_at, ends_at, registration_deadline, created_at, updated_at)
                VALUES (:title, :club_name, :category, :location, :description, :capacity,
                    :starts_at, :ends_at, :registration_deadline, :created_at, :updated_at)
            """, values)
            return activity_view(require_activity(connection, cursor.lastrowid))

    def update_activity(self, activity_id: int, data: ActivityInput):
        with self.database.transaction(write=True) as connection:
            current = require_activity(connection, activity_id)
            if data.capacity < current["registration_count"]:
                raise BusinessError(409, "CAPACITY_BELOW_REGISTRATIONS", "容量不能小于当前报名人数。")
            values = activity_values(data)
            values.update(id=activity_id, updated_at=timestamp(utc_now()))
            connection.execute("""
                UPDATE activities SET title=:title, club_name=:club_name, category=:category,
                    location=:location, description=:description, capacity=:capacity,
                    starts_at=:starts_at, ends_at=:ends_at, registration_deadline=:registration_deadline,
                    updated_at=:updated_at WHERE id=:id
            """, values)
            return activity_view(require_activity(connection, activity_id))

    def delete_activity(self, activity_id: int):
        with self.database.transaction(write=True) as connection:
            require_activity(connection, activity_id)
            connection.execute("DELETE FROM activities WHERE id = ?", (activity_id,))

    def register(self, activity_id: int, data: RegistrationInput):
        with self.database.transaction(write=True) as connection:
            activity = require_activity(connection, activity_id)
            duplicate = connection.execute(
                "SELECT 1 FROM registrations WHERE activity_id = ? AND student_id = ?",
                (activity_id, data.student_id),
            ).fetchone()
            if duplicate:
                raise BusinessError(409, "ALREADY_REGISTERED", "该学号已报名此活动。")
            now = utc_now()
            if now >= datetime.fromisoformat(activity["registration_deadline"]) or now >= datetime.fromisoformat(activity["starts_at"]):
                raise BusinessError(409, "REGISTRATION_CLOSED", "活动已开始或报名已截止。")
            if activity["registration_count"] >= activity["capacity"]:
                raise BusinessError(409, "ACTIVITY_FULL", "活动报名名额已满。")
            try:
                cursor = connection.execute("""
                    INSERT INTO registrations(activity_id, name, student_id, contact, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (activity_id, data.name, data.student_id, data.contact, timestamp(now)))
            except sqlite3.IntegrityError as exc:
                if exc.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE":
                    raise BusinessError(409, "ALREADY_REGISTERED", "该学号已报名此活动。") from exc
                raise
            return dict(connection.execute("SELECT * FROM registrations WHERE id = ?", (cursor.lastrowid,)).fetchone())

    def list_registrations(self, activity_id: int, page: int, page_size: int):
        with self.database.transaction() as connection:
            activity = require_activity(connection, activity_id)
            rows = connection.execute(
                "SELECT * FROM registrations WHERE activity_id = ? ORDER BY id ASC LIMIT ? OFFSET ?",
                (activity_id, page_size, (page - 1) * page_size),
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": activity["registration_count"], "page": page, "page_size": page_size}

    def stats(self):
        with self.database.transaction() as connection:
            counts = connection.execute("SELECT COUNT(*), COUNT(DISTINCT student_id) FROM registrations").fetchone()
            rows = connection.execute(ACTIVITY_SELECT + " ORDER BY a.id ASC").fetchall()
        return {
            "activity_count": len(rows),
            "registration_count": counts[0],
            "unique_student_count": counts[1],
            "activities": [
                {"activity_id": row["id"], "title": row["title"], "capacity": row["capacity"],
                 "registration_count": row["registration_count"],
                 "remaining_capacity": row["capacity"] - row["registration_count"]}
                for row in rows
            ],
        }

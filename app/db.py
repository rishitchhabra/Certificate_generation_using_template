import sqlite3
import time

from . import config


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS certificate_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    template_path TEXT,
    template_type TEXT,
    name_position TEXT,
    name_font_size REAL,
    name_font TEXT,
    name_color TEXT,
    created_at TEXT,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_set_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (certificate_set_id) REFERENCES certificate_sets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    created_at TEXT
);
"""


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        # Lightweight migration for databases created before template_type existed.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(certificate_sets)").fetchall()]
        if "template_type" not in cols:
            conn.execute("ALTER TABLE certificate_sets ADD COLUMN template_type TEXT")
        if "name_color" not in cols:
            conn.execute("ALTER TABLE certificate_sets ADD COLUMN name_color TEXT DEFAULT '#000000'")
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return str(int(time.time()))


def find_or_create_school(name: str) -> int:
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM schools WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO schools (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def create_set(school_id, name, template_path, template_type, position, font_size, font, color="#000000"):
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO certificate_sets
               (school_id, name, template_path, template_type, name_position, name_font_size, name_font, name_color, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (school_id, name, template_path, template_type, position, font_size, font, color, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_set(set_id, school_id, name, template_path, template_type, position, font_size, font, color="#000000"):
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE certificate_sets
               SET school_id = ?, name = ?, template_path = ?, template_type = ?, name_position = ?,
                   name_font_size = ?, name_font = ?, name_color = ?
               WHERE id = ?""",
            (school_id, name, template_path, template_type, position, font_size, font, color, set_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_set(set_id):
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT s.*, sc.name AS school_name
               FROM certificate_sets s
               JOIN schools sc ON sc.id = s.school_id
               WHERE s.id = ?""",
            (set_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_sets():
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT s.id, s.name, s.created_at, sc.name AS school_name,
                      (SELECT COUNT(*) FROM students st WHERE st.certificate_set_id = s.id) AS student_count
               FROM certificate_sets s
               JOIN schools sc ON sc.id = s.school_id
               ORDER BY sc.name, s.created_at"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def replace_students(set_id, names):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM students WHERE certificate_set_id = ?", (set_id,))
        conn.executemany(
            "INSERT INTO students (certificate_set_id, name) VALUES (?, ?)",
            [(set_id, n) for n in names],
        )
        conn.commit()
    finally:
        conn.close()


def count_students(set_id) -> int:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM students WHERE certificate_set_id = ?", (set_id,)
        ).fetchone()["c"]
    finally:
        conn.close()


def delete_set(set_id):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT school_id FROM certificate_sets WHERE id = ?", (set_id,)
        ).fetchone()
        conn.execute("DELETE FROM certificate_sets WHERE id = ?", (set_id,))
        if row:
            sid = row["school_id"]
            remaining = conn.execute(
                "SELECT COUNT(*) AS c FROM certificate_sets WHERE school_id = ?", (sid,)
            ).fetchone()["c"]
            if remaining == 0:
                conn.execute("DELETE FROM schools WHERE id = ?", (sid,))
        conn.commit()
    finally:
        conn.close()


def list_schools():
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT sc.id, sc.name,
                      (SELECT COUNT(*) FROM certificate_sets s WHERE s.school_id = sc.id) AS certificate_count
               FROM schools sc
               WHERE EXISTS (SELECT 1 FROM certificate_sets s WHERE s.school_id = sc.id)
               ORDER BY sc.name"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def school_certificates(school_id):
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, name FROM certificate_sets WHERE school_id = ? ORDER BY name""",
            (school_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def certificate_students(set_id):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name FROM students WHERE certificate_set_id = ? ORDER BY name",
            (set_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_student(set_id, student_id):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, name FROM students WHERE id = ? AND certificate_set_id = ?",
            (student_id, set_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_session(username: str) -> str:
    import secrets

    token = secrets.token_hex(32)
    conn = get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE username = ?", (username,))
        conn.execute(
            "INSERT INTO sessions (token, username, created_at) VALUES (?, ?, ?)",
            (token, username, _now()),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def session_username(token: str):
    if not token:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT username FROM sessions WHERE token = ?", (token,)
        ).fetchone()
        return row["username"] if row else None
    finally:
        conn.close()


def delete_session(token: str):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()

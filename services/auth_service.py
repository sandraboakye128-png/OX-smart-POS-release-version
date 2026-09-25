from database.db import (
    get_auth_connection, return_auth_connection,
    get_connection, return_connection,
    USE_POSTGRES,
)
import hashlib
from datetime import datetime

# ----------------------------------------------------------------
# Placeholder shim: we write queries with "?" and translate to "%s"
# when running on Postgres. This lets one file work on both backends.
# ----------------------------------------------------------------
P = "%s" if USE_POSTGRES else "?"

def _q(sql: str) -> str:
    return sql.replace("?", P) if USE_POSTGRES else sql


# ---------------- HASH PASSWORD ----------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------- LOG USER ACTION ----------------
def log_user_action(user_id, username, action, ip_address=None, user_agent=None):
    conn = get_auth_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(_q("""
            INSERT INTO user_logs (user_id, username, action, ip_address, user_agent, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """), (user_id, username, action, ip_address, user_agent, datetime.now()))
        conn.commit()
    except Exception as e:
        # Non-fatal: user_logs may be missing on very old DBs
        print(f"⚠️ Could not log user action: {e}")
    finally:
        return_auth_connection(conn)


# ---------------- CREATE USER ----------------
def create_user(username: str, password: str, role: str = "user") -> bool:
    conn = get_auth_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            _q("INSERT INTO users (username, password, role) VALUES (?, ?, ?)"),
            (username, hash_password(password), role)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Create user error: {e}")
        return False
    finally:
        return_auth_connection(conn)


# ---------------- LOGIN USER ----------------
def login_user(username: str, password: str, ip_address=None, user_agent=None):
    conn = get_auth_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            _q("SELECT id, username, role, password FROM users WHERE LOWER(username) = LOWER(?)"),
            (username,)
        )
        row = cursor.fetchone()
        if row and row[3] == hash_password(password):
            user = {"id": row[0], "username": row[1], "role": row[2]}
            log_user_action(row[0], row[1], 'login', ip_address, user_agent)
            return user
        if row:
            log_user_action(row[0], row[1], 'login_failed', ip_address, user_agent)
        return None
    finally:
        return_auth_connection(conn)


# ---------------- LOGOUT USER ----------------
def logout_user(user_id, username, ip_address=None, user_agent=None):
    log_user_action(user_id, username, 'logout', ip_address, user_agent)


# ---------------- GET USER LOGS ----------------
def get_user_logs(user_id=None, limit=100, offset=0, action_filter=None):
    conn = get_auth_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT ul.id, ul.user_id, ul.username, ul.action,
                   ul.ip_address, ul.user_agent, ul.timestamp
            FROM user_logs ul
        """
        conditions, params = [], []
        if user_id:
            conditions.append("ul.user_id = ?"); params.append(user_id)
        if action_filter:
            conditions.append("ul.action = ?"); params.append(action_filter)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY ul.timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(_q(query), params)
        rows = cursor.fetchall()
        return [
            {
                "id": r[0], "user_id": r[1], "username": r[2], "action": r[3],
                "ip_address": r[4], "user_agent": r[5],
                "timestamp": r[6].isoformat() if r[6] else None
            }
            for r in rows
        ]
    finally:
        return_auth_connection(conn)


# ---------------- ADMIN CHECKS ----------------
def admin_exists() -> bool:
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1")
        return cur.fetchone() is not None
    finally:
        return_auth_connection(conn)


def count_admins() -> int:
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        return cur.fetchone()[0]
    finally:
        return_auth_connection(conn)


# ---------------- GET ALL USERS ----------------
def get_all_users():
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at DESC")
        return [
            {"id": r[0], "username": r[1], "role": r[2], "created_at": r[3]}
            for r in cur.fetchall()
        ]
    finally:
        return_auth_connection(conn)


# ---------------- GET USER BY ID ----------------
def get_user_by_id(user_id: int):
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("SELECT id, username, role, created_at FROM users WHERE id = ?"), (user_id,))
        row = cur.fetchone()
        if row:
            return {"id": row[0], "username": row[1], "role": row[2], "created_at": row[3]}
        return None
    finally:
        return_auth_connection(conn)


# ---------------- UPDATE ROLE ----------------
def update_user_role(user_id: int, new_role: str) -> bool:
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("UPDATE users SET role = ? WHERE id = ?"), (new_role, user_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback(); print(f"Error updating user role: {e}"); return False
    finally:
        return_auth_connection(conn)


# ---------------- UPDATE PASSWORD ----------------
def update_user_password(user_id: int, new_password: str) -> bool:
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("UPDATE users SET password = ? WHERE id = ?"),
                    (hash_password(new_password), user_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback(); print(f"Error updating password: {e}"); return False
    finally:
        return_auth_connection(conn)


# ---------------- DELETE USER ----------------
def delete_user(user_id: int):
    """Delete a user. Checks sales on retail.db, then deletes on auth.db."""
    # Step A: sales dependency check on retail.db
    rconn = get_connection()
    try:
        rcur = rconn.cursor()
        rcur.execute(_q("SELECT COUNT(*) FROM sales WHERE user_id = ?"), (user_id,))
        sales_count = rcur.fetchone()[0]
        if sales_count > 0:
            return {
                "success": False,
                "error": f"Cannot delete user. They have {sales_count} sale(s) associated. "
                         "Please reassign or delete those records first."
            }
    finally:
        return_connection(rconn)

    # Step B: delete user-related rows on auth.db
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        # user_settings may not exist; ignore silently
        try:
            cur.execute(_q("DELETE FROM user_settings WHERE user_id = ?"), (user_id,))
        except Exception:
            pass
        # user_logs should exist after our AUTH_SCHEMA
        try:
            cur.execute(_q("DELETE FROM user_logs WHERE user_id = ?"), (user_id,))
        except Exception:
            pass
        cur.execute(_q("DELETE FROM users WHERE id = ?"), (user_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        return_auth_connection(conn)


# ---------------- CHANGE PASSWORD (Self) ----------------
def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("SELECT password FROM users WHERE id = ?"), (user_id,))
        row = cur.fetchone()
        if not row or row[0] != hash_password(old_password):
            return False
        cur.execute(_q("UPDATE users SET password = ? WHERE id = ?"),
                    (hash_password(new_password), user_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback(); print(f"Error changing password: {e}"); return False
    finally:
        return_auth_connection(conn)


# ---------------- IS PROTECTED USER ----------------
def is_protected_user(user_id: int) -> bool:
    conn = get_auth_connection()
    try:
        cur = conn.cursor()
        cur.execute(_q("SELECT username FROM users WHERE id = ?"), (user_id,))
        row = cur.fetchone()
        return bool(row and row[0].lower() == 'oxbee')
    finally:
        return_auth_connection(conn)
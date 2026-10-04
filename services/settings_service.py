# services/settings_service.py
"""
User settings service.

- Creates user_settings table on first run (SQLite + PostgreSQL aware).
- Adds new columns idempotently to existing tables.
- Supports: low_stock_threshold, font_size, font_family.
"""

from database.db import get_connection


# ------------------------------------------------------------
#  Canonical defaults
# ------------------------------------------------------------
DEFAULT_SETTINGS = {
    'theme':               'light',
    'currency_symbol':     '₵',
    'currency_code':       'GHS',
    'language':            'en',
    'date_format':         'DD/MM/YYYY',
    'timezone':            'UTC',
    'low_stock_threshold': 10,
    'font_size':           'medium',
    'font_family':         'system',
}

ALLOWED_FIELDS = list(DEFAULT_SETTINGS.keys())

LOW_STOCK_MIN = 1
LOW_STOCK_MAX = 500

VALID_FONT_SIZES    = {'small', 'medium', 'large', 'xlarge'}
VALID_FONT_FAMILIES = {'system', 'humanist', 'serif', 'mono', 'rounded'}


# ------------------------------------------------------------
#  Backend detection
# ------------------------------------------------------------
def _is_postgres(cur):
    try:
        cur.execute("SELECT version()")
        row = cur.fetchone()
        if row and 'PostgreSQL' in str(row[0]):
            return True
    except Exception:
        pass
    return False


# ------------------------------------------------------------
#  Schema bootstrap — create table if missing, then add columns
# ------------------------------------------------------------
def ensure_settings_table():
    """
    Idempotent:
      1. CREATE TABLE IF NOT EXISTS user_settings
      2. ALTER TABLE ADD COLUMN for any missing newer columns
    Works on SQLite (local dev) and PostgreSQL (Render).
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        is_pg = _is_postgres(cur)

        if is_pg:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id              INTEGER PRIMARY KEY,
                    theme                VARCHAR(20)  DEFAULT 'light',
                    currency_symbol      VARCHAR(10)  DEFAULT '₵',
                    currency_code        VARCHAR(10)  DEFAULT 'GHS',
                    language             VARCHAR(10)  DEFAULT 'en',
                    date_format          VARCHAR(20)  DEFAULT 'DD/MM/YYYY',
                    timezone             VARCHAR(50)  DEFAULT 'UTC',
                    low_stock_threshold  INTEGER      DEFAULT 10,
                    font_size            VARCHAR(20)  DEFAULT 'medium',
                    font_family          VARCHAR(40)  DEFAULT 'system',
                    updated_at           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # SQLite
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id              INTEGER PRIMARY KEY,
                    theme                TEXT DEFAULT 'light',
                    currency_symbol      TEXT DEFAULT '₵',
                    currency_code        TEXT DEFAULT 'GHS',
                    language             TEXT DEFAULT 'en',
                    date_format          TEXT DEFAULT 'DD/MM/YYYY',
                    timezone             TEXT DEFAULT 'UTC',
                    low_stock_threshold  INTEGER DEFAULT 10,
                    font_size            TEXT DEFAULT 'medium',
                    font_family          TEXT DEFAULT 'system',
                    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()

        # Now add any missing columns (for tables that existed before this upgrade)
        cols = set()
        if is_pg:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'user_settings'
            """)
            cols = {r[0].lower() for r in cur.fetchall()}
        else:
            cur.execute("PRAGMA table_info(user_settings)")
            cols = {r[1].lower() for r in cur.fetchall()}

        additions = [
            ('low_stock_threshold', 'INTEGER DEFAULT 10'),
            ('font_size',           "TEXT DEFAULT 'medium'" if not is_pg else "VARCHAR(20) DEFAULT 'medium'"),
            ('font_family',         "TEXT DEFAULT 'system'" if not is_pg else "VARCHAR(40) DEFAULT 'system'"),
        ]
        added = []
        for col_name, col_type in additions:
            if col_name.lower() not in cols:
                cur.execute(f"ALTER TABLE user_settings ADD COLUMN {col_name} {col_type}")
                added.append(col_name)
        if added:
            conn.commit()
            print(f"✅ user_settings columns added: {', '.join(added)}")
        else:
            print("✅ user_settings table ready.")
    except Exception as e:
        print(f"⚠️ ensure_settings_table failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


# Run at import time — same pattern as init_import_jobs_table / init_claims_table
ensure_settings_table()


# ------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------
def _row_to_dict(row):
    return {
        'theme':               row[0] or DEFAULT_SETTINGS['theme'],
        'currency_symbol':     row[1] or DEFAULT_SETTINGS['currency_symbol'],
        'currency_code':       row[2] or DEFAULT_SETTINGS['currency_code'],
        'language':            row[3] or DEFAULT_SETTINGS['language'],
        'date_format':         row[4] or DEFAULT_SETTINGS['date_format'],
        'timezone':            row[5] or DEFAULT_SETTINGS['timezone'],
        'low_stock_threshold': int(row[6]) if row[6] is not None else DEFAULT_SETTINGS['low_stock_threshold'],
        'font_size':           row[7] or DEFAULT_SETTINGS['font_size'],
        'font_family':         row[8] or DEFAULT_SETTINGS['font_family'],
    }


def _normalize(settings):
    clean = {}
    for key in ALLOWED_FIELDS:
        if key not in settings:
            continue
        val = settings[key]
        if key == 'low_stock_threshold':
            try:
                v = int(val)
            except (TypeError, ValueError):
                continue
            clean[key] = max(LOW_STOCK_MIN, min(LOW_STOCK_MAX, v))
        elif key == 'font_size':
            if val in VALID_FONT_SIZES:
                clean[key] = val
        elif key == 'font_family':
            if val in VALID_FONT_FAMILIES:
                clean[key] = val
        elif key == 'theme':
            if val in ('light', 'dark'):
                clean[key] = val
        else:
            clean[key] = val
    return clean


# ------------------------------------------------------------
#  Public API
# ------------------------------------------------------------
def get_user_settings(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT theme, currency_symbol, currency_code, language,
               date_format, timezone, low_stock_threshold,
               font_size, font_family
        FROM user_settings
        WHERE user_id = %s
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_dict(row)

    create_default_settings(user_id)
    return get_user_settings(user_id)


def create_default_settings(user_id):
    """INSERT OR IGNORE-style defaults. Safe to call multiple times."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 1 FROM user_settings WHERE user_id = %s
        """, (user_id,))
        if cursor.fetchone():
            return

        cursor.execute("""
            INSERT INTO user_settings
                (user_id, theme, currency_symbol, currency_code,
                 language, date_format, timezone,
                 low_stock_threshold, font_size, font_family)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            DEFAULT_SETTINGS['theme'],
            DEFAULT_SETTINGS['currency_symbol'],
            DEFAULT_SETTINGS['currency_code'],
            DEFAULT_SETTINGS['language'],
            DEFAULT_SETTINGS['date_format'],
            DEFAULT_SETTINGS['timezone'],
            DEFAULT_SETTINGS['low_stock_threshold'],
            DEFAULT_SETTINGS['font_size'],
            DEFAULT_SETTINGS['font_family'],
        ))
        conn.commit()
    except Exception as e:
        print(f"⚠️ create_default_settings failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def update_user_settings(user_id, settings):
    clean = _normalize(settings or {})
    if not clean:
        return False

    # Ensure a row exists before UPDATE
    create_default_settings(user_id)

    set_parts = []
    params = []
    for key, value in clean.items():
        set_parts.append(f"{key} = %s")
        params.append(value)

    params.append(user_id)
    query = f"""
        UPDATE user_settings
        SET {', '.join(set_parts)}, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s
    """

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    return True


# ------------------------------------------------------------
#  Getters
# ------------------------------------------------------------
def get_currency_symbol(user_id):  return get_user_settings(user_id).get('currency_symbol', DEFAULT_SETTINGS['currency_symbol'])
def get_currency_code(user_id):    return get_user_settings(user_id).get('currency_code',   DEFAULT_SETTINGS['currency_code'])
def get_theme(user_id):            return get_user_settings(user_id).get('theme',           DEFAULT_SETTINGS['theme'])
def get_date_format(user_id):      return get_user_settings(user_id).get('date_format',     DEFAULT_SETTINGS['date_format'])
def get_language(user_id):         return get_user_settings(user_id).get('language',        DEFAULT_SETTINGS['language'])
def get_font_size(user_id):        return get_user_settings(user_id).get('font_size',       DEFAULT_SETTINGS['font_size'])
def get_font_family(user_id):      return get_user_settings(user_id).get('font_family',     DEFAULT_SETTINGS['font_family'])

def get_low_stock_threshold(user_id):
    try:
        v = int(get_user_settings(user_id).get('low_stock_threshold',
                                              DEFAULT_SETTINGS['low_stock_threshold']))
    except (TypeError, ValueError):
        return DEFAULT_SETTINGS['low_stock_threshold']
    return max(LOW_STOCK_MIN, min(LOW_STOCK_MAX, v))


# ------------------------------------------------------------
#  Formatters
# ------------------------------------------------------------
def format_currency(amount, user_id, symbol=True):
    sym = get_currency_symbol(user_id)
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        amt = 0.0
    return f"{sym}{amt:,.2f}" if symbol else f"{amt:,.2f}"


def format_date(date_obj, user_id):
    if not date_obj:
        return ''
    fmt = get_date_format(user_id)
    mapping = {
        'DD/MM/YYYY': '%d/%m/%Y',
        'MM/DD/YYYY': '%m/%d/%Y',
        'YYYY-MM-DD': '%Y-%m-%d',
        'DD-MM-YYYY': '%d-%m-%Y',
        'MM-DD-YYYY': '%m-%d-%Y',
    }
    return date_obj.strftime(mapping.get(fmt, '%d/%m/%Y'))
import os
import re
import sqlite3
import time
from contextlib import contextmanager

# ---------- Optional Postgres imports (Render only) ----------
try:
    import psycopg2
    from psycopg2 import pool
except ImportError:
    psycopg2 = None
    pool = None

# ---------- Ensure folders exist ----------
DB_DIR = "database"
RECEIPTS_DIR = "receipts"
REPORTS_DIR = "reports"

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(RECEIPTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# ---------- DATABASE PATHS (for SQLite) ----------
DB_PATH = os.path.join(DB_DIR, "retail.db")
AUTH_DB_PATH = os.path.join(DB_DIR, "auth.db")

# ---------- Check if we are on Render (PostgreSQL) ----------
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None and psycopg2 is not None

# ---------- Connection Pool (for PostgreSQL) ----------
connection_pool = None
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# ==================================================================
# SQLite placeholder & syntax shim
# ------------------------------------------------------------------
# The services layer was originally written for Postgres and uses
#     %s          (positional placeholders)
#     :name       (named placeholders)
#     ::type      (type casts — ::date, ::numeric(10,2), ::text[], ...)
# SQLite understands only ? and has no :: cast operator.
#
# Rather than editing every service file, we wrap the SQLite
# connection + cursor so anything Postgres-flavored in the SQL string
# is rewritten before hitting the driver.
#
# The Postgres path is untouched — the shim is only applied in the
# SQLite branch of get_connection() / get_auth_connection().
#
# Known limitation: a literal '%s', ':name', or '::type' inside a SQL
# string literal (rare) would also be rewritten. If you ever need
# that, write the query with ? directly.
# ==================================================================
_PARAM_RE = re.compile(r'%s')
_NAMED_RE = re.compile(r'(?<![:%\w]):([a-zA-Z_][a-zA-Z0-9_]*)')
_CAST_RE  = re.compile(
    r'::[a-zA-Z_][a-zA-Z0-9_]*'              # ::text, ::date, ::numeric
    r'(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?'  # (50) or (10,2)
    r'(?:\s*\[\s*\])?'                        # [] for array types
)


def _rewrite(sql, params):
    """
    Rewrite Postgres-flavored SQL for SQLite.

      1) strip ::type casts        (::date, ::numeric(10,2), ::text[])
      2) %s     -> ?               (positional, tuple/list params)
      3) :name  -> ?               (named, dict params -> ordered list)

    Returns (sql, params).
    """
    if not isinstance(sql, str):
        return sql, params

    # 1) Strip Postgres casts first — they have no SQLite equivalent
    sql = _CAST_RE.sub('', sql)

    # 2) Named-placeholder style: dict params
    if isinstance(params, dict):
        order = []

        def repl(m):
            order.append(m.group(1))
            return '?'

        sql = _NAMED_RE.sub(repl, sql)
        try:
            new_params = [params[n] for n in order]
        except KeyError:
            # Caller passed a dict missing a key. Let sqlite raise a
            # clearer error by passing the original params through.
            return sql, params
        return sql, new_params

    # 3) Positional style (default)
    sql = _PARAM_RE.sub('?', sql)
    return sql, params


# ------------------------------------------------------------------
# Postgres SQL aggregate shims for SQLite
# ------------------------------------------------------------------
# Register SQLite emulations of Postgres-only aggregates so service
# queries written for Postgres don't crash on the local SQLite DB.
#
# Emulated:
#   array_agg(x)      -> comma-joined string of non-NULL x values
#   string_agg(x)     -> same (2-arg form still works via comma fallback)
#   json_agg(x)       -> JSON array string of non-NULL x values
# ------------------------------------------------------------------

class _ArrayAgg:
    """Emulates Postgres array_agg with a comma-joined string."""
    def __init__(self):
        self.items = []

    def step(self, value):
        if value is not None:
            self.items.append(value)

    def finalize(self):
        return ','.join(str(x) for x in self.items)


class _JsonAgg:
    """Emulates Postgres json_agg with a JSON array string."""
    def __init__(self):
        self.items = []

    def step(self, value):
        if value is not None:
            self.items.append(value)

    def finalize(self):
        import json
        return json.dumps(self.items)


def _register_sqlite_functions(conn):
    """Register SQLite implementations of Postgres-only aggregates."""
    try:
        conn.create_aggregate('array_agg',  1, _ArrayAgg)
        conn.create_aggregate('json_agg',   1, _JsonAgg)
        conn.create_aggregate('string_agg', 1, _ArrayAgg)
    except Exception as e:
        print(f"⚠️ Could not register SQLite function shims: {e}")


class _SQLiteShimCursor:
    """Wraps sqlite3.Cursor to rewrite Postgres-isms -> SQLite."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        sql, params = _rewrite(sql, params)
        if params is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        if isinstance(sql, str):
            sql = _CAST_RE.sub('', sql)
            sql = _PARAM_RE.sub('?', sql)
        return self._cursor.executemany(sql, seq_of_params)

    def executescript(self, sql):
        return self._cursor.executescript(sql)

    def __getattr__(self, name):
        # fetchone / fetchall / fetchmany / rowcount / lastrowid / description ...
        return getattr(self._cursor, name)

    def __iter__(self):
        return iter(self._cursor)


class _SQLiteShimConnection:
    """Wraps sqlite3.Connection so .cursor() and .execute() both shim."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _SQLiteShimCursor(self._conn.cursor())

    def execute(self, sql, params=None):
        sql, params = _rewrite(sql, params)
        if params is None:
            return self._conn.execute(sql)
        return self._conn.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        if isinstance(sql, str):
            sql = _CAST_RE.sub('', sql)
            sql = _PARAM_RE.sub('?', sql)
        return self._conn.executemany(sql, seq_of_params)

    def executescript(self, sql):
        return self._conn.executescript(sql)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        # row_factory, in_transaction, isolation_level, etc.
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._conn.__exit__(exc_type, exc, tb)


if USE_POSTGRES:
    print("Using PostgreSQL (Supabase) with connection pooling")

    # Ensure SSL is required
    if "sslmode" not in DATABASE_URL:
        if "?" in DATABASE_URL:
            DATABASE_URL += "&sslmode=require"
        else:
            DATABASE_URL += "?sslmode=require"

    # Add timeout and keepalive parameters
    if "connect_timeout" not in DATABASE_URL:
        DATABASE_URL += "&connect_timeout=10"

    print("PostgreSQL URL configured (SSL required)")

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        brand TEXT,
        cost_price REAL,
        selling_price REAL,
        stock INTEGER,
        category TEXT,
        discount REAL DEFAULT 0,
        base_unit TEXT DEFAULT 'piece'
    );

    CREATE TABLE IF NOT EXISTS sales (
        id SERIAL PRIMARY KEY,
        subtotal REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        total REAL,
        profit REAL,
        date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        payment_method VARCHAR(50) DEFAULT 'cash',
        cheque_number VARCHAR(100),
        user_id INTEGER REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS deleted_products (
        id SERIAL PRIMARY KEY,
        name TEXT,
        brand TEXT,
        cost_price REAL,
        selling_price REAL,
        stock INTEGER,
        category TEXT,
        discount REAL DEFAULT 0,
        action TEXT DEFAULT 'deleted',
        source TEXT DEFAULT 'product',
        deleted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        batch_id INTEGER,
        batch_quantity INTEGER,
        batch_remaining INTEGER,
        product_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS purchases (
        id SERIAL PRIMARY KEY,
        product_name TEXT NOT NULL,
        brand TEXT,
        category TEXT,
        quantity INTEGER,
        cost_price REAL,
        discount REAL DEFAULT 0,
        total REAL,
        selling_price REAL,
        date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        remaining_stock INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS purchase_batches (
        id SERIAL PRIMARY KEY,
        product_id INTEGER,
        quantity INTEGER,
        remaining_quantity INTEGER,
        claimed_quantity INTEGER DEFAULT 0,
        cost_price REAL,
        discount REAL,
        selling_price REAL,
        date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        action TEXT DEFAULT 'created',
        source TEXT DEFAULT 'created',
        original_quantity INTEGER,
        original_date TIMESTAMP WITH TIME ZONE,
        original_cost_price REAL,
        original_selling_price REAL,
        original_discount REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS sales_items (
        id SERIAL PRIMARY KEY,
        sale_id INTEGER,
        product_id INTEGER,
        batch_id INTEGER,
        quantity INTEGER,
        cost_price REAL,
        selling_price REAL,
        profit REAL,
        unit_id INTEGER,
        unit_quantity REAL
    );

    CREATE TABLE IF NOT EXISTS product_units (
        id SERIAL PRIMARY KEY,
        product_id INTEGER,
        unit_name TEXT,
        conversion_factor REAL,
        selling_price REAL
    );

    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- ---------- Auth-adjacent tables (mirrors SQLite AUTH_SCHEMA) ----------
    CREATE TABLE IF NOT EXISTS user_logs (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        username TEXT,
        action TEXT,
        ip_address TEXT,
        user_agent TEXT,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_settings (
        id SERIAL PRIMARY KEY,
        user_id INTEGER UNIQUE,
        settings_json TEXT,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_purchase_batches_product_id ON purchase_batches(product_id);
    CREATE INDEX IF NOT EXISTS idx_purchase_batches_remaining ON purchase_batches(remaining_quantity);
    CREATE INDEX IF NOT EXISTS idx_sales_items_sale_id ON sales_items(sale_id);
    CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
    CREATE INDEX IF NOT EXISTS idx_products_stock ON products(stock);
    CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
    CREATE INDEX IF NOT EXISTS idx_sales_payment_method ON sales(payment_method);
    CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales(user_id);
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_user_logs_user_id ON user_logs(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_logs_timestamp ON user_logs(timestamp);
    """

    POSTGRES_MIGRATIONS = [
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS category TEXT",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS discount REAL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS base_unit TEXT DEFAULT 'piece'",
        "ALTER TABLE sales ADD COLUMN IF NOT EXISTS discount REAL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN IF NOT EXISTS subtotal REAL DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN IF NOT EXISTS product_id INTEGER",
        "ALTER TABLE sales ADD COLUMN IF NOT EXISTS reversed INTEGER DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'cash'",
        "ALTER TABLE sales ADD COLUMN IF NOT EXISTS cheque_number VARCHAR(100)",
        "ALTER TABLE sales ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE purchases ADD COLUMN IF NOT EXISTS selling_price REAL DEFAULT 0",
        "ALTER TABLE purchases ADD COLUMN IF NOT EXISTS remaining_stock INTEGER DEFAULT 0",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS selling_price REAL DEFAULT 0",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS action TEXT DEFAULT 'created'",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS claimed_quantity INTEGER DEFAULT 0",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'created'",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS original_quantity INTEGER",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS original_date TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS original_cost_price REAL",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS original_selling_price REAL",
        "ALTER TABLE purchase_batches ADD COLUMN IF NOT EXISTS original_discount REAL DEFAULT 0",
        "ALTER TABLE deleted_products ADD COLUMN IF NOT EXISTS category TEXT",
        "ALTER TABLE deleted_products ADD COLUMN IF NOT EXISTS discount REAL DEFAULT 0",
        "ALTER TABLE deleted_products ADD COLUMN IF NOT EXISTS action TEXT DEFAULT 'deleted'",
        "ALTER TABLE deleted_products ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'product'",
        "ALTER TABLE deleted_products ADD COLUMN IF NOT EXISTS batch_id INTEGER",
        "ALTER TABLE deleted_products ADD COLUMN IF NOT EXISTS batch_quantity INTEGER",
        "ALTER TABLE deleted_products ADD COLUMN IF NOT EXISTS batch_remaining INTEGER",
        "ALTER TABLE deleted_products ADD COLUMN IF NOT EXISTS product_id INTEGER",
        "ALTER TABLE sales_items ADD COLUMN IF NOT EXISTS unit_id INTEGER",
        "ALTER TABLE sales_items ADD COLUMN IF NOT EXISTS unit_quantity REAL",
        "CREATE TABLE IF NOT EXISTS product_units (id SERIAL PRIMARY KEY, product_id INTEGER, unit_name TEXT, conversion_factor REAL, selling_price REAL)",
        # ---------- Auth-adjacent migrations ----------
        "CREATE TABLE IF NOT EXISTS user_logs (id SERIAL PRIMARY KEY, user_id INTEGER, username TEXT, action TEXT, ip_address TEXT, user_agent TEXT, timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS user_settings (id SERIAL PRIMARY KEY, user_id INTEGER UNIQUE, settings_json TEXT, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_batches_product_id ON purchase_batches(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_sales_items_sale_id ON sales_items(sale_id)",
        "CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)",
        "CREATE INDEX IF NOT EXISTS idx_sales_payment_method ON sales(payment_method)",
        "CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS idx_user_logs_user_id ON user_logs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_logs_timestamp ON user_logs(timestamp)",
    ]

    def init_pool():
        """Initialize or reinitialize the connection pool"""
        global connection_pool
        if connection_pool is not None:
            try:
                connection_pool.closeall()
            except Exception:
                pass
            connection_pool = None

        try:
            connection_pool = pool.SimpleConnectionPool(
                2,                     # min connections
                30,                    # max connections
                DATABASE_URL,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
                connect_timeout=10,
                sslmode='require',
                options='-c statement_timeout=30000'
            )
            # Test the pool
            test_conn = connection_pool.getconn()
            cursor = test_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            connection_pool.putconn(test_conn)
            print("PostgreSQL connection pool created successfully")
            return True
        except Exception as e:
            print(f"Failed to create connection pool: {e}")
            connection_pool = None
            return False

    def get_connection():
        """Get a connection from the pool with retries and fallback"""
        global connection_pool

        if connection_pool is None:
            if not init_pool():
                print("Pool init failed, using direct connection")
                return get_direct_connection()

        for attempt in range(MAX_RETRIES):
            try:
                conn = connection_pool.getconn()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                return conn
            except Exception as e:
                print(f"Error getting connection from pool (attempt {attempt+1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    init_pool()
                else:
                    print("Pool exhausted, falling back to direct connection")
                    return get_direct_connection()

        return get_direct_connection()

    def get_direct_connection():
        """Create a direct connection (no pooling) with retries"""
        for attempt in range(MAX_RETRIES):
            try:
                conn = psycopg2.connect(
                    DATABASE_URL,
                    sslmode='require',
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5
                )
                cursor = conn.cursor()
                cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'products')")
                tables_exist = cursor.fetchone()[0]
                if not tables_exist:
                    print("Creating database schema...")
                    cursor.execute(SCHEMA)
                    for migration in POSTGRES_MIGRATIONS:
                        try:
                            cursor.execute(migration)
                        except Exception as e:
                            print(f"Migration warning: {e}")
                    conn.commit()
                    print("Database schema created successfully")
                return conn
            except Exception as e:
                print(f"Direct connection attempt {attempt+1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise

    def return_connection(conn):
        """Return connection to the pool, or close it if not pooled."""
        global connection_pool
        if conn is None:
            return
        try:
            if connection_pool and hasattr(conn, '_pool'):
                connection_pool.putconn(conn)
            else:
                conn.close()
        except Exception as e:
            print(f"Error returning connection: {e}")
            try:
                conn.close()
            except Exception:
                pass

    # ---------- AUTH CONNECTION (Postgres) ----------
    # On Postgres everything lives in one database, so "auth" is the same pool.
    def get_auth_connection():
        """Return a connection that can query users / user_logs / user_settings."""
        return get_connection()

    def return_auth_connection(conn):
        """Return an auth connection to the pool (same as regular connection)."""
        return_connection(conn)

else:
    # ---------- SQLite (local development) ----------
    print("Using SQLite (local)")

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        brand TEXT,
        cost_price REAL,
        selling_price REAL,
        stock INTEGER,
        category TEXT,
        discount REAL DEFAULT 0,
        base_unit TEXT DEFAULT 'piece'
    );

    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subtotal REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        total REAL,
        profit REAL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        payment_method VARCHAR(50) DEFAULT 'cash',
        cheque_number VARCHAR(100),
        user_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS deleted_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        brand TEXT,
        cost_price REAL,
        selling_price REAL,
        stock INTEGER,
        category TEXT,
        discount REAL DEFAULT 0,
        action TEXT DEFAULT 'deleted',
        source TEXT DEFAULT 'product',
        deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        batch_id INTEGER,
        batch_quantity INTEGER,
        batch_remaining INTEGER,
        product_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        brand TEXT,
        category TEXT,
        quantity INTEGER,
        cost_price REAL,
        discount REAL DEFAULT 0,
        total REAL,
        selling_price REAL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        remaining_stock INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS purchase_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity INTEGER,
        remaining_quantity INTEGER,
        claimed_quantity INTEGER DEFAULT 0,
        cost_price REAL,
        discount REAL,
        selling_price REAL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        action TEXT DEFAULT 'created',
        source TEXT DEFAULT 'created',
        original_quantity INTEGER,
        original_date TIMESTAMP,
        original_cost_price REAL,
        original_selling_price REAL,
        original_discount REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS sales_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        product_id INTEGER,
        batch_id INTEGER,
        quantity INTEGER,
        cost_price REAL,
        selling_price REAL,
        profit REAL,
        unit_id INTEGER,
        unit_quantity REAL
    );

    CREATE TABLE IF NOT EXISTS product_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        unit_name TEXT,
        conversion_factor REAL,
        selling_price REAL,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    -- Indexes for SQLite
    CREATE INDEX IF NOT EXISTS idx_purchase_batches_product_id ON purchase_batches(product_id);
    CREATE INDEX IF NOT EXISTS idx_sales_items_sale_id ON sales_items(sale_id);
    CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
    CREATE INDEX IF NOT EXISTS idx_sales_payment_method ON sales(payment_method);
    CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales(user_id);
    """

    # ---------- AUTH DB (separate file: auth.db) ----------
    AUTH_SCHEMA = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        action TEXT,
        ip_address TEXT,
        user_agent TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        settings_json TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_user_logs_user_id ON user_logs(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_logs_timestamp ON user_logs(timestamp);
    """

    def get_connection():
        """Get SQLite connection to retail.db with proper settings.
        Returns a shimmed connection that auto-translates %s / :name / ::type
        and registers Postgres aggregate function shims.
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        _register_sqlite_functions(conn)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor.executescript(SCHEMA)

        # Safe migrations (each one silently skipped if column already exists)
        try: cursor.execute("ALTER TABLE products ADD COLUMN category TEXT")
        except Exception: pass
        try: cursor.execute("ALTER TABLE products ADD COLUMN discount REAL DEFAULT 0")
        except Exception: pass
        try: cursor.execute("ALTER TABLE products ADD COLUMN base_unit TEXT DEFAULT 'piece'")
        except Exception: pass

        try: cursor.execute("ALTER TABLE sales ADD COLUMN discount REAL DEFAULT 0")
        except Exception: pass
        try: cursor.execute("ALTER TABLE sales ADD COLUMN subtotal REAL DEFAULT 0")
        except Exception: pass
        try: cursor.execute("ALTER TABLE sales ADD COLUMN product_id INTEGER")
        except Exception: pass
        try: cursor.execute("ALTER TABLE sales ADD COLUMN reversed INTEGER DEFAULT 0")
        except Exception: pass
        try: cursor.execute("ALTER TABLE sales ADD COLUMN payment_method VARCHAR(50) DEFAULT 'cash'")
        except Exception: pass
        try: cursor.execute("ALTER TABLE sales ADD COLUMN cheque_number VARCHAR(100)")
        except Exception: pass
        try: cursor.execute("ALTER TABLE sales ADD COLUMN user_id INTEGER")
        except Exception: pass

        try: cursor.execute("ALTER TABLE purchases ADD COLUMN selling_price REAL DEFAULT 0")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchases ADD COLUMN remaining_stock INTEGER DEFAULT 0")
        except Exception: pass

        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN selling_price REAL DEFAULT 0")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN action TEXT DEFAULT 'created'")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN claimed_quantity INTEGER DEFAULT 0")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN source TEXT DEFAULT 'created'")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN original_quantity INTEGER")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN original_date TIMESTAMP")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN original_cost_price REAL")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN original_selling_price REAL")
        except Exception: pass
        try: cursor.execute("ALTER TABLE purchase_batches ADD COLUMN original_discount REAL DEFAULT 0")
        except Exception: pass

        try: cursor.execute("ALTER TABLE deleted_products ADD COLUMN category TEXT")
        except Exception: pass
        try: cursor.execute("ALTER TABLE deleted_products ADD COLUMN discount REAL DEFAULT 0")
        except Exception: pass
        try: cursor.execute("ALTER TABLE deleted_products ADD COLUMN action TEXT DEFAULT 'deleted'")
        except Exception: pass
        try: cursor.execute("ALTER TABLE deleted_products ADD COLUMN source TEXT DEFAULT 'product'")
        except Exception: pass
        try: cursor.execute("ALTER TABLE deleted_products ADD COLUMN batch_id INTEGER")
        except Exception: pass
        try: cursor.execute("ALTER TABLE deleted_products ADD COLUMN batch_quantity INTEGER")
        except Exception: pass
        try: cursor.execute("ALTER TABLE deleted_products ADD COLUMN batch_remaining INTEGER")
        except Exception: pass
        try: cursor.execute("ALTER TABLE deleted_products ADD COLUMN product_id INTEGER")
        except Exception: pass

        try: cursor.execute("ALTER TABLE sales_items ADD COLUMN unit_id INTEGER")
        except Exception: pass
        try: cursor.execute("ALTER TABLE sales_items ADD COLUMN unit_quantity REAL")
        except Exception: pass

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    unit_name TEXT,
                    conversion_factor REAL,
                    selling_price REAL,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)
        except Exception: pass

        # Indexes
        try: cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_batches_product_id ON purchase_batches(product_id)")
        except Exception: pass
        try: cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_items_sale_id ON sales_items(sale_id)")
        except Exception: pass
        try: cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)")
        except Exception: pass
        try: cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_stock ON products(stock)")
        except Exception: pass
        try: cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_payment_method ON sales(payment_method)")
        except Exception: pass
        try: cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_user_id ON sales(user_id)")
        except Exception: pass

        conn.commit()

        # Ensure auth.db exists and its schema is applied (side effect of get_connection)
        _ensure_auth_db()

        # Wrap in shim so services using %s / :name / ::type keep working.
        return _SQLiteShimConnection(conn)

    def return_connection(conn):
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    # ---------- AUTH CONNECTION (SQLite) ----------
    def _ensure_auth_db():
        """Create auth.db and its schema if not present. Safe to call repeatedly."""
        try:
            auth_conn = sqlite3.connect(AUTH_DB_PATH)
            auth_conn.executescript(AUTH_SCHEMA)
            auth_conn.commit()
            auth_conn.close()
        except Exception as e:
            print(f"⚠️ Could not initialize auth.db: {e}")

    def get_auth_connection():
        """Return a shimmed connection to auth.db (users, user_logs, user_settings).
        %s / :name / ::type are auto-translated to SQLite-friendly SQL,
        and Postgres aggregate shims are registered.
        """
        conn = sqlite3.connect(AUTH_DB_PATH)
        conn.row_factory = sqlite3.Row
        _register_sqlite_functions(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.executescript(AUTH_SCHEMA)
        conn.commit()
        return _SQLiteShimConnection(conn)

    def return_auth_connection(conn):
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------- Helper function to get parameter style ----------
def get_param_style(cursor):
    if hasattr(cursor, 'connection'):
        if hasattr(cursor.connection, 'psycopg2_version'):
            return "%s"  # PostgreSQL
    return "?"  # SQLite


# ---------- Context manager for automatic connection handling ----------
@contextmanager
def get_db_connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        return_connection(conn)


# ---------- Health check function ----------
def check_database_health():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return_connection(conn)
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False


# ---------- Close all connections (for shutdown) ----------
def close_all_connections():
    global connection_pool
    if connection_pool:
        try:
            connection_pool.closeall()
            print("All database connections closed")
        except Exception as e:
            print(f"Error closing connection pool: {e}")
        finally:
            connection_pool = None
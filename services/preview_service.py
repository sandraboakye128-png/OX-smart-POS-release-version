"""
Preview + edit service for sales and purchases data.

Category semantics match the sales pages:
    'Accessory'  →  any product whose category is NOT 'Screen'
    'Screen'     →  any product whose category IS  'Screen'  (case-insensitive)

This mirrors:
    /api/sales/products?exclude_category=Screen    (accessories)
    /api/sales/products?category=Screen            (screens)
"""

from datetime import datetime
from database.db import get_connection


# ── Badge helper ─────────────────────────────────────────────
def _append_badges_inline(cur, batch_id, code):
    """Append a badge code to purchase_batches.badges (dedup). Bumps
    updated_at. Idempotent. Never raises — a missing badges column
    just means the badge is silently dropped."""
    import json as _json
    try:
        cur.execute("SELECT COALESCE(badges, '[]') FROM purchase_batches WHERE id = %s", (batch_id,))
        r = cur.fetchone()
        if not r:
            return
        try:
            arr = _json.loads(r[0]) if r[0] else []
        except Exception:
            arr = []
        if not isinstance(arr, list):
            arr = []
        if code not in arr:
            arr.append(code)
            cur.execute("UPDATE purchase_batches SET badges = %s WHERE id = %s",
                        (_json.dumps(arr), batch_id))
    except Exception:
        pass


# ============================================================
#  Column schemas — drives both the sheet columns and CSV header
# ============================================================
PURCHASE_COLUMNS = [
    ('batch_id',           'Batch ID',       'int',   False),
    ('name',               'Name',           'text',  True),
    ('brand',              'Brand',          'text',  True),
    ('category',           'Category',       'text',  False),
    ('quantity',           'Quantity',       'int',   True),
    ('remaining_quantity', 'Remaining',      'int',   True),
    ('claimed_quantity',   'Claimed',        'int',   True),
    ('cost_price',         'Cost Price',     'float', True),
    ('selling_price',      'Selling Price',  'float', True),
    ('discount',           'Discount',       'float', True),
    ('date',               'Date',           'date',  True),
    ('source',             'Source',         'text',  True),
]

SALES_COLUMNS = [
    ('sale_id',        'Sale ID',    'int',   False),
    ('item_id',        'Item ID',    'int',   True),
    ('name',           'Product',    'text',  True),
    ('brand',          'Brand',      'text',  True),
    ('category',       'Category',   'text',  False),
    ('quantity',       'Quantity',   'int',   True),
    ('selling_price',  'Rate',       'float', True),
    ('cost_price',     'Cost',       'float', True),
    ('discount',       'Discount',   'float', True),
    ('date',           'Date',       'date',  True),
    ('payment_method', 'Payment',    'text',  True),
    ('cheque_number',  'Cheque #',   'text',  True),
    ('username',       'Sold By',    'text',  False),
]


# ============================================================
#  Category helpers
# ============================================================
def _is_screen_category(cat):
    return str(cat or '').strip().lower() == 'screen'


def _category_filter(category):
    """Return a (sql_fragment, params) tuple for the given preview category."""
    if category == 'Screen':
        return ("LOWER(COALESCE(%s, '')) = 'screen'", ['__CAT__'])
    # 'Accessory' → everything that is NOT Screen
    return ("LOWER(COALESCE(%s, '')) != 'screen'", ['__CAT__'])


def _canonical_category_for_new_products(cur, category):
    """Pick what category string to write for a NEW product in this preview
    category. Detects the convention already in use in the DB so we don't
    fragment it."""
    if category == 'Screen':
        # Screens is a single, standard label in this app
        return 'Screen'

    # Accessory mode: find the most common non-screen category in use
    cur.execute("""
        SELECT COALESCE(category, '') AS cat, COUNT(*) AS n
        FROM products
        WHERE LOWER(COALESCE(category, '')) != 'screen'
          AND category IS NOT NULL
          AND category != ''
        GROUP BY category
        ORDER BY n DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    return row[0] if row else 'accessories'


# ============================================================
#  Date helpers
# ============================================================
def _serialize_date(v):
    if v is None:
        return ''
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    return str(v)


def _parse_date(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now()


# ============================================================
#  History helper — called on every merge-edit so the purchases
#  page's "🔄 Updated" badge and View History modal stay accurate
# ============================================================
def _log_batch_update(cur, batch_id, old_data, new_data,
                      source='excel', user_id=None, username=None):
    """Record a batch edit in batch_update_history.

    source = 'excel' | 'import' | 'page'   (default 'excel' for back-compat)
    user_id = the logged-in user's id, or None for system actions
    """
    import json as _json
    diff = {}
    for key in old_data:
        if old_data.get(key) != new_data.get(key):
            diff[key] = {"old": old_data.get(key), "new": new_data.get(key)}
    if not diff:
        return
    # Try the extended schema first; fall back to the legacy 3-column
    # shape if the migration hasn't run yet.
    try:
        cur.execute("""
            INSERT INTO batch_update_history
            (batch_id, changed_fields, source, user_id, username, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (batch_id, _json.dumps(diff), source, user_id, username, datetime.now()))
        return
    except Exception:
        pass
    try:
        cur.execute("""
            INSERT INTO batch_update_history
            (batch_id, changed_fields, source, user_id, updated_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (batch_id, _json.dumps(diff), source, user_id, datetime.now()))
        return
    except Exception:
        pass
    try:
        cur.execute("""
            INSERT INTO batch_update_history (batch_id, changed_fields, updated_at)
            VALUES (%s, %s, %s)
        """, (batch_id, _json.dumps(diff), datetime.now()))
    except Exception:
        pass


# ============================================================
#  Read
# ============================================================
def get_purchase_rows(category):
    """Return purchase batch rows for a category ('Accessory' | 'Screen')."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if category == 'Screen':
            where = "LOWER(COALESCE(p.category, '')) = 'screen'"
        else:
            where = "LOWER(COALESCE(p.category, '')) != 'screen'"

        cur.execute(f"""
            SELECT
                pb.id,
                p.name,
                p.brand,
                p.category,
                pb.quantity,
                pb.remaining_quantity,
                pb.claimed_quantity,
                pb.cost_price,
                pb.selling_price,
                pb.discount,
                pb.date,
                COALESCE(pb.source, ''),
                COALESCE(pb.action, 'added')
            FROM purchase_batches pb
            JOIN products p ON p.id = pb.product_id
            WHERE {where}
            ORDER BY pb.date DESC, pb.id DESC
        """)
        rows = []
        for r in cur.fetchall():
            rows.append({
                'batch_id':           int(r[0]),
                'name':               r[1] or '',
                'brand':              r[2] or '',
                'category':           r[3] or '',
                'quantity':           int(r[4] or 0),
                'remaining_quantity': int(r[5] or 0),
                'claimed_quantity':   int(r[6] or 0),
                'cost_price':         float(r[7] or 0),
                'selling_price':      float(r[8] or 0),
                'discount':           float(r[9] or 0),
                'date':               _serialize_date(r[10]),
                'source':             r[11] or '',
                'action':             r[12] or 'added',
            })
        return rows
    finally:
        conn.close()


def _ensure_sales_action_column(cur):
    """Add sales.action if it's missing. Idempotent — safe to call every load."""
    try:
        cur.execute("ALTER TABLE sales ADD COLUMN action TEXT DEFAULT 'sale'")
    except Exception:
        pass  # column already exists


def _resolve_users_table(cur):
    """Return the correct users-table name for the current DB.

    SQLite → attach auth.db and use 'auth.users'
    Postgres → single schema, use 'users'

    Idempotent: 'already attached' errors from a second ATTACH are
    swallowed (the table name is what matters, not whether ATTACH
    succeeded on this specific call).
    """
    import os
    url = os.getenv('DATABASE_URL', '') or ''
    if url.startswith('postgres://') or url.startswith('postgresql://'):
        return 'users'
    try:
        from database.db import AUTH_DB_PATH
        cur.execute("ATTACH DATABASE ? AS auth", (AUTH_DB_PATH,))
    except Exception as e:
        # Usually 'already attached' — fine.
        msg = str(e).lower()
        if 'already' not in msg and 'attach' not in msg:
            print(f'[preview] ATTACH auth.db: {e}')
    return 'auth.users'


def get_archived_purchase_rows(category):
    """Return archived (BATCH DELETED) purchase batches for a category,
    shaped like get_purchase_rows() output but with _pendingDelete set
    so the client can render them red. Best-effort; failures return []."""
    conn = get_connection()
    cur = conn.cursor()
    rows = []
    try:
        if category == 'Screen':
            cat_where = "LOWER(COALESCE(dp.category, '')) = 'screen'"
        else:
            cat_where = "LOWER(COALESCE(dp.category, '')) != 'screen'"

        # Only BATCH DELETED (soft archived); PERMANENTLY DELETED should not reappear
        cur.execute(f"""
            SELECT dp.id, dp.name, dp.brand, dp.category,
                   dp.batch_quantity, dp.batch_remaining, dp.batch_remaining,
                   dp.cost_price, dp.selling_price, dp.discount,
                   dp.deleted_at, COALESCE(dp.source, ''),
                   dp.batch_id, dp.product_id
            FROM deleted_products dp
            WHERE dp.action = 'BATCH DELETED'
              AND dp.batch_id IS NOT NULL
              AND {cat_where}
            ORDER BY dp.deleted_at DESC
        """)
        for r in cur.fetchall():
            _archived_at = r[10]
            if hasattr(_archived_at, 'isoformat'):
                _archived_at = _archived_at.isoformat()
            rows.append({
                'batch_id':           int(r[12] or 0),
                'name':               r[1] or '',
                'brand':              r[2] or '',
                'category':           r[3] or '',
                'quantity':           int(r[4] or 0),
                'remaining_quantity': int(r[5] or 0),
                'claimed_quantity':   int(r[6] or 0),
                'cost_price':         float(r[7] or 0),
                'selling_price':      float(r[8] or 0),
                'discount':           float(r[9] or 0),
                'date':               str(_archived_at) if _archived_at else '',
                'source':             r[11] or '',
                'action':             'archived',
                '_pendingDelete':     True,
                '_archived':          True,
                '_archive_id':        int(r[0]),
                '_product_id':        int(r[13]) if r[13] is not None else None,
            })
    except Exception as e:
        print(f"[archived_purchase_rows] {e}")
    finally:
        try: conn.close()
        except Exception: pass
    return rows


def get_sales_rows(category):
    """Return sales item rows for a category ('Accessory' | 'Screen')."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        _ensure_sales_action_column(cur)
        if category == 'Screen':
            where = "LOWER(COALESCE(p.category, '')) = 'screen'"
        else:
            where = "LOWER(COALESCE(p.category, '')) != 'screen'"

        users_table = _resolve_users_table(cur)
        # GROUP BY (sale_id, product_id) so a single sale that drew stock
        # from multiple batches shows as ONE row. Weighted-average cost.
        cur.execute(f"""
            SELECT
                s.id                   AS sale_id,
                si.product_id          AS item_id,
                MAX(p.name)            AS name,
                MAX(p.brand)           AS brand,
                MAX(p.category)        AS category,
                SUM(si.quantity)       AS quantity,
                MAX(si.selling_price)  AS selling_price,
                CASE WHEN SUM(si.quantity) > 0
                     THEN SUM(si.cost_price * si.quantity) / SUM(si.quantity)
                     ELSE 0 END        AS cost_price,
                MAX(s.discount)        AS discount,
                MAX(s.date)            AS sale_date,
                MAX(COALESCE(s.payment_method, 'cash')) AS payment_method,
                MAX(COALESCE(s.cheque_number, ''))      AS cheque_number,
                MAX(COALESCE(s.action, 'sale'))         AS action,
                MAX(COALESCE(u.username, ''))           AS username
            FROM sales_items si
            JOIN sales s     ON s.id = si.sale_id
            JOIN products p  ON p.id = si.product_id
            LEFT JOIN {users_table} u ON u.id = s.user_id
            WHERE s.reversed = 0
              AND {where}
            GROUP BY s.id, si.product_id
            ORDER BY MAX(s.date) DESC, s.id DESC
        """)
        rows = []
        for r in cur.fetchall():
            rows.append({
                'sale_id':        int(r[0]),
                'item_id':        int(r[1]),
                'name':           r[2] or '',
                'brand':          r[3] or '',
                'category':       r[4] or '',
                'quantity':       int(r[5] or 0),
                'selling_price':  float(r[6] or 0),
                'cost_price':     float(r[7] or 0),
                'discount':       float(r[8] or 0),
                'date':           _serialize_date(r[9]),
                'payment_method': r[10] or 'cash',
                'cheque_number':  r[11] or '',
                'action':         r[12] or 'sale',
                'username':       r[13] or '',
            })
        return rows
    finally:
        conn.close()


# ============================================================
#  Soft-delete helpers — move rows to archive on preview delete
# ============================================================
def _soft_delete_purchase_batch(cur, batch_id):
    """Archive + remove a purchase batch."""
    cur.execute("""
        SELECT pb.id, pb.product_id, pb.quantity, pb.remaining_quantity,
               pb.claimed_quantity, pb.cost_price, pb.selling_price,
               pb.discount, COALESCE(pb.source,''),
               p.name, COALESCE(p.brand,''), COALESCE(p.category,'')
        FROM purchase_batches pb
        JOIN products p ON p.id = pb.product_id
        WHERE pb.id = %s
    """, (int(batch_id),))
    r = cur.fetchone()
    if not r:
        return False
    bid, pid, qty, rem, claimed, cost, sell, disc, src, name, brand, cat = r
    cur.execute("SELECT COUNT(*) FROM purchase_batches WHERE product_id = %s", (pid,))
    batch_count = cur.fetchone()[0]
    action = 'PRODUCT DELETED' if batch_count == 1 else 'BATCH DELETED'
    cur.execute("""
        INSERT INTO deleted_products
        (name, brand, cost_price, selling_price, stock, category, discount,
         action, product_id, source, batch_id, batch_quantity, batch_remaining)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (name, brand, cost, sell, rem, cat, disc,
          action, pid, src, bid, qty, rem))
    # Detach sales_items — preserve history, drop batch link
    cur.execute("UPDATE sales_items SET batch_id = NULL WHERE batch_id = %s", (bid,))
    cur.execute("DELETE FROM purchase_batches WHERE id = %s", (bid,))
    if action == 'PRODUCT DELETED':
        cur.execute("DELETE FROM products WHERE id = %s", (pid,))
    else:
        cur.execute("""
            UPDATE products SET stock = COALESCE((
                SELECT SUM(remaining_quantity) FROM purchase_batches WHERE product_id = %s
            ), 0) WHERE id = %s
        """, (pid, pid))
    return True


def _soft_delete_sale(cur, sale_id):
    """Reverse a sale — restores batch stock, marks sale as reversed."""
    cur.execute("SELECT id FROM sales WHERE id = %s", (int(sale_id),))
    if not cur.fetchone():
        return False
    cur.execute("SELECT batch_id, quantity FROM sales_items WHERE sale_id = %s", (int(sale_id),))
    for batch_id, qty in cur.fetchall():
        if not batch_id:
            continue
        cur.execute("UPDATE purchase_batches SET remaining_quantity = remaining_quantity + %s WHERE id = %s",
                    (int(qty or 0), batch_id))
        cur.execute("SELECT product_id FROM purchase_batches WHERE id = %s", (batch_id,))
        p = cur.fetchone()
        if p:
            cur.execute("""
                UPDATE products SET stock = COALESCE((
                    SELECT SUM(remaining_quantity) FROM purchase_batches WHERE product_id = %s
                ), 0) WHERE id = %s
            """, (p[0], p[0]))
    cur.execute("UPDATE sales SET reversed = 1 WHERE id = %s", (int(sale_id),))
    return True


# ============================================================
#  Save
# ============================================================
def _delete_category_purchases(cur, category):
    if category == 'Screen':
        where = "LOWER(COALESCE(category, '')) = 'screen'"
    else:
        where = "LOWER(COALESCE(category, '')) != 'screen'"

    # Detach sales_items from batches we're about to delete
    cur.execute(f"""
        UPDATE sales_items SET batch_id = NULL
        WHERE batch_id IN (
            SELECT pb.id FROM purchase_batches pb
            JOIN products p ON p.id = pb.product_id
            WHERE {where.replace('category', 'p.category')}
        )
    """)
    cur.execute(f"""
        DELETE FROM purchase_batches
        WHERE product_id IN (
            SELECT id FROM products WHERE {where}
        )
    """)
    cur.execute(f"DELETE FROM products WHERE {where}")


def _delete_category_sales(cur, category):
    if category == 'Screen':
        where = "LOWER(COALESCE(category, '')) = 'screen'"
    else:
        where = "LOWER(COALESCE(category, '')) != 'screen'"

    cur.execute(f"""
        DELETE FROM sales_items
        WHERE product_id IN (SELECT id FROM products WHERE {where})
    """)
    cur.execute("""
        DELETE FROM sales
        WHERE id NOT IN (SELECT DISTINCT sale_id FROM sales_items)
    """)


def _upsert_product(cur, name, brand, category, cost, selling, canonical_category):
    """Find or create a product. Preserves existing category on match."""
    cur.execute("""
        SELECT id, category FROM products
        WHERE name = %s AND brand = %s
        LIMIT 1
    """, (name, brand or ''))
    row = cur.fetchone()
    if row:
        # Preserve existing category — don't overwrite 'accessories' with 'Accessory'
        cur.execute("""
            UPDATE products
            SET cost_price = %s, selling_price = %s
            WHERE id = %s
        """, (cost, selling, row[0]))
        return row[0]

    cur.execute("""
        INSERT INTO products (name, brand, category, cost_price, selling_price, stock, discount)
        VALUES (%s, %s, %s, %s, %s, 0, 0)
    """, (name, brand or '', canonical_category, cost, selling))
    cur.execute("SELECT last_insert_rowid()")
    return cur.fetchone()[0]


def _maybe_split_for_create(cur, bid, name, brand, qty, remaining, claimed,
                            cost, selling, discount, date, source):
    """If `bid` refers to an existing batch with price or identity changes,
    split it: zero the old batch and insert a new one with the new values.
    Returns the new batch_id, or None if no change / not applicable."""
    try:
        bid_int = int(bid)
    except (TypeError, ValueError):
        return None
    if not bid_int:
        return None
    cur.execute("""
        SELECT pb.product_id, pb.quantity, pb.remaining_quantity, pb.claimed_quantity,
               pb.cost_price, pb.selling_price, pb.discount,
               pb.original_quantity, pb.original_date,
               pb.original_cost_price, pb.original_selling_price, pb.original_discount,
               COALESCE(pb.source, '')
        FROM purchase_batches pb WHERE pb.id = %s
    """, (bid_int,))
    row = cur.fetchone()
    if not row:
        return None
    (pid, cq, cr, cc, ccost, csell, cdisc,
     coq, codate, cocost, cosell, codisc, csrc) = row

    price_changed = (
        abs(float(ccost or 0) - float(cost))    > 0.001 or
        abs(float(csell or 0) - float(selling)) > 0.001 or
        abs(float(cdisc or 0) - float(discount)) > 0.001
    )
    cur.execute("SELECT name, COALESCE(brand,'') FROM products WHERE id = %s", (pid,))
    pr = cur.fetchone()
    ident_changed = bool(pr and (pr[0] != name or pr[1] != brand))

    if not (price_changed or ident_changed):
        return None

    cur.execute("""
        UPDATE purchase_batches
        SET remaining_quantity = 0,
            action = 'remaining_moved_to_new_batch',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (bid_int,))

    new_rem = max(int(cr or 0), 0)
    cur.execute("""
        INSERT INTO purchase_batches
        (product_id, quantity, remaining_quantity, claimed_quantity,
         cost_price, selling_price, discount, date, action, source,
         original_quantity, original_date,
         original_cost_price, original_selling_price, original_discount,
         badges, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'created_from_excel', %s,
                %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """, (pid, qty, new_rem, int(claimed or 0),
          cost, selling, discount, date,
          source or csrc or 'Unknown',
          coq or qty, codate or date,
          cocost if cocost is not None else cost,
          cosell if cosell is not None else selling,
          codisc if codisc is not None else discount,
          '["excel_add","excel_update"]'))
    try:
        cur.execute("SELECT last_insert_rowid()")
        new_bid = cur.fetchone()[0]
    except Exception:
        new_bid = None

    if ident_changed and new_bid:
        cur.execute("UPDATE products SET name = %s, brand = %s WHERE id = %s",
                    (name, brand, pid))

    try:
        _log_batch_update(cur,
            new_bid if new_bid else bid_int,
            {'quantity': cq, 'remaining': cr, 'cost_price': ccost,
             'selling_price': csell, 'discount': cdisc},
            {'quantity': qty, 'remaining': new_rem, 'cost_price': cost,
             'selling_price': selling, 'discount': discount},
            source='excel', user_id=None)
    except Exception:
        pass

    return new_bid


def save_purchases(rows, category, mode, deleted_ids=None, dirty_ids=None, update_mode='auto'):
    """mode: 'replace' | 'append' | 'merge'.

    Merge mode deduplicates on (name.lower, brand.lower, date) so editing a
    sheet row that already exists in the DB updates it instead of inserting
    a new batch. Also detects duplicates WITHIN the incoming batch of rows.
    """
    conn = get_connection()
    cur = conn.cursor()
    stats = {'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': []}
    seen_keys = set()   # (name_lower, brand_lower, date_iso) — within this submission

    try:
        # 0. Soft-delete first (rows the user removed from the sheet)
        print(f"[preview-save] deleted_ids={deleted_ids!r}")
        if deleted_ids:
            for did in deleted_ids:
                try:
                    _ok = _soft_delete_purchase_batch(cur, did)
                    print(f"[preview-save] soft-delete batch #{did}: {_ok}")
                    if _ok:
                        stats['deleted'] += 1
                except Exception as e:
                    import traceback as _tb
                    _tb.print_exc()
                    print(f"[preview-save] delete #{did} FAILED: {e}")
                    stats['errors'].append(f"Delete batch #{did}: {e}")

        canonical = _canonical_category_for_new_products(cur, category)

        if mode == 'replace':
            _delete_category_purchases(cur, category)
            stats['deleted'] = 1

        _dirty_set = None
        if dirty_ids is not None:
            try:
                _dirty_set = set(int(x) for x in dirty_ids if str(x).strip())
            except Exception:
                _dirty_set = None

        for i, row in enumerate(rows):
            try:
                # If caller sent a whitelist, skip untouched existing rows.
                # Without this, every save re-marks the whole sheet as
                # 'updated_from_excel'.
                if _dirty_set is not None:
                    _b = row.get('batch_id')
                    try:
                        _bi = int(_b) if _b not in (None, '', 0, '0') else None
                    except (TypeError, ValueError):
                        _bi = None
                    if _bi and _bi not in _dirty_set:
                        continue

                name = (row.get('name') or '').strip()
                if not name:
                    stats['errors'].append(f"Row {i+1}: empty name, skipped")
                    continue
                brand = (row.get('brand') or '').strip()
                qty = int(row.get('quantity') or 0)
                remaining = int(row.get('remaining_quantity') or qty)
                claimed = int(row.get('claimed_quantity') or 0)
                cost = float(row.get('cost_price') or 0)
                selling = float(row.get('selling_price') or 0)
                discount = float(row.get('discount') or 0)
                date = _parse_date(row.get('date')) or datetime.now()
                source = (row.get('source') or '').strip()
                bid = row.get('batch_id')

                # ---- Dedupe within this submission ----
                key = (name.lower(), brand.lower(), date.isoformat()[:19])
                if key in seen_keys:
                    stats['errors'].append(
                        f"Row {i+1}: duplicate within submission (same name+brand+date) — skipped"
                    )
                    continue
                seen_keys.add(key)

                # ---- create-mode split (purchases only) ----
                if update_mode == 'create' and mode == 'merge' and bid:
                    _new_bid = _maybe_split_for_create(
                        cur, bid, name, brand, qty, remaining, claimed,
                        cost, selling, discount, date, source)
                    if _new_bid:
                        stats['updated'] += 1
                        stats.setdefault('updated_ids', []).append(_new_bid)
                        continue

                # ---- Update existing batch if merge mode & numeric id ----
                if mode == 'merge' and bid:
                    try:
                        bid_int = int(bid)
                    except (TypeError, ValueError):
                        bid_int = None
                    if bid_int:
                        cur.execute("""
                            SELECT pb.id, pb.quantity, pb.remaining_quantity, pb.claimed_quantity,
                                   pb.cost_price, pb.selling_price, pb.discount,
                                   pb.date, pb.source, pb.original_date, p.name, p.brand
                            FROM purchase_batches pb
                            JOIN products p ON p.id = pb.product_id
                            WHERE pb.id = %s
                        """, (bid_int,))
                        old = cur.fetchone()
                        if old:
                            # Preserve original_date: set it once, never overwrite
                            orig_date = old[9] or old[7]
                            # Business date (user-editable) stays as orig;
                            # `date` becomes now() so "Last updated" reflects the edit.
                            cur.execute("""
                                UPDATE purchase_batches
                                SET quantity = %s, remaining_quantity = %s, claimed_quantity = %s,
                                    cost_price = %s, selling_price = %s, discount = %s,
                                    date = %s, source = %s,
                                    action = 'updated_from_excel',
                                    original_date = %s,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, (qty, remaining, claimed, cost, selling, discount,
                                   datetime.now(), source, orig_date, bid_int))
                            _append_badges_inline(cur, bid_int, 'excel_update')
                            # Update product name/brand if changed
                            if old[10] != name or old[11] != brand:
                                cur.execute("""
                                    UPDATE products SET name = %s, brand = %s
                                    WHERE id = (SELECT product_id FROM purchase_batches WHERE id = %s)
                                """, (name, brand, bid_int))
                            # Log for history modal
                            _log_batch_update(
                                cur, bid_int,
                                {'quantity': old[1], 'remaining': old[2],
                                 'claimed': old[3], 'cost_price': old[4],
                                 'selling_price': old[5], 'discount': old[6],
                                 'date': str(old[7]), 'source': old[8]},
                                {'quantity': qty, 'remaining': remaining,
                                 'claimed': claimed, 'cost_price': cost,
                                 'selling_price': selling, 'discount': discount,
                                 'date': str(date), 'source': source}
                            )
                            stats['updated'] += 1
                            stats.setdefault('updated_ids', []).append(bid_int)
                            continue

                # ---- Merge: also dedupe against DB rows with same key ----
                if mode == 'merge':
                    cur.execute("""
                        SELECT pb.id FROM purchase_batches pb
                        JOIN products p ON p.id = pb.product_id
                        WHERE LOWER(p.name) = LOWER(%s)
                          AND LOWER(COALESCE(p.brand,'')) = LOWER(%s)
                          AND pb.date = %s
                        LIMIT 1
                    """, (name, brand, date))
                    existing = cur.fetchone()
                    if existing:
                        cur.execute("""
                            UPDATE purchase_batches
                            SET quantity = %s, remaining_quantity = %s, claimed_quantity = %s,
                                cost_price = %s, selling_price = %s, discount = %s,
                                source = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (qty, remaining, claimed, cost, selling, discount,
                              source, existing[0]))
                        _append_badges_inline(cur, existing[0], 'excel_update')
                        stats['updated'] += 1
                        continue

                # ---- Insert new batch ----
                product_id = _upsert_product(cur, name, brand, category, cost, selling, canonical)
                cur.execute("""
                    INSERT INTO purchase_batches
                    (product_id, quantity, remaining_quantity, claimed_quantity,
                     cost_price, selling_price, discount, date, action, source,
                     badges, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'added_from_excel', %s,
                            %s, CURRENT_TIMESTAMP)
                """, (product_id, qty, remaining, claimed,
                      cost, selling, discount, date, source,
                      '["excel_add"]'))
                cur.execute("SELECT last_insert_rowid()")
                new_bid = cur.fetchone()[0]
                cur.execute("""
                    UPDATE products
                    SET stock = COALESCE(stock, 0) + %s
                    WHERE id = %s
                """, (remaining, product_id))
                stats['inserted'] += 1
                stats.setdefault('inserted_ids', []).append(new_bid)
            except Exception as e:
                stats['errors'].append(f"Row {i+1}: {e}")

        conn.commit()
        stats['canonical_category'] = canonical
        print(f"[preview-save] FINAL stats={stats}")
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_sales(rows, category, mode, deleted_ids=None, user_id=None):
    """mode: 'replace' | 'append' | 'merge'.

    When a new sale row is inserted (mode != 'replace' with matching
    sale_id), we:
      1. Resolve the product by name+brand (fallback: name-only).
      2. FIFO-deduct the sold quantity from that product's batches so the
         sale is properly accounted for and product stock stays accurate.
      3. Store the actual batch_id(s) and cost_price on the sales_item(s).

    Merge deduplication: matching sale_id → UPDATE.
    """
    conn = get_connection()
    cur = conn.cursor()
    stats = {'inserted': 0, 'updated': 0, 'deleted': 0, 'errors': []}
    seen_keys = set()   # (name_lower, date_iso, qty) — within this submission

    # 0. Soft-delete (reverse) first
    try:
        if deleted_ids:
            for did in deleted_ids:
                try:
                    if _soft_delete_sale(cur, did):
                        stats['deleted'] += 1
                except Exception as e:
                    stats['errors'].append(f"Reverse sale #{did}: {e}")
    except Exception:
        pass

    def _deduct_from_batches(product_id, needed_qty, sale_id, rate):
        """FIFO-deduct `needed_qty` from product's batches. Inserts sales_items
        rows using the given selling rate (the old code hardcoded 0 here,
        which is why batch rows showed Rate=$0.00 in the preview). Returns
        (units_deducted, cost_sum)."""
        cur.execute("""
            SELECT id, remaining_quantity, cost_price
            FROM purchase_batches
            WHERE product_id = %s AND remaining_quantity > 0
            ORDER BY date ASC, id ASC
        """, (product_id,))
        batches = cur.fetchall()
        remaining = needed_qty
        deducted = 0
        cost_sum = 0.0
        for (bid, batch_rem, batch_cost) in batches:
            if remaining <= 0:
                break
            take = min(int(batch_rem or 0), remaining)
            if take <= 0:
                continue
            cur.execute("""
                UPDATE purchase_batches
                SET remaining_quantity = remaining_quantity - %s
                WHERE id = %s
            """, (take, bid))
            item_profit = (float(rate) - float(batch_cost or 0)) * take
            cur.execute("""
                INSERT INTO sales_items
                (sale_id, product_id, batch_id, quantity, selling_price, cost_price, profit)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (sale_id, product_id, bid, take,
                  float(rate), float(batch_cost or 0), item_profit))
            deducted += take
            cost_sum += float(batch_cost or 0) * take
            remaining -= take
        return deducted, cost_sum

    try:
        if mode == 'replace':
            _delete_category_sales(cur, category)
            stats['deleted'] = 1

        for i, row in enumerate(rows):
            try:
                name = (row.get('name') or '').strip()
                if not name:
                    stats['errors'].append(f"Row {i+1}: empty product name, skipped")
                    continue
                brand = (row.get('brand') or '').strip()
                qty = int(row.get('quantity') or 0)
                if qty <= 0:
                    stats['errors'].append(f"Row {i+1}: qty must be > 0, skipped")
                    continue
                rate = float(row.get('selling_price') or 0)
                cost = float(row.get('cost_price') or 0)
                discount = float(row.get('discount') or 0)
                date = _parse_date(row.get('date')) or datetime.now()
                payment = (row.get('payment_method') or 'cash').strip().lower()
                cheque = (row.get('cheque_number') or '').strip()
                sale_id = row.get('sale_id')

                # ---- Dedupe within this submission ----
                key = (name.lower(), date.isoformat()[:19], qty)
                if key in seen_keys:
                    stats['errors'].append(
                        f"Row {i+1}: duplicate within submission — skipped"
                    )
                    continue
                seen_keys.add(key)

                # ---- Update existing sale if merge & sale_id present ----
                if mode == 'merge' and sale_id:
                    try:
                        sid_int = int(sale_id)
                    except (TypeError, ValueError):
                        sid_int = None
                    if sid_int:
                        cur.execute("SELECT id FROM sales WHERE id = %s", (sid_int,))
                        if cur.fetchone():
                            # Resolve product_id (needed for re-deduct)
                            cur.execute("SELECT id FROM products WHERE name = %s AND brand = %s LIMIT 1",
                                        (name, brand))
                            _p = cur.fetchone()
                            if not _p:
                                cur.execute("SELECT id FROM products WHERE name = %s LIMIT 1", (name,))
                                _p = cur.fetchone()
                            if not _p:
                                stats['errors'].append(f"Row {i+1}: product '{name}' not found, skipped")
                                continue
                            _pid = _p[0]

                            # Restore batch quantities from the sale's current items
                            cur.execute("SELECT batch_id, quantity FROM sales_items WHERE sale_id = %s", (sid_int,))
                            for _obid, _oqty in cur.fetchall():
                                if _obid:
                                    cur.execute(
                                        "UPDATE purchase_batches SET remaining_quantity = remaining_quantity + %s WHERE id = %s",
                                        (int(_oqty or 0), _obid)
                                    )
                            # Delete old items — we'll re-deduct cleanly below
                            cur.execute("DELETE FROM sales_items WHERE sale_id = %s", (sid_int,))

                            subtotal = qty * rate
                            total = subtotal - discount
                            cur.execute("""
                                UPDATE sales
                                SET discount = %s, date = %s, subtotal = %s,
                                    total = %s, payment_method = %s, cheque_number = %s
                                WHERE id = %s
                            """, (discount, date, subtotal, total,
                                  payment, cheque or None, sid_int))

                            # Re-deduct fresh
                            deducted, _csum = _deduct_from_batches(_pid, qty, sid_int, rate)
                            if deducted < qty:
                                short = qty - deducted
                                cur.execute("""
                                    INSERT INTO sales_items
                                    (sale_id, product_id, batch_id, quantity, selling_price, cost_price, profit)
                                    VALUES (%s, %s, NULL, %s, %s, %s, 0)
                                """, (sid_int, _pid, short, rate, cost))
                                stats['errors'].append(
                                    f"Row {i+1}: only {deducted}/{qty} units had batch stock for '{name}'"
                                )

                            # Recompute item-level profit, then roll up to sale
                            cur.execute("""
                                UPDATE sales_items
                                SET profit = (selling_price - cost_price) * quantity
                                WHERE sale_id = %s
                            """, (sid_int,))
                            cur.execute("SELECT COALESCE(SUM(profit), 0) FROM sales_items WHERE sale_id = %s",
                                        (sid_int,))
                            _ip = float(cur.fetchone()[0] or 0)
                            cur.execute("UPDATE sales SET profit = %s WHERE id = %s",
                                        (_ip - float(discount or 0), sid_int))

                            stats['updated'] += 1
                            stats.setdefault('updated_ids', []).append(sid_int)
                            continue

                # ---- Resolve product by name+brand, then name-only ----
                cur.execute("""
                    SELECT id FROM products WHERE name = %s AND brand = %s LIMIT 1
                """, (name, brand))
                prod = cur.fetchone()
                if not prod:
                    cur.execute("SELECT id FROM products WHERE name = %s LIMIT 1", (name,))
                    prod = cur.fetchone()
                if not prod:
                    stats['errors'].append(f"Row {i+1}: product '{name}' not found, skipped")
                    continue
                product_id = prod[0]

                # ---- Insert new sale ----
                subtotal = qty * rate
                total = subtotal - discount
                profit = (rate - cost) * qty - discount
                cur.execute("""
                    INSERT INTO sales
                    (date, subtotal, discount, total, profit, reversed, payment_method, cheque_number, user_id)
                    VALUES (%s, %s, %s, %s, %s, 0, %s, %s, %s)
                """, (date, subtotal, discount, total, profit, payment, cheque or None, user_id))
                cur.execute("SELECT last_insert_rowid()")
                new_sale_id = cur.fetchone()[0]
                stats.setdefault('inserted_ids', []).append(new_sale_id)

                # Try to deduct from real batches. If no batches exist, fall
                # back to a single sales_items row without batch_id so the
                # sale is still recorded.
                deducted, cost_sum = _deduct_from_batches(product_id, qty, new_sale_id, rate)
                if deducted == 0:
                    cur.execute("""
                        INSERT INTO sales_items
                        (sale_id, product_id, batch_id, quantity, selling_price, cost_price, profit)
                        VALUES (%s, %s, NULL, %s, %s, %s, %s)
                    """, (new_sale_id, product_id, qty, rate, cost, (rate - cost) * qty))
                    stats['errors'].append(
                        f"Row {i+1}: '{name}' had no batch stock — sale recorded without deduction"
                    )
                else:
                    if deducted < qty:
                        short = qty - deducted
                        cur.execute("""
                            INSERT INTO sales_items
                            (sale_id, product_id, batch_id, quantity, selling_price, cost_price, profit)
                            VALUES (%s, %s, NULL, %s, %s, %s, %s)
                        """, (new_sale_id, product_id, short, rate, cost, (rate - cost) * short))
                        stats['errors'].append(
                            f"Row {i+1}: only {deducted}/{qty} units had batch stock for '{name}'"
                        )
                    # Batch rows already carry their per-batch cost + rate.
                    # Recompute profit = (selling - cost) * qty, then roll up.
                    cur.execute("""
                        UPDATE sales_items
                        SET profit = (selling_price - cost_price) * quantity
                        WHERE sale_id = %s
                    """, (new_sale_id,))
                    cur.execute("SELECT COALESCE(SUM(profit), 0) FROM sales_items WHERE sale_id = %s",
                                (new_sale_id,))
                    _ip = float(cur.fetchone()[0] or 0)
                    cur.execute("UPDATE sales SET profit = %s, total = %s WHERE id = %s",
                                (_ip - float(discount or 0), subtotal - discount, new_sale_id))

                # Update product stock to reflect batch deductions
                cur.execute("""
                    UPDATE products
                    SET stock = COALESCE((
                        SELECT SUM(remaining_quantity) FROM purchase_batches
                        WHERE product_id = products.id
                    ), 0)
                    WHERE id = %s
                """, (product_id,))

                stats['inserted'] += 1
            except Exception as e:
                stats['errors'].append(f"Row {i+1}: {e}")

        conn.commit()
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
#  CSV export
# ============================================================
def rows_to_csv(rows, kind):
    import csv, io as _io
    cols = PURCHASE_COLUMNS if kind == 'purchases' else SALES_COLUMNS
    out = _io.StringIO()
    w = csv.writer(out)
    w.writerow([c[1] for c in cols])
    for r in rows:
        w.writerow([r.get(c[0], '') for c in cols])
    return out.getvalue()



# ============================================================
#  Suggestions for the preview sheet auto-complete
# ============================================================
def get_product_suggestions(category):
    """Return distinct (name, brand, category) tuples for the given context.
    Used by the client's auto-suggest dropdown for name / brand / category
    columns."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if category == 'Screen':
            where = "LOWER(COALESCE(category, '')) = 'screen'"
        else:
            where = "LOWER(COALESCE(category, '')) != 'screen'"
        cur.execute(f"""
            SELECT id, name, COALESCE(brand, ''), COALESCE(category, ''),
                   COALESCE(cost_price, 0), COALESCE(selling_price, 0)
            FROM products
            WHERE {where} AND name IS NOT NULL AND name != ''
            ORDER BY name ASC
        """)
        products = [{
            'id':             int(r[0]),
            'name':           r[1] or '',
            'brand':          r[2] or '',
            'category':       r[3] or '',
            'cost_price':     float(r[4] or 0),
            'selling_price':  float(r[5] or 0),
        } for r in cur.fetchall()]

        # Category list (for loose-category mode in Accessory view)
        cur.execute(f"""
            SELECT DISTINCT category
            FROM products
            WHERE {where} AND category IS NOT NULL AND category != ''
            ORDER BY category ASC
        """)
        categories = [r[0] for r in cur.fetchall()]

        return {
            'products': products,
            'categories': categories,
        }
    finally:
        conn.close()

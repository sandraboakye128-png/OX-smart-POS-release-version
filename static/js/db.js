// static/js/db.js
// Dexie schema for OX Smart POS offline store.
//
// Versioning rules:
//   - NEVER modify an existing version's stores() — existing users' DBs
//     would be silently wiped or migrated incorrectly.
//   - Add a NEW version() block whenever you add/remove tables or indexes.
//   - Dexie runs migrations automatically the next time the page loads.

const db = new Dexie('OxSmartOfflineDB');

// ------------------------------------------------------------------
// v1 — original schema. Do not modify.
// ------------------------------------------------------------------
db.version(1).stores({
    products: 'id, name, brand, category, stock, cost_price, selling_price, discount, last_sync',

    batches: 'id, product_id, quantity, remaining_quantity, cost_price, selling_price, discount, claimed_quantity, date, action, source, original_quantity, original_date, original_cost_price, original_selling_price, original_discount, last_sync',

    sales: 'id, date, subtotal, discount, total, profit, reversed, payment_method, cheque_number, user_id, last_sync',

    sales_items: 'id, sale_id, product_id, batch_id, quantity, selling_price, cost_price, profit, last_sync',

    claims: 'id, product_id, batch_id, product_name, brand, category, issue_type, description, quantity, status, created_at, updated_at, last_sync',

    pending_ops: '++id, operation, table, record_id, payload, timestamp, attempts, synced',

    deleted_products: 'id, name, brand, category, cost_price, selling_price, stock, discount, action, deleted_at, batch_id, batch_quantity, batch_remaining, product_id, source, last_sync'
});

// ------------------------------------------------------------------
// v2 — dashboard cache table.
// dashboard.html writes/reads here for API-first rendering with
// offline fallback: db.cache.put({ key, value, timestamp })
// ------------------------------------------------------------------
db.version(2).stores({
    cache: 'key, timestamp'
});

// ------------------------------------------------------------------
// v3 — Phase 2 foundation.
//   product_units, purchases  → mirror remaining SQLite tables
//   settings                  → local key/value for user prefs
//   sync_queue                → outbound change log (Phase 5)
//   meta                      → device_id, last_pull_at, schema_version
// ------------------------------------------------------------------
db.version(3).stores({
    product_units: 'id, product_id, unit_name',
    purchases:     'id, product_name, brand, category, date, last_sync',
    settings:      'key',
    sync_queue:    '++id, table_name, status, created_at',
    meta:          'key'
});

// ------------------------------------------------------------------
// Expose globally. base.html, dashboard.html, and all existing code
// continue to use `db` exactly as before.
// ------------------------------------------------------------------
window.db = db;

// Best-effort persistence request — Android WebView will otherwise
// evict IndexedDB under storage pressure.
if (navigator.storage && navigator.storage.persist) {
    navigator.storage.persist().catch(() => {});
}
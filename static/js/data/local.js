// static/js/data/local.js
// ------------------------------------------------------------------
// OX_DATA_LOCAL — the "APK" implementation.
//
// Reads from Dexie (IndexedDB). Method names AND return shapes must
// match OX_DATA_REMOTE exactly, so any page that works on web works
// on APK without knowing the source changed.
//
// The data in Dexie is refreshed by pullData() in sync.js, which runs
// on every boot (push-first, then full-replace pull).
// ------------------------------------------------------------------

window.OX_DATA_LOCAL = {

    // ---------------- PRODUCTS ----------------
    products: {
        /**
         * Reads db.products + db.batches + db.claims and reconstructs
         * the same grouped shape that /api/products returns.
         *
         * @param {{ category?: string, exclude_category?: string }} opts
         * @returns {Promise<{products: Array, total_products: number, total_batches: number}>}
         */
        async list(opts = {}) {
            if (typeof db === 'undefined' || !db) {
                throw new Error('Dexie (db) not available');
            }

            const { category, exclude_category } = opts;
            const catLower = category ? String(category).toLowerCase() : null;
            const exclLower = exclude_category ? String(exclude_category).toLowerCase() : null;

            const [allProducts, allBatches, allClaims] = await Promise.all([
                db.products.toArray(),
                db.batches.toArray(),
                db.claims.where('status').equals('active').toArray(),
            ]);

            // Sum active claim quantity per batch for `active_claims` + `good_stock`.
            const activeClaimsByBatch = {};
            for (const c of allClaims) {
                const bid = c.batch_id;
                if (!bid) continue;
                activeClaimsByBatch[bid] = (activeClaimsByBatch[bid] || 0) + (c.quantity || 0);
            }

            // Group batches by product_id.
            const batchesByProduct = {};
            for (const b of allBatches) {
                const pid = b.product_id;
                if (pid == null) continue;
                if (!batchesByProduct[pid]) batchesByProduct[pid] = [];
                batchesByProduct[pid].push(b);
            }

            const result = [];
            let total_batches = 0;

            for (const p of allProducts) {
                const pCat = (p.category || '').toLowerCase();
                if (catLower && pCat !== catLower) continue;
                if (exclLower && pCat === exclLower) continue;

                const productBatches = batchesByProduct[p.id] || [];
                // /api/products uses EXISTS(SELECT 1 FROM purchase_batches) —
                // products with zero batches are hidden.
                if (productBatches.length === 0) continue;

                // Stable ordering by date, matching the API's ORDER BY pb.date ASC.
                productBatches.sort((a, b) => {
                    const da = a.date ? new Date(a.date).getTime() : 0;
                    const db_ = b.date ? new Date(b.date).getTime() : 0;
                    return da - db_;
                });

                let totalStock = 0;
                let totalClaimed = 0;

                const batches = productBatches.map(b => {
                    const claimed      = b.claimed_quantity || 0;
                    const activeClaims = activeClaimsByBatch[b.batch_id || b.id] || 0;
                    const remaining    = b.remaining_quantity || 0;
                    const sold         = (typeof b.sold_quantity === 'number')
                        ? b.sold_quantity
                        : 0;

                    totalStock   += remaining;
                    totalClaimed += activeClaims;
                    total_batches += 1;

                    return {
                        batch_id:           b.id,
                        quantity:           b.quantity || 0,
                        remaining_quantity: remaining,
                        cost_price:         b.cost_price || 0,
                        selling_price:      b.selling_price || 0,
                        discount:           b.discount || 0,
                        date:               b.date,
                        is_faulty:          b.is_faulty || false,
                        claimed_quantity:   claimed,
                        active_claims:      activeClaims,
                        good_stock:         remaining - claimed,
                        sold_quantity:      sold,
                    };
                });

                result.push({
                    product_id:    p.id,
                    name:          p.name,
                    brand:         p.brand || '',
                    cost_price:    p.cost_price || 0,
                    selling_price: p.selling_price || 0,
                    category:      p.category || '',
                    discount:      p.discount || 0,
                    stock:         totalStock,
                    batches:       batches,
                    total_claimed: totalClaimed,
                });
            }

            return {
                products:       result,
                total_products: result.length,
                total_batches:  total_batches,
            };
        },
    },

    // ---------------- LOW STOCK ----------------
    lowStock: {
        /**
         * Returns the same shape as /api/low_stock/split.
         *
         * Handles virtual categories the way the Flask endpoint does:
         *   'all'          → no filter
         *   'non-Screen'   → exclude category === 'Screen'
         *   'Screen'       → only category === 'Screen'
         *   anything else  → exact match (case-insensitive)
         *
         * @param {{ category?: string }} opts
         * @returns {Promise<{success: boolean, batch_level: Object, product_level: Object}>}
         */
        async split(opts = {}) {
            if (typeof db === 'undefined' || !db) {
                throw new Error('Dexie (db) not available');
            }

            const { category } = opts;
            const catLower = category ? String(category).toLowerCase() : null;
            const isAll = !catLower || catLower === 'all';
            const isNonScreen = catLower === 'non-screen';
            const isScreenOnly = catLower === 'screen';

            const [allProducts, allBatches] = await Promise.all([
                db.products.toArray(),
                db.batches.toArray(),
            ]);

            // Sum remaining per product.
            const stockByProduct = {};
            for (const b of allBatches) {
                const pid = b.product_id;
                if (pid == null) continue;
                stockByProduct[pid] = (stockByProduct[pid] || 0) + (b.remaining_quantity || 0);
            }

            const LOW_THRESHOLD = 10;

            const low_stock_products = [];
            for (const p of allProducts) {
                const pCat = (p.category || '').toLowerCase();
                if (!isAll) {
                    if (isNonScreen) {
                        if (pCat === 'screen') continue;
                    } else if (isScreenOnly) {
                        if (pCat !== 'screen') continue;
                    } else {
                        if (pCat !== catLower) continue;
                    }
                }

                const stock = stockByProduct[p.id] || 0;
                // low_stock means 0 < stock <= 10.
                if (stock > 0 && stock <= LOW_THRESHOLD) {
                    low_stock_products.push({
                        product_id: p.id,
                        name:       p.name,
                        brand:      p.brand || '',
                        category:   p.category || '',
                        stock,
                    });
                }
            }

            return {
                success: true,
                batch_level: {
                    counts: { low_stock: 0, out_of_stock: 0 },
                    low_stock: [],
                    out_of_stock: [],
                },
                product_level: {
                    counts: {
                        low_stock: low_stock_products.length,
                        out_of_stock: 0,
                    },
                    low_stock: low_stock_products,
                    out_of_stock: [],
                },
            };
        },
    },

    // ---------------- DASHBOARD ----------------
    dashboard: {
        /**
         * Same shape as /api/dashboard/summary.
         * @param {{ start_datetime?: string, end_datetime?: string }} opts
         * @returns {Promise<{sales: number, profit: number, total_products: number, total_batches: number}>}
         */
        async summary(opts = {}) {
            if (typeof db === 'undefined' || !db) {
                throw new Error('Dexie (db) not available');
            }
            const { start_datetime, end_datetime } = opts;

            const [products, batches, sales] = await Promise.all([
                db.products.toArray(),
                db.batches.toArray(),
                db.sales.toArray(),
            ]);

            const filtered = _filterSales(sales, start_datetime, end_datetime);

            return {
                sales:          filtered.reduce((s, x) => s + (parseFloat(x.total)  || 0), 0),
                profit:         filtered.reduce((s, x) => s + (parseFloat(x.profit) || 0), 0),
                total_products: products.length,
                total_batches:  batches.length,
            };
        },

        /**
         * Same shape as /api/dashboard/top_products.
         * @param {{ start_datetime?: string, end_datetime?: string, limit?: number }} opts
         * @returns {Promise<Array<{name: string, brand: string, category: string, qty: number}>>}
         */
        async topProducts(opts = {}) {
            if (typeof db === 'undefined' || !db) {
                throw new Error('Dexie (db) not available');
            }
            const { start_datetime, end_datetime, limit = 10 } = opts;

            const [sales, items, products] = await Promise.all([
                db.sales.toArray(),
                db.sales_items.toArray(),
                db.products.toArray(),
            ]);

            const filtered = _filterSales(sales, start_datetime, end_datetime);
            const validIds = new Set(filtered.map(s => s.id));

            const qtyByProduct = {};
            for (const si of items) {
                if (!validIds.has(si.sale_id)) continue;
                const pid = si.product_id;
                if (pid == null) continue;
                qtyByProduct[pid] = (qtyByProduct[pid] || 0) + (si.quantity || 0);
            }

            const pmap = new Map(products.map(p => [p.id, p]));

            return Object.entries(qtyByProduct)
                .map(([pid, qty]) => {
                    const p = pmap.get(parseInt(pid, 10));
                    return {
                        name:     p ? p.name     : 'Unknown',
                        brand:    p ? p.brand    : '',
                        category: p ? p.category : '',
                        qty,
                    };
                })
                .sort((a, b) => b.qty - a.qty)
                .slice(0, limit);
        },

        /**
         * Same shape as /api/dashboard/sales_history.
         * @param {{ start_datetime?: string, end_datetime?: string }} opts
         * @returns {Promise<Array<{date: string, total_sales: number, profit: number, discount: number}>>}
         */
        async salesHistory(opts = {}) {
            if (typeof db === 'undefined' || !db) {
                throw new Error('Dexie (db) not available');
            }
            const { start_datetime, end_datetime } = opts;

            const sales = await db.sales.toArray();
            const filtered = _filterSales(sales, start_datetime, end_datetime);

            const byDate = {};
            for (const s of filtered) {
                if (!s.date) continue;
                // s.date is an ISO-ish timestamp. Group by calendar day.
                const key = String(s.date).split(' ')[0].split('T')[0];
                if (!key) continue;
                if (!byDate[key]) {
                    byDate[key] = { date: key, total_sales: 0, profit: 0, discount: 0 };
                }
                byDate[key].total_sales += parseFloat(s.total)    || 0;
                byDate[key].profit      += parseFloat(s.profit)   || 0;
                byDate[key].discount    += parseFloat(s.discount) || 0;
            }

            return Object.values(byDate).sort((a, b) => b.date.localeCompare(a.date));
        },
    },
};

// ------------------------------------------------------------------
// Internal helper — filter sales by date window, dropping reversed.
// Kept outside the object literal to avoid re-creating on every call.
// ------------------------------------------------------------------
function _filterSales(sales, startDt, endDt) {
    return sales.filter(s => {
        if (s.reversed) return false;
        if (startDt && (!s.date || s.date < startDt)) return false;
        if (endDt && (!s.date || s.date > endDt)) return false;
        return true;
    });
}
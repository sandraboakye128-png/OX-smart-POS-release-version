// static/js/data/remote.js
// ------------------------------------------------------------------
// OX_DATA_REMOTE — the "web" implementation.
//
// Every method here is a thin wrapper around an existing Flask API
// endpoint. The response shape is passed through untouched so any
// template that already consumed `/api/...` keeps working identically.
//
// Method names mirror what the pages currently call via fetch(), so
// swapping a page from raw fetch() to OX_DATA is a one-line change.
// ------------------------------------------------------------------

window.OX_DATA_REMOTE = {

    // ---------------- PRODUCTS ----------------
    products: {
        /**
         * Mirrors GET /api/products
         * @param {{ category?: string, exclude_category?: string }} opts
         * @returns {Promise<{products: Array, total_products: number, total_batches: number}>}
         */
        async list(opts = {}) {
            const params = new URLSearchParams();
            if (opts.category)         params.set('category',         opts.category);
            if (opts.exclude_category) params.set('exclude_category', opts.exclude_category);

            const url = '/api/products' + (params.toString() ? '?' + params : '');
            const res = await fetch(url, { credentials: 'include' });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        },
    },

    // ---------------- LOW STOCK ----------------
    lowStock: {
        /**
         * Mirrors GET /api/low_stock/split
         * @param {{ category?: string }} opts
         * @returns {Promise<{success: boolean, batch_level: Object, product_level: Object}>}
         */
        async split(opts = {}) {
            const params = new URLSearchParams();
            if (opts.category) params.set('category', opts.category);

            const url = '/api/low_stock/split' + (params.toString() ? '?' + params : '');
            const res = await fetch(url, { credentials: 'include' });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        },
    },
};
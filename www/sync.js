// www/sync.js — bundled copy for the APK shell.
//
// Identical to static/js/sync.js EXCEPT:
//   1. All API calls go to the absolute Render URL
//   2. Every request carries Authorization: Bearer <token>
//
// Routing, retry, and dead-lettering are byte-for-byte identical to the
// web version — nothing here changes how ops reach Supabase.

const _SYNC_API_BASE = 'https://ox-smart-pos-release-version.onrender.com';

function _syncAuthHeaders() {
    const h = { 'Content-Type': 'application/json' };
    try {
        const token = localStorage.getItem('ox_api_token');
        if (token) h['Authorization'] = 'Bearer ' + token;
    } catch (e) {}
    return h;
}

async function _syncFetch(path, options = {}) {
    const url = path.startsWith('http') ? path : _SYNC_API_BASE + path;
    const opts = Object.assign({ credentials: 'include' }, options);
    opts.headers = Object.assign(_syncAuthHeaders(), opts.headers || {});
    return fetch(url, opts);
}

const MAX_ATTEMPTS = 5;
let _fullSyncRunning = false;

async function pullData() {
    if (!navigator.onLine) {
        console.warn('⚠️ pullData skipped – offline');
        return;
    }
    try {
        console.log('📥 Pulling data from /api/sync/all...');
        const res = await _syncFetch('/api/sync/all');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const { products, batches, sales, sales_items, claims, deleted_products } = data;

        await db.transaction('rw',
            db.products, db.batches, db.sales, db.sales_items,
            db.claims, db.deleted_products,
            async () => {
                for (const p of products) {
                    await db.products.put({
                        id: p.id, name: p.name, brand: p.brand || '',
                        category: p.category || '', cost_price: p.cost_price,
                        selling_price: p.selling_price, stock: p.stock,
                        discount: p.discount || 0, last_sync: new Date().toISOString()
                    });
                }
                for (const b of batches) {
                    await db.batches.put({
                        id: b.id, product_id: b.product_id, quantity: b.quantity,
                        remaining_quantity: b.remaining_quantity,
                        cost_price: b.cost_price, selling_price: b.selling_price,
                        discount: b.discount || 0, claimed_quantity: b.claimed_quantity || 0,
                        date: b.date, action: b.action || '', source: b.source || '',
                        original_quantity: b.original_quantity, original_date: b.original_date,
                        original_cost_price: b.original_cost_price,
                        original_selling_price: b.original_selling_price,
                        original_discount: b.original_discount || 0,
                        last_sync: new Date().toISOString()
                    });
                }
                for (const s of sales) {
                    await db.sales.put({
                        id: s.id, date: s.date, subtotal: s.subtotal,
                        discount: s.discount, total: s.total, profit: s.profit,
                        reversed: s.reversed, payment_method: s.payment_method || 'cash',
                        cheque_number: s.cheque_number || null, user_id: s.user_id,
                        last_sync: new Date().toISOString()
                    });
                }
                for (const si of sales_items) {
                    await db.sales_items.put({
                        id: si.id, sale_id: si.sale_id, product_id: si.product_id,
                        batch_id: si.batch_id, quantity: si.quantity,
                        selling_price: si.selling_price, cost_price: si.cost_price,
                        profit: si.profit, last_sync: new Date().toISOString()
                    });
                }
                for (const c of claims) {
                    await db.claims.put({
                        id: c.id, product_id: c.product_id, batch_id: c.batch_id,
                        product_name: c.product_name, brand: c.brand || '',
                        category: c.category || '', issue_type: c.issue_type,
                        description: c.description || '', quantity: c.quantity,
                        status: c.status || 'active', created_at: c.created_at,
                        updated_at: c.updated_at, last_sync: new Date().toISOString()
                    });
                }
                for (const d of deleted_products) {
                    await db.deleted_products.put({
                        id: d.id, name: d.name, brand: d.brand || '',
                        category: d.category || '', cost_price: d.cost_price,
                        selling_price: d.selling_price, stock: d.stock,
                        discount: d.discount || 0, action: d.action || '',
                        deleted_at: d.deleted_at, batch_id: d.batch_id,
                        batch_quantity: d.batch_quantity, batch_remaining: d.batch_remaining,
                        product_id: d.product_id, source: d.source || '',
                        last_sync: new Date().toISOString()
                    });
                }
            }
        );

        localStorage.setItem('lastSyncTime', Date.now().toString());
        console.log('✅ Pull sync completed – all data updated locally.');
    } catch (err) {
        console.error('❌ Pull sync error:', err);
    }
}

async function savePendingOperation(table, operation, record_id, payload) {
    if (!db) { console.error('❌ Dexie not available'); return; }
    try {
        await db.pending_ops.add({
            table, operation, record_id, payload,
            user_id: _currentUserId(),
            scope: (table === 'settings' ? 'user' : 'global'),
            timestamp: new Date().toISOString(), attempts: 0, synced: 0
        });
        console.log(`💾 Pending op saved: ${table} ${operation} (${record_id})`);
        if (typeof updatePendingBadge === 'function') updatePendingBadge();
    } catch (err) { console.error('❌ Failed to save pending operation:', err); }
}

async function pushPending() {
    if (!navigator.onLine) {
        console.warn('⚠️ pushPending skipped – offline');
        return;
    }
    const me = _currentUserId();
    const pending = (await db.pending_ops.where('synced').equals(0).toArray())
        .filter(op => (op.attempts || 0) < MAX_ATTEMPTS)
        .filter(op => !op.user_id || op.user_id === me);

    if (pending.length === 0) {
        console.log('📭 No pending operations to push.');
        return;
    }
    console.log(`📤 Pushing ${pending.length} pending operations...`);
    let successCount = 0, failCount = 0, deadCount = 0;

    for (const op of pending) {
        try {
            let url = '', method = '', payload = op.payload;
            let serverId = null, wasCreate = false;

            switch (op.table) {
                case 'batches': {
                    const rawId = String(op.record_id || '');
                    const isTemp = rawId.startsWith('temp_') || !/^\d+$/.test(rawId);
                    const payloadBatchId = payload && payload.batch_id;
                    let hintedId = null;
                    if (payloadBatchId !== undefined && payloadBatchId !== null) {
                        const n = parseInt(payloadBatchId, 10);
                        if (Number.isFinite(n) && n > 0) hintedId = n;
                    }
                    if (op.operation === 'add' && isTemp && !hintedId) {
                        url = '/api/purchases'; method = 'POST'; wasCreate = true;
                    } else {
                        const numericId = /^\d+$/.test(rawId) ? parseInt(rawId, 10) : hintedId;
                        if (!numericId) throw new Error(`Cannot route batch op: record_id="${op.record_id}"`);
                        url = `/api/purchases/${numericId}`; method = 'PUT';
                        if (!payload || typeof payload !== 'object') payload = {};
                        if (!payload.update_mode) payload = Object.assign({}, payload, { update_mode: 'update' });
                        if (payload.batch_id === undefined) payload = Object.assign({}, payload, { batch_id: numericId });
                    }
                    break;
                }
                case 'sales':
                    if (op.operation === 'add') { url = '/api/sales/complete'; method = 'POST'; wasCreate = true; }
                    else throw new Error(`Unsupported sales op: ${op.operation}`);
                    break;
                case 'claims':
                    if (op.operation === 'add') { url = '/api/claims'; method = 'POST'; wasCreate = true; }
                    else if (op.operation === 'update') { url = `/api/claims/${op.record_id}`; method = 'PUT'; }
                    else if (op.operation === 'delete') { url = `/api/claims/${op.record_id}`; method = 'DELETE'; }
                    else throw new Error(`Unsupported claims op: ${op.operation}`);
                    break;
                case 'products':
                    if (op.operation === 'delete') {
                        const dtype = (op.payload && op.payload.deleteType) || 'keep';
                        url = `/api/products/${op.record_id}?type=${encodeURIComponent(dtype)}`;
                        method = 'DELETE';
                    } else throw new Error(`Unsupported products op: ${op.operation}`);
                    break;
                case 'batches_delete':
                    if (op.operation === 'delete') {
                        const dtype = (op.payload && op.payload.deleteType) || 'keep';
                        url = `/api/batches/${op.record_id}?type=${encodeURIComponent(dtype)}`;
                        method = 'DELETE';
                    } else throw new Error(`Unsupported batch-delete op: ${op.operation}`);
                    break;
                default: throw new Error(`Unknown table: ${op.table}`);
            }

            if (!url) throw new Error(`No endpoint for ${op.table} ${op.operation}`);

            const res = await _syncFetch(url, {
                method,
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${res.status}`);
            }
            const result = await res.json();
            if (result.success === false) throw new Error(result.error || 'Unknown server error');

            if (op.table === 'batches' && (result.batch_id || result.new_batch_id)) {
                serverId = result.batch_id || result.new_batch_id;
            } else if (op.table === 'claims' && result.claim_id) serverId = result.claim_id;
            else if (op.table === 'sales' && result.sale_id) serverId = result.sale_id;

            // ============================================================
            //  Swap temp ids for real server ids
            //
            //  Offline batch creates use 'temp_<ts>' ids locally, and the
            //  parent product gets 'prod_<ts>'. Once the server responds
            //  with real numeric ids, we must rewrite the local records —
            //  otherwise the temp records linger forever and:
            //    - Products view can't open their batches (string id breaks
            //      the onclick attribute),
            //    - Purchases view tries to PUT /api/purchases/temp_... and
            //      gets a 404.
            // ============================================================
            if (op.table === 'batches' && wasCreate && serverId) {
                const tempBatchId = op.record_id;
                try {
                    const tempBatch = await db.batches.get(tempBatchId);
                    if (tempBatch) {
                        const realProductId = result.product_id || tempBatch.product_id;
                        const updatedBatch = Object.assign({}, tempBatch, {
                            id: serverId,
                            product_id: realProductId,
                            last_sync: new Date().toISOString()
                        });
                        await db.batches.delete(tempBatchId);
                        await db.batches.put(updatedBatch);

                        // Swap the temp product for the real one too
                        if (tempBatch.product_id !== realProductId) {
                            const tempProduct = await db.products.get(tempBatch.product_id);
                            if (tempProduct) {
                                const updatedProduct = Object.assign({}, tempProduct, {
                                    id: realProductId,
                                    last_sync: new Date().toISOString()
                                });
                                await db.products.delete(tempBatch.product_id);
                                await db.products.put(updatedProduct);
                            }
                        }
                        console.log(`🔁 Swapped: batch ${tempBatchId} → ${serverId}, product ${tempBatch.product_id} → ${realProductId}`);
                    }
                } catch (swapErr) {
                    console.warn('[sync] temp-id swap failed (non-fatal):', swapErr);
                }
            }

            await db.pending_ops.delete(op.id);
            successCount++;
            console.log(`✅ Synced op ${op.id} (${op.table} ${op.operation}${wasCreate ? ' [create]' : ' [update]'})`);
            if (serverId) console.log(`   ↳ server assigned id ${serverId}`);

        } catch (err) {
            const attempts = (op.attempts || 0) + 1;
            if (attempts >= MAX_ATTEMPTS) {
                await db.pending_ops.update(op.id, { attempts, synced: -1 });
                console.error(`💀 Op ${op.id} failed ${attempts} times — dead-lettered:`, err.message);
                deadCount++;
            } else {
                await db.pending_ops.update(op.id, { attempts });
                console.warn(`❌ Push failed for op ${op.id} (attempt ${attempts}/${MAX_ATTEMPTS}):`, err.message);
                failCount++;
            }
        }
    }

    if (typeof updatePendingBadge === 'function') updatePendingBadge();
    console.log(`📤 Push completed: ${successCount} ok, ${failCount} failed, ${deadCount} dead.`);
}

async function fullSync() {
    if (_fullSyncRunning) { console.warn('⚠️ fullSync already running'); return; }
    _fullSyncRunning = true;
    try {
        console.log('🔄 Starting full sync...');
        await pullData();
        await pushPending();
        console.log('✅ Full sync completed.');
    } finally { _fullSyncRunning = false; }
}

async function clearAllPending() {
    if (!db) return;
    if (!confirm('Clear all pending operations?')) return;
    await db.pending_ops.where('synced').equals(0).delete();
    await db.pending_ops.where('synced').equals(-1).delete();
    if (typeof updatePendingBadge === 'function') updatePendingBadge();
}

async function getPendingCount() {
    if (!db) return 0;
    return db.pending_ops.where('synced').equals(0).count();
}

window.pullData = pullData;
window.pushPending = pushPending;
window.fullSync = fullSync;
window.savePendingOperation = savePendingOperation;
window.clearAllPending = clearAllPending;
window.getPendingCount = getPendingCount;
// static/js/data/provider.js
// ------------------------------------------------------------------
// OX_DATA — the single entry point every page should use.
//
// Picks the correct implementation once, at load time, based on
// OX_ENV.useLocalDb (which is true only inside the Capacitor APK).
//
//     Web  → OX_DATA === OX_DATA_REMOTE   (hits /api/* as before)
//     APK  → OX_DATA === OX_DATA_LOCAL    (reads Dexie, offline-capable)
//
// Templates never branch on OX_ENV directly. They just call
// OX_DATA.products.list() and get the right source for free.
// ------------------------------------------------------------------

(function () {
    const env = window.OX_ENV || {};
    const useLocal = !!env.useLocalDb;

    const remote = window.OX_DATA_REMOTE || {};
    const local  = window.OX_DATA_LOCAL  || {};

    if (useLocal && typeof db === 'undefined') {
        // APK is expected to always have Dexie loaded (via db.js).
        // If it isn't, falling back silently would hide the bug.
        console.error('[OX_DATA] useLocalDb is true but Dexie (db) is missing');
    }

    window.OX_DATA = useLocal ? local : remote;

    console.log('[OX_DATA] provider ready — source =', useLocal ? 'local (Dexie)' : 'remote (API)');
})();
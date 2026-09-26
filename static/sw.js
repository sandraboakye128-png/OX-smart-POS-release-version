// static/sw.js
// ============================================================
//  OX Smart POS Service Worker
//
//  Caching strategy:
//    /api/*          → pass-through (never cached here; Dexie handles offline)
//    HTML pages      → NETWORK-FIRST (template edits appear on plain reload)
//    /static/js|css  → NETWORK-FIRST (dev edits appear immediately)
//    icons/fonts/img → cache-first with background refresh
//
//  Bump CACHE_NAME whenever the SW logic itself changes; the activate
//  handler deletes any cache whose name doesn't match, so old stale
//  HTML can never be served after a version bump.
// ============================================================

// ⚠️ INCREMENT ON EVERY SW LOGIC CHANGE
const CACHE_NAME = 'oxsmart-v11';

const PRECACHE_ASSETS = [
  '/static/css/style.css',
  '/static/css/tailwind.min.css',
  '/static/css/all.min.css',
  '/static/js/env.js',
  '/static/js/db.js',
  '/static/js/sync.js',
  '/static/js/offline.js',
  '/static/js/data/remote.js',
  '/static/js/data/local.js',
  '/static/js/data/provider.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

// Paths that should ALWAYS hit the network first
const NETWORK_FIRST_PREFIXES = ['/static/js/', '/static/css/'];

// Paths the SW should never intercept (backend handles its own offline)
const NEVER_CACHE_PREFIXES = ['/api/'];


// ===== INSTALL =====
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[SW] pre-caching static assets');
      // Don't fail install if one asset 404s
      return Promise.allSettled(
        PRECACHE_ASSETS.map(url =>
          cache.add(url).catch(err =>
            console.warn('[SW] precache miss:', url, err && err.message)
          )
        )
      );
    }).then(() => self.skipWaiting())
  );
});


// ===== ACTIVATE =====
// Deletes every cache that isn't the current CACHE_NAME. This is what
// guarantees a version bump clears stale HTML on next page load.
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names =>
      Promise.all(
        names.filter(n => n !== CACHE_NAME).map(n => {
          console.log('[SW] deleting old cache:', n);
          return caches.delete(n);
        })
      )
    ).then(() => self.clients.claim())
  );
});


// ===== FETCH =====
self.addEventListener('fetch', event => {
  const req = event.request;
  const url = new URL(req.url);

  // Only handle same-origin GETs
  if (req.method !== 'GET') return;
  if (url.origin !== location.origin) return;

  // ----- /api/ : pass through. On failure return a real JSON Response -----
  if (NEVER_CACHE_PREFIXES.some(p => url.pathname.startsWith(p))) {
    event.respondWith(
      fetch(req).catch(() =>
        new Response(
          JSON.stringify({ error: 'offline', message: 'Network unavailable' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    );
    return;
  }

  // ----- /static/js/ and /static/css/ : network-first -----
  if (NETWORK_FIRST_PREFIXES.some(p => url.pathname.startsWith(p))) {
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res && res.ok) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then(c => c.put(req, clone)).catch(() => {});
          }
          return res;
        })
        .catch(() =>
          caches.match(req).then(cached =>
            cached || new Response('/* offline */', {
              status: 503,
              headers: { 'Content-Type': 'text/plain' }
            })
          )
        )
    );
    return;
  }

  // ----- HTML pages : network-first (so template edits appear immediately) -----
  // This is the branch that was previously cache-first and caused
  // base.html edits to be invisible until the SW was unregistered.
  const accept = req.headers.get('accept') || '';
  if (accept.includes('text/html')) {
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res && res.ok && res.type === 'basic') {
            const clone = res.clone();
            caches.open(CACHE_NAME).then(c => c.put(req, clone)).catch(() => {});
          }
          return res;
        })
        .catch(() =>
          caches.match(req).then(cached =>
            cached || new Response(
              `<!DOCTYPE html>
               <html><head><meta charset="utf-8"><title>Offline</title></head>
               <body style="font-family:sans-serif;padding:2rem;text-align:center;">
                 <h1>You are offline</h1>
                 <p>Please reconnect to use the app.</p>
               </body></html>`,
              { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
            )
          )
        )
    );
    return;
  }

  // ----- Everything else (icons, fonts, images) : cache-first -----
  event.respondWith(
    caches.match(req).then(cached => {
      if (cached) {
        event.waitUntil(
          fetch(req)
            .then(res => {
              if (res && res.ok && res.type === 'basic') {
                return caches.open(CACHE_NAME).then(c => c.put(req, res.clone()));
              }
            })
            .catch(() => {})
        );
        return cached;
      }

      return fetch(req)
        .then(res => {
          if (res && res.ok && res.type === 'basic') {
            const clone = res.clone();
            caches.open(CACHE_NAME).then(c => c.put(req, clone)).catch(() => {});
          }
          return res;
        })
        .catch(() => new Response('Offline', { status: 503 }));
    })
  );
});


// ===== MESSAGE HANDLER – cache pages on demand =====
// base.html sends type 'CACHE_ALL_PAGES' (older code may send 'CACHE_PAGES')
self.addEventListener('message', event => {
  const type = event.data && event.data.type;
  if (type !== 'CACHE_PAGES' && type !== 'CACHE_ALL_PAGES') return;

  const urls = event.data.urls || [];
  if (!urls.length) return;

  event.waitUntil(
    caches.open(CACHE_NAME).then(async cache => {
      for (const url of urls) {
        try {
          const res = await fetch(url, { credentials: 'include' });
          if (res && res.ok) {
            await cache.put(url, res);
            console.log('[SW] cached page:', url);
          } else {
            console.warn('[SW] failed to cache page:', url, res && res.status);
          }
        } catch (err) {
          console.warn('[SW] error caching page:', url, err && err.message);
        }
      }
      console.log('[SW] page pre-caching complete');
    })
  );
});
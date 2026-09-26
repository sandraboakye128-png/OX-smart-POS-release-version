// static/sw.js
// ============================================================
//  OX Smart POS Service Worker
//  - Pre-caches static assets
//  - Network-first for JS/CSS so dev edits show up immediately
//  - Cache-first for icons/fonts/images/HTML pages
//  - Never intercepts /api/ — Dexie handles offline data
//  - On-demand page caching via postMessage
// ============================================================

// ⚠️ INCREMENT ON EVERY DEPLOY
const CACHE_NAME = 'oxsmart-v10';

const PRECACHE_ASSETS = [
  '/static/css/style.css',
  '/static/css/tailwind.min.css',
  '/static/css/all.min.css',
  '/static/js/env.js',
  '/static/js/db.js',
  '/static/js/sync.js',
  '/static/js/offline.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

// Paths that should ALWAYS hit the network first (dev-friendly + fresh logic)
const NETWORK_FIRST_PREFIXES = ['/static/js/', '/static/css/'];

// Paths the SW should never cache at all
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

  // ----- /api/ : pass through. On failure return a real Response -----
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

  // ----- JS / CSS : network-first (fresh edits during dev) -----
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

  // ----- Everything else : cache-first with background refresh -----
  event.respondWith(
    caches.match(req).then(cached => {
      if (cached) {
        event.waitUntil(
          fetch(req)
            .then(res => {
              if (res && res.ok) {
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
        .catch(() => {
          const accept = req.headers.get('accept') || '';
          if (accept.includes('text/html')) {
            return new Response(
              `<!DOCTYPE html>
               <html><head><meta charset="utf-8"><title>Offline</title></head>
               <body style="font-family:sans-serif;padding:2rem;text-align:center;">
                 <h1>You are offline</h1>
                 <p>Please reconnect to use the app.</p>
               </body></html>`,
              { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
            );
          }
          return new Response('Offline', { status: 503 });
        });
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
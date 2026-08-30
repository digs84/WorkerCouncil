// Service worker: makes the chat UI installable and load instantly from
// cache, while API calls (/api/*) always go to the network - the whole
// point of this app is fresh, rate-limit-aware answers, so those must
// never be served stale or from a browser cache.

const CACHE_VERSION = "v4";
const CACHE_NAME = `wc-assistant-${CACHE_VERSION}`;

const APP_SHELL = [
  "/",
  "/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon-maskable-512.png",
  "/static/icons/apple-touch-icon.png",
  "/static/favicon.ico",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never cache API calls - always hit the network so answers/health are live.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(
        () =>
          new Response(
            JSON.stringify({
              detail:
                "You're offline. Connect to the internet to ask a question - the app shell still loaded from cache, but answers need a live connection.",
            }),
            { status: 503, headers: { "Content-Type": "application/json" } }
          )
      )
    );
    return;
  }

  // App shell / static assets: cache-first, refresh cache in the background.
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => cached);
      return cached || networkFetch;
    })
  );
});

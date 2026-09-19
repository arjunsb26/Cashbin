// Caches the app shell so the dashboard opens with no network.
// API calls and the socket are never cached: live data must be live.
const SHELL = "binbooks-shell-v1";
const FILES = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(FILES)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => n !== SHELL).map((n) => caches.delete(n)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ws")) return;
  if (request.mode !== "navigate" && !FILES.includes(url.pathname)) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        void caches.open(SHELL).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(() => caches.match(request).then((hit) => hit ?? caches.match("/"))),
  );
});

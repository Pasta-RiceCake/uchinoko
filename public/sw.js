// オフラインでも開けるように、画面だけ手元に置いておく。データの送受信（/api/）はさわらない。
const C = "uchinoko-v1";
const FILES = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(C).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== C).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  // 新しい画面を先に取りにいき、だめなら手元のものを出す
  const key = e.request.mode === "navigate" ? "/" : e.request;
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok) { const cp = r.clone(); caches.open(C).then((c) => c.put(key, cp)); }
        return r;
      })
      .catch(() => caches.match(key))
  );
});

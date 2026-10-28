// オフラインでも開けるように、画面だけ手元に置いておく。データの送受信（/api/）はさわらない。
const C = "uchinoko-v3";
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
  const nav = e.request.mode === "navigate", key = nav ? u.pathname : e.request;
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok) { const cp = r.clone(); caches.open(C).then((c) => c.put(key, cp)); }
        return r;
      })
      .catch(() => caches.match(key).then((r) => r || (nav ? caches.match("/") : r)))
  );
});

// 通知
self.addEventListener("push", (e) => {
  let m = {};
  try { m = e.data ? e.data.json() : {}; } catch (_) {}
  e.waitUntil(self.registration.showNotification(m.t || "うちの子手帳", { body: m.b || "", icon: "/icon-192.png", badge: "/icon-192.png", data: { u: m.u || "/" }, lang: "ja" }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const u = (e.notification.data && e.notification.data.u) || "/";
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((cs) => {
      for (const c of cs) if ("focus" in c) return c.focus();
      return self.clients.openWindow(u);
    })
  );
});

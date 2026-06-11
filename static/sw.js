// Slip 絲利普 service worker
// 重要：/static 採「網路優先」，避免部署後拿到舊的 style.css（快取優先會卡住更新）。
const CACHE = "slip-static-v4";
const ASSETS = [
  "/static/style.css",
  "/static/favicon/sela.svg",
  "/static/favicon/android-chrome-192x192.png",
  "/static/favicon/android-chrome-512x512.png"
];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // 只處理自家 /static：網路優先，順手更新快取；離線時才退回快取
  if (url.origin === location.origin && url.pathname.startsWith("/static/")) {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req))
    );
  }
  // 其餘（HTML、頭像、API）一律走網路，不快取
});

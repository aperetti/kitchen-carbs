/* Lets phones install the app (okf/architecture/install.md). Every request goes straight to the network and nothing
   is cached here, so a deploy is never hidden behind an old copy and offline works as before (okf/architecture/offline.md). */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  if (e.request.mode === "navigate") e.respondWith(fetch(e.request));
});

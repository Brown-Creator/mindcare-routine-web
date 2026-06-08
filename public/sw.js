const CACHE_NAME = "mindcare-cache-v1";
const ASSETS = [
  "/",
  "/manifest.json",
  "/vercel.svg"
];

// Install Service Worker
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate Service Worker
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch resources
self.addEventListener("fetch", (e) => {
  // API 및 Next.js hot reload 핫 모듈은 캐싱에서 격리
  if (e.request.url.includes("/api/") || e.request.url.includes("/_next/webpack-hmr")) {
    return;
  }
  
  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      if (cachedResponse) {
        // Stale-While-Revalidate 패턴 적용
        fetch(e.request).then((networkResponse) => {
          if (networkResponse.status === 200) {
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(e.request, networkResponse);
            });
          }
        }).catch(() => {});
        return cachedResponse;
      }

      return fetch(e.request).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== "basic") {
          return networkResponse;
        }
        
        // POST나 외부 scheme가 아닌 일반 GET 요청만 캐싱 처리
        if (e.request.method === "GET" && e.request.url.startsWith(self.location.origin)) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(e.request, responseToCache);
          });
        }
        return networkResponse;
      }).catch(() => {
        if (e.request.mode === "navigate") {
          return caches.match("/");
        }
      });
    })
  );
});
